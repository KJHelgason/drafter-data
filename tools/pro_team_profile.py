"""Turn a real pro team's pro_profile.json (gol.gg player pools + team draft habits) into the profile.json / team.json / profile.md
format the draft tools read (pick_check --opp, scout, draft_review, sim_viewer, sim_referee).

  python3 tools/pro_team_profile.py t1 [kc ...]

Input  teams/<slug>/pro_profile.json: {"team", "players": {Top|Jungle|Mid|Bot|Support: {"player", "champions": [{champion, games, wins,
       weighted_games, weighted_wr, last_played}]}}, "team_draft": {games, blue, red, bans_made, bans_received, first_rotation_picks}}
Output teams/<slug>/profile.json, profile.md, team.json (is_us false), stated_pools.json (a pro team's 'sheet': blind = comfort 0.80+, pickable = the rest). pro_profile.* are left untouched.

Comfort (0.40-1.00) for a pro player on a champion: 0.40 + 0.35 * min(1, weighted_games / 25) + 0.25 * clip((weighted_wr - 0.45) / 0.25),
so a pro's signature (25+ weighted games at 70%) is 1.0, a pocket pick with a few recent games sits near 0.55-0.70.
Champions with fewer than 3 career games are dropped, and so are off-role picks (not a pro/tag role of the champion) under 10 games. Sheet tier: 'blind' at comfort 0.80+, 'pickable' otherwise.
Draft value = comfort x max(pro power, 40) / 100, so a pro's signature on an off-meta champion still rates as a real pick.
Team habits: bans_by / bans_by_first_phase = bans made, bans_against = bans received per 10 games (the PRIORITY scale),
first_rotation_picks kept as draft_habits.
"""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from common import ROLES
from knowledge import pro_power, display, to_id

RMAP = {"Top": "top", "Jungle": "jungle", "Mid": "mid", "Bot": "bot", "Support": "support"}

def comfort(c):
    wg, wr = c.get("weighted_games", 0) or 0, c.get("weighted_wr", 0.5) or 0.5
    return round(0.40 + 0.35 * min(1.0, wg / 25) + 0.25 * max(0.0, min(1.0, (wr - 0.45) / 0.25)), 3)

TAGS = json.load(open(os.path.join(ROOT, "knowledge", "champion_tags.json"), encoding="utf-8"))
PRO = json.load(open(os.path.join(ROOT, "pro_data", "champion_pro_stats.json"), encoding="utf-8"))["champions"]
def role_tags(cid):
    return set(PRO.get(cid, {}).get("roles") or []) | set(TAGS.get(cid, {}).get("roles", []))

def handle(name):
    return name.split(" (")[0].strip()

