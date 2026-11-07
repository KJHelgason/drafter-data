#!/usr/bin/env python3
"""Mechanical champion facts from ability data -> knowledge/champion_facts.json and .md.

Sources (pulled through the browser, since the container can't reach them):
  pro_data/raw/abilities/ddragon_16.22.1.json  current Riot tooltips (Data Dragon championFull), all 173 champions
  pro_data/raw/abilities/meraki_25.15.json     Meraki Analytics: Riot subclass, attribute ratings, targeting, AoE flags
                                                (last updated patch 25.15, no Locke or Zaahen)

Only facts the ability text states: CC types, damage types, true and %HP damage, dashes, ally shields/heals,
anti-heal, stealth, unstoppable. The judgment layer (engage, peel, anti-tank and so on) lives in
knowledge/champion_profiles.json and is reviewed by hand.

Run: python3 tools/build_champion_facts.py
"""
import json, re, os, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "pro_data", "raw", "abilities")
DD = json.load(open(os.path.join(RAW, "ddragon_16.22.1.json")))
MK = json.load(open(os.path.join(RAW, "meraki_25.15.json")))
TAGS = json.load(open(os.path.join(ROOT, "knowledge", "champion_tags.json")))
SLOTS = ["Q", "W", "E", "R"]

# status words -> normalized CC type. hard = stops the target acting.
CC_MAP = [
    (r"knock(ed|ing|s)? ?up|airborne", "knockup"),
    (r"knock(ed|ing|s)? ?(back|away)|push", "knockback"),
    (r"suppress", "suppress"),
    (r"stun", "stun"),
    (r"charm", "charm"),
    (r"fear|flee", "fear"),
    (r"taunt", "taunt"),
    (r"asleep|sleep", "sleep"),
    (r"polymorph", "polymorph"),
    (r"pull|drag", "pull"),
    (r"berserk", "berserk"),
    (r"root|immobiliz|snare", "root"),
    (r"silenc", "silence"),
    (r"ground", "ground"),
    (r"blind|nearsight", "blind"),
    (r"disarm", "disarm"),
    (r"slow", "slow"),
]
HARD = {"knockup", "knockback", "suppress", "stun", "charm", "fear", "taunt", "sleep", "polymorph", "pull", "berserk"}
SEMI = {"root"}  # stops movement, not casting
SOFT = {"slow", "silence", "ground", "blind", "disarm"}

DASH_RE = re.compile(r"\b(dash|dashes|dashing|leap|leaps|lunge|lunges|blink|blinks|teleport|teleports|jumps?|vaults?|charges? (forward|toward|to)|rolls|tumbles|flips|hops?|pounce)", re.I)
PCT_RE = re.compile(r"(max(imum)?|missing|current|bonus)[ -]health (physical |magic |true )?damage|% of (the )?(target'?s?|their|enemy'?s?)? ?(max(imum)?|missing|current) health|(max(imum)?|missing|current) health (as )?(physical |magic |true )?damage|based on (the )?(target'?s?|their|enemy'?s?)? ?(max(imum)?|missing|current) health|increased (based on|by) (enemy |target'?s? )?missing health|(max|maximum|missing|current) health", re.I)
ANTIHEAL_RE = re.compile(r"grievous wounds|reduc\w* (their |the )?heal", re.I)
STEALTH_RE = re.compile(r"invisib|camouflag|keywordStealth", re.I)
UNSTOP_RE = re.compile(r"unstoppable|immune to crowd control|cleanse|removes? (all )?(crowd control|immobiliz|disables)", re.I)
UNTARG_RE = re.compile(r"untargetable|stasis|invulnerable|cannot die|revive|resurrect", re.I)
SHRED_RE = re.compile(r"(reduc|shred)\w* (the target'?s? |their |enemy )?(armor|magic resist)|armor penetration|magic penetration|ignor\w* .{0,20}(armor|magic resist)", re.I)
ANTIDASH_RE = re.compile(r"stops? enemy dashes|interrupt\w* (enemy )?dash|grounded", re.I)
EXECUTE_RE = re.compile(r"execut", re.I)


