"""Append to a live draft narration log and re-render its HTML page (tools/narration_page.py). Input is JSON on stdin,
so reasoning text with quotes or apostrophes never touches shell quoting. Use a quoted heredoc:

  python3 tools/narration_log.py drafts/live/mi_0Yybw_log.json <<'EOF'
  {"op": "act", "game": 2, "step": "Ban 1", "side": "blue", "kind": "ban", "champ": "Nocturne", "team": "T1", "read": "..."}
  EOF

ops:
  act      add one action: step (Ban 1..10, B1..B5, R1..R5), side, kind (ban|pick), champ (display name), team,
           why (our reasoning, for our actions) or read (what an enemy action tells us)
  fix      replace fields of an existing action: {"op":"fix","game":2,"step":"B3", ...fields}
  game     add or replace a game: {"op":"game","game":2,"us_side":"red","status":"live","plan":[...]}
  set      set game fields: {"op":"set","game":2,"status":"done","roles":{"blue":[...],"red":[...]},"review":{"objective":"..","players":"..","lines":[..]}}
Several ops at once: pass a JSON list. The HTML goes next to the log as <series>_narration.html.
"""
import json, sys, os, subprocess, datetime
L = sys.argv[1]
d = json.load(open(L, encoding="utf-8"))
ops = json.load(sys.stdin)
if isinstance(ops, dict): ops = [ops]
def game(n):
    for g in d["games"]:
        if g["game"] == n: return g
    raise SystemExit(f"no game {n} in log (add it with op=game)")
for o in ops:
    op = o.pop("op")
    if op == "game":
        n = o["game"]; d["games"] = [g for g in d["games"] if g["game"] != n] + [{"actions": [], **o}]; d["games"].sort(key=lambda g: g["game"])
    elif op == "act":
        g = game(o.pop("game")); g.setdefault("actions", []).append({"why": "", "read": "", **o})
    elif op == "fix":
        g = game(o.pop("game")); step = o.pop("step")
        for a in g["actions"]:
            if a["step"] == step: a.update(o)
    elif op == "set":
        g = game(o.pop("game")); g.update(o)
    else:
        raise SystemExit("unknown op " + op)
d["updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
json.dump(d, open(L, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
out = L.replace("_log.json", "_narration.html")
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "narration_page.py"), L, out], check=True)
