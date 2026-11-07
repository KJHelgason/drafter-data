#!/usr/bin/env python3
"""Team composition profile from champion profiles.

  python3 tools/comp_profile.py "Rumble,Vi,Orianna,Ezreal,Nautilus" [--vs "K'Sante,Lee Sin,Azir,Kalista,Lulu"]

comp(champs) returns the summed vector the draft tools use: damage mix (measured soloQ split), hard CC counts, anti-heal.
"""
import json, os, sys, functools
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from knowledge import to_id, display

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORES = ()   # data-only copy: no weighted engage/peel/... scores


@functools.lru_cache(None)
def profiles():
    p = os.path.join(ROOT, "knowledge", "champion_profiles.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def comp(champs):
    P = profiles()
    ids = [c if c in P else to_id(c) for c in champs if c]
    ids = [c for c in ids if c in P]
    v = {k: 0.0 for k in SCORES}
    phys = mag = tru = wsum = 0.0
    hard = aoe = pc = 0
    anti_heal = 0
    for c in ids:
        p = P[c]
        for k in SCORES: v[k] += p.get("scores", {}).get(k, 0)
        w = (p.get("soloq") or {}).get("dmg_rel", 1.0)
        d = p["damage"]
        phys += w * d["physical"]; mag += w * d["magic"]; tru += w * d["true"]; wsum += w
        hard += len(p["hard_cc_slots"]); aoe += len(p["aoe_hard_cc"]); pc += len(p["point_click_hard_cc"])
        anti_heal += 1 if p.get("anti_heal") else 0
    tot = (phys + mag + tru) or 1
    v.update({k: round(x, 1) for k, x in v.items()})
    v.update({"physical": round(phys / tot, 2), "magic": round(mag / tot, 2), "true": round(tru / tot, 2),
              "hard_cc": hard, "aoe_hard_cc": aoe, "point_click_hard_cc": pc, "anti_heal": anti_heal,
              "n": len(ids), "champs": ids})
    return v


def line(v):
    return (f"dmg P/M/T {round(v['physical']*100)}/{round(v['magic']*100)}/{round(v['true']*100)} | "
            f"hard CC {v['hard_cc']} (AoE {v['aoe_hard_cc']}, point-click {v['point_click_hard_cc']}) | anti-heal {v['anti_heal']}")


if __name__ == "__main__":
    a = sys.argv[1].split(",")
    print("OURS  ", ", ".join(display(c) for c in comp(a)["champs"]))
    print("      ", line(comp(a)))
    if "--vs" in sys.argv:
        b = sys.argv[sys.argv.index("--vs") + 1].split(",")
        print("THEIRS", ", ".join(display(c) for c in comp(b)["champs"]))
        print("      ", line(comp(b)))
