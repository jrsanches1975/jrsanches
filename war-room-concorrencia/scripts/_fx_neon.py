"""
Camada de efeitos visuais do tema técnico/neon do war_room.py — separada do
_effects.py (que é o tema cockpit usado por gerar_demo_live.py e
gerar_simulador.py).

Injete assim no HTML gerado:
  - FX_CSS   logo antes de </style>
  - FX_BODY  logo depois de <body> (camadas de ambiente + shell do modal)
  - FX_JS    logo antes de </body>

O que entra aqui:
  · campo de partículas em canvas com parallax de mouse (ambiente)
  · aurora/glow que deriva devagar + varredura de scanline
  · "lente": spotlight que segue o mouse, vidro (backdrop-filter) nos painéis,
    tilt 3D com reflexo de vidro percorrendo o card
  · neon: glow pulsante em item crítico, border-beam girando na etapa ativa do
    pipeline, anel do selo girando com sweep de radar
  · movimento: revelação em cascata no scroll, contadores animados, linha do
    gráfico se desenhando, troca de aba com crossfade
  · popups: modal de detalhe do battlecard e de qualquer linha de tabela,
    tooltip nos pontos do gráfico
  · botões: ripple no clique, chips de filtro de severidade que filtram de
    verdade os battlecards

Tudo respeita prefers-reduced-motion: o ambiente desenha um frame estático, as
animações contínuas param, e as interações (modal, filtro, ripple desligado)
continuam funcionando.
"""

