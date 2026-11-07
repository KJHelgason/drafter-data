"""Grade every counter listed in knowledge/matchups_source.md against pro head-to-heads, and write the graded knowledge/matchups.md.
  python3 tools/check_matchups.py            (after pro_data/build_lane_h2h.py)
knowledge/matchups_source.md is the hand-written list (edit that one). This script writes:
  knowledge/matchups.md           the same tables, each counter tagged with its pro record and grade; counters the pro data
                                  contradicts are moved out of the counters column into "Listed but not backed by pro data"
  knowledge/counter_records.json  {role: {target: {counter: {games, wins, as_counter_pick, as_counter_pick_wins, wr, grade, weight}}}}
  knowledge/matchups_check.md     the full report, worst first
Grades (pro games in that role, every 2026 Primary/Secondary game, weighted by patch and level (pro_data/load_games.py),
smoothed with 3 wins + 3 losses so small samples sit near 50%; game thresholds count weighted games):
  strong       >= 6 games and smoothed WR >= 0.56            weight 1.0
  favoured     smoothed WR >= 0.52                            weight 0.7
  untested     < 3 games: theory only (matchup knowledge, not proven) weight 0.5
  even         smoothed WR 0.45-0.52                          weight 0.25
  doubtful     3-4 games and smoothed WR < 0.45 (losing, small sample) weight 0.15
  contradicted >= 5 games and smoothed WR < 0.45 -> not a counter, weight 0
The weight is how much a listed counter counts as a lane edge before player comfort (see draft_review.py and scout.py).
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT
from knowledge import to_id, tags, display, pro, blend

SRC = os.path.join(ROOT, "knowledge", "matchups_source.md")
OUT = os.path.join(ROOT, "knowledge", "matchups.md")
HEADS = {"## top": "top", "## jungle": "jungle", "## mid": "mid", "## bot": "bot", "## adc": "bot", "## support": "support"}
H2H = json.load(open(os.path.join(ROOT, "pro_data", "lane_h2h.json"), encoding="utf-8"))

def record(role, x, y):
    """x's record vs y in that role: games, wins, games/wins where x was locked after y (x as the counter pick),
    then the weighted games and weighted x-wins (patch x level weight, load_games.py) that the grade uses."""
    for r in H2H.get(role, []):
        if {to_id(r["a"]), to_id(r["b"])} == {x, y}:
            wg = r.get("wg", r["games"]); wa = r.get("wa", r["a_wins"])
            if to_id(r["a"]) == x: return r["games"], r["a_wins"], r["a_after"], r["a_after_wins"], wg, wa
            return r["games"], r["games"] - r["a_wins"], r["b_after"], r["b_after_wins"], wg, wg - wa
    return 0, 0, 0, 0, 0, 0

def grade(g, w):
    s = (w + 3) / (g + 6)
    if g >= 5 and s < 0.45: return "contradicted", 0.0, s
    if g < 3: return "untested", 0.5, s
    if s < 0.45: return "doubtful", 0.15, s
    if g >= 6 and s >= 0.56: return "strong", 1.0, s
    if s >= 0.52: return "favoured", 0.7, s
    return "even", 0.25, s

def names(cell):
    out = []
    for raw in re.split(r",", cell):
        base = re.sub(r"\([^)]*\)", "", raw)
        for n in re.split(r"/| and |\+", base):
            n = n.strip().strip("*")
            cid = to_id(n) if n else None
            if cid and cid in tags(): out.append((cid, raw.strip()))
    return out

def main():
    if not os.path.exists(SRC):   # first run: the current hand-written file becomes the source
        import shutil; shutil.copy(OUT, SRC)
    role, L, recs, report = None, [], {}, []
    for line in open(SRC, encoding="utf-8").read().split("\n"):
        low = line.strip().lower()
        for h, r in HEADS.items():
            if low.startswith(h): role = r
        if low.startswith("## ") and not any(low.startswith(h) for h in HEADS): role = None
        cells = [c.strip() for c in line.strip().strip("|").split("|")] if line.startswith("|") else []
        if not role or len(cells) < 3 or line.startswith("|---") or cells[0] in ("Champion", "ADC"):
            L.append(line); continue
        rows = [to_id(n.strip()) for n in re.split(r"/", re.sub(r"\([^)]*\)", "", cells[0])) if to_id(n.strip()) in tags()]
        keep, drop = [], []
        for raw in [x.strip() for x in cells[1].split(",")]:
            ids = [c for c, _ in names(raw)]
            if not ids or not rows: keep.append(raw); continue
            tagsx = []; bad = True
            for c in ids:
                for t in rows:
                    # jungle table reads "row champion is advantaged vs listed": the row champion is the 'counter'
                    ctr, tgt = (t, c) if role == "jungle" else (c, t)
                    g, w, ga, wa, wg, ww = record(role, ctr, tgt)
                    bg, bw, sg, swr = blend(wg, ww, ctr, tgt, role)   # rare pro matchups lean on Master+ soloQ (knowledge.blend)
                    gr, wt, s = grade(bg, bw)
                    recs.setdefault(role, {}).setdefault(tgt, {})[ctr] = {"games": g, "wins": w, "as_counter_pick": ga, "as_counter_pick_wins": wa,
                                                                          "wr": round(w / g, 3) if g else None, "weighted_games": round(wg, 1),
                                                                          "weighted_wr": round(ww / wg, 3) if wg else None, "grade": gr, "weight": wt,
                                                                          "soloq_games": sg, "soloq_wr": round(swr, 4) if swr is not None else None}
                    report.append((s if g else 0.5, role, display(ctr), display(tgt), g, w, ga, wa, gr))
                    if gr != "contradicted": bad = False
                    rec = (f"{w}-{g - w}" if g else "no pro games") + (f", Master+ {swr:.1%}/{sg:,}" if sg else "") + f" {gr}" if (g or sg) else "untested"   # raw W-L shown; the grade uses the weighted record
                    tagsx.append(f"vs {display(t if role != 'jungle' else c)} {rec}" if len(rows) > 1 else rec)
            label = re.sub(r"\s*\(pro [^)]*\)", "", raw)
            (drop if bad else keep).append(f"{label} (pro {', '.join(dict.fromkeys(tagsx))})")
        why = cells[2] + (f" **Listed but not backed by pro data:** {', '.join(drop)}." if drop else "")
        L.append(f"| {cells[0]} | {', '.join(keep) or '-'} | {why} |")
    head = ("> Generated by `tools/check_matchups.py` from `matchups_source.md` (edit that file, then rerun). Every counter carries its pro lane record "
            "(counter's W-L vs that champion in the same role, 2025-26 pro and ERL games, plus Master+ soloQ lane win rates where shown; the grade weights recent patches and major leagues more, and soloQ counts as at most 12 pseudo pro games so it mainly fills in rare pro matchups) and a grade: **strong**, **favoured**, **untested** (theory only, "
            "under 3 pro games), **even**, **doubtful** (losing in a small sample). Counters the pro data contradicts are moved to \"Listed but not backed by pro data\" and do not count. "
            "A counter is a range, not a switch: weigh the grade, whether the player is comfortable on it, and what it adds to the team comp. "
            "In this league a counter the player is uncomfortable on is usually worse than their comfort pick.\n")
    i = next(k for k, l in enumerate(L) if l.startswith("# ")) + 1
    L.insert(i, "\n" + head)
    open(OUT, "w", encoding="utf-8").write("\n".join(L))
    json.dump(recs, open(os.path.join(ROOT, "knowledge", "counter_records.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    report.sort(key=lambda x: x[0])
    R = ["# Counter check: listed counters vs pro head-to-heads", "", "Worst first. Record = counter's W-L vs the target in that role; 'as counter pick' = games where the counter was locked after the target.", "",
         "| Role | Counter | Into | Pro W-L | As counter pick | Grade |", "|---|---|---|---|---|---|"]
    for s, role, c, t, g, w, ga, wa, gr in report:
        R.append(f"| {role} | {c} | {t} | {w}-{g - w} | {wa}-{ga - wa} | {gr} |")
    open(os.path.join(ROOT, "knowledge", "matchups_check.md"), "w", encoding="utf-8").write("\n".join(R) + "\n")
    from collections import Counter
    print(Counter(x[-1] for x in report))

if __name__ == "__main__":
    main()