def clean(t):
    return re.sub(r"\s+", " ", t or "")


def cc_types(text):
    found = []
    for mt in re.finditer(r"<status>(.*?)</status>", text, re.I):
        s = mt.group(1).lower()
        after = re.sub(r"<[^>]+>", "", text[mt.end():mt.end() + 80]).lower()
        if re.fullmatch(r"knock(s|ing|ed)?", s.strip()):
            s = s + " " + (after.split(".")[0])
            if re.search(r"\bup\b|airborne", s): found.append("knockup"); continue
            if re.search(r"\b(back|away|aside)\b", s): found.append("knockback"); continue
            if re.search(r"toward|direction|in\b|into", s): found.append("pull"); continue
            found.append("knockback"); continue
        for pat, name in CC_MAP:
            if re.search(pat, s):
                found.append(name)
                break
    # tooltip text without status tags (older champions, passives)
    plain = re.sub(r"<[^>]+>", "", text).lower()
    for pat, name in CC_MAP:
        if name in ("slow", "ground", "blind"):
            continue
        if re.search(r"\b(" + pat + r")", plain) and name not in found:
            if name == "knockback" and "push" in plain and "knock" not in plain:
                continue
            if name == "pull" and not re.search(r"pull\w* (the |all |nearby )?(enemies|target|champion|them|enemy)|drag", plain):
                continue
            found.append(name)
    return list(dict.fromkeys(found))


HP_RE = re.compile(r"(max(imum)?|missing|current|bonus) health", re.I)


def pct_hp(text):
    """Kinds of %HP damage against the target ('max', 'current', 'missing'): a health phrase inside a damage tag,
    or right next to 'damage' in the same clause. Empty set = none."""
    kinds = set()
    def add(t):
        for k, pat in (("max", r"max(imum)?|bonus"), ("current", r"current"), ("missing", r"missing")):
            if re.search(r"(" + pat + r") health", t, re.I): kinds.add(k)
    for m in re.finditer(r"<(physicalDamage|magicDamage|trueDamage)>(.*?)</\1>", text):
        if HP_RE.search(m.group(2)): add(m.group(2))
    plain = re.sub(r"<[^>]+>", "", text)
    for clause in re.split(r"[.;]", plain):
        if re.search(r"shield|heal|restor|gains?|cost", clause, re.I) and not re.search(r"damage", clause, re.I):
            continue
        if re.search(r"damage.{0,50}(of |the |their |target'?s? |enemy'?s? )(max(imum)?|missing|current) health|(target'?s?|enemy'?s?|their) (max(imum)?|missing|current) health.{0,40}damage|based on (the )?(target'?s?|enemy'?s?|their) ?(max(imum)?|missing|current) health|increased (based on|by) (the )?(enemy|target'?s?|their)? ?missing health", clause, re.I):
            add(clause)
    return sorted(kinds)


def dmg_types(text):
    out = []
    if "<physicalDamage>" in text: out.append("physical")
    if "<magicDamage>" in text: out.append("magic")
    if "<trueDamage>" in text or re.search(r"true damage", text, re.I): out.append("true")
    return out


def meraki_slot(name, slot):
    m = MK.get(name)
    if not m: return []
    return m["ab"].get(slot, [])


def is_aoe(mk):
    for s in mk:
        se = str(s.get("se") or "").lower(); tg = str(s.get("tg") or "").lower()
        if "aoe" in se or "area" in se or "proximity" in tg:
            return True
    return False


def is_pointclick(mk):
    return any(str(s.get("tg") or "").lower().startswith("unit") for s in mk)


def affects_allies(mk, text):
    if any("allies" in str(s.get("af") or "").lower() for s in mk):
        return True
    return bool(re.search(r"\b(an? )?all(y|ies)\b|allied champion", re.sub(r"<[^>]+>", "", text), re.I))


