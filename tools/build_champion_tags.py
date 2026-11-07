"""Write knowledge/champion_tags.json from data only (no hand-written judgment).

  python3 tools/build_champion_tags.py

Per champion:
  roles        pro roles with 15%+ of its pro picks (pro_data/champion_pro_stats.json role_share), else its soloQ roles with
               15%+ of games (knowledge/champion_profiles.json, lolalytics), else the pro role list.
  flex         true when it has two or more roles.
  damage       AD / AP / mixed, from the measured soloQ damage split (champion_profiles.json), else Riot's damage class.
  range        melee / short (attack range up to 500) / long, from base stats (champion_facts.json).
  blind_safety 1-5 from how often pros pick it blind in its main role (pro_data/role_timing.json blind_pct):
               80%+ = 5, 65%+ = 4, 45%+ = 3, 30%+ = 2, under 30% = 1; 3 when it has under 30 pro games in that role.
  archetypes   Riot's class and subclass for the champion (champion_facts.json), lowercased. No comp identities.
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K = lambda *p: os.path.join(ROOT, *p)
FACTS = json.load(open(K("knowledge", "champion_facts.json"), encoding="utf-8"))
PROF = json.load(open(K("knowledge", "champion_profiles.json"), encoding="utf-8"))
PRO = json.load(open(K("pro_data", "champion_pro_stats.json"), encoding="utf-8"))["champions"]
RT = json.load(open(K("pro_data", "role_timing.json"), encoding="utf-8"))
ROLES = ["top", "jungle", "mid", "bot", "support"]
SOLOQ_ROLE = {"top": "top", "jungle": "jungle", "mid": "mid", "middle": "mid", "bot": "bot", "bottom": "bot", "adc": "bot", "support": "support"}
norm = lambda s: "".join(ch for ch in (s or "").lower() if ch.isalnum())
timing = {}
for role in ROLES:
    for r in RT.get(role, []):
        timing[(norm(r["champ"]), role)] = r

out = {}
for cid, f in sorted(FACTS.items()):
    name = f.get("name", cid)
    p = PRO.get(cid) or {}
    roles = [r for r, sh in sorted((p.get("role_share") or {}).items(), key=lambda kv: -kv[1]) if sh >= 0.15 and r in ROLES]
    if not roles:
        sq = ((PROF.get(cid) or {}).get("soloq") or {}).get("roles") or {}
        tot = sum(sq.values()) or 1
        roles = [SOLOQ_ROLE[r] for r, g in sorted(sq.items(), key=lambda kv: -kv[1]) if g / tot >= 0.15 and r in SOLOQ_ROLE]
    if not roles:
        roles = [r for r in (p.get("roles") or []) if r in ROLES]
    roles = list(dict.fromkeys(roles))
    dmg = ((PROF.get(cid) or {}).get("damage") or {}).get("label") or f.get("damage_class") or "mixed"
    if dmg not in ("AD", "AP"): dmg = "mixed"
    rng = "melee" if f.get("attack") == "melee" else ("short" if (f.get("attack_range") or 0) <= 500 else "long")
    t = timing.get((norm(name), roles[0])) if roles else None
    if not t or t.get("games", 0) < 30:
        bs = 3
    else:
        b = t.get("blind_pct", 0)
        bs = 5 if b >= 0.8 else 4 if b >= 0.65 else 3 if b >= 0.45 else 2 if b >= 0.3 else 1
    out[cid] = {"name": name, "roles": roles, "archetypes": sorted({c.lower() for c in (f.get("class") or [])}),
                "damage": dmg, "range": rng, "blind_safety": bs, "flex": len(roles) >= 2, "comp_vs_soloq": ""}
json.dump(out, open(K("knowledge", "champion_tags.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "champions -> knowledge/champion_tags.json")
