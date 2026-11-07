"""Build one HTML page that shows simulated drafts with each captain's reasoning beside every ban and pick.

python3 tools/sim_viewer.py OUT.html [--title T] [--kicker K] [--intro TEXT] [--series series.json] "drafts/sims/a.json=Round 1" "drafts/sims/b.json=Round 2" ...
An analyst review in <sim dir>/reviews/<same file name> is shown under the board, with the draft_review.py data score and the objective draft-only score (champions alone, players left out).
--series: a series file ({"result": "...", "method": "...", "games": [{"file": "<sim file name>", "game": N, "winner": "blue"|"red", "score_after": "..."}]})
  turns the page into one series: games in the order given, a game-result line on each board, and a result column in the overview.
Champions locked by fearless from earlier games (the sim's fearless_blue/fearless_red) are shown on each board when there are any.

Roles are inferred per side from the team's role pools (profile.json) plus champion role tags.
The page is self-contained (data inlined); publish it as an Artifact.
"""
import itertools, json, os, re, sys, html
sys.path.insert(0, os.path.dirname(__file__))
from common import ROLES
from common import ORDER
from roles import role_prior

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = {"MonkeyKing": "Wukong", "Leblanc": "LeBlanc", "Khazix": "Kha'Zix", "KSante": "K'Sante",
         "Velkoz": "Vel'Koz", "Chogath": "Cho'Gath", "Kaisa": "Kai'Sa", "Belveth": "Bel'Veth",
         "RekSai": "Rek'Sai", "Nunu": "Nunu & Willump", "RenataGlasc": "Renata Glasc",
         "JarvanIV": "Jarvan IV", "DrMundo": "Dr. Mundo", "FiddleSticks": "Fiddlesticks"}

def disp(c):
    return NAMES.get(c) or re.sub(r"(?<=[a-z])(?=[A-Z])", " ", c)

def prof(slug):
    return json.load(open(os.path.join(ROOT, "teams", slug, "profile.json"), encoding="utf-8"))

def assign(picks, p):
    pools = p.get("pools", {})
    best, bs = None, -1e9
    for perm in itertools.permutations(picks):
        s = 0
        for c, r in zip(perm, ROLES):
            s += role_prior(c)[r] + 6 * pools.get(r, {}).get(c, 0)
        if s > bs: best, bs = perm, s
    return dict(zip(ROLES, best)) if best else {}

def team_name(p):
    return p.get("team") or p.get("slug")

def build(path, label):
    s = json.load(open(path, encoding="utf-8"))
    out = {"file": os.path.basename(path), "label": label, "intel": s.get("intel", "?"),
           "blue": {"slug": s["blue"]}, "red": {"slug": s["red"]}, "actions": []}
    n = {"blue": {"ban": 0, "pick": 0}, "red": {"ban": 0, "pick": 0}}
    for i, a in enumerate(s["actions"]):
        side, kind = ORDER[i]
        n[side][kind] += 1
        out["actions"].append({"i": i + 1, "side": side, "kind": kind, "champ": disp(a["champ"]),
                               "key": a["champ"], "tag": f"{side[0].upper()}{n[side][kind]}" if kind == "pick" else f"Ban {n[side][kind]}",
                               "why": a.get("reasoning", "")})
    out["complete"] = len(s["actions"]) >= len(ORDER)
    out["fearless"] = [{"key": c, "champ": disp(c), "side": side} for side in ("blue", "red") for c in s.get(f"fearless_{side}", [])]
    out["us"] = "blue" if prof(s["blue"]).get("is_us") else ("red" if prof(s["red"]).get("is_us") else "blue")
    for side in ("blue", "red"):
        p = prof(s[side])
        out[side]["name"] = team_name(p)
        picks = [a["champ"] for a in s["actions"] if a["side"] == side and a["kind"] == "pick"]
        roles = assign(picks, p) if len(picks) == 5 else {}
        out[side]["comp"] = [{"role": r, "champ": disp(roles[r]) if r in roles else None, "key": roles.get(r),
                              "player": p["roster"][r]["main"].title()} for r in ROLES]
    rv = os.path.join(os.path.dirname(path), "reviews", os.path.basename(path))   # analyst review (skills/predict-series/analyst_brief.md)
    out["review"] = json.load(open(rv, encoding="utf-8")) if os.path.exists(rv) else None
    if out["complete"]:
        import draft_review
        R = draft_review.review(*draft_review.from_sim(path))
        out["data"] = {"lean": R["lean"], "drivers": R["drivers"], "lanes": [{k: l[k] for k in ("role", "edge", "notes")} for l in R["lanes"]]}
        D = draft_review.review(*draft_review.from_sim(path), players=False)   # objective draft score: champions only, players left out
        out["draft_only"] = {"lean": D["lean"], "drivers": D["drivers"]}
        for side in ("blue", "red"):   # player = whoever on the team is best on that champion in that role (flex rosters)
            for c, row in zip(out[side]["comp"], R["facts"][side]["rows"]):
                if row["player"] and c["key"] == row["champ"]: c["player"] = row["player"].title()
    return out

