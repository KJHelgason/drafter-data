"""Load static knowledge: champion tags, pro stats, counter tables (parsed from knowledge/matchups.md)."""
import os, re, functools
from common import load, champ_id, ROOT, ROLES

@functools.lru_cache(None)
def tags():
    return load("knowledge/champion_tags.json")

@functools.lru_cache(None)
def pro():
    return load("pro_data/champion_pro_stats.json")["champions"]

@functools.lru_cache(None)
def id_lookup():
    """Map many spellings (display name, lowercase key, splash key) -> drafter id."""
    m = {}
    for cid, t in tags().items():
        for k in (cid, t.get("name", cid)):
            m[k] = cid
            m[re.sub(r"[^a-z0-9]", "", k.lower())] = cid
    m.update({"wukong": "MonkeyKing", "renataglasc": "Renata", "nunuwillump": "Nunu", "nunu": "Nunu"})
    return m

@functools.lru_cache(None)
def numeric_keys():
    return load("knowledge/champion_keys.json")

def to_id(name):
    if not name or name in ("None", "none", ""):
        return None
    if name.startswith("#") and name[1:].isdigit():      # drafter.lol ban image numeric id
        return numeric_keys().get(name[1:])
    lk = id_lookup()
    return lk.get(name) or lk.get(re.sub(r"[^a-z0-9]", "", name.lower())) or champ_id(name)

def display(cid):
    return tags().get(cid, {}).get("name", cid)

def pro_power_raw(cid):
    """Pro strength from presence, counting bans as strength (a champion banned constantly is picked
    rarely precisely because it is strong). Early bans (phase 1) count extra; win rate nudges it."""
    p = pro().get(cid)
    if not p:
        return 0.0
    t = p.get("avg_ban_turn") or 10.0
    early = max(0.0, min(1.0, (10.0 - t) / 8.4))          # 1 = always a first-rotation ban, 0 = last ban
    raw = p.get("weighted_pickrate", 0) + p.get("weighted_banrate", 0) * (1 + 0.5 * early)
    return raw * (1 + (p.get("weighted_winrate", 0.5) - 0.5) * 2)

@functools.lru_cache(None)
def _power_max():
    return max([pro_power_raw(c) for c in pro()] + [1e-9])

def pro_power(cid):
    """0..100, 100 = the strongest champion in current pro play."""
    return round(100 * pro_power_raw(cid) / _power_max())

def meta_score(cid):
    """0..1: pro power (presence incl. early bans, win-rate adjusted)."""
    return max(0.0, min(1.0, pro_power(cid) / 100 * 1.15))

def blind_safety(cid):
    return tags().get(cid, {}).get("blind_safety", 3)

def archetypes(cid):
    return set(tags().get(cid, {}).get("archetypes", []))

def damage(cid):
    return tags().get(cid, {}).get("damage", "mixed")

@functools.lru_cache(None)
def counters():
    """{role: {champ: set(counter champs)}} parsed from matchups.md tables.
    For jungle the table is 'X is advantaged vs Y' -> stored as counters[jungle][Y] includes X."""
    path = os.path.join(ROOT, "knowledge", "matchups.md")
    out = {r: {} for r in ROLES}
    role = None
    heads = {"## top": "top", "## jungle": "jungle", "## mid": "mid", "## bot": "bot", "## adc": "bot", "## support": "support"}
    for line in open(path, encoding="utf-8"):
        l = line.strip()
        low = l.lower()
        for h, r in heads.items():
            if low.startswith(h):
                role = r
        if not role or not l.startswith("|") or l.startswith("|---") or "Champion" in l.split("|")[1]:
            continue
        cells = [c.strip() for c in l.strip("|").split("|")]
        if len(cells) < 2:
            continue
        def names(s):
            s = re.sub(r"\([^)]*\)", "", s)
            res = []
            for n in re.split(r"[,/]| and ", s):
                n = n.strip().strip("*")
                cid = to_id(n) if n else None
                if cid and cid in tags():
                    res.append(cid)
            return res
        left, right = names(cells[0]), names(cells[1])
        if role == "jungle":
            for y in right:
                for x in left:
                    out[role].setdefault(y, set()).add(x)
        else:
            for x in left:
                out[role].setdefault(x, set()).update(right)
    return out