def ability_facts(name, slot, tooltip, desc):
    text = clean(tooltip) + " " + clean(desc)
    plain = re.sub(r"<[^>]+>", "", text)
    mk = meraki_slot(name, slot)
    allies = affects_allies(mk, text)
    f = {
        "slot": slot,
        "cc": cc_types(text),
        "damage": dmg_types(text),
        "aoe": is_aoe(mk),
        "point_click": is_pointclick(mk),
        "dash": bool(DASH_RE.search(plain)) and slot != "P",
        "pct_hp_kinds": pct_hp(text),
        "ally_shield": "<shield>" in text and allies or bool(re.search(r"shield\w* (an? )?all(y|ies)|allied champion.{0,40}shield", plain, re.I)),
        "ally_heal": "<healing>" in text and allies and bool(re.search(r"heal\w* .{0,30}all(y|ies)|all(y|ies).{0,40}heal", plain, re.I)),
        "ally_speed": "<speed>" in text and allies and bool(re.search(r"all(y|ies).{0,60}move speed|move speed.{0,60}all(y|ies)", plain, re.I)),
        "self_heal": "<healing>" in text or bool(re.search(r"life ?steal|omnivamp|heals? (himself|herself|itself|themsel)", plain, re.I)),
        "self_shield": "<shield>" in text and not allies,
        "anti_heal": bool(ANTIHEAL_RE.search(plain)),
        "stealth": bool(STEALTH_RE.search(text)),
        "unstoppable": bool(UNSTOP_RE.search(plain)),
        "untargetable": bool(UNTARG_RE.search(plain)),
        "shred": bool(SHRED_RE.search(plain)),
        "anti_dash": bool(ANTIDASH_RE.search(plain)),
        "execute": bool(EXECUTE_RE.search(plain)),
        "on_hit": "OnHit" in text or bool(re.search(r"on-hit", plain, re.I)),
    }
    return f


# Auto-attack weight in the damage split, by Riot subclass (rough share of a champion's damage that comes from attacks).
AA_WEIGHT = {"MARKSMAN": 3.0, "SKIRMISHER": 1.6, "JUGGERNAUT": 1.0, "DIVER": 0.9, "FIGHTER": 1.0, "ASSASSIN": 0.6,
             "SPECIALIST": 0.8, "VANGUARD": 0.5, "WARDEN": 0.5, "TANK": 0.5, "MAGE": 0.25, "BURST": 0.2, "BATTLEMAGE": 0.3,
             "ARTILLERY": 0.1, "ENCHANTER": 0.2, "CATCHER": 0.3, "SUPPORT": 0.2}
# Hand overrides where the text-based split is known to mislead (auto-attacks that deal magic damage, hybrid builds).
SPLIT_NOTES = {
    "Kaisa": "hybrid: builds AD on-hit or AP burst", "Varus": "hybrid: lethality, on-hit or AP W builds",
    "Corki": "autos deal 80% magic damage", "KogMaw": "W on-hit adds magic %HP; AP build possible",
    "Kayle": "AP autos with magic waves; true damage with E", "Teemo": "AP on-hit",
    "Shyvana": "AD or AP build", "Ezreal": "AD, but W is magic", "Gwen": "AP melee, true damage in Q center",
    "Katarina": "AP or on-hit build", "Jax": "mixed, W and R magic", "Belveth": "AD, true damage on attacks after R",
    "TwistedFate": "AP with magic E/Q; AD build rare", "Akshan": "AD", "Zeri": "AD, Q scales AD and AP",
    "Galio": "AP tank", "Sylas": "AP diver", "Diana": "AP diver", "Ekko": "AP assassin", "Lillia": "AP %HP",
    "Vayne": "AD + true %HP (W)", "Fiora": "AD + true %HP (passive)", "Camille": "AD + true (Q2)",
    "Darius": "AD + true at 5 stacks / R", "Olaf": "AD + true (E)", "Gangplank": "AD + true (passive, E barrels ignore armor)",
    "Garen": "AD + true (R)", "Cho'Gath": "AP + true (R)", "Chogath": "AP + true (R)", "Pyke": "AD + true execute",
    "Zaahen": "AD", "Locke": "AP on-hit and missing health damage",
}


