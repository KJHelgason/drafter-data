"""High-elo soloQ lane matchups -> soloq_h2h.json, a second source for counter grades where pro games are few.
Input  raw/soloq_matchups_*.json (newest file wins): {"source", "tier", "patch", "fetched_at",
       "matchups": {role: {Champ: {Opp: [games, wins]}}}} with drafter.lol ids (fetched on the PC, see README).
Output soloq_h2h.json: {"meta": {...}, role: {"A|B": [games, A wins]}} with A < B. Each pair is usually listed from both
       sides (A's page and B's page); the two views are averaged, which cancels lolalytics' +2.4% per-view offset (see BIAS).
Used by tools/knowledge.blend (counter_strength, check_matchups): soloQ counts as at most 12 pseudo pro games
(1 per 250 soloQ games) and its edge is doubled (SQ_AMP), so rare pro matchups lean on it and common ones stay pro-driven.
Run: python3 build_soloq_h2h.py && cd .. && python3 tools/check_matchups.py
"""
import json, glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
from knowledge import to_id
files = sorted(glob.glob(os.path.join(HERE, "raw", "soloq_matchups_*.json")))
if not files: sys.exit("no raw/soloq_matchups_*.json")
src = json.load(open(files[-1], encoding="utf-8"))
ROLE = {"top": "top", "jungle": "jungle", "mid": "mid", "middle": "mid", "bot": "bot", "bottom": "bot", "adc": "bot", "support": "support"}
out = {"meta": {k: src.get(k) for k in ("source", "tier", "patch", "fetched_at")} | {"file": os.path.basename(files[-1])}}
# lolalytics lists each pair from both champions' pages, and the two win rates sum to ~104.8% on average (sd 2%), not 100%:
# both views carry the same +2.4% offset. So a pair's win rate is the mean of A's view and (1 - B's view), which cancels it;
# a pair seen from one side only gets the offset subtracted.
BIAS = 0.024
views, bad = {}, set()
for r, champs in src["matchups"].items():
    role = ROLE.get(r.lower())
    if not role: continue
    for a, opps in champs.items():
        A = to_id(a)
        if not A: bad.add(a); continue
        for b, (g, w) in opps.items():
            B = to_id(b)
            if not B: bad.add(b); continue
            if A == B or not g: continue
            views.setdefault(role, {})[(A, B)] = (g, w / g)
for role, v in views.items():
    d = out.setdefault(role, {})
    for (A, B), (g, wr) in v.items():
        x, y = (A, B) if A < B else (B, A)
        k = f"{x}|{y}"
        if k in d: continue
        a_view = v.get((x, y)); b_view = v.get((y, x))
        if a_view and b_view:
            g2 = (a_view[0] + b_view[0]) / 2; p = (a_view[1] + 1 - b_view[1]) / 2
        elif a_view:
            g2, p = a_view[0], a_view[1] - BIAS
        else:
            g2, p = b_view[0], 1 - (b_view[1] - BIAS)
        d[k] = [round(g2), round(g2 * p)]
out["meta"]["pairs"] = {r: len(v) for r, v in out.items() if r != "meta"}
if bad: out["meta"]["unmapped"] = sorted(bad)
json.dump(out, open(os.path.join(HERE, "soloq_h2h.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(out["meta"])
