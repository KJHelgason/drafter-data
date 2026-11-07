"""Pro meta lookup (gol.gg, recency weighted; Worlds 2026 main event when present).
  python3 tools/pro_lookup.py "Qiyana,Lee Sin,Orianna"    -> one line per champion
  python3 tools/pro_lookup.py --role jungle [--top 15]     -> best pro champions for a role by presence
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from knowledge import to_id, display
D = json.load(open(os.path.join(os.path.dirname(__file__), "..", "pro_data", "champion_pro_stats.json"), encoding="utf-8"))
C = D["champions"]

# Fearless game-number split from the Leaguepedia pick/ban rows (671 games, 13 events, patches 26.16-26.20)
_ROWS = None
_ORDER = [("Team1", 1), ("Team2", 1), ("Team2", 2), ("Team1", 2), ("Team1", 3), ("Team2", 3), ("Team2", 4), ("Team1", 4), ("Team1", 5), ("Team2", 5)]
def game_split(name):
    global _ROWS
    if _ROWS is None:
        try:
            import glob
            f = sorted(glob.glob(os.path.join(os.path.dirname(__file__), "..", "pro_data", "raw", "leaguepedia_picks_*.json")))[-1]
            _ROWS = json.load(open(f, encoding="utf-8"))["rows"]
        except Exception:
            _ROWS = []
    out = []
    for lab, keep in (("G1", lambda g: g == "1"), ("G2+", lambda g: g != "1")):
        sub = [r for r in _ROWS if keep(r["GameId"].rsplit("_", 1)[1])]
        if not sub: continue
        pk = bn = bl = 0
        for r in sub:
            if name in [r.get(f"{t}Ban{i}") for t in ("Team1", "Team2") for i in range(1, 6)]: bn += 1
            for idx, (t, i) in enumerate(_ORDER):
                if r.get(f"{t}Pick{i}") == name:
                    pk += 1; role = r.get(f"{t}Role{i}"); o = "Team2" if t == "Team1" else "Team1"
                    e = [k for k, (tt, ii) in enumerate(_ORDER) if tt == o and r.get(f"{tt}Role{ii}") == role]
                    if e and e[0] > idx: bl += 1
        out.append(f"{lab} {len(sub)}g: presence {(pk + bn) / len(sub):.0%} (pick {pk / len(sub):.0%}, ban {bn / len(sub):.0%}), blind {bl}/{pk}")
    return (" | fearless " + "; ".join(out)) if out else ""
def line(cid):
    c = C.get(cid)
    if not c: return f"{display(cid)}: no pro data (rare in pro play)"
    w = c.get("worlds_2026_main_event") or {}
    ws = f" | Worlds26 {w.get('picks',0)}P {w.get('bans',0)}B {w.get('wins',0)}W" if w else ""
    return (f"{c['name']}: tier {c.get('tier')} | roles {'/'.join(c.get('roles', []))} | presence {c['weighted_presence']:.0%} "
            f"(pick {c['weighted_pickrate']:.0%}, ban {c['weighted_banrate']:.0%}) | WR {c['weighted_winrate']:.1%} | "
            f"avg pick round {c.get('avg_pick_round')} | blind {c.get('blind_pick_pct')}%{ws}{game_split(c['name'])}")
a = sys.argv[1:]
if a and a[0] == "--role":
    role = a[1]; top = int(a[a.index("--top") + 1]) if "--top" in a else 15
    xs = sorted((c for k, c in C.items() if role in c.get("roles", [])), key=lambda c: -c["weighted_presence"])[:top]
    for c in xs: print(line(next(k for k, v in C.items() if v is c)))
else:
    for n in " ".join(a).split(","):
        if n.strip(): print(line(to_id(n.strip())))
