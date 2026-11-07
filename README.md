# drafter (data and tools)

Pro League of Legends draft data and the tools to read it, for drafting on drafter.lol (hard fearless).
The tools print data: pro records, comfort, counters, timing. They don't tell you what to pick; that part is yours.
Data as of 2026-11-07 (patch 26.22).

## Data
| Path | What |
|---|---|
| `pro_data/champion_pro_stats.json` | Pro power 0-100 per champion (presence incl. bans, win rate), tier, roles, blind-pick %, average pick round. From gol.gg. |
| `pro_data/lane_h2h.json` | Pro lane head-to-heads per role (2025-26 Leaguepedia games, weighted by patch and level). |
| `pro_data/soloq_h2h.json` | Master+ soloQ lane head-to-heads. |
| `pro_data/role_timing.json` | Per role: how often pros pick each champion blind vs as a counter, with win rates. |
| `pro_data/b1_priority.json` | Pro first-pick (B1) rates by game of the series. |
| `pro_data/raw/` | The Leaguepedia and gol.gg exports everything above is built from. `pro_data/README.md` lists the rebuild commands. |
| `knowledge/matchups_source.md`, `matchups.md`, `counter_records.json` | Lane counters taken from pro lane records only (20+ pro games in the lane, smoothed win rate 57%+), graded strong / favoured. |
| `knowledge/role_timing.md`, `b1_priority.md`, `matchups_check.md` | Readable versions of the timing, B1 and counter data. |
| `knowledge/champion_facts.*` | Per champion from the ability text: CC types, dashes, %HP and true damage, anti-heal. |
| `knowledge/champion_profiles.*` | Measured soloQ damage split and durability, plus the CC facts. |
| `knowledge/champion_tags.json` | Built from data: roles (pro picks), damage type (measured), range (base stats), blind safety 1-5 (how often pros blind-pick it), Riot classes. |
| `teams/whisky`, `teams/chuds`, `teams/sma_nibu`, `teams/fenrir` | Kia deild (Iceland) teams from public data: `team.json` (lineup, Riot IDs), `challengermode_roster.json`, `soloq.json/.md` (op.gg and u.gg research), `presence.json` (picks and bans aimed at each player in league games), and `profile.json/.md` (per player: comfort per champion from league games, soloQ and mastery; bans by and against the team). |
| `teams/t1`, `teams/kc`, `teams/geng` | Pro team profiles: each player's champion pool with a comfort score from weighted pro games and win rate. `stated_pools.json` is generated from comfort (blind = 0.80+, pickable = the rest). |
| `assets/ddragon/` | Champion icons and splash art (Riot Data Dragon). |

## Tools (`tools/`, Python 3)
- `scout.py <team> "Champ1,Champ2"` or `scout.py <team> --role mid`: everything on a champion for a team (pro power, the player's comfort, bans by and against, pro timing, counters).
- `pick_check.py <us> <role> "Champ" [--enemy ... --enemy-roles ... --ours ... --used ... --bans ... --opp <them>]`: the data for one pick on the current board, with a role board of the player's open champions.
- `draft_review.py --blue <slug> --red <slug> --blue-picks "A,B,C,D,E" --red-picks "..."` (add `--draft-only` to leave players out): a data score for a finished draft (comfort, pro power, graded lanes).
- `b1_plan.py <us> <them> --side blue|red --game N`: pro B1 champions against both rosters.
- `pro_lookup.py "Champ"` or `--role <role>`: pro power and tier.
- `comp_profile.py "A,B,C,D,E" [--vs "..."]`: a comp's damage mix and hard CC count.
- `drafter_bot.js`: paste into a drafter.lol tab to get `window.D` (join a seat, read the board, ban and pick, a timeout autopilot with your own fallback lists, role confirmation). The header comment explains its use.
- `browser_state.py`: turns a `D.state()` read into a draft state JSON.
- `narration_page.py` and `narration_log.py`: a live narration page for a series (a drafter.lol-style board plus a note for every action).
- `sim_referee.py`, `sim_viewer.py`: a board and a viewer for simulated drafts.
- Building data: `pro_team_profile.py` (team pools from gol.gg data), `leaguepedia_team_profile.py` (team pools from the Leaguepedia exports), `build_champion_facts.py`, `build_champion_profiles.py`, `build_champion_tags.py`, `build_matchups_from_pro.py` then `check_matchups.py`, `build_bot_roles.py`.

## Adding a pro team
`python tools/leaguepedia_team_profile.py <slug> "<Leaguepedia team name>" --players Top=A,Jungle=B,Mid=C,Bot=D,Support=E`, then `python tools/pro_team_profile.py <slug>`. A role pool is everything the team played in that role, so check that the roster was stable over the sample.