FX_CSS = """
  /* ---------------------------------------------------------------- ambiente */
  #fx-particles {
    position: fixed; inset: 0; z-index: 0; pointer-events: none; display: block;
  }
  #fx-aurora {
    position: fixed; inset: -20%; z-index: -1; pointer-events: none; opacity: .85;
    background:
      radial-gradient(38% 30% at 22% 18%, rgba(17,135,240,.30), transparent 65%),
      radial-gradient(32% 26% at 78% 12%, rgba(85,174,255,.22), transparent 65%),
      radial-gradient(34% 30% at 62% 76%, rgba(17,135,240,.16), transparent 68%);
    filter: blur(38px);
    animation: fx-drift 34s ease-in-out infinite alternate;
  }
  @keyframes fx-drift {
    0%   { transform: translate3d(0,0,0) scale(1); }
    50%  { transform: translate3d(2.5%, -2%, 0) scale(1.06); }
    100% { transform: translate3d(-2%, 2.5%, 0) scale(1.03); }
  }
  #fx-scan {
    position: fixed; left: 0; right: 0; top: 0; height: 34vh; z-index: 0; pointer-events: none;
    background: linear-gradient(to bottom, transparent, rgba(85,174,255,.05) 45%, transparent);
    animation: fx-scan-move 11s linear infinite;
  }
  @keyframes fx-scan-move { 0% { transform: translateY(-40vh); } 100% { transform: translateY(140vh); } }
  #fx-spotlight {
    position: fixed; inset: 0; z-index: 1; pointer-events: none; mix-blend-mode: soft-light;
    background: radial-gradient(260px circle at var(--sx, -999px) var(--sy, -999px),
                                rgba(140,200,255,.5), transparent 70%);
    transition: opacity .3s ease; opacity: 0;
  }
  body.fx-pointer #fx-spotlight { opacity: 1; }
  header.top, .pipeline, .status-banner, .tabs, .shell { position: relative; z-index: 2; }

  /* ------------------------------------------------------------------- vidro */
  .tabs, .gauge, .squadron-card, .hist-chart-card, .card, .selecao-coluna,
  .credbar, .data-table-wrap, .ml-radar-table-wrap, .pipe-step {
    backdrop-filter: blur(16px) saturate(135%); -webkit-backdrop-filter: blur(16px) saturate(135%);
  }

  /* -------------------------------------------------------- neon / tipografia */
  h1.cover-title em {
    text-shadow: 0 0 26px rgba(17,135,240,.55), 0 0 62px rgba(17,135,240,.28);
  }
  .gauge-value { text-shadow: 0 0 22px rgba(85,174,255,.35); }
  .pill-badge { box-shadow: 0 0 22px -8px rgba(17,135,240,.8), inset 0 0 18px -10px rgba(17,135,240,.9); }
  .status-pill.alta { animation: fx-alert-breathe 2.6s ease-in-out infinite; }
  @keyframes fx-alert-breathe {
    0%, 100% { box-shadow: 0 0 0 rgba(224,66,107,0); }
    50%      { box-shadow: 0 0 30px -6px rgba(224,66,107,.75); }
  }
  .card.sev-alta::before {
    content: ""; position: absolute; inset: -1px; border-radius: inherit; pointer-events: none;
    box-shadow: 0 0 26px -8px rgba(224,66,107,.6); animation: fx-alert-breathe 2.8s ease-in-out infinite;
  }

  /* border-beam girando na etapa ativa do pipeline (o quadrado gira DENTRO do
     card, com overflow:hidden, para a ponta do gradiente nunca vazar) */
  .pipe-step.on { position: relative; isolation: isolate; overflow: hidden; }
  .pipe-step.on::before {
    content: ""; position: absolute; top: 50%; left: 50%; width: 200%; height: 0; padding-bottom: 200%;
    margin: -100% 0 0 -100%; z-index: 0;
    background: conic-gradient(from 0deg, transparent 0 60%, #8fd0ff 80%, #ffffff 88%, transparent 96%);
    animation: fx-beam 3.4s linear infinite;
  }
  .pipe-step.on::after {
    content: ""; position: absolute; inset: 1.5px; border-radius: 9px; z-index: 1;
    background: #0a1526;
  }
  .pipe-step.on > * { position: relative; z-index: 2; }
  @keyframes fx-beam { to { transform: rotate(1turn); } }

  /* pulso viajando pelas setas do pipeline */
  .pipe-arrow { position: relative; overflow: hidden; }
  .pipe-arrow::after {
    content: ""; position: absolute; left: -30%; top: 50%; width: 26%; height: 2px; margin-top: -1px;
    background: linear-gradient(90deg, transparent, var(--accent-strong), transparent);
    animation: fx-pulse-travel 2.6s ease-in-out infinite; animation-delay: var(--pd, 0s);
  }
  @keyframes fx-pulse-travel {
    0%   { left: -35%; opacity: 0; }
    25%  { opacity: 1; }
    75%  { opacity: 1; }
    100% { left: 110%; opacity: 0; }
  }

  /* selo: anel externo girando + sweep de radar */
  .seal-spin { transform-origin: 64px 64px; animation: fx-seal-spin 26s linear infinite; }
  @keyframes fx-seal-spin { to { transform: rotate(1turn); } }
  .seal-sweep {
    transform-origin: 64px 64px; animation: fx-seal-spin 4.6s linear infinite;
    fill: url(#seal-sweep-grad);
  }

  /* ------------------------------------------------------- lente 3D nos cards */
  .card {
    transform-style: preserve-3d;
    transition: transform .28s cubic-bezier(.2,.7,.3,1), box-shadow .28s ease, border-color .28s ease;
  }
  .card::after {
    content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none; opacity: 0;
    background: radial-gradient(320px circle at var(--gx, 50%) var(--gy, 0%),
                                rgba(160,215,255,.20), transparent 62%);
    transition: opacity .28s ease;
  }
  .card.fx-tilt::after { opacity: 1; }
  .card.fx-tilt {
    box-shadow: 0 26px 50px -22px rgba(0,0,0,.85), 0 0 34px -12px rgba(17,135,240,.55);
    border-color: var(--border-strong);
  }
  .card[data-alerta-idx] { cursor: pointer; }
  .card .fx-open-hint {
    position: absolute; right: 14px; bottom: 14px; font-size: .62rem; letter-spacing: .12em;
    text-transform: uppercase; color: var(--accent-strong); opacity: 0; transition: opacity .25s ease;
    font-weight: 700; pointer-events: none;
  }
  .card.fx-tilt .fx-open-hint { opacity: .95; }

  /* ---------------------------------------------- revelação em cascata (scroll) */
  .fx-reveal { opacity: 0; transform: translateY(18px); }
  .fx-reveal.in {
    opacity: 1; transform: none;
    transition: opacity .55s cubic-bezier(.2,.7,.3,1) var(--rd, 0s),
                transform .55s cubic-bezier(.2,.7,.3,1) var(--rd, 0s);
  }

  /* ------------------------------------------------------------ chips de filtro */
  .fx-filterbar {
    display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px;
  }
  .fx-filterbar .fx-flabel {
    font-size: .62rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
    color: var(--text-mute); margin-right: 4px;
  }
  .fx-chip {
    font-family: inherit; font-size: .72rem; font-weight: 700; letter-spacing: .04em; cursor: pointer;
    padding: 6px 13px; border-radius: 999px; border: 1px solid var(--border); background: var(--surface-2);
    color: var(--text-dim); position: relative; overflow: hidden;
    transition: color .18s, border-color .18s, background .18s, box-shadow .18s;
  }
  .fx-chip:hover { color: var(--text); border-color: var(--border-strong); }
  .fx-chip[aria-pressed="true"] {
    color: #fff; border-color: var(--accent); background: rgba(17,135,240,.18);
    box-shadow: 0 0 20px -6px rgba(17,135,240,.85);
  }
  .fx-chip.sev-alta[aria-pressed="true"] {
    border-color: var(--critical); background: var(--critical-bg); box-shadow: 0 0 20px -6px rgba(224,66,107,.85);
  }
  .fx-chip.sev-media[aria-pressed="true"] {
    border-color: var(--warning); background: var(--warning-bg); box-shadow: 0 0 20px -6px rgba(250,178,25,.8);
  }
  .fx-chip-count {
    display: inline-block; margin-left: 6px; font-variant-numeric: tabular-nums; opacity: .75;
  }
  .card.fx-hidden { display: none; }
  .fx-empty-filter {
    grid-column: 1 / -1; padding: 40px; text-align: center; color: var(--text-mute); font-size: .86rem;
    border: 1px dashed var(--border); border-radius: 10px;
  }

  /* ---------------------------------------------------------------- ripple */
  .btn, .btn-mini, .tab-btn, .fx-chip { position: relative; overflow: hidden; }
  .fx-ripple {
    position: absolute; border-radius: 50%; transform: translate(-50%, -50%) scale(0);
    background: radial-gradient(circle, rgba(190,225,255,.55), rgba(190,225,255,0) 70%);
    pointer-events: none; animation: fx-ripple-go .62s ease-out forwards;
  }
  @keyframes fx-ripple-go { to { transform: translate(-50%, -50%) scale(1); opacity: 0; } }

  /* ----------------------------------------------------------------- modal */
  #fx-modal {
    position: fixed; inset: 0; z-index: 90; display: none; align-items: center; justify-content: center;
    padding: 24px;
  }
  #fx-modal.open { display: flex; }
  #fx-modal-backdrop {
    position: absolute; inset: 0; background: rgba(2,5,12,.72);
    backdrop-filter: blur(9px) saturate(120%); -webkit-backdrop-filter: blur(9px) saturate(120%);
    animation: fx-fade-in .22s ease;
  }
  @keyframes fx-fade-in { from { opacity: 0; } to { opacity: 1; } }
  #fx-modal-card {
    position: relative; width: min(760px, 100%); max-height: min(84vh, 900px); overflow-y: auto;
    background: linear-gradient(180deg, rgba(13,28,54,.96), rgba(7,14,30,.98));
    border: 1px solid var(--border-strong); border-radius: 14px; padding: 26px 28px 24px;
    box-shadow: 0 40px 90px -30px rgba(0,0,0,.95), 0 0 60px -18px rgba(17,135,240,.5);
    animation: fx-modal-in .3s cubic-bezier(.2,.8,.3,1);
  }
  @keyframes fx-modal-in {
    from { opacity: 0; transform: translateY(22px) scale(.97); }
    to   { opacity: 1; transform: none; }
  }
  #fx-modal-card::before {
    content: ""; position: absolute; left: 0; right: 0; top: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent-strong), transparent);
  }
  #fx-modal-close {
    position: absolute; top: 16px; right: 16px; width: 32px; height: 32px; border-radius: 8px;
    background: var(--surface-2); border: 1px solid var(--border); color: var(--text-dim);
    font-size: 1rem; cursor: pointer; line-height: 1;
  }
  #fx-modal-close:hover { color: #fff; border-color: var(--border-strong); }
  .fx-modal-eyebrow {
    font-size: .62rem; font-weight: 700; letter-spacing: .16em; text-transform: uppercase;
    color: var(--accent-strong); margin-bottom: 8px;
  }
  .fx-modal-title {
    margin: 0 0 18px; font-size: 1.3rem; font-weight: 800; letter-spacing: -.01em; padding-right: 40px;
  }
  .fx-modal-dl { display: grid; grid-template-columns: minmax(120px, 190px) 1fr; gap: 1px; }
  .fx-modal-dl > div {
    padding: 10px 12px; background: rgba(255,255,255,.025); font-size: .84rem;
  }
  .fx-modal-dl .k {
    color: var(--accent-strong); font-size: .64rem; font-weight: 700; letter-spacing: .1em;
    text-transform: uppercase; padding-top: 13px;
  }
  .fx-modal-dl .v { color: var(--text-dim); line-height: 1.55; }
  .fx-modal-dl .v ul { margin: 0; padding-left: 16px; }
  .fx-modal-dl .v li { margin-bottom: 5px; }
  .fx-modal-foot {
    margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--border);
    display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between;
    font-size: .74rem; color: var(--text-mute);
  }

  /* --------------------------------------------------------------- tooltip */
  #fx-tip {
    position: fixed; z-index: 95; pointer-events: none; opacity: 0; transform: translate(-50%, -118%);
    background: rgba(7,16,32,.97); border: 1px solid var(--border-strong); border-radius: 8px;
    padding: 8px 11px; font-size: .74rem; color: var(--text); white-space: nowrap; max-width: 320px;
    box-shadow: 0 14px 30px -12px rgba(0,0,0,.9); transition: opacity .14s ease;
  }
  #fx-tip.show { opacity: 1; }
  #fx-tip b { color: var(--accent-strong); font-weight: 700; }
  .hist-chart-svg circle { cursor: crosshair; }

  /* --------------------------------------------- gráfico: linha se desenhando */
  .hist-linha.fx-draw { stroke-dasharray: var(--len); stroke-dashoffset: var(--len); }
  .hist-linha.fx-draw.in { stroke-dashoffset: 0; transition: stroke-dashoffset 1.5s cubic-bezier(.3,.7,.2,1); }
  .hist-chart-svg circle.fx-pop { opacity: 0; transform: scale(.3); transform-box: fill-box; transform-origin: center; }
  .hist-chart-svg circle.fx-pop.in {
    opacity: 1; transform: none;
    transition: opacity .3s ease var(--pd2, 0s), transform .42s cubic-bezier(.2,1.5,.4,1) var(--pd2, 0s);
  }

  /* linhas de tabela clicáveis + varredura de entrada linha a linha */
  .data-table tbody tr, .ml-radar-table tbody tr { cursor: pointer; transition: background .16s ease; }
  .data-table tbody tr:hover td, .ml-radar-table tbody tr:hover td {
    background: rgba(17,135,240,.11); color: var(--text);
  }
  .data-table tbody tr td:first-child, .ml-radar-table tbody tr td:first-child {
    position: relative;
  }
  .data-table tbody tr:hover td:first-child::before,
  .ml-radar-table tbody tr:hover td:first-child::before {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: var(--accent);
    box-shadow: 0 0 10px var(--accent);
  }
  tr.fx-row { opacity: 0; transform: translateX(-8px); }
  tr.fx-row.in {
    opacity: 1; transform: none;
    transition: opacity .4s ease var(--rowd, 0s), transform .4s cubic-bezier(.2,.8,.3,1) var(--rowd, 0s);
  }
  /* linha "NÓS" no radar pulsa de leve — é a nossa referência na tabela */
  tr.radar-proprio td:first-child::after {
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: var(--accent-strong);
    animation: fx-us-pulse 2.8s ease-in-out infinite;
  }
  @keyframes fx-us-pulse {
    0%, 100% { opacity: .45; box-shadow: none; }
    50% { opacity: 1; box-shadow: 0 0 12px var(--accent-strong); }
  }

  /* ---------------------------------------------- realce de barras/medidores */
  .signal-bar span, .ga4-dev-bar, .ga4-funil-bar { position: relative; overflow: hidden; }
  .signal-bar span::after, .ga4-dev-bar::after, .ga4-funil-bar::after {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,.5), transparent);
    animation: fx-shine 3.6s ease-in-out infinite; animation-delay: var(--sd, 0s);
  }
  @keyframes fx-shine { 0% { transform: translateX(-100%); } 55%, 100% { transform: translateX(230%); } }

  /* KPI da GA4: brilho de borda ao passar o mouse + valor ganhando neon */
  .ga4-kpi { transition: border-color .22s ease, transform .22s ease, box-shadow .22s ease; }
  .ga4-kpi:hover {
    border-color: var(--border-strong); transform: translateY(-3px);
    box-shadow: 0 16px 32px -18px rgba(0,0,0,.85), 0 0 26px -10px rgba(17,135,240,.6);
  }
  .ga4-kpi:hover .ga4-kpi-value { text-shadow: 0 0 24px rgba(85,174,255,.6); }
  .ga4-kpi::after {
    content: ""; position: absolute; inset: 0; pointer-events: none; opacity: 0;
    background: radial-gradient(220px circle at var(--gx, 50%) var(--gy, 0%), rgba(160,215,255,.16), transparent 60%);
    transition: opacity .22s ease;
  }
  .ga4-kpi.fx-tilt::after { opacity: 1; }

  /* quadrantes e diagnóstico com lift */
  .ga4-quad, .ga4-diag, .ga4-dev, .squadron-card, .gauge {
    transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
  }
  .ga4-quad:hover, .ga4-diag:hover, .ga4-dev:hover, .squadron-card:hover, .gauge:hover {
    transform: translateY(-3px); border-color: var(--border-strong);
    box-shadow: 0 16px 32px -18px rgba(0,0,0,.85), 0 0 24px -12px rgba(17,135,240,.5);
  }
  .ga4-diag.sev-alta:hover { box-shadow: 0 16px 32px -18px rgba(0,0,0,.85), 0 0 26px -10px rgba(224,66,107,.6); }

  /* etapa do funil com maior vazamento respira */
  .ga4-funil-linha.vazamento { animation: fx-alert-breathe 3s ease-in-out infinite; }

  @media (prefers-reduced-motion: reduce) {
    #fx-aurora, #fx-scan, .pipe-step.on::before, .pipe-arrow::after,
    .seal-spin, .seal-sweep, .status-pill.alta, .card.sev-alta::before,
    .signal-bar span::after, .ga4-dev-bar::after, .ga4-funil-bar::after,
    .ga4-funil-linha.vazamento, tr.radar-proprio td:first-child::after { animation: none !important; }
    .ga4-funil-bar, .ga4-dev-bar { animation: none !important; width: var(--w) !important; }
    tr.fx-row { opacity: 1; transform: none; }
    .ga4-quad, .ga4-diag, .ga4-dev, .squadron-card, .gauge, .ga4-kpi { transition: none; }
    #fx-spotlight { display: none; }
    .fx-reveal { opacity: 1; transform: none; }
    .hist-linha.fx-draw { stroke-dasharray: none; stroke-dashoffset: 0; }
    .hist-chart-svg circle.fx-pop { opacity: 1; transform: none; }
    .card { transition: none; }
    .fx-ripple { display: none; }
    #fx-modal-card, #fx-modal-backdrop { animation: none; }
  }
"""

