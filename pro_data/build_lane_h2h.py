"""Pro lane head-to-heads for every role, from every 2026 Leaguepedia game (load_games.all_rows(), weighted by patch and level).
Run: python3 build_lane_h2h.py  ->  lane_h2h.json
For each role and champion pair (A, B) that met in that role: games, A's wins, and the counter-pick split:
  a_after = games where A was locked after B (A was the counter pick), a_after_wins = A's wins in those games.
Bot and support are also given as the 2v2 (adc+support pair vs pair is too sparse, so lanes are per role).
"""
import json, glob, os, collections as co
HERE = os.path.dirname(os.path.abspath(__file__))
from load_games import matchup_rows as all_rows, summary
rows = all_rows()
ORDER = ['B1', 'R1', 'R2', 'B2', 'B3', 'R3', 'R4', 'B4', 'B5', 'R5']
ROLES = {'Top': 'top', 'Jungle': 'jungle', 'Mid': 'mid', 'Bot': 'bot', 'Support': 'support'}
def P(r, t):
    lab = ['B1', 'B2', 'B3', 'B4', 'B5'] if t == 1 else ['R1', 'R2', 'R3', 'R4', 'R5']
    return {r[f'Team{t}Role{i}']: (r[f'Team{t}Pick{i}'], lab[i - 1]) for i in range(1, 6)}
h = {r: co.defaultdict(co.Counter) for r in ROLES.values()}
for r in rows:
    p1, p2 = P(r, 1), P(r, 2)
    for R, role in ROLES.items():
        if R not in p1 or R not in p2: continue
        (a, sa), (b, sb) = p1[R], p2[R]
        if not a or not b or a == b: continue
        k = tuple(sorted([a, b])); x = h[role][k]; aw = (r['Winner'] in (1, '1')) == (a == k[0])
        # store from k[0]'s point of view
        first_is_a = a == k[0]
        k0_slot, k1_slot = (sa, sb) if first_is_a else (sb, sa)
        w = r['_w']; x['games'] += 1; x['k0_wins'] += aw; x['wg'] += w; x['wa'] += w * aw
        if (r['Patch'] or '') >= '26.16': x['rg'] += 1; x['ra'] += aw
        if ORDER.index(k0_slot) > ORDER.index(k1_slot): x['k0_after'] += 1; x['k0_after_wins'] += aw
        else: x['k1_after'] += 1; x['k1_after_wins'] += (not aw)
out = {'meta': {**summary(rows), 'source': 'load_games.all_rows(): every Primary/Secondary Leaguepedia game since 2026-01-01 (+ the curated 26.16-26.20 set)',
                'fields': 'games/a_wins/a_after...: raw counts. wg/wa: weighted games and a-wins (patch x level weight, see load_games.py); grades use these. rg/ra: patch 26.16+ only.'}}
for role, d in h.items():
    out[role] = [{'a': k[0], 'b': k[1], 'games': x['games'], 'a_wins': x['k0_wins'], 'a_after': x['k0_after'], 'a_after_wins': x['k0_after_wins'],
                  'b_after': x['k1_after'], 'b_after_wins': x['k1_after_wins'], 'wg': round(x['wg'], 2), 'wa': round(x['wa'], 2),
                  'rg': x['rg'], 'ra': x['ra']} for k, x in sorted(d.items(), key=lambda kv: -kv[1]['games'])]
json.dump(out, open(os.path.join(HERE, 'lane_h2h.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
print({r: len(v) for r, v in out.items() if r != 'meta'}, 'games', len(rows))