def counters_of(cid, role):
    return counters().get(role, {}).get(cid, set())

# ---------- graded counters (knowledge/counter_records.json from tools/check_matchups.py) ----------
@functools.lru_cache(None)
def counter_records():
    p = os.path.join(ROOT, "knowledge", "counter_records.json")
    return load("knowledge/counter_records.json") if os.path.exists(p) else {}

@functools.lru_cache(None)
def _h2h():
    p = os.path.join(ROOT, "pro_data", "lane_h2h.json")
    if not os.path.exists(p): return {}
    d = load("pro_data/lane_h2h.json"); out = {}
    for role, rows in d.items():
        if role == "meta": continue
        for r in rows:
            a, b = to_id(r["a"]), to_id(r["b"])
            if a and b: out[(role, a, b)] = r
    return out

def lane_record(x, y, role):
    """x's pro record vs y in that role: (games, x wins, games with x as the counter pick, x wins in those)."""
    r = _h2h().get((role, x, y))
    if r: return r["games"], r["a_wins"], r["a_after"], r["a_after_wins"]
    r = _h2h().get((role, y, x))
    if r: return r["games"], r["games"] - r["a_wins"], r["b_after"], r["b_after_wins"]
    return 0, 0, 0, 0

def lane_weighted(x, y, role):
    """x vs y in that role as (weighted games, weighted x wins): recent patches and major leagues count more (pro_data/load_games.py)."""
    r = _h2h().get((role, x, y))
    if r: return r.get("wg", r["games"]), r.get("wa", r["a_wins"])
    r = _h2h().get((role, y, x))
    if r: g = r.get("wg", r["games"]); return g, g - r.get("wa", r["a_wins"])
    return 0, 0

# ---------- high-elo soloQ lane matchups (pro_data/soloq_h2h.json from pro_data/build_soloq_h2h.py) ----------
@functools.lru_cache(None)
def _sq():
    p = os.path.join(ROOT, "pro_data", "soloq_h2h.json")
    return load("pro_data/soloq_h2h.json") if os.path.exists(p) else {}

def soloq_record(x, y, role):
    """x vs y in that lane in Master+ soloQ: (games, x win rate) or (0, None)."""
    d = _sq().get(role, {})
    r = d.get(f"{x}|{y}")
    if r: return r[0], r[1] / r[0] if r[0] else None
    r = d.get(f"{y}|{x}")
    if r: return r[0], 1 - r[1] / r[0] if r[0] else None
    return 0, None

SQ_AMP = 2.0          # a soloQ lane edge counts double as a pro edge (soloQ win rates are diluted by skill spread and team gaps)
SQ_MAX_PSEUDO = 12    # soloQ adds at most 12 pseudo pro games, so the pro record dominates once it has a real sample
SQ_GAMES_PER = 250    # soloQ games per pseudo pro game (3,000+ soloQ games = the full 12)

def blend(wg, ww, x, y, role):
    """Pro weighted record (wg games, ww x-wins) plus the soloQ matchup as pseudo-games: returns (games, wins, soloq_games, soloq_wr).
    Rare pro matchups lean on soloQ; common ones stay pro-driven."""
    sg, swr = soloq_record(x, y, role)
    if not sg or swr is None: return wg, ww, 0, None
    k = min(SQ_MAX_PSEUDO, sg / SQ_GAMES_PER)
    q = max(0.0, min(1.0, 0.5 + SQ_AMP * (swr - 0.5)))
    return wg + k, ww + k * q, sg, swr

