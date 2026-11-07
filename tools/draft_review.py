"""Post-draft evaluation: who won the draft, and the facts an analyst needs to write lane, jungle and teamfight notes.
  python3 tools/draft_review.py <sim.json>                       -> markdown facts + score (stdout)
  python3 tools/draft_review.py <sim.json> --json                -> the same as JSON
  python3 tools/draft_review.py --blue <slug> --red <slug> --blue-picks "A,B,C,D,E" --red-picks "..."   (live drafts: spectate/autodraft)
  add --roles-blue "top,jungle,mid,bot,support order of the picks" to override role inference (same for --roles-red).
  add --draft-only for the objective draft score: the champions alone, players left out (no comfort component, every
  counter counts at full grade weight, no comfort-gap notes). Roles are still read from the team pools.

The score is deliberately coarse: it says which side the data leans to and why, not a win probability to trust to the percent.
Components per side (all from project data, full knowledge of both teams):
  comfort   each player's comfort on his champion (profile pools: soloQ mastery + comp record + team sheet)
  power     pro power 0-100 (picks + bans, phase-1 bans extra)
  lanes     matchups.md counters per lane (+1 for the side whose champion counters the other) and pro ADC-vs-ADC records
  synergy   bot duo synergy (duo_synergy.json) and jungle/mid pair synergy (mj_blocks.json): pair WR vs the two champions apart, shrunk by sample
  comp      damage-type flags only (4+ AD or 4+ AP champions)
"""
import sys, os, json, math, itertools
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, ROLES
from knowledge import display, to_id, pro_power, archetypes, damage, counters_of, tags, counter_strength, comfort_factor, counter_note
from common import ORDER
from roles import role_prior

def J(rel, d=None):
    p = os.path.join(ROOT, rel)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d

def prof(slug): return J(f"teams/{slug}/profile.json", {})

def assign(picks, p):
    pools = p.get("pools", {}); best, bs = None, -1e9
    for perm in itertools.permutations(picks):
        s = sum(role_prior(c)[r] + 6 * pools.get(r, {}).get(c, 0) for c, r in zip(perm, ROLES))
        if s > bs: best, bs = perm, s
    return dict(zip(ROLES, best))

def player_entry(p, role, cid):
    """The role's player who is best on cid (main first on ties). Player keys are 'name' or 'name@role' for a second role."""
    main = p.get("roster", {}).get(role, {}).get("main")
    best = (None, None, -1)
    for k, v in p.get("players", {}).items():
        if v.get("role") != role: continue
        name = k.split("@")[0]
        e = next((x for x in v.get("pool", []) if x["champ"] == cid), None)
        c = (e or {}).get("comfort", 0) + (0.001 if name == main else 0)
        if c > best[2]: best = (name, e, c)
    return (best[0] or main), best[1]

PAIR = None
def pair_rec(key, a_key, a, b_key, b):
    global PAIR
    if PAIR is None: PAIR = J("pro_data/pairings.json", {})
    for r in PAIR.get(key, []):
        if r[a_key] == display(a) and r[b_key] == display(b): return r
    return None

def adc_lane(a, b):
    """a's pro ADC-lane record vs b from every 2026 game (lane_h2h.json): (raw wins, raw games, smoothed weighted WR), or None under 8 weighted games."""
    from knowledge import lane_record, lane_weighted
    g, w, _, _ = lane_record(a, b, "bot"); wg, ww = lane_weighted(a, b, "bot")
    if wg < 8: return None
    return w, g, (ww + 3) / (wg + 6)

def side_facts(p, comp):
    rows, com, pw = [], [], []
    for r in ROLES:
        c = comp[r]; main, e = player_entry(p, r, c)
        cf = e["comfort"] if e else 0.0
        com.append(cf); pw.append(pro_power(c))
        rows.append({"role": r, "champ": c, "name": display(c), "player": main, "comfort": round(cf, 2), "power": pro_power(c),
                     "soloq": f"{e['soloq_games']}g {e.get('soloq_wr', '?')}%" if e and e.get("soloq_games") else "0g",
                     "comp": f"{e['comp_games']}g {e.get('comp_wins', 0)}w" if e else "0g", "sheet": (e or {}).get("stated") or "-",
                     "archetypes": sorted(archetypes(c)), "damage": damage(c)})
    champs = [comp[r] for r in ROLES]
    ad = sum(damage(c) == "AD" for c in champs); ap = sum(damage(c) == "AP" for c in champs)
    flags = []
    if ad >= 4: flags.append(f"{ad} AD champions (armour stacks)")
    if ap >= 4: flags.append(f"{ap} AP champions (MR stacks)")
    return {"rows": rows, "comfort": sum(com) / 5, "power": sum(pw) / 5, "flags": flags, "ad": ad, "ap": ap}