def build(slug):
    src = json.load(open(os.path.join(ROOT, "teams", slug, "pro_profile.json"), encoding="utf-8"))
    td = src.get("team_draft", {}); games = td.get("games") or 1
    pools, players, roster = {r: {} for r in ROLES}, {}, {}
    for R, p in src["players"].items():
        r = RMAP[R]; name = handle(p["player"]).lower()
        rows = []
        for c in p["champions"]:
            cid = to_id(c["champion"])
            if not cid or c.get("games", 0) < 3: continue
            if r not in role_tags(cid) and c["games"] < 10: continue   # off-role pocket picks (Faker's Nocturne) stay out of the role pool
            cf = comfort(c)
            rows.append({"champ": cid, "name": display(cid), "comp_games": c["games"], "comp_wins": c["wins"], "comp_unknown": 0,
                         "comp_wgames": c.get("weighted_games"), "prev_split_games": 0, "prev_split_wins": 0, "soloq_games": 0, "soloq_wr": None,
                         "stated": "blind" if cf >= 0.80 else "pickable", "comfort": cf, "league_presence": 0,
                         "draft_value": round(cf * max(pro_power(cid), 40) / 100, 3), "last_played": c.get("last_played"),
                         "comp_vs_soloq": f"pro: {c['games']} games, {c['wins']} wins, weighted {c.get('weighted_games')} g at {c.get('weighted_wr', 0):.0%}"})
        rows.sort(key=lambda x: -x["comfort"])
        for x in rows: pools[r][x["champ"]] = x["comfort"]
        players[name] = {"role": r, "is_main": True, "riot_ids": [], "soloq_sources": [], "soloq_rank": "pro (LCK/LEC)",
                         "comp_pool": [x["name"] for x in rows[:12]], "soloq_pool": [], "soloq_only": [], "comp_only": [], "feared": [],
                         "league_presence_top": [], "pool": rows, "career": {k: p.get(k) for k in ("career_games", "career_wr", "games_2026", "wr_2026")}}
        roster[r] = {"main": name, "alternates": []}
    ids = lambda lst: {to_id(n): k for n, k in lst if to_id(n)}
    bans_made, bans_recv = ids(td.get("bans_made", [])), ids(td.get("bans_received", []))
    prof = {"team": src["team"], "slug": slug, "is_us": False, "region": "pro", "leagues": ["pro (gol.gg 2026)"], "roster": roster, "pools": pools,
            "players": players, "record": {"games": games, "wins": td.get("blue", [0, 0])[0] + td.get("red", [0, 0])[0],
                                            "blue": td.get("blue"), "red": td.get("red")},
            "bans_by": bans_made, "bans_by_first_phase": bans_made, "bans_recent": {}, "ban_last_date": {}, "ban_targets": {}, "bans_habit": [],
            "opponents_faced": games, "bans_against": {c: round(10 * k / games, 2) for c, k in bans_recv.items()}, "archetype_tendency": {},
            "draft_habits": {"first_rotation_picks": td.get("first_rotation_picks", [])},
            "note": f"Built by tools/pro_team_profile.py from teams/{slug}/pro_profile.json (real pro pools, gol.gg)."}
    out = os.path.join(ROOT, "teams", slug)
    sheet = {"_source": f"Generated by tools/pro_team_profile.py from pro_profile.json: blind = comfort 0.80+, pickable = the rest of the pro pool (3+ games)."}
    for r in ROLES:
        rows = players[roster[r]["main"]]["pool"]
        sheet[r] = {"player": roster[r]["main"], "blind": [x["champ"] for x in rows if x["stated"] == "blind"],
                    "pickable": [x["champ"] for x in rows if x["stated"] != "blind"], "counter": []}
    json.dump(sheet, open(os.path.join(out, "stated_pools.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(prof, open(os.path.join(out, "profile.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"name": src["team"], "slug": slug, "region": "pro", "leagues": ["pro"], "is_us": False, "profile_source": "tools/pro_team_profile.py", "comp_team_names": [src["team"]],
               "lineup": {r: [roster[r]["main"]] for r in ROLES}}, open(os.path.join(out, "team.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    L = [f"# {src['team']} profile (pro team, from pro_profile.json)", "",
         f"Real pro pools from {src.get('source', 'gol.gg')}. Comfort 0.40-1.00 from weighted games and weighted WR (see tools/pro_team_profile.py). Record 2026: blue {td.get('blue')}, red {td.get('red')} (games-wins).", ""]
    for r in ROLES:
        k = roster[r]["main"]; v = players[k]; car = v["career"]
        L += [f"## {r.upper()}: {k} ({car.get('career_games')} career games, {car.get('wr_2026', 0):.0%} in 2026)",
              "| Champ | Comfort | Pro G (W) | Weighted | Sheet | Pro power | Draft value | Last played |", "|---|---|---|---|---|---|---|---|"]
        for x in v["pool"][:15]:
            L.append(f"| {x['name']} | {x['comfort']} | {x['comp_games']} ({x['comp_wins']}) | {x['comp_wgames']} | {x['stated']} | {pro_power(x['champ']):.0f} | {x['draft_value']} | {x['last_played']} |")
        more = [x["name"] for x in v["pool"][15:]]
        if more: L.append(f"Also played: {', '.join(more)}")
        L.append("")
    L += ["## Team draft habits", "- Bans made: " + ", ".join(f"{n} {k}" for n, k in td.get("bans_made", [])),
          "- Bans received: " + ", ".join(f"{n} {k}" for n, k in td.get("bans_received", [])),
          "- First-rotation picks: " + ", ".join(f"{n} {k}" for n, k in td.get("first_rotation_picks", []))]
    open(os.path.join(out, "profile.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("wrote", out, {r: len(p) for r, p in pools.items()})

if __name__ == "__main__":
    for s in sys.argv[1:] or ["t1", "kc"]: build(s)
