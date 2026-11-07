// drafter.lol browser helper. Inject once per page load with the javascript tool:
//   (paste this whole file) -> creates window.D
// Proven on drafter.lol (Nov 2026). Selectors: champion tiles are img[alt="<Display Name>"];
// slots .blue-pick/.red-pick/.blue-ban/.red-ban; phase header text "Blue ban 26" / "Red pick 15" (number = seconds left).
// Lessons (2026-11-07):
//  - The second pick of a double (B2/B3, R1/R2, B4/B5, R4/R5) can fail with "nobutton" if clicked right after the first lock.
//    Use D.actNext(name): it waits until the board shows the first lock, then acts, and retries once.
//  - While you act by hand, set D.manual = true (D.act/actNext do it for you) so the timeout autopilot can't fire a queued
//    champion in the middle of your clicks. The autopilot fires only at <= threshold seconds; keep its queue current.
//  - Role screen: D.toRoles() until "Confirm roles" shows, then D.arrangeIdx([top, jungle, mid, bot, support]) (slots are in
//    T/J/M/B/S order on the role screen, for both sides), then D.confirmRoles().
//  - Decline the cookie banner (D.clickText('Do not consent')) and the sign-in popup ('Not now').
(() => {
  const D = window.D = window.D || {};
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));
  const visible = (e) => e && e.offsetParent !== null;
  D.sleep = sleep;
  D.clickText = (t) => { const els = [...document.querySelectorAll('button,div,span,p,a')].filter(e => e.innerText?.trim() === t && visible(e)); const el = els[els.length - 1]; if (!el) return 'notfound ' + t; (el.closest('button,[role=button],a') || el).click(); return 'clicked ' + t; };

  // ---- joining ----
  D.btn = (t) => [...document.querySelectorAll('button')].find(b => visible(b) && b.innerText.trim().split('\n')[0].trim().toLowerCase() === t.toLowerCase());
  // D.join('GenG','Red drafter')  or D.join(null,'Spectate')
  D.join = async (teamName, seat) => { const out = []; if (teamName) { const b = D.btn(teamName); if (!b) return 'team button not found: ' + teamName; b.click(); out.push('team ' + teamName); await sleep(700); } const s = D.btn(seat); if (!s) return out.concat('seat not found ' + seat).join(' | '); s.click(); out.push('seat ' + seat); await sleep(1000); return out.join(' | '); };
  D.teams = () => [...document.querySelectorAll('button')].filter(b => visible(b) && /Drafter seat/i.test(b.innerText)).map(b => b.innerText.trim().replace(/\n/g, ' / '));
  D.ready = () => { const b = D.btn('Ready'); if (!b) return 'no Ready button'; b.click(); return 'clicked Ready'; };

  // ---- reading ----
  D.phase = () => { const re = /^(Blue|Red) (ban|pick)\s*(\d*)$/i; const el = [...document.querySelectorAll('div,span,p,h1,h2,h3')].find(e => e.children.length <= 3 && re.test(e.innerText?.trim() || '')); if (!el) return null; const m = el.innerText.trim().match(re); return { side: m[1].toLowerCase(), kind: m[2].toLowerCase(), timer: m[3] ? +m[3] : null, text: el.innerText.trim() }; };
  const idMap = () => { const m = {}; document.querySelectorAll('img[alt]').forEach(i => { const k = (i.src.match(/champions\/(\d+)-/) || [])[1]; if (k && i.alt && i.alt !== 'Ban' && i.alt !== 'Pick') m[k] = i.alt; }); return m; };
  const slotChamp = (el, ids) => { const pk = el.querySelector('img[alt="Pick"]'), bn = el.querySelector('img[alt="Ban"]') || [...el.querySelectorAll('img')].find(i => /champions\/\d+-/.test(i.src));
    if (pk) { const lines = (el.innerText || '').split('\n').map(x => x.trim()).filter(Boolean); const nm = lines.filter(l => !/^(Top|Jungle|Mid|Middle|Bottom|Bot|Support)$/i.test(l)).pop(); return nm || (pk.src.match(/splashes\/([a-z0-9]+)-/) || [])[1] || '?'; }
    if (bn) { const k = (bn.src.match(/champions\/(\d+)-/) || [])[1]; return ids[k] || ('#' + k); } return (el.innerText || '').includes('None') ? 'None' : null; };
  D.state = () => { const ids = idMap(); const read = (sel, rev) => { let a = [...document.querySelectorAll(sel)].map(e => slotChamp(e, ids)); return rev ? a.reverse() : a; };   // red bans are in reversed DOM order
    const unavailable = [...document.querySelectorAll('img[alt]')].filter(i => i.className.includes?.('grayscale') || i.closest('.grayscale')).map(i => i.alt).filter(a => a && a !== 'Ban' && a !== 'Pick');
    return { phase: D.phase(), blue: { bans: read('.blue-ban'), picks: read('.blue-pick') }, red: { bans: read('.red-ban', true), picks: read('.red-pick') }, unavailable: [...new Set(unavailable)], url: location.href }; };
  D.available = (name) => { const i = document.querySelector(`img[alt="${name.replace(/"/g, '\\"')}"]`); return !!i && !(i.className.includes('grayscale') || i.closest('.grayscale')); };
  D.filled = () => document.querySelectorAll('.blue-pick img[alt="Pick"], .red-pick img[alt="Pick"], .blue-ban img[alt="Ban"], .red-ban img[alt="Ban"]').length;

  // ---- acting ----
  // D.act('Orianna') -> selects the tile, polls up to 4 s for the Ban/Pick/Lock button, clicks it. Expect 'did Pick X' / 'did Ban X'.
  D.act = async (name) => {
    const im = document.querySelector(`img[alt="${name}"]`);
    if (!im) return 'nochamp ' + name;
    if (!D.available(name)) return 'unavailable ' + name;
    D.manual = true;
    try {
      im.parentElement.parentElement.click();
      for (let t = 0; t < 20; t++) {
        await sleep(200);
        const b = [...document.querySelectorAll('button')].find(b => /^(Ban|Lock in|Pick|Lock)$/i.test(b.innerText.trim()) && visible(b) && !b.disabled);
        if (b) { const txt = b.innerText.trim(); b.click(); D.lastAct = { name, txt, at: Date.now() }; return 'did ' + txt + ' ' + name; }
        if (t % 5 === 4) im.parentElement.parentElement.click();
      }
      return 'nobutton ' + name;
    } finally { D.manual = false; }
  };
  // Second action of a double: wait for the board to register the previous lock (filled count grows), then act; retry once.
  D.actNext = async (name, prevFilled) => {
    const t0 = Date.now(); while (prevFilled != null && D.filled() <= prevFilled && Date.now() - t0 < 5000) await sleep(200);
    await sleep(600);
    let r = await D.act(name); if (!r.startsWith('did')) { await sleep(900); r += ' | retry: ' + await D.act(name); } return r;
  };
  D.actFirst = async (names) => { for (const n of names) { if (D.available(n)) return D.act(n); } return 'none-available'; };
  // Wait until it is our side's turn (or ms passes). Returns D.state().
  D.waitUs = async (ms = 45000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { const p = D.phase(); if (p && p.side === D.auto.mySide) return D.state(); await sleep(500); } return { timeout: true, s: D.state() }; };

  // ---- autopilot (timeout protection) ----
  // D.auto.start('blue', 5) ; D.auto.set({kind:'ban', names:[...]}) ; fires when it's our turn and timer <= threshold, unless D.manual.
  D.auto = D.auto || {};
  D.auto.queue = D.auto.queue || { ban: [], pick: [] }; D.auto.log = D.auto.log || [];
  D.auto.generic = { ban: [], pick: [] };   // fill your own fallback lists with D.auto.set
  D.auto.set = (q) => { D.auto.queue[q.kind] = q.names || []; return 'queue ' + q.kind + ': ' + (q.names || []).join(', '); };
  D.auto.start = (side, threshold = 5) => {
    D.auto.mySide = side; D.auto.threshold = threshold;
    if (D.auto.timer) clearInterval(D.auto.timer);
    D.auto.timer = setInterval(async () => {
      try {
        const p = D.phase();
        if (!p || p.side !== D.auto.mySide || p.timer == null || p.timer > D.auto.threshold || D.auto.busy || D.manual) return;
        const key = p.text.replace(/\s*\d+$/, '') + '#' + D.filled();
        if (D.auto.firedKey === key) return;
        D.auto.busy = true; D.auto.firedKey = key;
        const r = await D.actFirst([...(D.auto.queue[p.kind] || []), ...(D.auto.generic[p.kind] || [])]);
        D.auto.log.push({ at: new Date().toISOString(), key, r });
        if (!String(r).startsWith('did')) D.auto.firedKey = null;
      } finally { D.auto.busy = false; }
    }, 400);
    return 'autopilot on for ' + side + ' at <=' + threshold + 's';
  };
  D.auto.stop = () => { clearInterval(D.auto.timer); D.auto.timer = null; return 'autopilot off'; };

  // ---- after the draft: role confirmation ----
  const startBtn = (t) => [...document.querySelectorAll('button')].find(x => visible(x) && x.innerText.trim().startsWith(t));
  D.toRoles = async () => { const out = []; for (const t of ['Not now', 'Ready for role confirmation', 'Got it']) { const x = startBtn(t); if (x) { x.click(); out.push(t); await sleep(1200); } } return out.join(', ') || 'nothing to click'; };
  D.waitConfirm = async (ms = 40000) => { const t0 = Date.now(); let log = ''; while (Date.now() - t0 < ms) { if (startBtn('Confirm roles')) return 'confirm ready ' + log; if (!log.includes('Ready')) log += await D.toRoles(); await sleep(700); } return 'no confirm button ' + log; };
  // want = display names in TOP, JUNGLE, MID, BOT, SUPPORT order; swaps our side's slots by clicking two of them.
  D.arrangeIdx = async (want) => { const side = D.auto.mySide || 'blue'; const sl = () => [...document.querySelectorAll('.' + side + '-pick')]; const rr = () => sl().map(e => (e.innerText || '').split('\n').map(x => x.trim()).filter(Boolean).pop()); const log = [];
    for (let i = 0; i < 5; i++) for (let t = 0; t < 4 && rr()[i] !== want[i]; t++) { const j = rr().indexOf(want[i]); if (j < 0) { log.push('missing ' + want[i]); break; } sl()[i].click(); await sleep(600); sl()[j].click(); await sleep(1000); log.push(i + '<->' + j); }
    const now = rr(); return { ok: want.every((w, k) => now[k] === w), now, log }; };
  D.arrange = D.arrangeIdx;
  D.confirmRoles = () => { const x = startBtn('Confirm roles'); if (!x) return 'no Confirm roles button'; x.click(); return 'confirmed'; };
  // After confirming, slots show "Role|Champ" labels: check them with this.
  D.roleLabels = () => ({ blue: [...document.querySelectorAll('.blue-pick')].map(e => e.innerText.replace(/\n/g, '|')), red: [...document.querySelectorAll('.red-pick')].map(e => e.innerText.replace(/\n/g, '|')) });

  // Read every game of a drafter.lol series (works on any series link, no seat needed).
  D.series = async (url) => {
    url = url || location.href;
    const t = await (await fetch(url, { headers: { RSC: '1' } })).text();
    let i = t.indexOf('"drafts":['); if (i < 0) return { error: 'no drafts in RSC payload' };
    i += 9; let d = 0, j = i, inStr = false;
    for (; j < t.length; j++) { const c = t[j];
      if (inStr) { if (c === '\\') j++; else if (c === '"') inStr = false; continue; }
      if (c === '"') inStr = true; else if (c === '[' || c === '{') d++; else if (c === ']' || c === '}') { d--; if (d === 0) { j++; break; } } }
    const arr = JSON.parse(t.slice(i, j)); const used = new Set();
    const games = arr.map((g, k) => { const f = (p) => [1, 2, 3, 4, 5].map(n => g[p + n]).filter(x => x !== undefined);
      const o = { game: k + 1, draftId: g.draftId, done: g.done, patch: g.patch, blue: g.drafterBlue, red: g.drafterRed, blueBans: f('blueBan'), redBans: f('redBan'), bluePicks: f('bluePick'), redPicks: f('redPick'), roles: g.roleAssignments || null };
      [...o.bluePicks, ...o.redPicks].forEach(c => { if (c && c !== 'None') used.add(c); }); return o; });
    return { seriesId: arr[0] && arr[0].seriesId, fearless: arr[0] && arr[0].fearless, games, used: [...used] };
  };
  // Replay a finished simulated draft (both seats' tabs): D.replay(seq, 'blue') / D.replay(seq, 'red'); read D.replayLog.
  D.replay = (seq, side) => {
    D.replayLog = [];
    (async () => {
      for (let n = 0; n < seq.length; n++) {
        if (seq[n][0] !== side) continue;
        for (let i = 0; i < 240; i++) { const p = D.phase(); if (p && p.side === side && D.filled() === n) break; await sleep(250); }
        D.replayLog.push((n + 1) + ' ' + await D.act(seq[n][1]));
      }
      D.replayLog.push('done');
    })();
    return 'replay started for ' + side;
  };
  return 'D ready: ' + Object.keys(D).join(',');
})();
