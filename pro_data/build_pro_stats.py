#!/usr/bin/env python3
"""Rebuild champion_pro_stats.json from the gol.gg slices in raw/.

Usage:  python3 build_pro_stats.py            (from any cwd)

Tune the weights below and re-run. See README.md for how to refresh raw/.
"""
import glob
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "champion_pro_stats.json")
TAGS = os.path.join(HERE, "..", "knowledge", "champion_tags.json")

# ---------------------------------------------------------------- weights ---
# Tournament slices (all patches inside the event). Key = gol.gg tournament name.
TOURNAMENT_WEIGHTS = {
    "Worlds 2026 Main Event": 1.0,
    "Worlds 2026 Play-In": 0.9,
    "LCK 2026 Season Playoffs": 0.8,
    "LPL 2026 Grand Finals": 0.8,
    "LPL 2026 Regional Finals": 0.8,
    "LEC 2026 Summer Playoffs": 0.7,
    "EMEA Masters 2026 Summer Main Event": 0.6,
    "Demacia Cup Global Invitational 2026": 0.6,
    "LCS 2026 Summer Playoffs": 0.5,
    "CBLOL 2026 Split 2 Playoffs": 0.4,
    "EMEA Masters 2026 Summer LCQ": 0.4,
    "LCK CL 2026 Season Playoffs": 0.35,
    "VCS 2026 Finals Stage 2": 0.35,
}
# Patch slices (every league gol.gg tracks, all tournaments on that patch).
# gol.gg names patches 16.x; pro play skipped 16.19, and 16.21/16.22 have no pro games yet.
PATCH_WEIGHTS = {"16.20": 1.0, "16.18": 0.7, "16.17": 0.45, "16.16": 0.25}
DEFAULT_OLDER_PATCH_WEIGHT = 0.25
# Final rate = BLEND_T * tournament-blend + BLEND_P * patch-blend.
# (Patch slices overlap the tournament slices; the blend is a mixture, not a sum.)
BLEND_T = 0.65
BLEND_P = 0.35
# Role-share slices: weight per slice key (scope part of the slice key).
ROLE_WEIGHTS = {"Worlds 2026 Main Event": 1.0, "P16.20.": 1.0, "P16.18.": 0.7, "P16.17.": 0.45}
ROLE_MIN_SHARE = 0.10          # roles under this share are dropped from "roles" (kept in role_share)
PRIOR_GAMES = 10.0             # Bayesian winrate prior: (wins + k*0.5) / (picks + k)
TIERS = [("S", 0.60), ("A", 0.40), ("B", 0.25), ("C", 0.10), ("D", 0.0)]  # on weighted_presence
ROLE_NAMES = {"TOP": "top", "JUNGLE": "jungle", "MID": "mid", "ADC": "bot", "SUPPORT": "support"}
# -----------------------------------------------------------------------------


def load_slices():
    out = []
    for f in sorted(glob.glob(os.path.join(RAW, "*.json"))):
        with open(f) as fh:
            d = json.load(fh)
        d["_file"] = os.path.basename(f)
        out.append(d)
    return out


def blend(slices, weight_of):
    """Weighted sums over slices. Returns (W_games, per-champ sums, used list)."""
    W = 0.0
    acc = defaultdict(lambda: defaultdict(float))
    used = []
    for s in slices:
        w = weight_of(s)
        if not w:
            continue
        used.append({"slice": s["slice_key"], "weight": w, "games": s["games"]})
        W += w * s["games"]
        for r in s["rows"]:
            a = acc[r["champion_id"]]
            a["picks"] += w * r["picks"]
            a["bans"] += w * r["bans"]
            a["wins"] += w * r["wins"]
            # pick-order stats, weighted by (w * picks) / (w * bans)
            if r.get("avg_pick_round") is not None and r["picks"]:
                a["rp_num"] += w * r["picks"] * r["avg_pick_round"]
                a["rp_den"] += w * r["picks"]
            if r.get("blind_pick_pct") is not None and r["picks"]:
                a["bp_num"] += w * r["picks"] * r["blind_pick_pct"]
                a["bp_den"] += w * r["picks"]
            if r.get("avg_ban_turn") is not None and r["bans"]:
                a["bt_num"] += w * r["bans"] * r["avg_ban_turn"]
                a["bt_den"] += w * r["bans"]
            a["raw_picks"] += r["picks"]
            a["raw_bans"] += r["bans"]
            a["raw_wins"] += r["wins"]
    return W, acc, used