def damage_split(name, abil, passive):
    pts = collections.Counter()
    roles = (MK.get(name) or {}).get("roles") or []
    aa = max([AA_WEIGHT.get(r, 0.5) for r in roles] or [0.8])
    # autos: physical unless passive/on-hit says magic
    aa_type = "physical"
    if name in ("Corki",): aa_type = "magic"
    pts[aa_type] += aa
    for a in abil + [passive]:
        w = 1.5 if a["slot"] == "R" else (0.6 if a["slot"] == "P" else 1.0)
        types = a["damage"]
        if not types: continue
        for t in types:
            pts[t] += w / len(types)
    tot = sum(pts.values()) or 1
    return {k: round(pts.get(k, 0) / tot, 2) for k in ("physical", "magic", "true")}


def damage_class(split, name):
    p, m, t = split["physical"], split["magic"], split["true"]
    mk = MK.get(name) or {}
    low = (mk.get("ar") or {}).get("damage", 3) <= 1 and set(mk.get("roles") or []) & {"TANK", "SUPPORT", "ENCHANTER", "WARDEN", "VANGUARD", "CATCHER"}
    main = "AD" if p >= m else "AP"
    ratio = max(p, m) / max(1e-9, (p + m))
    if ratio < 0.62:
        cls = "mixed"
    else:
        cls = main
    if t >= 0.10:
        cls += "+true"
    if low:
        cls = "utility (" + cls + ")"
    return cls


def build():
    out = {}
    for name in sorted(DD):
        c = DD[name]
        abil = [ability_facts(name, SLOTS[i], s.get("t"), s.get("d")) for i, s in enumerate(c["s"][:4])]
        passive = ability_facts(name, "P", c["p"]["d"], "")
        allab = [passive] + abil
        cc = [(a["slot"], t, a["aoe"], a["point_click"]) for a in allab for t in a["cc"]]
        hard = [x for x in cc if x[1] in HARD]
        semi = [x for x in cc if x[1] in SEMI]
        soft = [x for x in cc if x[1] in SOFT]
        split = damage_split(name, abil, passive)
        mk = MK.get(name, {})
        f = {
            "name": TAGS.get(name, {}).get("name", name),
            "riot_tags": c["tags"],
            "subclass": [r for r in (mk.get("roles") or []) if r not in ("FIGHTER", "MAGE", "TANK", "SUPPORT", "MARKSMAN", "ASSASSIN")],
            "class": mk.get("roles") or [t.upper() for t in c["tags"]],
            "ratings": mk.get("ar") or {},
            "attack": "ranged" if c["range"] >= 300 else "melee",
            "attack_range": c["range"],
            "base_hp_18": round(c["hp"] + 17 * c["hppl"]),
            "cc": [{"slot": s, "type": t, "aoe": ao, "point_click": pc} for s, t, ao, pc in cc],
            "hard_cc": len({(s, t) for s, t, _, _ in hard}),
            "hard_cc_slots": sorted({s for s, *_ in hard}, key="PQWER".index),
            "aoe_hard_cc": sorted({s for s, t, ao, _ in hard if ao}, key="PQWER".index),
            "point_click_hard_cc": sorted({s for s, t, _, pc in hard if pc}, key="PQWER".index),
            "roots": sorted({s for s, *_ in semi}, key="PQWER".index),
            "soft_cc": sorted({t for _, t, _, _ in soft}),
            "dashes": [a["slot"] for a in abil if a["dash"]],
            "damage_split": split,
            "damage_class": damage_class(split, name),
            "damage_note": SPLIT_NOTES.get(name, ""),
            "true_damage": [a["slot"] for a in allab if "true" in a["damage"]],
            "pct_hp_damage": [a["slot"] for a in allab if a["pct_hp_kinds"]],
            "pct_hp_max_current": [a["slot"] for a in allab if set(a["pct_hp_kinds"]) & {"max", "current"}],
            "pct_hp_missing": [a["slot"] for a in allab if "missing" in a["pct_hp_kinds"]],
            "shred": [a["slot"] for a in allab if a["shred"]],
            "execute": [a["slot"] for a in allab if a["execute"]],
            "anti_heal": [a["slot"] for a in allab if a["anti_heal"]],
            "ally_shield": [a["slot"] for a in allab if a["ally_shield"]],
            "ally_heal": [a["slot"] for a in allab if a["ally_heal"]],
            "ally_speed": [a["slot"] for a in allab if a["ally_speed"]],
            "self_sustain": [a["slot"] for a in allab if a["self_heal"] or a["self_shield"]],
            "anti_dash": [a["slot"] for a in allab if a["anti_dash"]],
            "stealth": [a["slot"] for a in allab if a["stealth"]],
            "unstoppable": [a["slot"] for a in allab if a["unstoppable"]],
            "untargetable": [a["slot"] for a in allab if a["untargetable"]],
            "meraki_patch": mk.get("p"),
        }
        out[name] = f
    return out


