"""Render a live draft narration log (drafts/live/<series>_log.json) as one self-contained HTML page for the Artifact tool.

  python3 tools/narration_page.py drafts/live/mi_0Yybw_log.json drafts/live/mi_0Yybw_narration.html

Log shape: {"title", "us", "them", "url", "intro": [..], "games": [{"game", "us_side", "status", "plan": [..],
  "actions": [{"step": "Ban 1", "side": "blue|red", "kind": "ban|pick", "champ", "team", "why", "read"}],
  "review": {"objective", "players", "lines": [..]}}]}
"why" = our reasoning (our actions), "read" = what an enemy action tells us. Champion icons are inlined from assets/ddragon/square.
"""
import json, os, sys, html, base64, io
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from knowledge import to_id

ORDER = [("blue", "ban"), ("red", "ban"), ("blue", "ban"), ("red", "ban"), ("blue", "ban"), ("red", "ban"),
         ("blue", "pick"), ("red", "pick"), ("red", "pick"), ("blue", "pick"), ("blue", "pick"), ("red", "pick"),
         ("red", "ban"), ("blue", "ban"), ("red", "ban"), ("blue", "ban"),
         ("red", "pick"), ("blue", "pick"), ("blue", "pick"), ("red", "pick")]
_icons = {}
def icon(name):
    if not name or name == "None": return ""
    if name in _icons: return _icons[name]
    cid = to_id(name) or name.replace(" ", "").replace("'", "")
    p = os.path.join(ROOT, "assets", "ddragon", "square", f"{cid}.png")
    uri = ""
    if os.path.exists(p):
        try:
            from PIL import Image
            im = Image.open(p).convert("RGB").resize((56, 56)); b = io.BytesIO(); im.save(b, "JPEG", quality=82)
            uri = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
        except Exception:
            uri = ""
    _icons[name] = uri
    return uri

E = lambda s: html.escape(str(s or ""))

def chip(name, cls=""):
    u = icon(name)
    img = f'<img src="{u}" alt="" width="28" height="28">' if u else '<span class="noimg"></span>'
    return f'<span class="chip {cls}">{img}<span>{E(name or "—")}</span></span>'

_splash = {}
def splash(name):
    """Wide splash crop for a pick bar (drafter.lol style), inlined as a data URI."""
    if not name or name == "None": return ""
    if name in _splash: return _splash[name]
    cid = to_id(name) or name.replace(" ", "").replace("'", "")
    p = os.path.join(ROOT, "assets", "ddragon", "splash", f"{cid}.jpg")
    uri = ""
    if os.path.exists(p):
        try:
            from PIL import Image
            im = Image.open(p).convert("RGB"); w, h = im.size
            im = im.crop((int(w * .10), int(h * .06), int(w * .90), int(h * .56))); im.thumbnail((960, 300))
            b = io.BytesIO(); im.save(b, "JPEG", quality=74, optimize=True)
            uri = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
        except Exception:
            uri = ""
    _splash[name] = uri
    return uri

SLOT = {"blue": ["B1", "B2", "B3", "B4", "B5"], "red": ["R1", "R2", "R3", "R4", "R5"]}

