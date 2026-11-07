"""Per role and champion: when pros pick it (blind vs counter, phase 1 vs phase 2, by game of the series), how it does
each way, and which champions are reliably gone before pros blind it. From every 2026 game (load_games.all_rows()).
Run: python3 build_role_timing.py -> role_timing.json (+ ../knowledge/role_timing.md)
  blind    locked before the enemy laner in the same role      counter  locked after the enemy laner
  phase1   picked in picks 1-3 of the team (B1-B3 / R1-R3)
  wr_ci    Wilson 95% range for the win rate: if it spans 50%, the win rate tells you nothing
  gone_before_blind: champions banned or taken by the enemy before a blind lock clearly more often than at the same
           draft step in all games (lift >= 1.5, at least 8 cases, z >= 2). Empty = pros blind it regardless.
"""
import json, glob, os, re, math, collections as co
HERE = os.path.dirname(os.path.abspath(__file__))
from load_games import all_rows, summary
rows = all_rows()   # every 2026 Primary/Secondary game: blind vs counter win rates need the bigger sample
SEQ = ([(1, 'ban', 1), (2, 'ban', 1), (1, 'ban', 2), (2, 'ban', 2), (1, 'ban', 3), (2, 'ban', 3),
        (1, 'pick', 1), (2, 'pick', 1), (2, 'pick', 2), (1, 'pick', 2), (1, 'pick', 3), (2, 'pick', 3),
        (2, 'ban', 4), (1, 'ban', 4), (2, 'ban', 5), (1, 'ban', 5), (2, 'pick', 4), (1, 'pick', 4), (1, 'pick', 5), (2, 'pick', 5)])
ROLES = {'Top': 'top', 'Jungle': 'jungle', 'Mid': 'mid', 'Bot': 'bot', 'Support': 'support'}
def wilson(w, n):
    if not n: return None
    p, z = w / n, 1.96; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 2), round(c + h, 2)]
def gnum(r): return min(int(re.search(r'_(\d+)$', r['GameId']).group(1)), 4)
C = co.defaultdict(lambda: co.defaultdict(co.Counter)); gone_at = co.defaultdict(co.Counter); steps = co.Counter()
blinds = co.defaultdict(list)
for r in rows:
    seq = [(t, k, i, r.get(f'Team{t}{"Ban" if k == "ban" else "Pick"}{i}')) for t, k, i in SEQ]
    idx = {x[:3]: n for n, x in enumerate(seq)}
    for t in (1, 2):
        e = 3 - t; win = r['Winner'] in (t, str(t))
        for i in range(1, 6):
            R = ROLES.get(r[f'Team{t}Role{i}']); c = r[f'Team{t}Pick{i}']
            if not R or not c: continue
            ej = next((j for j in range(1, 6) if ROLES.get(r[f'Team{e}Role{j}']) == R), None)
            if ej is None: continue
            me, opp = idx[(t, 'pick', i)], idx[(e, 'pick', ej)]
            gone = {x[3] for x in seq[:me] if x[3] and (x[1] == 'ban' or x[0] == e)}
            steps[me] += 1
            for g in gone: gone_at[me][g] += 1
            x = C[R][c]; gm = gnum(r); kind = 'blind' if me < opp else 'counter'
            x['games'] += 1; x['wins'] += win; x[f'g{gm}'] += 1; x[kind] += 1; x[kind + '_wins'] += win
            if i <= 3: x['phase1'] += 1
            if kind == 'blind': blinds[(R, c)].append((me, gone))
out = {'meta': {**summary(rows), 'note': 'every 2026 Primary/Secondary Leaguepedia game (raw counts, not weighted); win-rate ranges are Wilson 95%'}}
for R, d in C.items():
    L = []
    for c, x in d.items():
        if x['games'] < 8: continue
        sig = []
        B = blinds[(R, c)]
        if len(B) >= 8:
            cand = co.Counter(g for _, gone in B for g in gone)
            for g, n in cand.items():
                exp = sum(gone_at[me][g] / steps[me] for me, _ in B)
                if n >= 8 and exp > 0 and n / exp >= 1.5:
                    z = (n - exp) / math.sqrt(exp * (1 - exp / len(B)) + 1e-9)
                    if z >= 2: sig.append({'champ': g, 'n': n, 'of': len(B), 'lift': round(n / exp, 2)})
        L.append({'champ': c, 'games': x['games'], 'wins': x['wins'], 'wr_ci': wilson(x['wins'], x['games']),
                  'by_game': [x['g1'], x['g2'], x['g3'], x['g4']], 'blind': x['blind'], 'counter': x['counter'],
                  'blind_pct': round(x['blind'] / x['games'], 2), 'phase1_pct': round(x['phase1'] / x['games'], 2),
                  'blind_wr': [x['blind_wins'], x['blind'], wilson(x['blind_wins'], x['blind'])],
                  'counter_wr': [x['counter_wins'], x['counter'], wilson(x['counter_wins'], x['counter'])],
                  'gone_before_blind': sorted(sig, key=lambda s: -s['lift'])[:5]})
    out[R] = sorted(L, key=lambda e: -e['games'])
json.dump(out, open(os.path.join(HERE, 'role_timing.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
def ci(v): return f"{v[0]}-{v[1]}-{v[1] - v[0]}" if False else (f"{v[0]}-{v[1] - v[0]}" + (f" ({round(100 * v[2][0])}-{round(100 * v[2][1])}%)" if v[2] else '')) if v[1] else '-'
M = ['# Pick timing by role: blind or counter, by game of the series', '',
     f"From {len(rows)} pro games (`pro_data/build_role_timing.py`). **Blind** = locked before the enemy laner in that role; **counter** = after. Win records show the Wilson 95% range: when it spans 50% the record means nothing on its own. **Gone before blind** lists only clear patterns (at least 8 cases, 1.5x the normal rate, z >= 2).", '']
for R in ('top', 'jungle', 'mid', 'bot', 'support'):
    M += [f"## {R.title()}", '', '| Champion | Games (G1/G2/G3/G4+) | Blind % | Phase-1 % | Blind W-L (95% range) | Counter W-L (95% range) | Gone before blind |', '|---|---|---|---|---|---|---|']
    for e in out[R][:18]:
        M.append(f"| {e['champ']} | {e['games']} ({'/'.join(map(str, e['by_game']))}) | {round(100 * e['blind_pct'])}% | {round(100 * e['phase1_pct'])}% | {ci(e['blind_wr'])} | {ci(e['counter_wr'])} | "
                 + (', '.join(f"{s['champ']} {s['n']}/{s['of']} x{s['lift']}" for s in e['gone_before_blind']) or '-') + ' |')
    M.append('')
open(os.path.join(HERE, '..', 'knowledge', 'role_timing.md'), 'w', encoding='utf-8').write('\n'.join(M))
print({R: len(out[R]) for R in C})