def counter_strength(counter, target, role):
    """How much `counter` really counters `target` in that lane, before player comfort. None = not a counter.
    Listed counters (matchups.md) carry their pro grade; an unlisted pair counts as a 'pro-only' counter when the pros
    win it clearly (>= 8 weighted games, smoothed weighted WR >= 0.60). weight: strong 1.0, favoured 0.7, pro-only 0.6, untested 0.5,
    even 0.25, doubtful 0.15, contradicted 0."""
    g, w, ga, wa = lane_record(counter, target, role)
    rec = {"games": g, "wins": w, "as_counter_pick": ga, "as_counter_pick_wins": wa}
    r = counter_records().get(role, {}).get(target, {}).get(counter)   # includes listed counters the pro data dropped
    if r: return {**rec, "grade": r["grade"], "weight": r["weight"], "listed": True, "soloq_games": r.get("soloq_games", 0), "soloq_wr": r.get("soloq_wr")}
    wg, ww = lane_weighted(counter, target, role)
    if counter in counters_of(target, role):
        # listed in a group row that check_matchups can't grade (e.g. "Assassins: ..."): grade it here, same thresholds
        sm = (ww + 3) / (wg + 6)
        gr, wt = (("contradicted", 0.0) if wg >= 5 and sm < 0.45 else ("untested", 0.5) if wg < 3 else ("doubtful", 0.15) if sm < 0.45
                  else ("strong", 1.0) if wg >= 6 and sm >= 0.56 else ("favoured", 0.7) if sm >= 0.52 else ("even", 0.25))
        return {**rec, "grade": gr, "weight": wt, "listed": True}
    bg, bw, sg, swr = blend(wg, ww, counter, target, role)
    if bg >= 8 and (bw + 3) / (bg + 6) >= 0.60:
        return {**rec, "grade": "pro-only" if bg - wg < wg else "soloq", "weight": 0.6, "listed": False, "soloq_games": sg, "soloq_wr": swr}
    return None

def comfort_factor(c):
    """Player comfort (0-1) -> how much of a counter's value they can actually use. In this league a counter the
    player barely plays is close to worthless: <= 0.2 -> 0, 0.6+ -> full value."""
    return max(0.0, min(1.0, ((c or 0) - 0.2) / 0.4))

def counter_note(cs):
    if not cs: return ""
    rec = f"pro {cs['wins']}-{cs['games'] - cs['wins']}" if cs["games"] else "no pro games"
    if cs.get("soloq_games"): rec += f", Master+ {cs['soloq_wr']:.1%} in {cs['soloq_games']:,}"
    return f"{cs['grade']}, {rec}"

# ---------- mid + jungle pairs (pro_data/mj_blocks.json, build_mj_blocks.py) ----------
@functools.lru_cache(None)
def _mj():
    p = os.path.join(ROOT, "pro_data", "mj_blocks.json")
    if not os.path.exists(p): return {}
    import json
    d = json.load(open(p, encoding="utf-8"))
    return {(to_id(x["jungle"]), to_id(x["mid"])): x for x in d.get("pairs", [])}

def mj_pair(jungle, mid):
    """Pro record of this jungle + mid on the same team (all 2026 games, weighted), or None."""
    return _mj().get((jungle, mid))

def mj_synergy(jungle, mid):
    """Synergy points of a jungle + mid pair, shrunk by sample (synergy x wg / (wg + 40)); 0 below 25 weighted games.
    +7 = the pair wins ~7 points more than its two champions do apart. Returns (points, pair record or None)."""
    x = mj_pair(jungle, mid)
    if not x or x["wg"] < 25: return 0.0, x
    return round(x["synergy"] * x["wg"] / (x["wg"] + 40), 1), x

def mj_note(jungle, mid):
    pts, x = mj_synergy(jungle, mid)
    if not x: return ""
    tag = ("too few games to call" if x["wg"] < 25 else "real synergy" if pts >= 3 else "anti-synergy" if pts <= -3 else "no pair effect")
    return (f"{display(jungle)} + {display(mid)}: {x['wins']}-{x['games'] - x['wins']} in {x['games']} pro games "
            f"({round(100 * x['wr_smoothed'])}% weighted vs {round(100 * x['expected'])}% expected from the two apart; {tag}, {pts:+} after sample shrink)")

# ---------- bot duos (pro_data/duo_synergy.json, build_duo_synergy.py) ----------
@functools.lru_cache(None)
def _duo():
    p = os.path.join(ROOT, "pro_data", "duo_synergy.json")
    if not os.path.exists(p): return {}
    import json
    return {(to_id(x["adc"]), to_id(x["support"])): x for x in json.load(open(p, encoding="utf-8")).get("pairs", [])}

