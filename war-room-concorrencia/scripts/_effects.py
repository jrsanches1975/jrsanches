"""
Efeitos especiais compartilhados pelos 3 geradores de HTML (war_room.py,
gerar_demo_live.py, gerar_simulador.py) — starfield ambiente, boot sequence
de inicialização, materialização aprimorada dos cards e glitch no título.

Import estes 3 blocos e injete:
  - EFFECTS_CSS   logo antes de </style>
  - EFFECTS_BODY_HTML  logo depois de <body> (antes do resto do conteúdo)
  - EFFECTS_JS    logo antes de </body></html>

Tudo respeita prefers-reduced-motion (o starfield desenha 1 frame estático e
para; o boot overlay é pulado; o glitch e o hover-lift não animam).
"""

EFFECTS_CSS = """
  #starfield { position: fixed; inset: 0; z-index: 0; pointer-events: none; display: block; }
  @keyframes rise {
    0% { opacity: 0; transform: translateY(14px) scale(.97); filter: brightness(2.4) saturate(1.7); }
    55% { opacity: 1; filter: brightness(1.25) saturate(1.15); }
    100% { opacity: 1; transform: none; filter: brightness(1) saturate(1); }
  }
  .card { transition: transform .25s ease, box-shadow .25s ease; }
  .card:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 26px -10px rgba(41,255,224,.4), 0 0 0 1px var(--hud-soft);
  }
  @keyframes glitch-flicker {
    0%, 100% { text-shadow: 0 0 10px var(--hud-soft), 0 0 30px rgba(41,255,224,.2); }
    10% { text-shadow: 2px 0 0 #ff3b52, -2px 0 0 #29ffe0, 0 0 10px var(--hud-soft); }
    22% { text-shadow: -3px 0 0 #29ffe0, 3px 0 0 #ff3b52, 0 0 14px var(--hud-soft); }
    35% { text-shadow: 0 0 10px var(--hud-soft); }
    48% { text-shadow: 2px 0 0 #ffb02e, -2px 0 0 #29ffe0; }
    60%, 100% { text-shadow: 0 0 10px var(--hud-soft), 0 0 30px rgba(41,255,224,.2); }
  }
  h1.glitch-active { animation: glitch-flicker .9s steps(1) 1; }
  .boot-overlay {
    position: fixed; inset: 0; z-index: 80; background: var(--void);
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 18px; transition: opacity .6s ease, visibility 0s linear .6s;
  }
  .boot-overlay.done { opacity: 0; visibility: hidden; pointer-events: none; }
  .boot-lines {
    font-family: 'Share Tech Mono', monospace; font-size: .82rem; color: var(--hud);
    min-height: 7.5em; white-space: pre-wrap; text-shadow: 0 0 8px var(--hud-soft);
    max-width: 560px; width: 90vw; margin: 0;
  }
  .boot-bar { width: min(320px, 70vw); height: 3px; background: rgba(255,255,255,.08); border-radius: 2px; overflow: hidden; }
  .boot-bar span { display: block; height: 100%; width: 0%; background: var(--hud); box-shadow: 0 0 8px var(--hud-soft); }
  @media (prefers-reduced-motion: reduce) {
    .boot-overlay { display: none; }
    .card { transition: none; }
    .card:hover { transform: none; }
  }
"""

EFFECTS_BODY_HTML = """<canvas id="starfield" aria-hidden="true"></canvas>
<div class="boot-overlay" id="bootOverlay" aria-hidden="true">
  <pre class="boot-lines" id="bootLines"></pre>
  <div class="boot-bar"><span id="bootBarFill"></span></div>
</div>
"""

EFFECTS_JS = """<script>
(function(){
  var canvas = document.getElementById('starfield');
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext('2d');
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var stars = [];
  function resize(){ canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
  function seed(){
    var n = Math.max(50, Math.floor((canvas.width * canvas.height) / 9000));
    stars = [];
    for (var i = 0; i < n; i++) {
      stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: Math.random() * 1.4 + 0.3,
        phase: Math.random() * Math.PI * 2,
        speed: Math.random() * 0.15 + 0.02
      });
    }
  }
  resize(); seed();
  window.addEventListener('resize', function(){ resize(); seed(); });
  var t = 0;
  function draw(){
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (var i = 0; i < stars.length; i++) {
      var s = stars[i];
      var a = 0.35 + 0.45 * Math.abs(Math.sin(t * s.speed + s.phase));
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(180,255,240,' + a.toFixed(3) + ')';
      ctx.fill();
    }
    t += 0.05;
    if (!reduceMotion) requestAnimationFrame(draw);
  }
  draw();
})();

(function(){
  var overlay = document.getElementById('bootOverlay');
  if (!overlay) return;
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function finish(){
    overlay.classList.add('done');
    var h1 = document.querySelector('h1');
    if (h1) h1.classList.add('glitch-active');
  }
  if (reduceMotion) { finish(); return; }
  var linesEl = document.getElementById('bootLines');
  var barEl = document.getElementById('bootBarFill');
  var lines = [
    '> INICIANDO SISTEMA DE GUERRA COMPETITIVA...',
    '> CARREGANDO TELEMETRIA DE CONCORRENTES...',
    '> SINCRONIZANDO RADAR MERCADO LIVRE...',
    '> ARMANDO ESQUADRAO DE COMBATE...',
    '> SISTEMAS NOMINAIS.'
  ];
  var li = 0, ci = 0, out = '';
  function step(){
    if (li >= lines.length) {
      barEl.style.width = '100%';
      setTimeout(finish, 300);
      return;
    }
    var line = lines[li];
    if (ci <= line.length) {
      linesEl.textContent = out + line.slice(0, ci);
      barEl.style.width = Math.round(((li + ci / line.length) / lines.length) * 100) + '%';
      ci++;
      setTimeout(step, 14);
    } else {
      out += line + '\\n';
      li++; ci = 0;
      setTimeout(step, 140);
    }
  }
  step();
})();
</script>
"""
