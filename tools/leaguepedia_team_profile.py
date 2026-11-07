"""Build teams/<slug>/pro_profile.json (+ .md) for a real pro team from the Leaguepedia game exports in pro_data/raw,
in the same shape tools/pro_team_profile.py reads (the T1/KC files came from gol.gg; this is the Leaguepedia route).

  python3 tools/leaguepedia_team_profile.py geng "Gen.G" --players Top=Kiin,Jungle=Canyon,Mid=Chovy,Bot=Ruler,Support=Duro
  python3 tools/pro_team_profile.py geng

Leaguepedia rows carry the team's picks with roles but no player names, so a role pool = what the team played in that role.
That is the player's pool only when the roster was stable over the sample: pass --players and check the roster yourself.
Sample: every leaguepedia_*_all_*.json file in pro_data/raw (2025 + 2026 at the time of writing). Team1 = blue side.
Weighted games use exp(-age/1000 days) like the gol.gg profiles; weighted WR is smoothed toward the player's own WR (k = 5).
team_draft (bans, first-rotation picks, side record) uses the current year only, like the T1/KC files.
"""
import json, os, sys, glob, math, datetime
from collections import defaultdict, Counter
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROLES = ["Top", "Jungle", "Mid", "Bot", "Support"]

def main():
    a = sys.argv[1:]
    slug, team = a[0], a[1]
    players = dict(kv.split("=") for kv in a[a.index("--players") + 1].split(",")) if "--players" in a else {r: r for r in ROLES}
    today = datetime.date.fromisoformat(a[a.index("--today") + 1]) if "--today" in a else datetime.date.today()
    rows, seen = [], set()
    for f in sorted(glob.glob(os.path.join(ROOT, "pro_data", "raw", "leaguepedia_*_all_*.json"))):
        for x in json.load(open(f, encoding="utf-8"))["rows"]:
            if team in (x.get("Team1"), x.get("Team2")) and x["GameId"] not in seen:
                seen.add(x["GameId"]); rows.append(x)
    rows.sort(key=lambda x: x["Date"])
    year = max(x["Date"][:4] for x in rows)
    champ = {r: defaultdict(lambda: {"games": 0, "wins": 0, "wg": 0.0, "ww": 0.0, "last": ""}) for r in ROLES}
    tot = {r: [0, 0] for r in ROLES}
    td = {"games": 0, "blue": [0, 0], "red": [0, 0]}
    bans_made, bans_recv, first_rot, bans_p1 = Counter(), Counter(), Counter(), Counter()
    for x in rows:
        us = "Team1" if x["Team1"] == team else "Team2"; them = "Team2" if us == "Team1" else "Team1"
        win = (x["Winner"] == 1) == (us == "Team1")
        d = datetime.date.fromisoformat(x["Date"][:10]); w = math.exp(-(today - d).days / 1000)
        for i in range(1, 6):
            c, r = x.get(f"{us}Pick{i}"), x.get(f"{us}Role{i}")
            if not c or r not in champ: continue
            e = champ[r][c]; e["games"] += 1; e["wins"] += win; e["wg"] += w; e["ww"] += w * win; e["last"] = max(e["last"], x["Date"][:10])
            tot[r][0] += 1; tot[r][1] += win
        if x["Date"][:4] == year:
            td["games"] += 1; side = "blue" if us == "Team1" else "red"
            td[side][0] += win; td[side][1] += 1
            for i in range(1, 6):
                if x.get(f"{us}Ban{i}"): bans_made[x[f"{us}Ban{i}"]] += 1
                if x.get(f"{them}Ban{i}"): bans_recv[x[f"{them}Ban{i}"]] += 1
            for i in range(1, 4):
                if x.get(f"{us}Ban{i}"): bans_p1[x[f"{us}Ban{i}"]] += 1
                if x.get(f"{us}Pick{i}"): first_rot[x[f"{us}Pick{i}"]] += 1
    out = {"team": team, "source": f"Leaguepedia CargoExport rows in pro_data/raw ({rows[0]['Date'][:10]} to {rows[-1]['Date'][:10]}, {len(rows)} games)",
           "players": {}, "team_draft": {**td, "bans_made": bans_made.most_common(12), "bans_received": bans_recv.most_common(12),
                                         "bans_first_phase": bans_p1.most_common(12), "first_rotation_picks": first_rot.most_common(12)}}
    for r in ROLES:
        pwr = tot[r][1] / max(1, tot[r][0]); L = []
        for c, e in champ[r].items():
            wwr = (e["ww"] + 5 * pwr) / (e["wg"] + 5)
            L.append({"champion": c, "games": e["games"], "wins": e["wins"], "weighted_games": round(e["wg"], 1), "weighted_wr": round(wwr, 3), "last_played": e["last"]})
        L.sort(key=lambda z: -z["weighted_games"])
        yr = [x for x in rows if x["Date"][:4] == year]
        out["players"][r] = {"player": players.get(r, r), "champions": L, "career_games": tot[r][0], "career_wr": round(pwr, 3),
                             "games_2026": len(yr), "wr_2026": round(sum((x["Winner"] == 1) == (x["Team1"] == team) for x in yr) / max(1, len(yr)), 3)}
    d = os.path.join(ROOT, "teams", slug); os.makedirs(d, exist_ok=True)
    json.dump(out, open(os.path.join(d, "pro_profile.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    M = [f"# {team} pro profile", "", f"{out['source']}. Role pools = the team's picks in that role (roster stable over the sample).",
         "Weighted games use exp(-age/1000 days). WR is smoothed toward the player's own win rate.", ""]
    for r in ROLES:
        p = out["players"][r]
        M += [f"## {r}: {p['player']}", f"{p['career_games']} games in sample, {p['career_wr']:.1%} overall, {p['wr_2026']:.1%} in {year} ({p['games_2026']} games).", "",
              "| Champion | Games | Weighted | Weighted WR | Last played |", "|---|---|---|---|---|"]
        M += [f"| {c['champion']} | {c['games']} | {c['weighted_games']} | {c['weighted_wr']:.1%} | {c['last_played']} |" for c in p["champions"][:15]]
        M.append("")
    t = out["team_draft"]
    M += [f"## Team draft {year}", f"Blue {t['blue'][0]}-{t['blue'][1]-t['blue'][0]}, red {t['red'][0]}-{t['red'][1]-t['red'][0]} ({t['games']} games).",
          "- Bans made: " + ", ".join(f"{n} {k}" for n, k in t["bans_made"]),
          "- Phase-1 bans: " + ", ".join(f"{n} {k}" for n, k in t["bans_first_phase"]),
          "- Bans received: " + ", ".join(f"{n} {k}" for n, k in t["bans_received"]),
          "- First-rotation picks: " + ", ".join(f"{n} {k}" for n, k in t["first_rotation_picks"])]
    open(os.path.join(d, "pro_profile.md"), "w", encoding="utf-8").write("\n".join(M) + "\n")
    print("wrote", d, len(rows), "games", {r: len(out["players"][r]["champions"]) for r in ROLES})

if __name__ == "__main__":
    main()
