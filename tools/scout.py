"""Everything the project knows about a champion for a team, in one call (for drafting captains).
  python3 tools/scout.py <team> "Qiyana,Vi"          -> per champion: pro power/presence, every player on <team> who plays it
                                                        (soloQ mastery, competitive record, team sheet tier, draft value),
                                                        how often it is banned vs/by the team, our drafter history, matchup notes
  add --public to see <team> only as an opponent could (profile_public.json: no team sheet, scrims or drafter history)
  python3 tools/scout.py <team> --role jungle [--n 12] -> that role's pool ranked by draft value + strong pro champions they lack
Sources: teams/<team>/profile.json, pro_data/champion_pro_stats.json, pro_data/role_timing.json, pro_data/b1_priority.json, knowledge/matchups.md + counter_records.json (graded vs pro lane records).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from knowledge import to_id, display, pro, pro_power, tags
ROOT = os.path.join(os.path.dirname(__file__), "..")

def _th(team, pname):
    return "-"

def J(rel, d=None):
    p = os.path.join(ROOT, rel)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d

def dv(e):
    eff = max(pro_power(e["champ"]), min(100, round(10 * e.get("league_presence", 0))))
    return e.get("draft_value") or round(e["comfort"] * (0.55 + 0.45 * eff / 100), 3)

def pro_line(cid):
    c = pro().get(cid)
    if not c: return f"PRO: no pro data (power 0)"
    w = c.get("worlds_2026_main_event") or {}
    return (f"PRO: power {pro_power(cid)}/100, tier {c.get('tier')}, roles {'/'.join(c.get('roles', []))}, presence {c['weighted_presence']:.0%} "
            f"(pick {c['weighted_pickrate']:.0%} + ban {c['weighted_banrate']:.0%}, avg ban turn {c.get('avg_ban_turn')}), WR {c['weighted_winrate']:.1%}, "
            f"blind-picked {c.get('blind_pick_pct')}%" + (f", Worlds26 {w.get('picks',0)} picks / {w.get('bans',0)} bans / {w.get('wins',0)} wins" if w else ""))

_PAIR = None
def _rng(w, n):
    """Wilson 95% range as ' (95% 41-63%)', and a flag when the sample is too small to decide anything."""
    import math
    if not n: return ""
    p, z = w / n, 1.96; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    lo, hi = round(100 * (c - h)), round(100 * (c + h))
    tag = ", small sample: tiebreaker only" if n < 20 else ", no clear edge" if lo < 50 < hi else ""
    return f" (95% {lo}-{hi}%{tag})"
def pairing_lines(cid):
    """Pro pairings (knowledge/pairings.md, pro_data/pairings.json): duo partners, mid/jungle partners, pick timing."""
    global _PAIR
    if _PAIR is None: _PAIR = J("pro_data/pairings.json", {}) or {}
    name = display(cid); out = []
    # established pairs first (pro_data/pro_pairs.json): drafted together as a habit, with each half's WR without the other
    from knowledge import established_partners, PAIR_KINDS
    for (r1, r2) in PAIR_KINDS:
        est = [(p, x) for p, x in established_partners(r1, cid, r2) if x["status"].startswith("established")][:4]
        if est:
            first = r1 in ("bot", "jungle")
            out.insert(0, f"PRO ESTABLISHED PAIRS as {r1} ({r2} partner, knowledge/pro_pairs.md): " + "; ".join(
                f"{display(p)} [{x['status']}] {x['games']}G x{x['lift']} chance, synergy {x['synergy_shrunk']:+}, "
                f"{name} {round(100 * (x['a_wr_without'] if first else x['b_wr_without']))}% without it" for p, x in est))
    def fmt(r, other): return f"{r[other]} {r['games']}G {round(100 * r['wins'] / max(r['games'], 1))}%WR{_rng(r['wins'], r['games'])} (same rotation {round(100 * r.get('together_same_rotation_pct', 0))}%" + (f", Worlds {r['worlds_games']}G {r.get('worlds_wins', 0)}W" if r.get('worlds_games') else "") + ")"
    # jungle + mid: synergy from every 2026 game (pro_data/mj_blocks.json), not raw win rate
    mjp = (J("pro_data/mj_blocks.json", {}) or {})
    for me, other in (("jungle", "mid"), ("mid", "jungle")):
        rows = [r for r in mjp.get("pairs", []) if r[me] == name and r["wg"] >= 25]
        if not rows: continue
        sh = lambda r: round(r["synergy"] * r["wg"] / (r["wg"] + 40), 1)
        good = sorted([r for r in rows if sh(r) >= 3], key=lambda r: -sh(r))[:4]; bad = sorted([r for r in rows if sh(r) <= -3], key=sh)[:3]
        f = lambda r: f"{r[other]} {r['wins']}-{r['games'] - r['wins']} ({sh(r):+} pts, together {round(100 * r['together'] / r['games'])}%)"
        if good or bad:
            out.append(f"PRO {me.upper()}+{other.upper()} PAIR, SAME TEAM (synergy = pair WR vs the two apart; not a matchup): "
                       + ("works with " + ", ".join(map(f, good)) if good else "no clear synergy partner") + (" | avoid " + ", ".join(map(f, bad)) if bad else ""))
        fu = mjp.get("after_jungle_first" if me == "jungle" else "after_mid_first", {}).get(name)
        if fu and fu["partners"]:
            out.append(f"PRO FOLLOW-UP after {name} is locked first ({fu['first_locks']} times): " + ", ".join(f"{y['partner']} {round(100 * y['share'])}% (x{y['lift']}, {round(100 * y['wr_smoothed'])}% WR)" for y in fu["partners"][:5]))
    ds = (J("pro_data/duo_synergy.json", {}) or {})
    for me, other in (("adc", "support"), ("support", "adc")):
        rows = [r for r in ds.get("pairs", []) if r[me] == name and r["wg"] >= 25]
        sh = lambda r: round(r["synergy"] * r["wg"] / (r["wg"] + 40), 1)
        good = sorted([r for r in rows if sh(r) >= 3], key=lambda r: -sh(r))[:4]; bad = sorted([r for r in rows if sh(r) <= -3], key=sh)[:3]
        f = lambda r: f"{r[other]} {r['wins']}-{r['games'] - r['wins']} ({sh(r):+} pts)"
        if good or bad:
            out.append(f"PRO DUO SYNERGY, SAME TEAM ({other} partner; pair WR vs the two apart, all 2026; not a matchup): "
                       + ("works with " + ", ".join(map(f, good)) if good else "no clear synergy partner") + (" | avoid " + ", ".join(map(f, bad)) if bad else ""))
    for key, a, b in (("bot_pairs", "adc", "support"),):
        for me, other in ((a, b), (b, a)):
            rows = [r for r in _PAIR.get(key, []) if r[me] == name][:5]
            if rows: out.append(f"PRO PAIR, SAME TEAM ({other} partner; not a matchup): " + "; ".join(fmt(r, other) for r in rows))
    # pick timing and ADC lanes now come from role_timing.json / lane_h2h.json (PRO TIMING, PRO LANE), one source for all roles
    from knowledge import _h2h
    lanes = []
    for (role, a, b), r in _h2h().items():
        if role == "bot" and cid in (a, b) and r["games"] >= 6:
            w = r["a_wins"] if cid == a else r["games"] - r["a_wins"]
            lanes.append((r["games"], f"PRO LANE VS (opponent ADC): vs {display(b if cid == a else a)} {w}-{r['games'] - w}{_rng(w, r['games'])}"))
    out += [l for _, l in sorted(lanes, key=lambda x: -x[0])[:5]]
    return out[:12]

def matchup_lines(cid):
    import re
    pat = re.compile(r"(?<![A-Za-z'])(" + re.escape(display(cid)) + "|" + re.escape(cid) + r")(?![A-Za-z'])", re.I); out = []
    p = os.path.join(ROOT, "knowledge", "matchups.md")
    for l in open(p, encoding="utf-8"):
        if l.startswith("|") and pat.search(l): out.append(l.strip())
    return out[:6]

def counter_lines(team, prof, cid):
    """Graded counters (knowledge/counter_records.json): what cid counters, what counters it, and whether this team's
    player in that role can actually play cid well enough for the counter to count."""
    from knowledge import counter_records, comfort_factor
    out, pools = [], prof.get("pools", {})
    rec = lambda r: (f"{r['grade']} {r['wins']}-{r['games'] - r['wins']}" if r["games"] else r["grade"]) + (f" (Master+ {r['soloq_wr']:.1%}/{r['soloq_games']:,})" if r.get("soloq_games") else "")
    for role, recs in counter_records().items():
        into = sorted(((t, d[cid]) for t, d in recs.items() if cid in d), key=lambda x: -x[1]["weight"])
        if into:
            cf = pools.get(role, {}).get(cid)
            use = (f"{team}'s {role} comfort {cf:.2f} -> uses {comfort_factor(cf):.0%} of the counter value" if cf is not None
                   else f"nobody on {team} plays it {role}: worth ~0 as a counter here")
            out.append(f"COUNTER INTO ({role}; record is {display(cid)}'s W-L in that lane): " + ", ".join(f"{display(cid)} vs {display(t)} {rec(r)}" for t, r in into) + f" | {use}")
        by = sorted(recs.get(cid, {}).items(), key=lambda x: -x[1]["weight"])
        if by:
            out.append(f"COUNTERED BY ({role}; record is the counter's W-L vs {display(cid)}): " + ", ".join(f"{display(c)} vs {display(cid)} {rec(r)}" for c, r in by))
    from knowledge import _h2h
    po = []
    for (role, a, b), r in _h2h().items():   # clear pro lane wins that matchups.md doesn't list (>= 8 weighted games, smoothed weighted >= 60%)
        if cid not in (a, b): continue
        wg = r.get("wg", r["games"]); wwa = r.get("wa", r["a_wins"])
        if wg < 8: continue
        g = r["games"]; other = b if cid == a else a; w = r["a_wins"] if cid == a else g - r["a_wins"]; ww = wwa if cid == a else wg - wwa
        known = counter_records().get(role, {})
        if (ww + 3) / (wg + 6) >= 0.6 and cid not in known.get(other, {}):
            po.append((wg, f"PRO-ONLY ({role}): {display(cid)} beats {display(other)} {w}-{g - w} in pro lanes (not in matchups.md)"))
        elif (wg - ww + 3) / (wg + 6) >= 0.6 and other not in known.get(cid, {}):
            po.append((wg, f"PRO-ONLY ({role}): {display(other)} beats {display(cid)} {g - w}-{w} in pro lanes (not in matchups.md)"))
    return out + [l for _, l in sorted(po, key=lambda x: -x[0])[:6]]

def pro_timing_lines(cid):
    """Role pick timing, B1 priority and bot pair timing (pro_data/role_timing.json, b1_priority.json, bot_blocks.json)."""
    out, name = [], display(cid)
    rt = J("pro_data/role_timing.json", {}) or {}
    rng = lambda v: f"{v[0]}-{v[1] - v[0]}" + (f" (95% range {round(100 * v[2][0])}-{round(100 * v[2][1])}%)" if v[2] else "")
    for role in ("top", "jungle", "mid", "bot", "support"):
        for e in rt.get(role, []):
            if to_id(e["champ"]) != cid: continue
            g = e["by_game"]
            line = (f"PRO TIMING ({role}, {e['games']} games: G1 {g[0]}, G2 {g[1]}, G3 {g[2]}, G4+ {g[3]}): blind {round(100 * e['blind_pct'])}% "
                    f"(W-L {rng(e['blind_wr'])}), counter W-L {rng(e['counter_wr'])}, phase-1 pick {round(100 * e['phase1_pct'])}%")
            if e["gone_before_blind"]:
                line += " | pros blind it more after these are gone: " + ", ".join(f"{x['champ']} ({x['n']}/{x['of']}, x{x['lift']})" for x in e["gone_before_blind"])
            out.append(line)
    b1 = J("pro_data/b1_priority.json", {}) or {}
    parts = []
    for g in ("1", "2", "3", "4"):
        e = next((x for x in b1.get(g, []) if to_id(x["champ"]) == cid), None)
        if e and e["b1"]: parts.append(f"G{g if g != '4' else '4+'} {e['b1']}x ({round(100 * e['b1_when_avail'])}% when available)")
    if parts: out.append("PRO B1: " + ", ".join(parts))
    bb = J("pro_data/bot_blocks.json", {}) or {}
    for p in bb.get("pairs", []):
        if cid in (to_id(p["adc"]), to_id(p["support"])) and p["games"] >= 10:
            out.append(f"PRO BOT PAIR, SAME TEAM {p['adc']} + {p['support']}: {p['games']} games ({p['wins']}-{p['games'] - p['wins']}), locked together {round(100 * p['together'] / p['games'])}%, "
                       f"blind {p['blind']} / half-blind {p['half_blind']} / answered {p['answered']}")
    return out[:8]

def history(team, cid):
    return None

def champ(team, prof, cid):
    print(f"## {display(cid)}"); print(pro_line(cid))
    found = False
    for pname, pl in prof["players"].items():
        for e in pl["pool"]:
            if e["champ"] == cid:
                found = True
                print(f"PLAYER {pname} ({pl['role']}{', main' if pl.get('is_main') else ', alternate'}): comfort {e['comfort']}, draft value {dv(e)} | "
                      f"comp {e['comp_games']}G {e['comp_wins']}W{(' ' + str(e.get('comp_unknown')) + ' result unknown') if e.get('comp_unknown') else ''} (+{e['prev_split_games']} prev split) | soloQ {e['soloq_games']}G {e['soloq_wr'] if e['soloq_wr'] is not None else '-'}% | "
                      f"team sheet: {e.get('stated') or 'not listed'} | league presence {e.get('league_presence', 0)} (picks + bans aimed at him) | player threat {_th(team, pname)}")
    for pname, pl in prof["players"].items():
        for r in pl.get("feared", []):
            if r["champ"] == cid: found = True; print(f"FEARED: opponents ban it vs {pname} ({r['phase1_bans_vs']} phase-1, {r['phase2_bans_vs']} phase-2) though he rarely plays it in league")
    if not found: print(f"PLAYERS: nobody on {team} has it in their pool")
    ba = prof.get("bans_against", {}).get(cid); bb = prof.get("bans_by", {}).get(cid)
    bt = prof.get("ban_targets", {}).get(cid, {})
    kind = ("blanket ban, a habit vs most opponents" if cid in prof.get("bans_habit", []) else
            "targeted: only vs these opponents, not a habit vs others") if bt else ""
    print(f"BANS: banned against {team} {ba or 0} (recency weighted) | banned by {team} {bb or 0}"
          + (f" (vs {', '.join(f'{o} {n}' for o, n in bt.items())}; {len(bt)}/{prof.get('opponents_faced', '?')} opponents: {kind})" if bt else ""))
    h = history(team, cid)
    if h: print(h)
    for l in pairing_lines(cid): print(l)
    for l in pro_timing_lines(cid): print(l)
    for l in counter_lines(team, prof, cid): print(l)
    for l in matchup_lines(cid): print("MATCHUP NOTE: " + l)
    print()

if __name__ == "__main__":
    a = sys.argv[1:]; PUBLIC = "--public" in a; a = [x for x in a if x != "--public"]; team = a[0]
    prof = J(f"teams/{team}/profile_public.json") if PUBLIC else None
    prof = prof or J(f"teams/{team}/profile.json")
    if not prof: sys.exit(f"no profile for {team}")
    if "--role" in a:
        role = a[a.index("--role") + 1]; n = int(a[a.index("--n") + 1]) if "--n" in a else 12
        for pname, pl in prof["players"].items():
            if pl["role"] != role: continue
            print(f"## {pname} ({role}{', main' if pl.get('is_main') else ', alternate'}) {pl.get('soloq_rank') or ''}")
            for e in sorted(pl["pool"], key=lambda e: -dv(e))[:n]:
                print(f"{e['name']}: draft value {dv(e)} | comfort {e['comfort']} | pro {pro_power(e['champ'])} | league presence {e.get('league_presence', 0)} | comp {e['comp_games']}G {e['comp_wins']}W{('/' + str(e.get('comp_unknown')) + '?') if e.get('comp_unknown') else ''} | "
                      f"soloQ {e['soloq_games']}G {e['soloq_wr'] if e['soloq_wr'] is not None else '-'}% | sheet {e.get('stated') or '-'}")
            if pl.get("feared"): print("Feared but rarely seen: " + ", ".join(f"{r['name']} (bans {round(r['phase1_bans_vs'] + r['phase2_bans_vs'], 1)})" for r in pl["feared"]))
            have = {e["champ"] for e in pl["pool"]}
            lack = [c for c in sorted(pro(), key=lambda c: -pro_power(c)) if role in pro()[c].get("roles", []) and c not in have][:8]
            print("Strong pro champions NOT in this pool (deny/ban candidates or blind spots): " + ", ".join(f"{display(c)} {pro_power(c)}" for c in lack))
            print()
    else:
        for n in " ".join(a[1:]).split(","):
            if n.strip(): champ(team, prof, to_id(n.strip()))
