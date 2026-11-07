"""Writes the champion -> roles map that drafter_bot.js's autopilot uses so a timeout fallback never fills a role we already have.
Roles come from knowledge/champion_tags.json plus every team's pools (comfort >= 0.3; sim_only teams such as teams/pro_level are skipped), keyed by drafter.lol display name.
Run: python3 tools/build_bot_roles.py   (rewrites the block between the ROLEMAP markers in tools/drafter_bot.js)"""
import json, os, re, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLES = ["top", "jungle", "mid", "bot", "support"]
tags = json.load(open(os.path.join(ROOT, 'knowledge/champion_tags.json'), encoding='utf-8'))
m = {cid: set(t.get('roles', [])) for cid, t in tags.items()}
for f in glob.glob(os.path.join(ROOT, 'teams/*/profile.json')):
    tj = os.path.join(os.path.dirname(f), 'team.json')
    if os.path.exists(tj) and json.load(open(tj, encoding='utf-8')).get('sim_only'): continue   # hypothetical sim teams never feed real drafts
    for r, pool in (json.load(open(f, encoding='utf-8')).get('pools') or {}).items():
        if r in ROLES:
            for cid, v in pool.items():
                if (v if isinstance(v, (int, float)) else 0) >= 0.3: m.setdefault(cid, set()).add(r)
out = {tags.get(cid, {}).get('name', cid): [r for r in ROLES if r in rs] for cid, rs in sorted(m.items()) if rs}
js = 'D.auto.roleMap = ' + json.dumps(out, ensure_ascii=False, separators=(',', ':')) + ';'
p = os.path.join(ROOT, 'tools/drafter_bot.js'); src = open(p, encoding='utf-8').read()
src = re.sub(r'(// ROLEMAP-START\n).*?(\n\s*// ROLEMAP-END)', lambda k: k.group(1) + '  ' + js + k.group(2), src, flags=re.S)
open(p, 'w', encoding='utf-8').write(src); print(len(out), 'champions')
