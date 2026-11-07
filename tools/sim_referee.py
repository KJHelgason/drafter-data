"""Referee for a simulated draft between two captain agents.
  python3 tools/sim_referee.py new <sim.json> --blue <slug> --red <slug> [--fearless-blue A,B] [--fearless-red C,D] [--game 1] [--series series.json]
  python3 tools/sim_referee.py board <sim.json>            -> board + whose turn (text)
  python3 tools/sim_referee.py state <sim.json> <side>     -> draft state JSON from that side's perspective
  python3 tools/sim_referee.py apply <sim.json> "<Champion>" "<reasoning>"
  python3 tools/sim_referee.py wait <sim.json> <side> [--timeout 900]   -> blocks until it's that side's turn
  python3 tools/sim_referee.py seq <sim.json>              -> [["blue","Jax"],...] for D.replay() on drafter.lol
  python3 tools/sim_referee.py log <sim.json>              -> markdown log of the draft with reasoning
Hard fearless: every champion picked in earlier games of the series (either team) is unavailable.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
from knowledge import to_id, display, tags
from common import ORDER

def load(p): return json.load(open(p, encoding="utf-8"))
def save(p, o): json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def unavailable(s):
    u = set(s["fearless_blue"]) | set(s["fearless_red"])
    u |= {a["champ"] for a in s["actions"] if a["champ"]}
    return u

def board(s):
    L = [f"Game {s['game']}: BLUE {s['blue']} vs RED {s['red']} (hard fearless)"]
    if s["fearless_blue"] or s["fearless_red"]:
        L.append("Fearless-locked (picked earlier in series): " + ", ".join(display(c) for c in sorted(set(s["fearless_blue"]) | set(s["fearless_red"]))))
    for side in ("blue", "red"):
        bans = [display(a["champ"]) if a["champ"] else "None" for a in s["actions"] if a["side"] == side and a["kind"] == "ban"]
        picks = [display(a["champ"]) for a in s["actions"] if a["side"] == side and a["kind"] == "pick"]
        L.append(f"{side.upper()} ({s[side]}) bans: {', '.join(bans) or '-'} | picks (in order): {', '.join(picks) or '-'}")
    i = len(s["actions"])
    if i >= len(ORDER):
        L.append("DRAFT COMPLETE")
    else:
        side, kind = ORDER[i]
        L.append(f"NEXT: step {i+1}/20 = {side.upper()} {kind.upper()} ({s[side]})")
        nxt = [f"{x[0][0].upper()}{x[1][0].upper()}" for x in ORDER[i:i+4]]
        L.append("Upcoming order: " + " ".join(nxt))
    return "\n".join(L)

def engine_state(s, side):
    other = "red" if side == "blue" else "blue"
    return {"us": s[side], "them": s[other], "our_side": side, "actions": [{"side": a["side"], "kind": a["kind"], "champ": a["champ"]} for a in s["actions"]],
            "fearless_unavailable": sorted(set(s["fearless_blue"]) | set(s["fearless_red"])),
            "fearless_ours": s[f"fearless_{side}"], "fearless_theirs": s[f"fearless_{other}"]}

if __name__ == "__main__":
    a = sys.argv; cmd, path = a[1], a[2]
    g = lambda n, d=None: a[a.index(n) + 1] if n in a else d
    if cmd == "new":
        fb = [to_id(x) for x in (g("--fearless-blue") or "").split(",") if x]
        fr = [to_id(x) for x in (g("--fearless-red") or "").split(",") if x]
        if g("--series"):   # JSON from D.series(): fearless = every pick of the games before --game, split by team name
            ser = json.load(open(g("--series"), encoding="utf-8")); n = int(g("--game", 1))
            prev = [x for x in ser["games"] if x["game"] < n]
            cur = next((x for x in ser["games"] if x["game"] == n), None)
            bname = cur["blue"] if cur else (prev[-1]["red"] if prev else None)   # sides usually swap; override with --fearless-* if wrong
            for x in prev:
                for team, picks in ((x["blue"], x["bluePicks"]), (x["red"], x["redPicks"])):
                    ids = [to_id(c) for c in picks if c and c != "None"]
                    (fb if team == bname else fr).extend(ids)
        save(path, {"blue": g("--blue"), "red": g("--red"), "game": int(g("--game", 1)), "fearless_blue": fb, "fearless_red": fr, "actions": []})
        print(board(load(path)))
    elif cmd == "board":
        print(board(load(path)))
    elif cmd == "state":
        print(json.dumps(engine_state(load(path), a[3]), ensure_ascii=False))
    elif cmd == "apply":
        s = load(path); i = len(s["actions"])
        if i >= len(ORDER): sys.exit("draft already complete")
        side, kind = ORDER[i]
        name = a[3]; why = a[4] if len(a) > 4 else ""
        cid = None if name.lower() in ("none", "skip") else to_id(name)
        if cid and cid not in tags(): sys.exit(f"unknown champion: {name}")
        if cid and cid in unavailable(s): sys.exit(f"{display(cid)} is unavailable (banned/picked/fearless)")
        s["actions"].append({"side": side, "kind": kind, "champ": cid, "reasoning": why})
        save(path, s); print(f"OK {side} {kind} {display(cid) if cid else 'None'}\n" + board(s))
    elif cmd == "wait":   # block until it's <side>'s turn or the draft is complete (polls every 2 s)
        import time
        side = a[3]; t0 = time.time(); limit = float(g("--timeout", 900))
        while True:
            s = load(path); i = len(s["actions"])
            if i >= len(ORDER): print("DRAFT COMPLETE\n" + board(s)); break
            if ORDER[i][0] == side: print("YOUR TURN\n" + board(s)); break
            if time.time() - t0 > limit: print("TIMEOUT waiting\n" + board(s)); break
            time.sleep(2)
    elif cmd == "seq":    # replay sequence for D.replay() in drafter_bot.js
        s = load(path); print(json.dumps([[x["side"], display(x["champ"]) if x["champ"] else "None"] for x in s["actions"]], ensure_ascii=False))
    elif cmd == "log":
        s = load(path)
        L = [f"# Simulated draft: game {s['game']}, {s['blue']} (blue) vs {s['red']} (red)", "", "| # | Side | Action | Champion | Reasoning |", "|---|---|---|---|---|"]
        for n, x in enumerate(s["actions"], 1):
            L.append(f"| {n} | {x['side']} ({s[x['side']]}) | {x['kind']} | {display(x['champ']) if x['champ'] else 'None'} | {x.get('reasoning','').replace('|','/')} |")
        print("\n".join(L))