def main():
    slices = load_slices()
    tags = {}
    if os.path.exists(TAGS):
        with open(TAGS) as fh:
            tags = json.load(fh)

    t_sl = [s for s in slices if s["kind"] == "tournament"]
    p_sl = [s for s in slices if s["kind"] == "patch"]
    r_sl = [s for s in slices if s["kind"] == "role"]

    WT, accT, usedT = blend(t_sl, lambda s: TOURNAMENT_WEIGHTS.get(s["tournament"], 0.0))
    WP, accP, usedP = blend(p_sl, lambda s: PATCH_WEIGHTS.get(s["patch"], DEFAULT_OLDER_PATCH_WEIGHT))

    # role shares
    role_acc = defaultdict(lambda: defaultdict(float))
    used_roles = []
    for s in r_sl:
        scope = s["slice_key"].split(":")[1]
        w = ROLE_WEIGHTS.get(scope, 0.0)
        if not w:
            continue
        used_roles.append({"slice": s["slice_key"], "weight": w})
        for r in s["rows"]:
            role_acc[r["champion_id"]][ROLE_NAMES[s["role"]]] += w * r["picks"]

    worlds = next((s for s in t_sl if s["tournament"] == "Worlds 2026 Main Event"), None)
    worlds_rows = {r["champion_id"]: r for r in worlds["rows"]} if worlds else {}

    champs = {}
    for cid in sorted(set(accT) | set(accP)):
        a, b = accT.get(cid, {}), accP.get(cid, {})
        g = lambda d, k: d.get(k, 0.0)
        pr = BLEND_T * g(a, "picks") / WT + BLEND_P * g(b, "picks") / WP
        br = BLEND_T * g(a, "bans") / WT + BLEND_P * g(b, "bans") / WP
        wpicks = BLEND_T * g(a, "picks") + BLEND_P * g(b, "picks")
        wwins = BLEND_T * g(a, "wins") + BLEND_P * g(b, "wins")
        wr = (wwins + PRIOR_GAMES * 0.5) / (wpicks + PRIOR_GAMES)
        raw_wr = (wwins / wpicks) if wpicks else None

        def ratio(n, d):
            num = g(a, n) + g(b, n)
            den = g(a, d) + g(b, d)
            return round(num / den, 2) if den else None

        rs = role_acc.get(cid, {})
        tot = sum(rs.values())
        share = {k: round(v / tot, 3) for k, v in sorted(rs.items(), key=lambda x: -x[1])} if tot else {}
        roles = [k for k, v in share.items() if v >= ROLE_MIN_SHARE]
        role_src = "gol.gg role filter"
        if not roles:
            roles = list(tags.get(cid, {}).get("roles", []))
            share = {k: round(1 / len(roles), 3) for k in roles} if roles else {}
            role_src = "champion_tags.json fallback (no pro picks in role slices)"
        presence = pr + br
        tier = next(t for t, th in TIERS if presence >= th)
        wm = worlds_rows.get(cid)
        champs[cid] = {
            "name": tags.get(cid, {}).get("name", cid),
            "roles": roles,
            "role_share": share,
            "role_source": role_src,
            "tier": tier,
            "weighted_presence": round(presence, 4),
            "weighted_pickrate": round(pr, 4),
            "weighted_banrate": round(br, 4),
            "weighted_games": round(wpicks, 2),
            "weighted_winrate": round(wr, 4),
            "weighted_winrate_unsmoothed": round(raw_wr, 4) if raw_wr is not None else None,
            "avg_pick_round": ratio("rp_num", "rp_den"),
            "blind_pick_pct": ratio("bp_num", "bp_den"),
            "avg_ban_turn": ratio("bt_num", "bt_den"),
            "raw_totals": {
                "tournament_slices": {"picks": int(g(a, "raw_picks")), "bans": int(g(a, "raw_bans")),
                                      "wins": int(g(a, "raw_wins")), "games": sum(s["games"] for s in t_sl)},
                "patch_slices": {"picks": int(g(b, "raw_picks")), "bans": int(g(b, "raw_bans")),
                                 "wins": int(g(b, "raw_wins")), "games": sum(s["games"] for s in p_sl)},
            },
            "worlds_2026_main_event": None if not wm else {
                "picks": wm["picks"], "bans": wm["bans"], "wins": wm["wins"],
                "presence": round((wm["picks"] + wm["bans"]) / worlds["games"], 4),
                "winrate": round(wm["wins"] / wm["picks"], 4) if wm["picks"] else None,
                "avg_pick_round": wm["avg_pick_round"], "blind_pick_pct": wm["blind_pick_pct"],
                "avg_ban_turn": wm["avg_ban_turn"]},
        }

    # per-role rankings
    by_role = {}
    for role in ROLE_NAMES.values():
        rows = []
        for cid, c in champs.items():
            sh = c["role_share"].get(role, 0)
            if sh >= ROLE_MIN_SHARE:
                rows.append((cid, round(c["weighted_pickrate"] * sh, 4), c["weighted_presence"], c["weighted_winrate"]))
        rows.sort(key=lambda x: (-x[2], -x[1]))
        by_role[role] = [{"id": r[0], "role_pickrate": r[1], "presence": r[2], "winrate": r[3]} for r in rows[:25]]
    worlds_by_role = {}
    for s in r_sl:
        if s["tournament"] == "Worlds 2026 Main Event":
            worlds_by_role[ROLE_NAMES[s["role"]]] = [
                {"id": r["champion_id"], "picks": r["picks"], "wins": r["wins"]}
                for r in sorted(s["rows"], key=lambda r: -r["picks"])]

    out = {
        "meta": {
            "source": "gol.gg (see README.md)",
            "built_from": sorted(s["_file"] for s in slices),
            "fetched": sorted({s["fetch_date"] for s in slices}),
            "tournament_blend": {"weight": BLEND_T, "weighted_games": round(WT, 2), "slices": usedT},
            "patch_blend": {"weight": BLEND_P, "weighted_games": round(WP, 2), "slices": usedP},
            "role_slices": used_roles,
            "formulas": {
                "weighted_pickrate": "BLEND_T*sum(w*picks)/sum(w*games) [tournaments] + BLEND_P*same [patches]",
                "weighted_presence": "weighted_pickrate + weighted_banrate",
                "weighted_games": "BLEND_T*sum_T(w*picks) + BLEND_P*sum_P(w*picks)",
                "weighted_winrate": f"(weighted_wins + {PRIOR_GAMES}*0.5) / (weighted_games + {PRIOR_GAMES})",
                "tier": {t: th for t, th in TIERS},
            },
        },
        "champions": dict(sorted(champs.items(), key=lambda kv: -kv[1]["weighted_presence"])),
        "by_role": by_role,
        "worlds_2026_main_event_by_role": worlds_by_role,
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=1)
    print(f"wrote {OUT}: {len(champs)} champions")
    for i, (cid, c) in enumerate(list(out["champions"].items())[:25], 1):
        print(f"{i:2d} {cid:13s} {c['tier']} pres={c['weighted_presence']:.3f} pick={c['weighted_pickrate']:.3f} "
              f"ban={c['weighted_banrate']:.3f} wr={c['weighted_winrate']:.3f} roles={c['roles']}")


if __name__ == "__main__":
    main()
