#!/usr/bin/env python3
"""Champion profiles: facts (ability text) + measured soloQ damage profile -> per-champion data profile (damage split, CC, dashes).

Inputs
  knowledge/champion_facts.json                      tools/build_champion_facts.py (ability text, Riot subclass)
  pro_data/raw/abilities/lolalytics_16.22.json       lolalytics build page per champion and role, patch 16.22 soloQ:
                                                     physical / magic / true damage to champions, damage taken, healing
  knowledge/champion_tags.json                       existing hand tags (archetypes)

Output: knowledge/champion_profiles.json / .md

Data only: no weighted scores (the hand-tuned weights and overrides are not in this copy).
Run: python3 tools/build_champion_profiles.py
"""
import json, os, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K = os.path.join(ROOT, "knowledge")
FACTS = json.load(open(os.path.join(K, "champion_facts.json")))
TAGS = json.load(open(os.path.join(K, "champion_tags.json")))
LA_PATH = os.path.join(ROOT, "pro_data", "raw", "abilities", "lolalytics_16.22.json")
LA = json.load(open(LA_PATH)) if os.path.exists(LA_PATH) else []
LANE = {"top": "top", "jungle": "jungle", "middle": "mid", "bottom": "bot", "support": "support"}


def measured():
    """Per champion: game-weighted damage split, plus damage taken / healing relative to the role average."""
    by_role = collections.defaultdict(list)
    for r in LA:
        if r.get("Total Damage"): by_role[r["lane"]].append(r)
    avg = {l: {k: sum(x[k] for x in rows) / len(rows) for k in ("Damage Taken", "Healing", "Total Damage", "Deaths")}
           for l, rows in by_role.items()}
    out = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in LA:
        if not r.get("Total Damage"): continue
        g = r.get("games") or 1
        o = out[r["k"]]
        o["g"] += g
        tot = r["Total Damage"]
        for key, name in (("Physical Damage", "physical"), ("Magic Damage", "magic"), ("True Damage", "true")):
            o[name] += g * r[key] / tot
        a = avg[r["lane"]]
        o["taken_rel"] += g * r["Damage Taken"] / a["Damage Taken"]
        o["taken_per_death_rel"] += g * (r["Damage Taken"] / max(r["Deaths"], 1)) / (a["Damage Taken"] / max(a["Deaths"], 1))
        o["heal_rel"] += g * r["Healing"] / a["Healing"]
        o["dmg_rel"] += g * tot / a["Total Damage"]
        o.setdefault("roles", {})
        o["roles"][LANE[r["lane"]]] = r.get("games")
    res = {}
    for k, o in out.items():
        g = o["g"]
        res[k] = {"physical": round(o["physical"] / g, 3), "magic": round(o["magic"] / g, 3), "true": round(o["true"] / g, 3),
                  "taken_rel": round(o["taken_rel"] / g, 2), "taken_per_death_rel": round(o["taken_per_death_rel"] / g, 2),
                  "heal_rel": round(o["heal_rel"] / g, 2), "dmg_rel": round(o["dmg_rel"] / g, 2),
                  "soloq_games": int(g), "roles": dict(o["roles"])}
    return res


def damage_profile(m, facts):
    """Two axes: the type mix (from measured soloQ damage) and how much of it is true or %HP."""
    if not m:
        sp = facts["damage_split"]
        p, mg, t = sp["physical"], sp["magic"], sp["true"]
        src = "ability text (no soloQ sample)"
    else:
        p, mg, t = m["physical"], m["magic"], m["true"]
        src = "soloQ 16.22"
    main, other = ("AD", "AP") if p >= mg else ("AP", "AD")
    share = max(p, mg) / max(1e-9, p + mg)
    if share >= 0.8: mix = main
    elif share >= 0.6: mix = f"{main}-leaning mixed"
    else: mix = "mixed"
    label = mix + (" + true" if t >= 0.12 else "")
    return {"physical": round(p, 2), "magic": round(mg, 2), "true": round(t, 2), "label": label, "source": src}


def clamp(x, lo=0.0, hi=3.0):
    return max(lo, min(hi, x))


def build():
    M = measured()
    out = {}
    for name, f in FACTS.items():
        m = M.get(name)
        out[name] = {
            "name": f["name"],
            "class": f["class"],
            "damage": damage_profile(m, f),
            "anti_heal": bool(f["anti_heal"]),
            "soloq": m,
            "hard_cc_slots": f["hard_cc_slots"], "aoe_hard_cc": f["aoe_hard_cc"], "point_click_hard_cc": f["point_click_hard_cc"],
            "dashes": f["dashes"], "true_damage": f["true_damage"], "pct_hp_damage": f["pct_hp_damage"], "pct_hp_max_current": f["pct_hp_max_current"], "pct_hp_missing": f["pct_hp_missing"],
        }
    return out


def md(out):
    L = ["# Champion profiles (generated, data only)", "",
         "From `champion_facts.json` (ability text) and lolalytics soloQ 16.22 damage and durability. No weighted engage/peel scores. "
         "Rebuild: `python3 tools/build_champion_profiles.py`.", "",
         "| Champion | Damage (P/M/T %) | Hard CC | AoE hard CC | Point-click hard CC | Dashes | %HP damage | Anti-heal | Taken/death vs role |",
         "|---|---|---|---|---|---|---|---|---|"]
    for n, p in sorted(out.items(), key=lambda kv: kv[1]["name"]):
        d = p["damage"]; m = p["soloq"] or {}
        L.append(f"| {p['name']} | {d['label']} ({round(d['physical']*100)}/{round(d['magic']*100)}/{round(d['true']*100)}) | {len(p['hard_cc_slots'])} | {len(p['aoe_hard_cc'])} | "
                 f"{len(p['point_click_hard_cc'])} | {len(p['dashes'])} | {'yes' if p['pct_hp_damage'] else ''} | {'yes' if p['anti_heal'] else ''} | {m.get('taken_per_death_rel', '')} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = build()
    json.dump(out, open(os.path.join(K, "champion_profiles.json"), "w"), indent=1, ensure_ascii=False)
    open(os.path.join(K, "champion_profiles.md"), "w").write(md(out))
    print(len(out), "profiles ->", "knowledge/champion_profiles.json/.md", "| soloQ rows:", len(LA))