def fmt_md(out):
    L = ["# Champion facts (generated)", "",
         "Mechanical facts from the ability text: Data Dragon 16.22.1 tooltips (all 173) + Meraki Analytics 25.15 (subclass, ratings, targeting; no Locke or Zaahen). "
         "Regenerate: `python3 tools/build_champion_facts.py`. The judgment layer is `champion_profiles.json`.", "",
         "Columns: hard CC slots (AoE ones in **bold**, point-and-click marked *), roots, soft CC, dashes, damage split P/M/T % and class, true and %HP damage slots, ally shield/heal/speed, anti-dash, stealth/untargetable.", "",
         "| Champion | Class | Hard CC | Roots | Soft | Dashes | P/M/T % | Dmg | True | %HP | Ally util | Other |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n, f in out.items():
        hc = []
        for s in f["hard_cc_slots"]:
            types = ",".join(sorted({c["type"] for c in f["cc"] if c["slot"] == s and c["type"] in HARD}))
            lab = f"{s} {types}"
            if s in f["aoe_hard_cc"]: lab = f"**{lab}**"
            if s in f["point_click_hard_cc"]: lab += "*"
            hc.append(lab)
        sp = f["damage_split"]
        util = " ".join(x for x in [
            ("shield " + "".join(f["ally_shield"])) if f["ally_shield"] else "",
            ("heal " + "".join(f["ally_heal"])) if f["ally_heal"] else "",
            ("speed " + "".join(f["ally_speed"])) if f["ally_speed"] else ""] if x)
        other = " ".join(x for x in [
            ("anti-dash " + "".join(f["anti_dash"])) if f["anti_dash"] else "",
            ("stealth " + "".join(f["stealth"])) if f["stealth"] else "",
            ("untarg " + "".join(f["untargetable"])) if f["untargetable"] else "",
            ("unstop " + "".join(f["unstoppable"])) if f["unstoppable"] else "",
            ("antiheal " + "".join(f["anti_heal"])) if f["anti_heal"] else "",
            ("shred " + "".join(f["shred"])) if f["shred"] else ""] if x)
        L.append(f"| {f['name']} | {'/'.join(c.title() for c in f['class'][:3])} | {'; '.join(hc)} | {''.join(f['roots'])} | {','.join(f['soft_cc'])} | {''.join(f['dashes'])} | "
                 f"{round(sp['physical']*100)}/{round(sp['magic']*100)}/{round(sp['true']*100)} | {f['damage_class']} | {''.join(f['true_damage'])} | {''.join(f['pct_hp_damage'])} | {util} | {other} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    out = build()
    json.dump(out, open(os.path.join(ROOT, "knowledge", "champion_facts.json"), "w"), indent=1, ensure_ascii=False)
    open(os.path.join(ROOT, "knowledge", "champion_facts.md"), "w").write(fmt_md(out))
    print(len(out), "champions -> knowledge/champion_facts.json/.md")