def board(g, us, them):
    """drafter.lol-style champ select: blue picks as splash bars on the left, red on the right (pick order),
    team headers on top, the draft order strip in the centre, bans as grey squares underneath (3 + 2 per side)."""
    acts = g.get("actions", [])
    side_of = {"blue": us if g["us_side"] == "blue" else them, "red": them if g["us_side"] == "blue" else us}
    live = g.get("status") != "done"
    nxt = ORDER[len(acts)] if live and len(acts) < 20 else None
    players = g.get("players") or {}
    def picks_col(s):
        picks = [a["champ"] for a in acts if a["side"] == s and a["kind"] == "pick"]
        roles = (g.get("roles") or {}).get(s) or []
        out = []
        for i in range(5):
            if i < len(picks):
                c = picks[i]; u = splash(c); role = roles[i] if i < len(roles) else SLOT[s][i]
                who = (players.get(side_of[s]) or {}).get(role, "")
                bg = f' style="background-image:url({u})"' if u else ""
                out.append(f'<li class="pk filled"{bg}><span class="txt"><span class="role">{E(role)}{f" · {E(who)}" if who else ""}</span>'
                           f'<span class="cn">{E(c)}</span></span></li>')
            else:
                active = nxt == (s, "pick") and i == len(picks)
                out.append(f'<li class="pk{" active" if active else ""}"><span class="txt"><span class="role">{SLOT[s][i]}</span>'
                           f'<span class="cn">{"Picking…" if active else ""}</span></span></li>')
        return "".join(out)
    def bans_row(s):
        bans = [a["champ"] for a in acts if a["side"] == s and a["kind"] == "ban"]
        cells = []
        for i in range(5):
            if i < len(bans):
                u = icon(bans[i]); c = bans[i]
                cells.append(f'<span class="bn" title="{E(c)}">' + (f'<img src="{u}" alt="{E(c)}">' if u else f'<i>{E(c)[:2]}</i>') + '</span>')
            else:
                active = nxt == (s, "ban") and i == len(bans)
                cells.append(f'<span class="bn empty{" active" if active else ""}"></span>')
        return f'<div class="bgrp">{"".join(cells[:3])}</div><div class="bgrp">{"".join(cells[3:])}</div>'
    strip = []
    for i, (s, k) in enumerate(ORDER):
        if i in (6, 12, 16): strip.append('<span class="gap"></span>')
        if i < len(acts):
            u = icon(acts[i]["champ"])
            strip.append(f'<span class="st {s} {k} done" title="{E(acts[i]["step"])}: {E(acts[i]["champ"])}">' + (f'<img src="{u}" alt="">' if u else "") + '</span>')
        else:
            strip.append(f'<span class="st {s} {k}{" active" if live and i == len(acts) else ""}"></span>')
    phase = f'{nxt[0].title()} {nxt[1]}' if nxt else ("Draft complete" if not live else "Waiting")
    head = lambda s: (f'<div class="th {s}{" us" if side_of[s] == us else ""}"><b>{E(side_of[s])}</b><small>{s} side</small></div>')
    return (f'<div class="dl"><div class="dl-top">{head("blue")}<div class="dl-mid"><span class="gm">Game {g["game"]}</span>'
            f'<span class="ph {nxt[0] if nxt else ""}">{phase}</span></div>{head("red")}</div>'
            f'<div class="dl-body"><ol class="col blue">{picks_col("blue")}</ol>'
            f'<div class="dl-center"><div class="strip">{"".join(strip)}</div><p class="legend">Draft order: bans, picks B1 R1 R2 B2 B3 R3, bans, picks R4 B4 B5 R5</p></div>'
            f'<ol class="col red">{picks_col("red")}</ol></div>'
            f'<div class="dl-bans"><div class="bside blue">{bans_row("blue")}</div><div class="bside red">{bans_row("red")}</div></div></div>')

def timeline(g, us, them):
    acts = g.get("actions", []); out = []
    for i, (s, k) in enumerate(ORDER):
        if i >= len(acts):
            if g.get("status") != "done":
                out.append(f'<li class="pending"><span class="n">{i+1}</span><div class="body"><div class="head"><b>{s.title()} {k}</b><span class="who">waiting…</span></div></div></li>'); break
            continue
        a = acts[i]; ours = a.get("team") == us
        txt = a.get("why") if ours else a.get("read")
        lab = "Why" if ours else "Read"
        out.append(f'<li class="{a["side"]} {"ours" if ours else "theirs"} {a["kind"]}"><span class="n">{i+1}</span><div class="body">'
                   f'<div class="head">{chip(a["champ"], "ban" if a["kind"] == "ban" else "")}<span class="step">{E(a.get("step"))}</span><span class="who">{E(a.get("team"))}</span></div>'
                   + (f'<p><span class="lab">{lab}</span>{E(txt)}</p>' if txt else "") + '</div></li>')
    return '<ol class="timeline">' + "".join(out) + "</ol>"

def page(log):
    us, them = log["us"], log["them"]
    games = log.get("games", [])
    nav = "".join(f'<a href="#game-{g["game"]}" class="{"live" if g.get("status") != "done" else ""}">Game {g["game"]}</a>' for g in games)
    secs = []
    for g in games:
        g.setdefault("players", log.get("players", {}))
        rv = g.get("review") or {}
        review = ""
        if rv:
            review = (f'<div class="review"><h3>Who won the draft</h3><div class="verdicts">'
                      f'<div><span class="lab">Objective (champions only)</span><strong>{E(rv.get("objective"))}</strong></div>'
                      f'<div><span class="lab">With players</span><strong>{E(rv.get("players"))}</strong></div></div>'
                      + "".join(f"<p>{E(x)}</p>" for x in rv.get("lines", [])) + "</div>")
        plan = "".join(f"<li>{E(x)}</li>" for x in g.get("plan", []))
        status = "Live" if g.get("status") != "done" else "Done"
        secs.append(f'<section id="game-{g["game"]}" class="game"><header><h2>Game {g["game"]}</h2>'
                    f'<span class="pill {"live" if status == "Live" else ""}">{status}</span><span class="meta">{E(us)} on {E(g["us_side"])} side</span></header>'
                    f'{board(g, us, them)}'
                    + (f'<details open class="plan"><summary>Pre-draft plan</summary><ul>{plan}</ul></details>' if plan else "")
                    + f'<h3>Every ban and pick, in order</h3>{timeline(g, us, them)}{review}</section>')
    intro = "".join(f"<p>{E(x)}</p>" for x in log.get("intro", []))
    return TEMPLATE.replace("%%TITLE%%", E(log["title"])).replace("%%US%%", E(us)).replace("%%THEM%%", E(them)) \
        .replace("%%URL%%", E(log.get("url"))).replace("%%INTRO%%", intro).replace("%%NAV%%", nav).replace("%%GAMES%%", "".join(secs)) \
        .replace("%%UPDATED%%", E(log.get("updated", "")))