def review(blue, red, bp, rp, roles_b=None, roles_r=None, players=True):
    """players=False: objective draft score, champions only (see module docstring, --draft-only)."""
    PB, PR = prof(blue), prof(red)
    cb = dict(zip(roles_b, bp)) if roles_b else assign(bp, PB)
    cr = dict(zip(roles_r, rp)) if roles_r else assign(rp, PR)
    F = {"blue": side_facts(PB, cb), "red": side_facts(PR, cr)}
    F["blue"]["team"], F["red"]["team"] = PB.get("team", blue), PR.get("team", red)
    lanes = []
    for r in ROLES:
        b, rd = cb[r], cr[r]; edge = 0; why = []
        i = ROLES.index(r)
        # a counter only counts as much as the pros back it (grade weight) and the player can play it (comfort factor)
        for ctr, tgt, sign, side in ((rd, b, -1, "red"), (b, rd, 1, "blue")):
            cs = counter_strength(ctr, tgt, r)
            if not cs: continue
            row = F[side]["rows"][i]; k = comfort_factor(row["comfort"]) if players else 1.0; v = cs["weight"] * k
            edge += sign * v
            if cs["weight"] == 0:
                why.append(f"{display(ctr)} is a theory counter to {display(tgt)} but the pros lose it ({counter_note(cs)}): no edge")
            else:
                why.append(f"{display(ctr)} counters {display(tgt)} ({counter_note(cs)})" + (f"; {row['player']} comfort {row['comfort']:.2f} -> counts {v:.2f} of 1" if players else ""))
        if r == "bot":
            x = adc_lane(b, rd)
            if x:
                w, g, sw = x; why.append(f"pro ADC lane {display(b)} {w}-{g - w} vs {display(rd)}")
                if sw >= 0.56: edge += 1
                elif sw <= 0.44: edge -= 1
        dc = F["blue"]["rows"][ROLES.index(r)]["comfort"] - F["red"]["rows"][ROLES.index(r)]["comfort"]
        if players and abs(dc) >= 0.2: why.append(f"comfort gap {dc:+.2f} ({'blue' if dc > 0 else 'red'} player much more practised)")
        lanes.append({"role": r, "blue": display(b), "red": display(rd), "edge": round(max(-2, min(2, edge)), 2), "notes": why,
                      "weight": 0.5 if r == "jungle" else 1.0})
    syn = {}
    for side, cm in (("blue", cb), ("red", cr)):
        s, notes = 0.0, []
        from knowledge import mj_synergy, mj_note, duo_synergy, duo_note
        pts, bt = duo_synergy(cm["bot"], cm["support"])   # pro_data/duo_synergy.json: duo effect beyond the two champions apart
        if bt:
            s += pts * 0.15; notes.append("bot duo " + duo_note(cm["bot"], cm["support"]))
        pts, mj = mj_synergy(cm["jungle"], cm["mid"])   # pro_data/mj_blocks.json: pair effect beyond the two champions apart
        if mj:
            s += pts * 0.15; notes.append("jungle/mid " + mj_note(cm["jungle"], cm["mid"]))
        syn[side] = {"score": round(s, 2), "notes": notes or ["no common pro pairing (>= 8 games)"]}
    idedge = 0.0
    # score: comfort (0-1) matters most in this league, then lanes, power, comp and synergy
    def S(side):
        f = F[side]; sign = 1 if side == "blue" else -1
        lane = sum(l["edge"] * l["weight"] for l in lanes) * sign
        return {**({"comfort": round(30 * f["comfort"], 1)} if players else {}), "power": round(0.12 * f["power"], 1), "lanes": round(2.0 * lane, 1),
                "synergy": round(syn[side]["score"], 1), "comp": round(6 * idedge * sign - 2.5 * len(f["flags"]), 1)}
    sb, sr = S("blue"), S("red")
    tb, tr = sum(sb.values()), sum(sr.values())
    # calibrated so a typical gap reads 55-65 and a lopsided one tops out at 70: a draft rarely decides more than that
    pb = min(0.70, max(0.30, 1 / (1 + math.exp(-(tb - tr) / 20))))
    drivers = sorted(((k, sb[k] - sr[k]) for k in sb), key=lambda x: -abs(x[1]))
    return {"blue": blue, "red": red, "comp": {"blue": cb, "red": cr}, "facts": F, "lanes": lanes, "synergy": syn,
            "identity_edge_blue": round(idedge, 2), "score": {"blue": sb, "red": sr, "total_blue": round(tb, 1), "total_red": round(tr, 1)},
            "lean": {"blue": round(100 * pb), "red": 100 - round(100 * pb)}, "players": players, "drivers": [f"{k} {'blue' if d > 0 else 'red'} {abs(d):.1f}" for k, d in drivers[:3]]}

