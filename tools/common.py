"""Shared helpers for the drafter data pipeline."""
import json, os, re, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROLES = ["top", "jungle", "mid", "bot", "support"]
# drafter.lol standard 20-step order: bans B R B R B R, picks B1 R1 R2 B2 B3 R3, bans R B R B, picks R4 B4 B5 R5
ORDER = [("blue","ban"),("red","ban"),("blue","ban"),("red","ban"),("blue","ban"),("red","ban"),
         ("blue","pick"),("red","pick"),("red","pick"),("blue","pick"),("blue","pick"),("red","pick"),
         ("red","ban"),("blue","ban"),("red","ban"),("blue","ban"),
         ("red","pick"),("blue","pick"),("blue","pick"),("red","pick")]

def load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)

def save(rel, obj):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

_SPECIAL = {"Wukong": "MonkeyKing", "Renata Glasc": "Renata", "Nunu & Willump": "Nunu",
            "LeBlanc": "Leblanc", "Kai'Sa": "Kaisa", "Kha'Zix": "Khazix", "Vel'Koz": "Velkoz",
            "Cho'Gath": "Chogath", "Kog'Maw": "KogMaw", "K'Sante": "KSante", "Bel'Veth": "Belveth",
            "Rek'Sai": "RekSai", "Dr. Mundo": "DrMundo"}

def champ_id(name):
    """Display name (Leaguepedia / gol.gg) -> drafter.lol id (e.g. 'Lee Sin' -> 'LeeSin')."""
    if not name or name == "None":
        return None
    if name in _SPECIAL:
        return _SPECIAL[name]
    return re.sub(r"[^A-Za-z0-9]", "", name)

def norm_player(n):
    """Normalise scoreboard names (zero-width chars, Greek Alpha in 'Αddi', case)."""
    n = (n or "").replace("⁠", "").replace("Α", "A").strip()
    return n.lower()

def recency_weight(date_str, today=None, half_life_days=45):
    """Exponential decay: a game half_life_days old counts half as much."""
    today = today or datetime.date.today()
    try:
        y, m, d = [int(x) for x in date_str.split("-")[:3]]
        age = (today - datetime.date(y, m, d)).days
    except Exception:
        age = 120
    return 0.5 ** (max(age, 0) / half_life_days)
