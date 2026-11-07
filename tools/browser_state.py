"""Convert D.state() output (from drafter_bot.js) into a draft state JSON.
Usage: python3 tools/browser_state.py browser.json --us <us> --them <them> --side blue [--fearless used.json] > state.json
used.json: {"ours":[...], "theirs":[...]} (drafter ids or names) from earlier games of the series.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from knowledge import to_id
from common import ORDER

def convert(b, us, them, side, fearless=None):
    q = {(s, k): list(b[s]["bans" if k == "ban" else "picks"]) for s in ("blue", "red") for k in ("ban", "pick")}
    actions = []
    for s, k in ORDER:
        lst = q[(s, k)]
        if not lst: break
        v = lst.pop(0)
        if v is None: break                      # slot not reached yet
        actions.append({"side": s, "kind": k, "champ": None if v == "None" else to_id(v)})
    f = fearless or {}
    ours = [to_id(x) for x in f.get("ours", [])]; theirs = [to_id(x) for x in f.get("theirs", [])]
    return {"us": us, "them": them, "our_side": side, "actions": actions,
            "fearless_unavailable": sorted(set(ours + theirs) | {to_id(x) for x in b.get("unavailable", [])} - {a["champ"] for a in actions}),
            "fearless_ours": ours, "fearless_theirs": theirs, "phase": b.get("phase")}

if __name__ == "__main__":
    a = sys.argv
    g = lambda n, d=None: a[a.index(n) + 1] if n in a else d
    b = json.load(open(a[1], encoding="utf-8"))
    f = json.load(open(g("--fearless"), encoding="utf-8")) if g("--fearless") else None
    print(json.dumps(convert(b, g("--us"), g("--them"), g("--side", "blue"), f), ensure_ascii=False))
