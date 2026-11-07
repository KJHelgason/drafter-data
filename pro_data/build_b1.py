"""First-pick priority in pro play, per game number of a series (fearless), from raw/leaguepedia_picks_*.json.
Run: python3 build_b1.py -> b1_priority.json (+ ../knowledge/b1_priority.md)
Per game number (1, 2, 3, 4+) and champion:
  b1        games it was the blue first pick (B1)
  rot1      games it was picked in the first rotation by either side (B1, R1, R2)
  p1ban     games it was banned in phase 1 (first 3 bans of either team)
  avail     games it was still available at B1 (not banned in phase 1, not used earlier in the series)
  b1_when_avail = b1 / avail: how often pros take it B1 when they can (the B1 priority)
  b1_wins   B1 games won
Game 1 has the full champion pool; later games lose what was played earlier (hard fearless), so the B1 list shifts.
"""
import json, glob, os, re, collections as co
HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for f in sorted(glob.glob(os.path.join(HERE, 'raw', 'leaguepedia_picks_*.json'))): rows += json.load(open(f, encoding='utf-8'))['rows']
series = co.defaultdict(list)
for r in rows:
    m = re.match(r'(.*)_(\d+)$', r['GameId']); series[m.group(1)].append((int(m.group(2)), r))
S = co.defaultdict(lambda: co.defaultdict(co.Counter)); G = co.Counter()
for sid, games in series.items():
    used = set()
    for n, r in sorted(games, key=lambda x: x[0]):
        g = str(min(n, 4)); G[g] += 1
        p1 = {r.get(f'Team{t}Ban{i}') for t in (1, 2) for i in (1, 2, 3)} - {None, ''}
        picks = [r.get(f'Team{t}Pick{i}') for t in (1, 2) for i in range(1, 6)]
        b1, r1, r2 = r['Team1Pick1'], r['Team2Pick1'], r['Team2Pick2']
        for c in p1: S[g][c]['p1ban'] += 1
        for c in (b1, r1, r2): S[g][c]['rot1'] += 1
        S[g][b1]['b1'] += 1; S[g][b1]['b1_wins'] += r['Winner'] in (1, '1')
        pool = {c for gg in S.values() for c in gg} | set(picks) | p1
        for c in pool:
            if c and c not in p1 and c not in used: S[g][c]['avail'] += 1
        used |= {c for c in picks if c}
out = {'meta': {'games': len(rows), 'series': len(series), 'games_by_number': dict(G),
                'note': 'Leaguepedia pro games 26.16-26.20 (Worlds and regional leagues); game 4 includes 5'}}
for g, d in sorted(S.items()):
    L = []
    for c, x in d.items():
        if x['b1'] + x['rot1'] + x['p1ban'] == 0: continue
        L.append({'champ': c, 'b1': x['b1'], 'b1_wins': x['b1_wins'], 'rot1': x['rot1'], 'p1ban': x['p1ban'], 'avail': x['avail'],
                  'b1_when_avail': round(x['b1'] / x['avail'], 3) if x['avail'] else 0,
                  'presence': round((x['rot1'] + x['p1ban']) / G[g], 3)})
    out[g] = sorted(L, key=lambda e: (-e['b1'], -e['presence']))
json.dump(out, open(os.path.join(HERE, 'b1_priority.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
M = ['# First-pick (B1) priority in pro play, by game of the series', '',
     f"From {len(rows)} pro games in {len(series)} series (patches 26.16-26.20; `pro_data/build_b1.py`). Hard fearless: later games lose every champion played earlier, so their B1 lists are what is left.",
     '', '**B1 when available** = how often pros take it B1 in games where it survived phase-1 bans (and fearless). **Phase-1 ban** = share of games it was banned in the first 3 bans of either team. **Rotation 1** = picked B1, R1 or R2.', '']
for g in ('1', '2', '3', '4'):
    if g not in out: continue
    M += [f"## Game {g if g != '4' else '4-5'} ({G[g]} games)", '', '| Champion | B1 | B1 when available | B1 win | Rotation 1 | Phase-1 ban | Presence (rot 1 + P1 ban) |', '|---|---|---|---|---|---|---|']
    for e in [e for e in out[g] if e['b1'] >= 2 or e['presence'] >= 0.25][:20]:
        M.append(f"| {e['champ']} | {e['b1']} | {round(100 * e['b1_when_avail'])}% | {e['b1_wins']}-{e['b1'] - e['b1_wins']} | {round(100 * e['rot1'] / G[g])}% | {round(100 * e['p1ban'] / G[g])}% | {round(100 * e['presence'])}% |")
    M.append('')
open(os.path.join(HERE, '..', 'knowledge', 'b1_priority.md'), 'w', encoding='utf-8').write('\n'.join(M))
print(dict(G))