TEMPLATE = """<title>%%TITLE%%</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@500;700&family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
/* Layout: a champ-select board per game, then a vertical draft-order timeline where each step carries its reasoning. */
:root{
 --bg:#f3f1ec; --panel:#fffdf8; --ink:#1d1b17; --muted:#6b6458; --line:#ddd6c8;
 --blue:#2d6cdf; --red:#d23a3a; --gold:#a8843e; --ban:#8c857a;
 --display:"Saira Condensed","Arial Narrow",sans-serif; --body:"IBM Plex Sans",system-ui,sans-serif; --mono:"IBM Plex Mono",ui-monospace,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15140f;--panel:#1e1c16;--ink:#ece6d8;--muted:#a59d8c;--line:#37332a;--blue:#6b9cff;--red:#ff6b6b;--gold:#d4b06a;--ban:#7d776c;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#15140f;--panel:#1e1c16;--ink:#ece6d8;--muted:#a59d8c;--line:#37332a;--blue:#6b9cff;--red:#ff6b6b;--gold:#d4b06a;--ban:#7d776c;color-scheme:dark}
body{background:var(--bg);color:var(--ink);font:15px/1.55 var(--body);padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:28px 64px}
.wrap{max-width:none;margin:0 auto;display:grid;gap:28px}
.top,.game>header,.plan,.game>h3,.timeline,.review,footer{width:100%;max-width:1040px;margin-inline:auto}
h1,h2,h3,h4{font-family:var(--display);font-weight:700;letter-spacing:.01em;text-wrap:balance;margin:0}
h1{font-size:clamp(34px,6vw,56px);line-height:1}
h1 .vs{color:var(--muted);font-weight:500;padding-inline:.2em}
h1 .g{color:var(--gold)} h1 .t{color:var(--red)}
h2{font-size:32px} h3{font-size:22px;margin-top:8px}
.top{display:grid;gap:12px}
.top p{margin:0;max-width:68ch;color:var(--muted)}
.link{font-family:var(--mono);font-size:14px;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between}
.link code{user-select:all;overflow-wrap:anywhere}
.link button{font:600 13px var(--body);border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:6px;padding:6px 12px;cursor:pointer}
.link button:focus-visible,nav a:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
nav{display:flex;gap:8px;flex-wrap:wrap}
nav a{font:600 13px var(--body);text-decoration:none;color:var(--ink);border:1px solid var(--line);border-radius:999px;padding:4px 12px}
nav a.live{border-color:var(--gold);color:var(--gold)}
.game{display:grid;gap:16px;border-top:2px solid var(--line);padding-top:20px}
.game header{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
.meta{color:var(--muted);font-size:14px}
.pill{font:600 12px var(--mono);text-transform:uppercase;letter-spacing:.08em;border:1px solid var(--line);border-radius:999px;padding:2px 10px;color:var(--muted)}
.pill.live{color:var(--gold);border-color:var(--gold)}
.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.side{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px;display:grid;gap:10px;min-width:0}
.side h4{font-size:22px;display:flex;align-items:center;gap:8px}
.side h4 small{font:500 12px var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.dot{width:10px;height:10px;border-radius:50%}
.side.blue .dot{background:var(--blue)} .side.red .dot{background:var(--red)}
.side.us{box-shadow:inset 0 3px 0 var(--gold)}
.picks{list-style:none;margin:0;padding:0;display:grid;gap:6px}
.picks li{display:flex;align-items:center;justify-content:space-between;gap:8px}
.picks em{font:500 12px var(--mono);color:var(--muted);font-style:normal;text-transform:uppercase}
.picks li.empty{opacity:.45}
.bans{display:flex;gap:6px;flex-wrap:wrap}
.chip{display:inline-flex;align-items:center;gap:8px;min-width:0}
.chip img,.chip .noimg{width:28px;height:28px;border-radius:5px;flex:none;background:var(--line);display:inline-block}
.chip.ban img{filter:grayscale(1);opacity:.7}
.bans .chip span:last-child{display:none}
.chip.ban span{color:var(--ban);text-decoration:line-through}
.plan{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
.plan summary{font:700 18px var(--display);cursor:pointer}
.plan ul{margin:8px 0 0;padding-left:20px;display:grid;gap:4px;max-width:80ch}
.timeline{list-style:none;margin:0 auto;padding:0;display:grid;gap:8px}
.timeline li{display:grid;grid-template-columns:34px 1fr;gap:10px;align-items:start}
.timeline .n{font:500 13px var(--mono);color:var(--muted);text-align:right;padding-top:9px;font-variant-numeric:tabular-nums}
.timeline .body{border:1px solid var(--line);border-left:4px solid var(--line);border-radius:8px;padding:8px 12px;background:var(--panel);min-width:0}
.timeline li.blue .body{border-left-color:var(--blue)} .timeline li.red .body{border-left-color:var(--red)}
.timeline li.theirs .body{background:transparent}
.timeline .head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.timeline .step{font:500 12px var(--mono);text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.timeline .who{margin-left:auto;font-weight:600;font-size:13px}
.timeline li.ours .who{color:var(--gold)}
.timeline p{margin:6px 0 0;max-width:80ch}
.lab{font:500 11px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-right:8px}
.timeline li.pending .body{border-style:dashed;color:var(--muted)}
.review{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;display:grid;gap:8px}
.verdicts{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.verdicts div{display:grid;gap:2px}
.verdicts strong{font:700 22px var(--display)}
.review p{margin:0;max-width:80ch}
footer{color:var(--muted);font-size:13px}
/* drafter.lol board: one deliberate dark look in both page themes, like the site itself */
.dl{min-height:calc(100vh - 40px);grid-template-rows:auto 1fr auto;--dl-bg:#0c0e13;--dl-panel:#141821;--dl-line:#232a37;--dl-ink:#e8ecf3;--dl-mute:#8590a3;--dl-blue:#3d8bff;--dl-red:#ff4655;
 background:var(--dl-bg);color:var(--dl-ink);border:1px solid var(--dl-line);border-radius:12px;padding:14px;display:grid;gap:14px;color-scheme:dark;min-width:0}
.dl-top{display:grid;grid-template-columns:1fr auto 1fr;align-items:end;gap:10px}
.th{display:grid;gap:0}
.th b{font:700 clamp(26px,3vw,44px)/1 var(--display);letter-spacing:.02em}
.th small{font:500 11px var(--mono);text-transform:uppercase;letter-spacing:.1em;color:var(--dl-mute)}
.th.blue b{color:var(--dl-blue)} .th.red{text-align:right} .th.red b{color:var(--dl-red)}
.th.us b::after{content:" ★";font-size:14px;color:#d4b06a;vertical-align:top}
.dl-mid{display:grid;justify-items:center;gap:4px}
.gm{font:500 11px var(--mono);text-transform:uppercase;letter-spacing:.12em;color:var(--dl-mute);border:1px solid var(--dl-line);border-radius:999px;padding:2px 10px}
.ph{font:700 clamp(20px,2vw,30px) var(--display);letter-spacing:.03em;text-transform:uppercase}
.ph.blue{color:var(--dl-blue)} .ph.red{color:var(--dl-red)}
.dl-body{display:grid;grid-template-columns:minmax(0,1fr) minmax(180px,.55fr) minmax(0,1fr);gap:clamp(12px,1.5vw,24px);align-items:stretch}
.col{list-style:none;margin:0;padding:0;display:grid;grid-template-rows:repeat(5,1fr);gap:8px;min-width:0}
.pk{position:relative;min-height:clamp(74px,calc((100vh - 300px) / 5),150px);border-radius:6px;background:var(--dl-panel) center 30%/cover no-repeat;border:1px solid var(--dl-line);overflow:hidden;display:flex;align-items:flex-end}
.col.blue .pk{border-left:3px solid var(--dl-blue)} .col.red .pk{border-right:3px solid var(--dl-red);justify-content:flex-end}
.pk.filled::before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(8,10,14,.92) 0%,rgba(8,10,14,.45) 55%,rgba(8,10,14,.1) 100%)}
.col.red .pk.filled::before{background:linear-gradient(270deg,rgba(8,10,14,.92) 0%,rgba(8,10,14,.45) 55%,rgba(8,10,14,.1) 100%)}
.pk .txt{position:relative;display:grid;padding:10px 18px;gap:0;min-width:0}
.col.red .pk .txt{text-align:right}
.pk .role{font:500 clamp(11px,.9vw,14px) var(--mono);text-transform:uppercase;letter-spacing:.1em;color:var(--dl-mute)}
.pk .cn{font:700 clamp(22px,2.4vw,38px)/1.1 var(--display);letter-spacing:.02em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pk.active{border-color:#d4b06a}
.col.blue .pk.active{box-shadow:inset 0 0 0 1px var(--dl-blue)} .col.red .pk.active{box-shadow:inset 0 0 0 1px var(--dl-red)}
.pk.active .cn{font-size:15px;color:var(--dl-mute)}
.dl-center{display:grid;gap:14px;justify-items:center;align-content:center}
.strip{display:grid;grid-template-columns:repeat(6,clamp(24px,2.6vw,40px));gap:6px;justify-content:center}
.strip .gap{grid-column:1/-1;height:4px}
.st{width:clamp(24px,2.6vw,40px);height:clamp(24px,2.6vw,40px);border-radius:4px;background:var(--dl-panel);border:1px solid var(--dl-line);overflow:hidden;position:relative}
.st.blue{border-bottom:2px solid var(--dl-blue)} .st.red{border-bottom:2px solid var(--dl-red)}
.st.ban img{filter:grayscale(1);opacity:.6}
.st img{width:100%;height:100%;display:block}
.st.active{outline:2px solid #d4b06a;outline-offset:1px}
.legend{margin:0;font:500 12px/1.4 var(--mono);color:var(--dl-mute);text-align:center;max-width:26ch}
.dl-bans{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;border-top:1px solid var(--dl-line);padding-top:12px}
.bside{display:flex;gap:clamp(14px,2vw,28px)}
.bside.red{flex-direction:row-reverse}
.bgrp{display:flex;gap:4px}
.bside.red .bgrp{flex-direction:row-reverse}
.bn{width:clamp(36px,3.6vw,58px);height:clamp(36px,3.6vw,58px);border-radius:4px;background:var(--dl-panel);border:1px solid var(--dl-line);overflow:hidden;position:relative;display:grid;place-items:center}
.bn img{width:100%;height:100%;filter:grayscale(1) brightness(.75)}
.bn:not(.empty)::after{content:"";position:absolute;left:-20%;right:-20%;top:50%;height:2px;background:rgba(255,70,85,.75);transform:rotate(-45deg)}
.bn i{font:600 11px var(--mono);color:var(--dl-mute);font-style:normal}
.bn.active{outline:2px solid #d4b06a;outline-offset:1px}
@media (max-width:640px){
 .dl{min-height:0}
 .dl-body{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
 .dl-center{grid-column:1/-1;order:-1}
 .strip{grid-template-columns:repeat(10,22px)} .st{width:22px;height:22px} .strip .gap{display:none}
 .pk{min-height:60px} .pk .cn{font-size:18px} .th b{font-size:20px} .st{width:22px;height:22px}
 .bn{width:28px;height:28px}
}
@media (prefers-reduced-motion:no-preference){.pk.active,.st.active,.bn.active{animation:pulse 1.6s ease-in-out infinite}}
@media (prefers-reduced-motion:no-preference){.timeline li.pending .body{animation:pulse 1.6s ease-in-out infinite}@keyframes pulse{50%{opacity:.55}}}
</style>
<div class="wrap">
 <div class="top">
  <h1><span class="g">%%US%%</span><span class="vs">vs</span><span class="t">%%THEM%%</span></h1>
  %%INTRO%%
  <div class="link"><code id="series-link">%%URL%%</code><button type="button" id="copy">Copy link</button></div>
  <nav>%%NAV%%</nav>
 </div>
 %%GAMES%%
 <footer>Updated %%UPDATED%%. Comfort numbers are 0.40 to 1.00 from each player's weighted pro games and win rate (2025-26). Pro power is 0 to 100 from pick and ban presence at pro level.</footer>
</div>
<script>
document.getElementById('copy').addEventListener('click',async e=>{const t=document.getElementById('series-link');try{await navigator.clipboard.writeText(t.textContent);e.target.textContent='Copied'}catch(_){const r=document.createRange();r.selectNodeContents(t);const s=getSelection();s.removeAllRanges();s.addRange(r);e.target.textContent='Selected'}});
</script>
"""

if __name__ == "__main__":
    log = json.load(open(sys.argv[1], encoding="utf-8"))
    open(sys.argv[2], "w", encoding="utf-8").write(page(log))
    print("wrote", sys.argv[2])
