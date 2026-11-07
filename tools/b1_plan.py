"""B1 plan: which pro first-pick champions overlap with our pools, which the opponent is likely to ban first.
  python3 tools/b1_plan.py <us> <opp> [--public] [--game N] [--used "Champ1,Champ2"] [--banned "Qiyana,Vi"] [--n 15]
--game picks the pro B1 list for that game of the series (pro_data/b1_priority.json); --used = champions gone to hard fearless;
--public reads the opponent's public profile only (for a captain with public knowledge of them).
--banned = phase-1 bans already made (live drafts), so the list shows what is actually left at B1.
For each candidate: pro B1 priority, pro power, our best player + comfort, their best player + comfort (deny value),
and how likely the opponent bans it in phase 1 against us (their bans aimed at us, their phase-1 ban habit, what every team bans vs us).
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT, ROLES
from knowledge import to_id, display, pro_power, comfort_factor

def J(p, d=None):
    p = os.path.join(ROOT, p)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d

def best(prof, cid):
    b = (None, None, 0.0)
    for pname, pl in prof.get("players", {}).items():
        for e in pl.get("pool", []):
            if e["champ"] == cid and e["comfort"] > b[2]: b = (pname, pl["role"], e["comfort"])
    return b

def team_name(slug): return (J(f"teams/{slug}/team.json", {}) or {}).get("name", slug)

def ban_risk(opp, us_name, us_prof, cid):
    """0-1 guess that `opp` bans cid in phase 1 vs us, with the evidence."""
    tg = opp.get("ban_targets", {}).get(cid, {}); vs_us = sum(v for k, v in tg.items() if k.lower().startswith(us_name.lower()[:5]))
    p1 = opp.get("bans_by_first_phase", {}).get(cid, 0); games = max(1, opp.get("record", {}).get("games", 1))
    hab = cid in opp.get("bans_habit", [])
    ag = us_prof.get("bans_against", {}).get(cid, 0)          # every team's bans vs us (recency weighted)
    r = min(1.0, 0.35 * min(vs_us, 2) + 0.4 * min(1, 3 * p1 / games) + (0.3 if hab else 0) + 0.08 * ag)
    ev = []
    if vs_us: ev.append(f"banned vs us {vs_us}x")
    if p1: ev.append(f"P1-banned {p1}x in {games} games")
    if hab: ev.append("blanket ban")
    if ag >= 1: ev.append(f"teams ban it vs us {ag:.1f}")
    return r, ev

def main():
    a = sys.argv[1:]; g = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    us, opp = a[0], a[1]; game = str(min(int(g("--game", 1)), 4)); n = int(g("--n", 15))
    gone = {to_id(x.strip()) for x in (g("--used", "") + "," + g("--banned", "")).split(",") if x.strip()}
    U = J(f"teams/{us}/profile.json")
    O = (J(f"teams/{opp}/profile_public.json") if "--public" in a else None) or J(f"teams/{opp}/profile.json")
    B = J("pro_data/b1_priority.json")[game]
    rows = []
    for e in B:
        cid = to_id(e["champ"])
        if not cid or cid in gone or (e["b1"] < 2 and e["presence"] < 0.25): continue
        up, ur, uc = best(U, cid); op, orl, oc = best(O, cid); risk, ev = ban_risk(O, team_name(us), U, cid)
        # value of taking it B1 for us: pro first-pick priority x our comfort, plus a bit for denying their player
        prio = min(1.0, e["b1_when_avail"] / 0.25)
        val = prio * (0.5 + 0.5 * pro_power(cid) / 100) * comfort_factor(uc) + 0.3 * comfort_factor(oc) * prio
        # would red take it at R1/R2 if we don't B1 it? Their player good on it -> they pick it; a strong pro B1 they can half-play -> maybe
        surv = ("no: their player is good on it" if oc >= 0.6 else
                "maybe: pro-strong and playable for them" if (oc >= 0.45 and e["b1_when_avail"] >= 0.15) or oc >= 0.5 else
                "likely: nobody on their team plays it well")
        rows.append(dict(cid=cid, e=e, up=up, ur=ur, uc=uc, op=op, orl=orl, oc=oc, risk=risk, ev=ev, val=val, surv=surv))
    # shared comfort picks pros don't B1 (e.g. Yunara vs Chuds' Sæþór): in our league these are real B1 candidates
    have = {r["cid"] for r in rows}
    for pl in U.get("players", {}).values():
        for en in pl.get("pool", []):
            cid = en["champ"]
            if cid in have or cid in gone or en["comfort"] < 0.7: continue
            op, orl, oc = best(O, cid)
            if oc < 0.6: continue
            up, ur, uc = best(U, cid); risk, ev = ban_risk(O, team_name(us), U, cid)
            e0 = next((x for x in B if to_id(x["champ"]) == cid), {"b1": 0, "b1_when_avail": 0, "b1_wins": 0})
            val = 0.5 * comfort_factor(uc) + 0.4 * comfort_factor(oc)
            rows.append(dict(cid=cid, e=e0, up=up, ur=ur, uc=uc, op=op, orl=orl, oc=oc, risk=risk, ev=ev + ["shared comfort, not a pro B1"], val=val,
                             surv="no: their player is good on it")); have.add(cid)
    rows.sort(key=lambda r: -r["val"])
    print(f"# B1 plan: {us} vs {opp}, game {g('--game', 1)} (pro B1 list for game {game if game != '4' else '4-5'})" + (f", gone: {', '.join(display(c) for c in sorted(gone))}" if gone else ""))
    print("| Champion | Pro B1 (when available) | Pro power | Our player (comfort) | Their player (comfort) | Ban risk vs us | Survives to B2? | B1 value for us |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows[:n]:
        e = r["e"]
        print(f"| {display(r['cid'])} | {e['b1']} ({round(100 * e['b1_when_avail'])}%) | {pro_power(r['cid'])} | "
              f"{(r['up'] + ' ' + r['ur'] + ' ' + format(r['uc'], '.2f')) if r['up'] else '-'} | {(r['op'] + ' ' + r['orl'] + ' ' + format(r['oc'], '.2f')) if r['op'] else '-'} | "
              f"{'high' if r['risk'] >= 0.6 else 'medium' if r['risk'] >= 0.3 else 'low'} ({'; '.join(r['ev']) or 'no history'}) | {r['surv']} | {r['val']:.2f} |")
    ours = [r for r in rows if r["uc"] >= 0.5]
    likely = [r for r in ours if r["risk"] >= 0.6]; left = [r for r in ours if r["risk"] < 0.6]
    print()
    if likely: print("Likely banned before B1: " + ", ".join(display(r["cid"]) for r in likely))
    deny = [r for r in rows if r["oc"] >= 0.6 and r["uc"] < 0.5][:4]
    if deny: print("Their comfortable B1 champions we do not play: " + ", ".join(f"{display(r['cid'])} ({r['op']} {r['oc']:.2f})" for r in deny))

if __name__ == "__main__":
    main()