ASSETS = os.path.join(ROOT, "assets", "ddragon")

def images(keys):
    """Data Dragon art for the champions used, resized and inlined as data URIs: q = square icon, s = splash crop."""
    import base64, io
    from PIL import Image
    out, missing = {}, []
    def uri(path, size, crop):
        im = Image.open(path).convert("RGB")
        if crop:   # splash: keep the upper-centre band where the face usually is
            w, h = im.size
            im = im.crop((int(w * .08), int(h * .02), int(w * .92), int(h * .72)))
        im.thumbnail(size)
        b = io.BytesIO(); im.save(b, "JPEG", quality=78, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
    for k in sorted(keys):
        q, s = os.path.join(ASSETS, "square", k + ".png"), os.path.join(ASSETS, "splash", k + ".jpg")
        e = {}
        if os.path.exists(q): e["q"] = uri(q, (96, 96), False)
        if os.path.exists(s): e["s"] = uri(s, (560, 400), True)
        if not e: missing.append(k)
        out[k] = e
    if missing: print("no Data Dragon art for:", ", ".join(missing), "(see skills/predict-series/SKILL.md step 4)")
    return out

def main():
    args = sys.argv[1:]
    opt = lambda n, d: args[args.index(n) + 1] if n in args else d
    title, kicker = opt("--title", "Draft sims"), opt("--kicker", "Kia deild · hard fearless · game 1 simulations")
    intro, series = opt("--intro", None), opt("--series", None)
    for n in ("--title", "--kicker", "--intro", "--series"):
        if n in args: i = args.index(n); del args[i:i + 2]
    outp, specs = args[0], args[1:]
    sims = []
    for sp in specs:
        path, _, label = sp.partition("=")
        sims.append(build(path, label or os.path.basename(path)))
    meta = {"series": None}
    if series:
        ser = json.load(open(series, encoding="utf-8"))
        meta["series"] = {"result": ser.get("result", ""), "method": ser.get("method", "")}
        by = {g["file"]: g for g in ser.get("games", [])}
        for x in sims:
            g = by.get(x["file"])
            if g: x["result"] = {"game": g.get("game"), "winner": g.get("winner"), "score_after": g.get("score_after", "")}
    tpl = open(os.path.join(os.path.dirname(__file__), "sim_viewer_template.html"), encoding="utf-8").read()
    data = json.dumps(sims, ensure_ascii=False).replace("</", "<\\/")
    keys = {a["key"] for s in sims for a in s["actions"]} | {f["key"] for s in sims for f in s.get("fearless", [])}
    img = json.dumps(images(keys))
    page = tpl.replace("__TITLE__", html.escape(title)).replace("__KICKER__", html.escape(kicker))
    if intro: page = re.sub(r'(<p class="muted" id="intro"[^>]*>).*?(</p>)', lambda m: m.group(1) + html.escape(intro) + m.group(2), page, count=1, flags=re.S)
    page = page.replace("/*__META__*/{}", json.dumps(meta, ensure_ascii=False).replace("</", "<\\/"))
    open(outp, "w", encoding="utf-8").write(page.replace("/*__DATA__*/[]", data).replace("/*__IMG__*/{}", img))
    print(f"wrote {outp}: {len(sims)} sims")

if __name__ == "__main__":
    main()
