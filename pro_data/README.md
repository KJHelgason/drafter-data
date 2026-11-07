# Pro data

Pro champion stats from gol.gg and pro games from Leaguepedia, plus the scripts that build the tables the tools read. Fetched 2026-11-06 and 2026-11-07 (Worlds 2026 Main Event in progress, 61 games played through 2026-11-05).

## Files
| File | What | Built by |
|---|---|---|
| `champion_pro_stats.json` | Per champion: pro power and tier, weighted presence, pick, ban and win rates, roles and role share, average pick round, blind-pick %, average ban turn. Also `by_role` (weighted top 25 per role) and `worlds_2026_main_event_by_role`. | `build_pro_stats.py` from the gol.gg slices in `raw/` |
| `lane_h2h.json` | For every role, each pair of champions that met in that lane: games, wins, the counter-pick split (games where one side was locked after the other), weighted `wg`/`wa` and recent-patch `rg`/`ra`. | `build_lane_h2h.py` |
| `soloq_h2h.json` | Master+ soloQ lane matchups, both views of each pair merged. | `build_soloq_h2h.py` |
| `b1_priority.json` | Per game of the series (1, 2, 3, 4-5, hard fearless): how often each champion is B1, B1 when still available, rotation-1 picks, phase-1 bans. Readable copy: `../knowledge/b1_priority.md`. | `build_b1.py` |
| `role_timing.json` | Per role and champion: games by game of the series, blind vs counter share and win rate each way (Wilson 95% ranges), phase-1 share, champions clearly gone before a blind lock (8+ cases, 1.5x, z >= 2). Readable copy: `../knowledge/role_timing.md`. | `build_role_timing.py` |
| `load_games.py` | Shared loader for the Leaguepedia games (see below). | |
| `decode_leaguepedia_export.py` | Turns `raw/_leaguepedia_export_2026-11-06.txt` into `raw/leaguepedia_picks_2026-11-06.json`. | |

## Raw sources (`raw/`)
- `tournament__*.json`, `patch__*.json`, `role__*.json`: one file per gol.gg slice (tournament, patch or role filter). Each holds `source_url`, the exact `post_params`, `fetched_at`, `games`, and per-champion rows: picks, bans, wins, losses, avg_ban_turn, avg_pick_round, blind_pick_pct, kda.
- `_golgg_export_2026-11-06.csv`: the compact export the slice files were split from.
- `leaguepedia_picks_2026-11-06.json` (from `_leaguepedia_export_2026-11-06.txt`): 671 recent games with full pick order, Worlds and top leagues, patches 26.16-26.20.
- `leaguepedia_2026_all_2026-11-06.json`: 11,061 rows, every Leaguepedia game from 2026-01-01 to 2026-11-06 in a Primary or Secondary tournament (2,938 Primary, 8,123 Secondary, 917 qualifier rows), with full pick and ban order. Fetched with `Special:CargoExport` (tables `PicksAndBansS7=PB, ScoreboardGames=SG, Tournaments=T`, joins `PB.GameId=SG.GameId, SG.OverviewPage=T.OverviewPage`, where `SG.DateTime_UTC >= '2026-01-01' AND T.TournamentLevel IN ('Primary','Secondary')`, `limit=500`, paged by offset).
- `leaguepedia_2025_all_2026-11-07.json`: 12,436 Leaguepedia games, 2025-01-11 to 2025-12-29, Primary + Secondary (2,812 / 9,624), same query and format as the 2026 file (some early-2025 Patch values are text like "25.S1.1").
- `soloq_matchups_2026-11-07.json`: lolalytics counters pages, Master+, all regions, ranked solo, last 30 days (16.21 + 16.22): 12,545 lane-vs-lane matchups (~9.15M lane games), every champion in each lane with 5%+ of its games. lolalytics only lists matchups with 100+ games.
- `abilities/`: Data Dragon 16.22.1 and Meraki ability data (read by `../tools/build_champion_facts.py`) and lolalytics 16.22 build pages per champion and role (damage split, damage taken, healing; read by `../tools/build_champion_profiles.py`).

## Weights (gol.gg stats)
gol.gg uses `16.x` patch names (Leaguepedia uses 26.x for the same patches). There are no pro games on 16.19, 16.21 or 16.22. Worlds 2026 Play-In and Main Event are both on 16.20.

| patch | weight | games (all leagues) |
|---|---|---|
| 16.20 | 1.0 | 112 |
| 16.18 | 0.7 | 378 |
| 16.17 | 0.45 | 567 |
| 16.16 | 0.25 | 604 |

| tournament | weight | games |
|---|---|---|
| Worlds 2026 Main Event | 1.0 | 61 |
| Worlds 2026 Play-In | 0.9 | 22 |
| LCK 2026 Season Playoffs | 0.8 | 41 |
| LPL 2026 Grand Finals | 0.8 | 55 |
| LPL 2026 Regional Finals | 0.8 | 12 |
| LEC 2026 Summer Playoffs | 0.7 | 31 |
| EMEA Masters 2026 Summer Main Event | 0.6 | 193 |
| Demacia Cup Global Invitational 2026 | 0.6 | 71 |
| LCS 2026 Summer Playoffs | 0.5 | 39 |
| CBLOL 2026 Split 2 Playoffs | 0.4 | 40 |
| EMEA Masters 2026 Summer LCQ | 0.4 | 47 |
| LCK CL 2026 Season Playoffs | 0.35 | 40 |
| VCS 2026 Finals Stage 2 | 0.35 | 19 |

