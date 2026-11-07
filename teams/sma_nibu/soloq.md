# Smá Nibu solo-queue champion pools (fetched 2026-11-06, patch 16.22, S2026)

Source: op.gg champions tab ("Ranked" = Solo/Duo + Flex + 5s combined). S2026 is the default view, and S2025 comes from `?season_id=31`. Weighted pool = current season x1.0 + previous x0.5, with account-seasons under 5 games halved. Full tables are in `soloq.json`.

| Role | Player (Riot ID) | Solo rank | Top weighted pool (games over S26+S25, WR) |
|---|---|---|---|
| TOP | Boppa#Big | Master 1069 LP (50%, 1781 g) | Jax 555 53%, Jayce 500 52%, Gnar 522 51%, Sion 390 45%, Rumble 291 48% |
| JUNGLE | Sosa#qwer (captain) | Diamond 4 92 LP (50%) | Shaco 32 56%, Morgana 16 56%, Nidalee 11 73%, Shen 10 60%, Kha'Zix 9 67% |
| MID | Zarzator#EUW | Unranked (S25 Diamond 2) | Mel 11 55%, Bard 9 78%, Sylas 6 50%, Poppy 5, Nautilus 5 (soloQ = support) |
| MID (sub) | Legions1#EUW | Diamond 1 58 LP (54%) | Akali 16 69%, LeBlanc 17 53%, Yone 13 46%, Cassiopeia 10 40%, Syndra 11 46% |
| BOT | redside hater#EUWs (= "Kristut") | Master 290 LP (56%) | Ezreal 24 46%, Corki 23 61%, Lucian 8 50%, Yorick 10 50%, Smolder 15 66% |
| SUPPORT | Red Umbrella#EUW ("Kiddi") | Diamond 4 26 LP (55%, 20 g) | Lulu 29 58%, Corki 24 59%, Miss Fortune 12 58%, Rell 11 55%, Nami 11 55% |
| SUB TOP/MID | Seifur#9000 | Master 162 LP (51%) | Jayce 77 47%, Rumble 66 44%, Ambessa 57 39%, Akali 49 45%, Sylas 57 56% |
| SUB BOT/SUP | MiQ#HZK (medium confidence) | Emerald 1 75 LP (50%) | Twitch 156 50%, Jhin 131 55%, Yunara 97 52%, Kai'Sa 61 59%, Vayne 52 44% |

## Identities
- **redside hater#EUWs = Kristut** (high confidence). The Challengermode user "kristut" links this account. The Spring 2026 bot picks (Corki, Varus, Ezreal, Sivir, Caitlyn) match this account's S25 soloQ. op.gg shows no name history and has no separate Kristut account.
- **Aqua Umbrella#EUW** (medium confidence alt of Red Umbrella/Kiddi). It is a separate account, not a rename (both exist). Level 118, Emerald 1, 85% bot. It appears on the Autumn week-1 scoreboard in his slot. It counts at 0.5 weight.
- **MiQ#HZK** (medium confidence). It was found through op.gg search. Level 512, Emerald 1, 74% bot. The top champions Yunara and Twitch match his two Autumn competitive games exactly. Challengermode does not confirm the link. Miq#EUW (Silver, inactive-style) was rejected.
- No alts found for Boppa, Sosa, Zarzator, Legions1 or Seifur.

## Notes
- **Boppa (top):** high-volume Master top-laner with a stable pool: Jax (mastery 241), Jayce, Gnar, Sion, Rumble, Ornn, Mundo, Renekton, Malphite, Ambessa. Best results are Renekton 62% and Ornn 56%. Sion is weak (45%). Every competitive pick is in his pool. Camille and Vayne are low-volume counter-picks.
- **Sosa (jungle):** low volume, with Shaco as the clear main (also picked in competitive). Small-sample strengths: Nidalee 8-3, Kha'Zix 6-3, Elise 6-2, Lee Sin 5-1, Skarner 4-1. Graves is 38%. He also plays support in soloQ (Morgana, Leona). Competitive Xin Zhao, Jayce, Mundo, Olaf, Kayn, Malphite and Poppy have no soloQ games, so use his competitive history.
- **Zarzator (mid):** almost no ranked play (15 flex games in S26). In soloQ he is a support main (Pyke/Thresh/Bard/Rakan mastery). The competitive mid pool (Anivia x3, TF, Lux, Kled, Karthus, Ahri, Orianna, Annie) is not reflected in soloQ apart from Anivia 4 g and Mel/Sylas. Draft from his competitive picks.
- **Legions1 (sub mid):** Akali 69% (4.6 KDA) and LeBlanc 60% are the comfort picks. Also Ryze 6-2, Kassadin, Syndra, Yone, Cassiopeia, TF, Orianna, Azir. All competitive picks match. He was a jungler in S25 (Wukong 11-4, Lee Sin, Nidalee 5-0), so a jungle flex is possible.
- **redside hater (bot):** low volume. He plays bot (Lucian, Ezreal, Jhin, Caitlyn, Kalista; Corki and Smolder in S25) and also a lot of top this season (Renekton 5-0, Yorick). Yunara has no soloQ games but he picked it in both splits.
- **Red Umbrella (support):** 41 ranked games in S26, with a shift to engage (Leona, Nautilus, Rell) that matches competitive. In S25 he was an enchanter (Lulu 27 g, Nami, Yuumi, Karma, Milio). Competitive Poppy, Elise and Bard are not in soloQ.
- **Seifur (sub top/mid):** Master, with 90+ champions. The strongest signals are Jayce, Rumble, Sylas 70%, Zaahen 70%, K'Sante, Yone 85% and Locke 67%. Ambessa is bad (32%). His wide pool makes target bans weak.
- **MiQ (sub bot):** Yunara, Jhin, Twitch, Kai'Sa, Vayne, Ezreal, Lucian. His support options are Karma, Lulu, Thresh and Senna. His competitive support picks (Nautilus, Nami, Leona) barely appear in soloQ.

## Sources that failed
leagueofgraphs, u.gg, mobalytics (client errors); op.gg Kristut-EUW (client error) and search 'Kristut' (no results); op.gg `season_id=30` (ignored, so there is no S2024 champion data); direct curl to op.gg (proxy 403).