FX_BODY = """<canvas id="fx-particles" aria-hidden="true"></canvas>
<div id="fx-aurora" aria-hidden="true"></div>
<div id="fx-scan" aria-hidden="true"></div>
<div id="fx-spotlight" aria-hidden="true"></div>
<div id="fx-tip" role="status" aria-live="polite"></div>
<div id="fx-modal" role="dialog" aria-modal="true" aria-labelledby="fx-modal-title" hidden>
  <div id="fx-modal-backdrop"></div>
  <div id="fx-modal-card">
    <button id="fx-modal-close" type="button" aria-label="Fechar">✕</button>
    <div class="fx-modal-eyebrow" id="fx-modal-eyebrow"></div>
    <h2 class="fx-modal-title" id="fx-modal-title"></h2>
    <div id="fx-modal-body"></div>
  </div>
</div>
"""

FX_JS = """<script>
(function () {
  'use strict';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ============================================================ partículas */
  (function () {
    var cv = document.getElementById('fx-particles');
    if (!cv || !cv.getContext) return;
    var ctx = cv.getContext('2d');
    var pts = [], mx = 0, my = 0, tmx = 0, tmy = 0;
    function size() {
      cv.width = window.innerWidth; cv.height = window.innerHeight;
      var n = Math.min(150, Math.max(40, Math.round(cv.width * cv.height / 16000)));
      pts = [];
      for (var i = 0; i < n; i++) {
        pts.push({
          x: Math.random() * cv.width, y: Math.random() * cv.height,
          r: Math.random() * 1.5 + 0.4, d: Math.random() * 0.55 + 0.12,
          vx: (Math.random() - 0.5) * 0.16, vy: (Math.random() - 0.5) * 0.16,
          ph: Math.random() * 6.28
        });
      }
    }
    size();
    window.addEventListener('resize', size);
    window.addEventListener('mousemove', function (e) {
      tmx = (e.clientX / window.innerWidth - 0.5) * 2;
      tmy = (e.clientY / window.innerHeight - 0.5) * 2;
    });
    var t = 0;
    function frame() {
      mx += (tmx - mx) * 0.045; my += (tmy - my) * 0.045;
      ctx.clearRect(0, 0, cv.width, cv.height);
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        if (!reduce) { p.x += p.vx; p.y += p.vy; }
        if (p.x < -10) p.x = cv.width + 10; if (p.x > cv.width + 10) p.x = -10;
        if (p.y < -10) p.y = cv.height + 10; if (p.y > cv.height + 10) p.y = -10;
        var px = p.x + mx * 26 * p.d, py = p.y + my * 26 * p.d;
        var a = 0.20 + 0.42 * Math.abs(Math.sin(t * 0.6 * p.d + p.ph));
        ctx.beginPath(); ctx.arc(px, py, p.r, 0, 6.2832);
        ctx.fillStyle = 'rgba(140,200,255,' + a.toFixed(3) + ')'; ctx.fill();
        for (var j = i + 1; j < pts.length; j++) {
          var q = pts[j];
          var qx = q.x + mx * 26 * q.d, qy = q.y + my * 26 * q.d;
          var dx = px - qx, dy = py - qy, d2 = dx * dx + dy * dy;
          if (d2 < 13000) {
            ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(qx, qy);
            ctx.strokeStyle = 'rgba(17,135,240,' + (0.13 * (1 - d2 / 13000)).toFixed(3) + ')';
            ctx.lineWidth = 1; ctx.stroke();
          }
        }
      }
      t += 0.016;
      if (!reduce) requestAnimationFrame(frame);
    }
    frame();
  })();

  /* ============================================================= spotlight */
  (function () {
    if (reduce) return;
    var sp = document.getElementById('fx-spotlight');
    if (!sp) return;
    window.addEventListener('mousemove', function (e) {
      document.body.classList.add('fx-pointer');
      sp.style.setProperty('--sx', e.clientX + 'px');
      sp.style.setProperty('--sy', e.clientY + 'px');
    });
    window.addEventListener('mouseleave', function () { document.body.classList.remove('fx-pointer'); });
  })();

  /* ======================================================= tilt 3D + reflexo */
  (function () {
    if (reduce) return;
    document.querySelectorAll('.card').forEach(function (card) {
      card.addEventListener('mousemove', function (e) {
        var r = card.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
        card.classList.add('fx-tilt');
        card.style.transform = 'perspective(900px) rotateY(' + ((px - 0.5) * 5).toFixed(2) +
                               'deg) rotateX(' + ((0.5 - py) * 5).toFixed(2) + 'deg) translateY(-4px)';
        card.style.setProperty('--gx', (px * 100).toFixed(1) + '%');
        card.style.setProperty('--gy', (py * 100).toFixed(1) + '%');
      });
      card.addEventListener('mouseleave', function () {
        card.classList.remove('fx-tilt'); card.style.transform = '';
      });
    });
    // reflexo (sem tilt) nos KPIs da GA4 — mesma lente, movimento mais contido
    document.querySelectorAll('.ga4-kpi').forEach(function (k) {
      k.addEventListener('mousemove', function (e) {
        var r = k.getBoundingClientRect();
        k.classList.add('fx-tilt');
        k.style.setProperty('--gx', (((e.clientX - r.left) / r.width) * 100).toFixed(1) + '%');
        k.style.setProperty('--gy', (((e.clientY - r.top) / r.height) * 100).toFixed(1) + '%');
      });
      k.addEventListener('mouseleave', function () { k.classList.remove('fx-tilt'); });
    });
  })();

  /* ============================= linhas de tabela entrando em cascata + shine */
  (function () {
    document.querySelectorAll('.signal-bar span, .ga4-dev-bar, .ga4-funil-bar').forEach(function (b, i) {
      b.style.setProperty('--sd', (i % 7) * 0.4 + 's');
    });
    var tabelas = document.querySelectorAll('.data-table tbody, .ml-radar-table tbody');
    if (!tabelas.length) return;
    tabelas.forEach(function (tb) {
      Array.prototype.slice.call(tb.rows).forEach(function (tr, i) {
        tr.classList.add('fx-row');
        tr.style.setProperty('--rowd', Math.min(i, 18) * 0.028 + 's');
      });
    });
    function mostrar(tb) {
      Array.prototype.slice.call(tb.rows).forEach(function (tr) { tr.classList.add('in'); });
    }
    if (reduce || !('IntersectionObserver' in window)) {
      tabelas.forEach(mostrar);
      return;
    }
    var io = new IntersectionObserver(function (ens) {
      ens.forEach(function (en) { if (en.isIntersecting) { mostrar(en.target); io.unobserve(en.target); } });
    }, { threshold: 0.02, rootMargin: '0px 0px -4% 0px' });
    tabelas.forEach(function (tb) { io.observe(tb); });
    document.querySelectorAll('.tab-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        setTimeout(function () {
          document.querySelectorAll('.tab-panel.active .data-table tbody, .tab-panel.active .ml-radar-table tbody')
            .forEach(function (tb) {
              if (tb.getBoundingClientRect().top < window.innerHeight * 1.1) mostrar(tb);
            });
        }, 40);
      });
    });
  })();

  /* =========================================== revelação em cascata (scroll) */
  (function () {
    var alvos = [];
    document.querySelectorAll('.tab-panel').forEach(function (panel) {
      var itens = panel.querySelectorAll('section, .card, .gauge, .squadron-card, .hist-chart-card, .credbar, .selecao-coluna');
      itens.forEach(function (el, i) {
        el.classList.add('fx-reveal');
        el.style.setProperty('--rd', Math.min(i, 9) * 0.05 + 's');
        alvos.push(el);
      });
    });
    if (reduce || !('IntersectionObserver' in window)) {
      alvos.forEach(function (el) { el.classList.add('in'); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
    alvos.forEach(function (el) { io.observe(el); });
    // ao trocar de aba, revela o que já está visível no painel novo
    document.querySelectorAll('.tab-btn').forEach(function (b) {
      b.addEventListener('click', function () {
        setTimeout(function () {
          document.querySelectorAll('.tab-panel.active .fx-reveal:not(.in)').forEach(function (el) {
            var r = el.getBoundingClientRect();
            if (r.top < window.innerHeight * 1.05) el.classList.add('in');
          });
        }, 40);
      });
    });
  })();

  /* ========================================================== contadores */
  (function () {
    var els = document.querySelectorAll('[data-count]');
    function run(el) {
      var alvo = parseFloat(el.dataset.count);
      if (isNaN(alvo)) return;
      var dec = parseInt(el.dataset.countDec || '0', 10);
      var pre = el.dataset.countPre || '', suf = el.dataset.countSuf || '';
      // inteiro grande mantém o separador de milhar pt-BR (senão "20310" no lugar de "20.310")
      function fmt(v) {
        if (dec > 0) return v.toFixed(dec).replace('.', ',');
        return Math.round(v).toLocaleString('pt-BR');
      }
      if (reduce) { el.textContent = pre + fmt(alvo) + suf; return; }
      var t0 = null, dur = 1100;
      function step(ts) {
        if (t0 === null) t0 = ts;
        var k = Math.min(1, (ts - t0) / dur);
        var e = 1 - Math.pow(1 - k, 3);
        el.textContent = pre + fmt(alvo * e) + suf;
        if (k < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }
    if (!('IntersectionObserver' in window)) { els.forEach(run); return; }
    var io = new IntersectionObserver(function (ens) {
      ens.forEach(function (en) { if (en.isIntersecting) { run(en.target); io.unobserve(en.target); } });
    }, { threshold: 0.4 });
    els.forEach(function (el) { io.observe(el); });
  })();

  /* ============================================ gráfico: desenho + tooltip */
  (function () {
    var tip = document.getElementById('fx-tip');
    document.querySelectorAll('.hist-linha').forEach(function (ln) {
      var len = 0;
      try { len = ln.getTotalLength(); } catch (e) { return; }
      if (!len) return;
      ln.classList.add('fx-draw');
      ln.style.setProperty('--len', len);
    });
    document.querySelectorAll('.hist-chart-svg circle').forEach(function (c, i) {
      c.classList.add('fx-pop');
      c.style.setProperty('--pd2', (0.35 + Math.min(i, 14) * 0.045) + 's');
    });
    function ligar(svg) {
      svg.querySelectorAll('.hist-linha, circle').forEach(function (el) { el.classList.add('in'); });
    }
    if (reduce || !('IntersectionObserver' in window)) {
      document.querySelectorAll('.hist-chart-svg').forEach(ligar);
    } else {
      var io = new IntersectionObserver(function (ens) {
        ens.forEach(function (en) { if (en.isIntersecting) { ligar(en.target); io.unobserve(en.target); } });
      }, { threshold: 0.25 });
      document.querySelectorAll('.hist-chart-svg').forEach(function (s) { io.observe(s); });
      document.querySelectorAll('.tab-btn').forEach(function (b) {
        b.addEventListener('click', function () {
          setTimeout(function () {
            document.querySelectorAll('.tab-panel.active .hist-chart-svg').forEach(function (s) {
              var r = s.getBoundingClientRect();
              if (r.top < window.innerHeight) ligar(s);
            });
          }, 60);
        });
      });
    }
    if (!tip) return;
    document.addEventListener('mouseover', function (e) {
      var c = e.target.closest ? e.target.closest('.hist-chart-svg circle') : null;
      if (!c) return;
      var t = c.querySelector('title');
      if (!t) return;
      var txt = t.textContent.trim();
      var partes = txt.split(' — ');
      tip.innerHTML = partes.map(function (p, i) { return i === 0 ? '<b>' + p + '</b>' : p; }).join('<br>');
      var r = c.getBoundingClientRect();
      tip.style.left = (r.left + r.width / 2) + 'px';
      tip.style.top = r.top + 'px';
      tip.classList.add('show');
    });
    document.addEventListener('mouseout', function (e) {
      if (e.target.closest && e.target.closest('.hist-chart-svg circle')) tip.classList.remove('show');
    });
  })();

  /* ============================================================== ripple */
  (function () {
    if (reduce) return;
    document.addEventListener('click', function (e) {
      var b = e.target.closest ? e.target.closest('.btn, .btn-mini, .tab-btn, .fx-chip') : null;
      if (!b) return;
      var r = b.getBoundingClientRect();
      var s = document.createElement('span');
      s.className = 'fx-ripple';
      var d = Math.max(r.width, r.height) * 2.2;
      s.style.width = s.style.height = d + 'px';
      s.style.left = (e.clientX - r.left) + 'px';
      s.style.top = (e.clientY - r.top) + 'px';
      b.appendChild(s);
      setTimeout(function () { s.remove(); }, 640);
    });
  })();

  /* ================================================================ modal */
  var MODAL = (function () {
    var wrap = document.getElementById('fx-modal');
    if (!wrap) return { abrir: function () {}, fechar: function () {} };
    var eyebrow = document.getElementById('fx-modal-eyebrow');
    var title = document.getElementById('fx-modal-title');
    var body = document.getElementById('fx-modal-body');
    var ultimoFoco = null;

    function fechar() {
      wrap.classList.remove('open'); wrap.hidden = true;
      document.body.style.overflow = '';
      if (ultimoFoco && ultimoFoco.focus) ultimoFoco.focus();
    }
    function abrir(eb, tt, html) {
      ultimoFoco = document.activeElement;
      eyebrow.textContent = eb; title.textContent = tt; body.innerHTML = html;
      wrap.hidden = false; wrap.classList.add('open');
      document.body.style.overflow = 'hidden';
      document.getElementById('fx-modal-close').focus();
    }
    document.getElementById('fx-modal-close').addEventListener('click', fechar);
    document.getElementById('fx-modal-backdrop').addEventListener('click', fechar);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && wrap.classList.contains('open')) fechar();
    });
    return { abrir: abrir, fechar: fechar };
  })();

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function dl(pares) {
    return '<div class="fx-modal-dl">' + pares.map(function (p) {
      return '<div class="k">' + esc(p[0]) + '</div><div class="v">' + p[1] + '</div>';
    }).join('') + '</div>';
  }

  /* --- popup do battlecard (dado real do alerta, vindo do payload JSON) --- */
  (function () {
    var el = document.getElementById('fx-alertas-data');
    if (!el) return;
    var alertas;
    try { alertas = JSON.parse(el.textContent); } catch (e) { return; }
    document.querySelectorAll('.card[data-alerta-idx]').forEach(function (card) {
      var hint = document.createElement('span');
      hint.className = 'fx-open-hint';
      hint.textContent = 'clique p/ detalhe';
      card.appendChild(hint);
      card.setAttribute('tabindex', '0');
      card.setAttribute('role', 'button');
      function abrir() {
        var a = alertas[parseInt(card.dataset.alertaIdx, 10)];
        if (!a) return;
        var pares = [
          ['Severidade', esc((a.severidade || '').toUpperCase()) + ' · nível ' + esc(a.nivel)],
          ['Tipo', esc((a.tipo || '').replace(/_/g, ' '))],
          ['Produto', esc(a.produto)],
          ['Concorrente', esc(a.concorrente)],
          ['O que mudou', esc(a.resumo)],
          ['Impacto na concorrência', esc(a.impacto_concorrencia)],
          ['Impacto no volume', esc(a.impacto_volume)],
          ['Estratégia imediata', '<ul>' + (a.estrategia || []).map(function (s) {
            return '<li>' + esc(s) + '</li>'; }).join('') + '</ul>'],
          ['KPIs impactados', esc((a.kpis || []).join(' · '))]
        ];
        if (a.agente_nome) {
          pares.push(['Agente responsável', esc(a.agente_emblema || '') + ' ' + esc(a.agente_nome) +
            (a.status_acao ? ' — <b>' + esc(a.status_acao.replace(/_/g, ' ')) + '</b>' : '')]);
        }
        var foot = '<div class="fx-modal-foot"><span>' + esc(a.data || '') + '</span>' +
          (a.evidencia_url ? '<a href="' + esc(a.evidencia_url) + '" target="_blank" rel="noopener">ver evidência ↗</a>' : '') +
          '</div>';
        MODAL.abrir('Battlecard · ' + esc(a.tipo || '').replace(/_/g, ' '),
                    a.produto + '  vs  ' + a.concorrente, dl(pares) + foot);
      }
      card.addEventListener('click', function (e) {
        if (e.target.closest('a')) return;
        abrir();
      });
      card.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); abrir(); }
      });
    });
  })();

  /* --- popup genérico de linha de tabela (lê os próprios <th> e <td>) --- */
  (function () {
    document.addEventListener('click', function (e) {
      var tr = e.target.closest ? e.target.closest('.data-table tbody tr, .ml-radar-table tbody tr') : null;
      if (!tr || e.target.closest('a')) return;
      var tabela = tr.closest('table');
      var ths = Array.prototype.map.call(tabela.querySelectorAll('thead th'), function (th) {
        return th.textContent.trim();
      });
      var tds = Array.prototype.slice.call(tr.children);
      var pares = tds.map(function (td, i) {
        return [ths[i] || ('Coluna ' + (i + 1)), esc(td.textContent.trim() || '—')];
      }).filter(function (p) { return p[0]; });
      var secao = tr.closest('.tab-panel');
      var eb = secao ? (secao.querySelector('h2') || {}).textContent || 'Detalhe' : 'Detalhe';
      var titulo = tds.length > 1 ? (tds[0].textContent.trim() + ' · ' + tds[1].textContent.trim())
                                  : (tds[0] ? tds[0].textContent.trim() : 'Detalhe');
      MODAL.abrir(eb.trim(), titulo, dl(pares));
    });
  })();

  /* ============================== chips de filtro de severidade (reais) */
  (function () {
    var grid = document.querySelector('.tab-panel[data-tab="visao-geral"] .grid');
    if (!grid) return;
    var cards = Array.prototype.slice.call(grid.querySelectorAll('.card'));
    if (!cards.length) return;
    var contagem = { alta: 0, media: 0, baixa: 0 };
    cards.forEach(function (c) {
      ['alta', 'media', 'baixa'].forEach(function (s) { if (c.classList.contains('sev-' + s)) contagem[s]++; });
    });
    var defs = [
      ['todos', 'Todos', cards.length],
      ['alta', 'Críticos', contagem.alta],
      ['media', 'Atenção', contagem.media],
      ['baixa', 'Nominais', contagem.baixa]
    ].filter(function (d) { return d[0] === 'todos' || d[2] > 0; });

    var bar = document.createElement('div');
    bar.className = 'fx-filterbar';
    bar.innerHTML = '<span class="fx-flabel">Filtrar</span>' + defs.map(function (d, i) {
      return '<button type="button" class="fx-chip sev-' + d[0] + '" data-sev="' + d[0] +
             '" aria-pressed="' + (i === 0 ? 'true' : 'false') + '">' + d[1] +
             '<span class="fx-chip-count">' + d[2] + '</span></button>';
    }).join('');
    grid.parentNode.insertBefore(bar, grid);

    var vazio = document.createElement('div');
    vazio.className = 'fx-empty-filter';
    vazio.textContent = 'Nenhum alerta nesta severidade nesta rodada.';
    vazio.style.display = 'none';
    grid.appendChild(vazio);

    bar.addEventListener('click', function (e) {
      var chip = e.target.closest('.fx-chip');
      if (!chip) return;
      bar.querySelectorAll('.fx-chip').forEach(function (c) { c.setAttribute('aria-pressed', 'false'); });
      chip.setAttribute('aria-pressed', 'true');
      var sev = chip.dataset.sev, visiveis = 0;
      cards.forEach(function (c) {
        var ok = sev === 'todos' || c.classList.contains('sev-' + sev);
        c.classList.toggle('fx-hidden', !ok);
        if (ok) visiveis++;
      });
      vazio.style.display = visiveis ? 'none' : 'block';
    });
  })();

  /* ============================ navegação por teclado nas abas (setas) */
  (function () {
    var btns = Array.prototype.slice.call(document.querySelectorAll('.tab-btn'));
    if (!btns.length) return;
    btns.forEach(function (b, i) {
      b.addEventListener('keydown', function (e) {
        var d = e.key === 'ArrowRight' ? 1 : (e.key === 'ArrowLeft' ? -1 : 0);
        if (!d) return;
        e.preventDefault();
        var alvo = btns[(i + d + btns.length) % btns.length];
        alvo.focus(); alvo.click();
      });
    });
  })();
})();
</script>
"""