Role slices: Worlds 2026 Main Event (weight 1.0), patch 16.20 (1.0), 16.18 (0.7), 16.17 (0.45), each for all 5 roles.

Formulas in `build_pro_stats.py` (all weights are dicts at the top of the script):
- Tournament blend: `pickrate_T = Σ w·picks / Σ w·games`, the same for bans. Patch blend: the same with the patch weights.
- `weighted_pickrate = 0.65·pickrate_T + 0.35·pickrate_P`; the ban rate uses the same mix. `weighted_presence = pickrate + banrate`.
- `weighted_games = 0.65·Σ_T w·picks + 0.35·Σ_P w·picks` (the effective sample size).
- `weighted_winrate = (weighted_wins + 10·0.5) / (weighted_games + 10)`: smoothed toward 50% with a 10-game prior. The unsmoothed value is stored too.
- `avg_pick_round`, `blind_pick_pct` (gol.gg "BP%", the share of picks made blind) and `avg_ban_turn` (1 = first ban) are averages weighted by w·picks (w·bans for ban turn).
- `roles` / `role_share`: weighted role-slice picks; roles under 10% share are dropped. Champions with no role-slice picks fall back to `../knowledge/champion_tags.json`.
- Tier on weighted presence: S ≥ 0.60, A ≥ 0.40, B ≥ 0.25, C ≥ 0.10, D below.

Patch slices cover every league gol.gg tracks, ERLs included, and overlap the tournament slices, which is why the two are blended rather than added.

## Leaguepedia games (`load_games.py`)
- `recent_rows()`: the 671-game recent window (`raw/leaguepedia_picks_*.json`). `build_b1.py` reads the same files directly, since B1 priority follows the current meta.
- `all_rows()`: recent + all 2026, deduplicated by GameId; rows without a winner or all 10 picks are dropped (10,959 games). Each row gets `_w` = patch weight (26.16+ 1.0, 26.11-15 0.7, 26.06-10 0.5, older 0.35) × level weight (Primary 1.0, Secondary 0.6, qualifiers ×0.8). `build_role_timing.py` uses it (raw counts).
- `matchup_rows()`: `all_rows()` plus the 2025 games at weight 0.2 × level (23,261 games). `build_lane_h2h.py` uses it.
- Leaguepedia patch floats lose a trailing zero (26.2 = 26.20); `patch_num` fixes that.

## Lane counters
`../tools/build_matchups_from_pro.py` lists, for every champion in a lane, the champions with 20+ pro games against it (15+ weighted) and a smoothed win rate of 0.57+, in `../knowledge/matchups_source.md`. `../tools/check_matchups.py` grades them against `lane_h2h.json` and writes `../knowledge/matchups.md`, `../knowledge/counter_records.json` (read by scout, pick_check and draft_review) and `../knowledge/matchups_check.md`.

SoloQ blending (`tools/knowledge.blend`, used by the grades): soloQ adds min(12, games / 250) pseudo pro games at 0.5 + 2 × (soloQ WR − 0.5), so rare pro matchups lean on soloQ and anything with a real pro sample stays pro-driven. Notes print both, e.g. "strong, pro 20-3, Master+ 50.8% in 2,762".

## Rebuild
After refreshing `raw/`:
`cd pro_data && python build_pro_stats.py && python build_soloq_h2h.py && python build_lane_h2h.py && python build_b1.py && python build_role_timing.py && cd .. && python tools/build_matchups_from_pro.py && python tools/check_matchups.py`

## Refreshing gol.gg
gol.gg blocks scripted access, so fetch from a normal browser tab: open `https://gol.gg/tournament/list/`, then run same-origin `fetch()` calls from the page console, at least 3 s apart.
1. Tournaments and patches: `https://gol.gg/tournament/list/` lists events; the patch list is the `<select id="patch">` on any champion-list page (values like `16.20.` with a trailing dot).
2. Champion list: `https://gol.gg/champion/list/season-S16/split-ALL/tournament-<URL-encoded name or ALL>/`. A GET returns all patches and roles. Patch and role filters are a POST of form-encoded fields to the same URL: `cbtournament=<name|ALL>&patch=<16.20.|ALL>&role=<ALL|TOP|JUNGLE|MID|ADC|SUPPORT>&leaguePost=true&side=ALL&draft=ALL` (`side=Blue|Red` and `draft=0|1` for Classic/Fearless also work).
3. Parse `table.playerslist`: Champion, Picks, Bans, PrioScore, Wins, Losses, Winrate, KDA, Avg BT, Avg RP, BP%, GT, CSM, DPM, GPM, CSD@15, GD@15, XPD@15. The champion id is the icon file name in `td img[src]`. Drop zero-pick, zero-ban rows.
4. Save one JSON per slice in the format of the existing `raw/` files (`games = Σpicks/10`, role slices `/2`, with the post params recorded), update the weight dicts in `build_pro_stats.py`, and run the rebuild above.

gol.gg icon names are the champion ids except `Wukong→MonkeyKing`, `RenataGlasc→Renata`, `Dr.Mundo→DrMundo`, `KhaZix→Khazix`, `LeBlanc→Leblanc`, `VelKoz→Velkoz`, `NunuWillump→Nunu`.