def md(R):
    L = [f"# Draft review facts: {R['facts']['blue']['team']} (blue) vs {R['facts']['red']['team']} (red)", "",
         ("Draft only (champions, players left out). " if not R.get("players", True) else "") + f"**Data lean: blue {R['lean']['blue']} - {R['lean']['red']} red.** Biggest drivers: {', '.join(R['drivers'])}.", "",
         "| Component | Blue | Red |", "|---|---|---|"]
    for k in R["score"]["blue"]: L.append(f"| {k} | {R['score']['blue'][k]} | {R['score']['red'][k]} |")
    L.append(f"| total | {R['score']['total_blue']} | {R['score']['total_red']} |"); L.append("")
    for side in ("blue", "red"):
        f = R["facts"][side]
        L += [f"## {f['team']} ({side})", "| Role | Champion | Player | Comfort | SoloQ | Comp | Sheet | Pro power | Archetypes | Dmg |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in f["rows"]:
            L.append(f"| {r['role']} | {r['name']} | {r['player']} | {r['comfort']} | {r['soloq']} | {r['comp']} | {r['sheet']} | {r['power']} | {', '.join(r['archetypes'])} | {r['damage']} |")
        L += [f"Damage: {f['ad']} AD / {f['ap']} AP. Flags: {', '.join(f['flags']) or 'none'}.",
              f"Synergy: {'; '.join(R['synergy'][side]['notes'])}.", ""]
    L += ["## Lanes (edge: + favours blue, - favours red)", "| Lane | Blue | Red | Edge | Notes |", "|---|---|---|---|---|"]
    for l in R["lanes"]: L.append(f"| {l['role']} | {l['blue']} | {l['red']} | {(format(l['edge'], '+.2f') if l['edge'] else '0')} | {'; '.join(l['notes']) or 'no counter on record'} |")
    return "\n".join(L)

def from_sim(path):
    s = json.load(open(path, encoding="utf-8"))
    bp = [a["champ"] for a in s["actions"] if a["side"] == "blue" and a["kind"] == "pick"]
    rp = [a["champ"] for a in s["actions"] if a["side"] == "red" and a["kind"] == "pick"]
    return s["blue"], s["red"], bp, rp

if __name__ == "__main__":
    a = sys.argv[1:]; g = lambda n, d=None: a[a.index(n) + 1] if n in a else d
    if a and a[0].endswith(".json"): blue, red, bp, rp = from_sim(a[0])
    else:
        blue, red = g("--blue"), g("--red")
        bp = [to_id(x.strip()) for x in g("--blue-picks").split(",")]; rp = [to_id(x.strip()) for x in g("--red-picks").split(",")]
    rb = g("--roles-blue"); rr = g("--roles-red")
    R = review(blue, red, bp, rp, rb.split(",") if rb else None, rr.split(",") if rr else None, players="--draft-only" not in a)
    print(json.dumps(R, ensure_ascii=False, indent=1) if "--json" in a else md(R))
