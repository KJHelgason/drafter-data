"""Data lookup for one pick: the facts on a champion in a role given the board. It prints data, not advice.

  python3 tools/pick_check.py <us> <role> "<Champion>" [--enemy "Varus,Briar"] [--enemy-roles "bot,jungle"]
        [--ours "LeBlanc"] [--used "fearless list"] [--bans "this game's bans"] [--opp <their slug>]

Prints:
  SHEET       our player's comfort tier for it (teams/<us>/stated_pools.json), if the file exists.
  LANE        the pro lane record against the enemy laner, if he is locked (knowledge/counter_records.json grades).
  COUNTERS    graded pro counters to this champion that are still open (not picked, banned or used).
  OPP COMFORT (with --opp) enemy players who have this champion in their top pool, with their comfort.
  COMP        damage mix and hard CC of our picks with this one, and of theirs (knowledge/champion_profiles.json).
  ROLE BOARD  every open champion in our player's pool for the role: comfort and the pro lane record against the
              locked enemy laner, or the number of graded counters still open when the lane is blind. Sorted by comfort.
"""
import os, sys, json, argparse
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT
from knowledge import to_id, display, counter_records, counter_strength, counter_note, counters_of
from roles import role_prior

ap = argparse.ArgumentParser()
ap.add_argument("team"); ap.add_argument("role"); ap.add_argument("champ")
ap.add_argument("--slot", choices=["blind", "counter"], default=None, help="accepted for compatibility; not used")
ap.add_argument("--enemy", default=""); ap.add_argument("--ours", default="")
ap.add_argument("--enemy-roles", default=""); ap.add_argument("--our-roles", default="")
ap.add_argument("--used", default=""); ap.add_argument("--bans", default="")
ap.add_argument("--opp", default=""); ap.add_argument("--phase", default=None)
a = ap.parse_args()

def ids(s): return [to_id(x.strip()) for x in s.split(",") if x.strip()]
def load(p, d):
    p = os.path.join(ROOT, p); return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d
cid = to_id(a.champ); role = a.role.lower().replace("adc", "bot")
enemy, ours = ids(a.enemy), ids(a.ours)
eroles = dict(zip([r.strip().lower().replace("adc", "bot") for r in a.enemy_roles.split(",") if r.strip()], enemy))
taken = set(enemy) | set(ours) | set(ids(a.used)) | set(ids(a.bans))
def _top_role(c):
    rp = role_prior(c); return max(rp, key=rp.get) if any(rp.values()) else None
laner = eroles.get(role) or next((c for c in enemy if c not in eroles.values() and _top_role(c) == role), None)

sheet = load(f"teams/{a.team}/stated_pools.json", {}).get(role, {})
tiers = ("signature", "blind", "pickable", "counter")
tier = next((t for t in tiers if any(to_id(c) == cid for c in sheet.get(t, []))), None)
if sheet: print(f"SHEET {display(cid)} ({role}): {tier or 'not in pool'}")

if laner:
    them, us = counter_strength(laner, cid, role), counter_strength(cid, laner, role)
    if us: print(f"LANE {display(cid)} into {display(laner)}: {counter_note(us)}")
    elif them: print(f"LANE {display(laner)} into {display(cid)}: {counter_note(them)}")
    else: print(f"LANE no pro record for {display(cid)} vs {display(laner)}")

graded = [(c, x) for c, x in counter_records().get(role, {}).get(cid, {}).items() if x.get("grade") in ("strong", "favoured")]
open_c = [(c, x) for c, x in graded if c not in taken]
if graded:
    print(f"COUNTERS graded pro counters to {display(cid)} in {role}, still open: "
          + (", ".join(f"{display(c)} ({x['grade']})" for c, x in open_c) or "none"))

if a.opp:
    op = load(f"teams/{a.opp}/profile.json", {})
    for pname, pl in (op.get("players") or {}).items():
        for e in pl.get("pool", [])[:8]:
            if to_id(e["champ"]) == cid:
                print(f"OPP COMFORT {pname} ({pl.get('role')}): comfort {e['comfort']}")

try:
    from comp_profile import comp as _comp, line as _cline, profiles as _profiles
    if _profiles():
        print(f"COMP ours with {display(cid)}: {_cline(_comp(ours + [cid]))}")
        if enemy: print(f"COMP theirs: {_cline(_comp(enemy))}")
except Exception as e:
    print(f"COMP unavailable ({e})")

pool = load(f"teams/{a.team}/profile.json", {}).get("pools", {}).get(role, {})
cands = list(dict.fromkeys([cid] + [to_id(c) for t in tiers for c in sheet.get(t, [])] + list(pool)))
board = []
for x in cands:
    if x != cid and x in taken: continue
    cf = pool.get(x, 0.0)
    if laner:
        us, them = counter_strength(x, laner, role), counter_strength(laner, x, role)
        m = (f"vs {display(laner)}: {counter_note(us)}" if us else f"{display(laner)} vs it: {counter_note(them)}" if them
             else f"no pro record vs {display(laner)}")
    else:
        n = sum(1 for c in counters_of(x, role) if c not in taken and (counter_strength(c, x, role) or {}).get("grade") in ("strong", "favoured"))
        m = f"{n} graded counter(s) still open"
    board.append((cf, x, m))
board.sort(key=lambda z: -z[0])
print(f"ROLE BOARD {role} ({'enemy laner ' + display(laner) + ' locked' if laner else 'lane still blind'}; sorted by comfort):")
for i, (cf, x, m) in enumerate(board[:10], 1):
    print(f"  {i}. {display(x)}{' <- this pick' if x == cid else ''}: comfort {cf:.2f}, {m}")
