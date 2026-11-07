"""Infer which role each of 5 picked champions played (drafter.lol stores picks by pick order, not role)."""
import itertools
from common import load, ROLES

_TAGS = None
def tags():
    global _TAGS
    if _TAGS is None:
        _TAGS = load("knowledge/champion_tags.json")
    return _TAGS

def role_prior(champ, extra=None):
    """Score per role: champion_tags roles (+1 primary order bonus) plus optional extra counts {role:{champ:n}}."""
    t = tags().get(champ, {})
    rs = t.get("roles", [])
    score = {r: 0.0 for r in ROLES}
    for i, r in enumerate(rs):
        score[r] += 3.0 - i * 0.8
    if extra:
        for r in ROLES:
            score[r] += 2.0 * extra.get(r, {}).get(champ, 0)
    return score

def assign_roles(champs, extra=None):
    """Best permutation of 5 champs onto 5 roles. Returns {role: champ}."""
    champs = [c for c in champs if c]
    if len(champs) != 5:
        return {}
    pri = {c: role_prior(c, extra) for c in champs}
    best, best_s = None, -1e9
    for perm in itertools.permutations(champs):
        s = sum(pri[c][r] for c, r in zip(perm, ROLES))
        if s > best_s:
            best, best_s = perm, s
    return dict(zip(ROLES, best))