def duo_synergy(adc, support):
    """Same measure as mj_synergy for an ADC + support on one team. Returns (shrunk points, record or None)."""
    x = _duo().get((adc, support))
    if not x or x["wg"] < 25: return 0.0, x
    return round(x["synergy"] * x["wg"] / (x["wg"] + 40), 1), x

def duo_note(adc, support):
    pts, x = duo_synergy(adc, support)
    if not x: return ""
    tag = ("too few games to call" if x["wg"] < 25 else "real synergy" if pts >= 3 else "anti-synergy" if pts <= -3 else "no pair effect")
    return (f"{display(adc)} + {display(support)}: {x['wins']}-{x['games'] - x['wins']} in {x['games']} pro games "
            f"({round(100 * x['wr_smoothed'])}% weighted vs {round(100 * x['expected'])}% expected from the two apart; {tag}, {pts:+} after sample shrink)")

# ---------- established pro pairs (pro_data/pro_pairs.json, build_pro_pairs.py) ----------
PAIR_KINDS = {("bot", "support"): "bot", ("support", "bot"): "bot", ("jungle", "mid"): "mid_jungle", ("mid", "jungle"): "mid_jungle"}

@functools.lru_cache(None)
def _pro_pairs():
    p = os.path.join(ROOT, "pro_data", "pro_pairs.json")
    if not os.path.exists(p): return {}
    import json
    d = json.load(open(p, encoding="utf-8"))
    return {k: {(to_id(x["a"]), to_id(x["b"])): x for x in d.get(k, [])} for k in ("bot", "mid_jungle")}

def _pair_key(role, champ, other_role, partner):
    """(kind, a, b) with a = bot/jungle half, b = support/mid half."""
    kind = PAIR_KINDS.get((role, other_role))
    if not kind: return None, None, None
    first = role in ("bot", "jungle")
    return kind, (champ if first else partner), (partner if first else champ)

def pro_pair(role, champ, other_role, partner):
    """Pro record for champ (in role) + partner (in other_role) on one team, or None. Fields: see build_pro_pairs.py."""
    kind, a, b = _pair_key(role, champ, other_role, partner)
    return _pro_pairs().get(kind, {}).get((a, b)) if kind else None

def established_partners(role, champ, other_role):
    """Pro partners for champ that are a drafting habit or real synergy (status set), best first: [(partner id, record)]."""
    kind = PAIR_KINDS.get((role, other_role))
    if not kind: return []
    first = role in ("bot", "jungle")
    out = [((b if first else a), x) for (a, b), x in _pro_pairs().get(kind, {}).items()
           if (a if first else b) == champ and x.get("status")]
    rank = {"established_strong": 0, "established": 1, "synergy_only": 2, "established_loses": 3}
    return sorted(out, key=lambda t: (rank.get(t[1]["status"], 9), -t[1]["games"]))

def pair_line(role, champ, other_role, partner):
    """One line on a pair: habit (lift, share), synergy, and each half's WR without the other."""
    x = pro_pair(role, champ, other_role, partner)
    if not x: return ""
    first = role in ("bot", "jungle")
    mine_wo, theirs_wo = (x["a_wr_without"], x["b_wr_without"]) if first else (x["b_wr_without"], x["a_wr_without"])
    rec = f"{x['wins']}-{x['games'] - x['wins']}" + (f", 26.16+ {x['recent_wins']}-{x['recent_games'] - x['recent_wins']}" if x["recent_games"] else "")
    return (f"{display(champ)} + {display(partner)} [{x['status'] or ('anti-synergy' if x['synergy_shrunk'] <= -3 else 'no pair habit')}]: {x['games']} pro games ({rec}), drafted together x{x['lift']} chance, "
            f"synergy {x['synergy']:+} ({x['synergy_shrunk']:+} shrunk); {display(champ)} wins {round(100 * mine_wo)}% without {display(partner)}, "
            f"{display(partner)} {round(100 * theirs_wo)}% without {display(champ)}")
