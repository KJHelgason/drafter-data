"""Shared loader for Leaguepedia pro drafts.

recent_rows()  the curated recent window: raw/leaguepedia_picks_*.json (patches 26.16-26.20, 13 top events). Used for
               meta-dependent data: tiers, B1 priority, bot pair timing, same-team pairings.
all_rows()     recent window + raw/leaguepedia_2026_all_*.json (every Primary/Secondary Leaguepedia event since 2026-01-01),
               deduplicated by GameId. Used for lane matchups / counter grades and role timing, where sample size matters
               more than the exact meta. Each row gets a weight r['_w'] = patch weight x level weight (see below).

matchup_rows() all_rows() + raw/leaguepedia_2025_all_*.json (every Primary/Secondary event in 2025) at weight 0.2 x level.
               Used for lane matchups / counter grades and jungle+mid pairs only: more games for rare matchups, while
               the older balance counts for little next to 2026.
Patch weight (champion and item changes make old games less relevant):
  26.16 and later 1.0 | 26.11-26.15 0.7 | 26.06-26.10 0.5 | 26.01-26.05 0.35 | 25.x 0.2 (matchup_rows only)
Level weight: Primary (major leagues, internationals) 1.0 | Secondary (ERLs, academies, 2nd divisions) 0.6;
  qualifiers x0.8.
"""
import json, glob, os, functools
HERE = os.path.dirname(os.path.abspath(__file__))

def patch_num(p):
    """Leaguepedia patches arrive as '26.2' (= 26.20), 26.1 (= 26.10), '26.05', 25.24 ... -> (season, minor)."""
    if p is None or p == '': return None
    s = str(p)
    if '.' not in s: return None
    a, b = s.split('.', 1)
    if len(b) == 1: b = b + '0'          # float lost the trailing zero: 26.2 -> 26.20
    try: return int(a), int(b)
    except ValueError: return None

def patch_weight(p):
    n = patch_num(p)
    if not n: return 0.35
    s, m = n
    if s < 26: return 0.35
    if m >= 16: return 1.0
    if m >= 11: return 0.7
    if m >= 6: return 0.5
    return 0.35

def level_weight(r):
    w = 1.0 if r.get('Level', 'Primary') == 'Primary' else 0.6
    if str(r.get('IsQualifier', 0)) in ('1', 'True', 'true'): w *= 0.8
    return w

def _norm(r):
    n = patch_num(r.get('Patch'))
    if n: r['Patch'] = f'{n[0]}.{n[1]:02d}'
    for t in (1, 2):
        for i in range(1, 6):
            for k in (f'Team{t}Pick{i}', f'Team{t}Ban{i}'):
                if r.get(k) in ('', 'None', '-'): r[k] = None
    try: r['Winner'] = int(r['Winner'])
    except (TypeError, ValueError, KeyError): r['Winner'] = None
    return r

def _ok(r):
    if r.get('Winner') not in (1, 2): return False
    roles = {r.get(f'Team{t}Role{i}') for t in (1, 2) for i in range(1, 6)}
    return all(r.get(f'Team{t}Pick{i}') for t in (1, 2) for i in range(1, 6)) and {'Top', 'Jungle', 'Mid', 'Bot', 'Support'} <= roles

@functools.lru_cache(None)
def recent_rows():
    rows = []
    for f in sorted(glob.glob(os.path.join(HERE, 'raw', 'leaguepedia_picks_*.json'))):
        rows += json.load(open(f, encoding='utf-8'))['rows']
    for r in rows: r.setdefault('Level', 'Primary'); r['_w'] = 1.0
    return tuple(_norm(r) for r in rows)

@functools.lru_cache(None)
def all_rows():
    seen, out = set(), []
    for r in recent_rows():
        seen.add(r['GameId']); out.append(r)
    for f in sorted(glob.glob(os.path.join(HERE, 'raw', 'leaguepedia_2026_all_*.json'))):
        for r in json.load(open(f, encoding='utf-8'))['rows']:
            if r['GameId'] in seen: continue
            r = _norm(dict(r))
            if not _ok(r): continue
            seen.add(r['GameId']); r['_w'] = round(patch_weight(r['Patch']) * level_weight(r), 3); out.append(r)
    return tuple(out)

@functools.lru_cache(None)
def matchup_rows():
    seen, out = {r['GameId'] for r in all_rows()}, list(all_rows())
    for f in sorted(glob.glob(os.path.join(HERE, 'raw', 'leaguepedia_2025_all_*.json'))):
        for r in json.load(open(f, encoding='utf-8'))['rows']:
            if r['GameId'] in seen: continue
            r = _norm(dict(r))
            if not _ok(r): continue
            seen.add(r['GameId']); r['_w'] = round(0.2 * level_weight(r), 3); out.append(r)
    return tuple(out)

def summary(rows):
    import collections as co
    c = co.Counter(); w = 0.0
    for r in rows: c[r.get('Level', 'Primary')] += 1; w += r['_w']
    return {'games': len(rows), 'weighted_games': round(w, 1), 'by_level': dict(c)}

if __name__ == '__main__':
    print('recent', summary(recent_rows()))
    print('all', summary(all_rows()))
    print('matchup', summary(matchup_rows()))
