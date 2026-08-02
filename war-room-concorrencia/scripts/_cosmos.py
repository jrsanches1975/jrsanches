"""
Arte cósmica GERADA PROCEDURALMENTE (SVG) + tokens do tema "cosmos" do war room.

Por que gerada e não baixada: a rede deste ambiente é bloqueada para hosts
arbitrários, e imagem de terceiro traria problema de direito de uso. Tudo aqui é
desenhado com gradientes/formas SVG e um starfield determinístico (seed fixa),
então o HTML continua 100% autocontido e reproduzível — a mesma seed sempre gera
o mesmo céu.

Exporta:
  · COSMOS_TOKENS_CSS  — paleta e utilitários do tema (violeta→magenta→ciano)
  · hero_svg(...)      — nebulosa com disco de acreção, buraco negro e cometa
  · nebula_strip_svg() — faixa de nebulosa suave para usar como divisor/fundo
  · planet_svg(...)    — planeta/orbe decorativo para cantos de seção

Nada aqui carrega dado: é só decoração. Nenhum número do dashboard passa por
este módulo.
"""

# ------------------------------------------------------------------ starfield
def _rng(seed):
    """LCG minúsculo — determinístico e sem depender de random(), para o mesmo
    céu ser gerado em qualquer máquina/execução."""
    estado = seed & 0xFFFFFFFF

    def prox():
        nonlocal estado
        estado = (1103515245 * estado + 12345) & 0x7FFFFFFF
        return estado / 0x7FFFFFFF
    return prox


def _starfield(w, h, n, seed, r_max=1.5, opac=(0.25, 0.95)):
    r = _rng(seed)
    partes = []
    for _ in range(n):
        x, y = r() * w, r() * h
        rr = 0.25 + r() * r_max
        op = opac[0] + r() * (opac[1] - opac[0])
        # algumas estrelas ganham brilho de 4 pontas
        if r() > 0.94:
            l = rr * 5
            partes.append(
                f'<g opacity="{op:.2f}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{rr:.2f}" fill="#fff"/>'
                f'<path d="M{x:.1f} {y - l:.1f}V{y + l:.1f}M{x - l:.1f} {y:.1f}H{x + l:.1f}" '
                f'stroke="#fff" stroke-width=".5" stroke-linecap="round" opacity=".55"/></g>')
        else:
            partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rr:.2f}" fill="#fff" opacity="{op:.2f}"/>')
    return "".join(partes)


# --------------------------------------------------------------------- tokens
COSMOS_TOKENS_CSS = """
  :root {
    --violet: #8b5cf6; --violet-soft: rgba(139,92,246,.16);
    --magenta: #d946ef; --cyan: #22d3ee; --indigo: #6366f1;
    --grad-hero: linear-gradient(96deg, #a78bfa 0%, #d946ef 52%, #22d3ee 100%);
    --grad-cta: linear-gradient(96deg, #8b5cf6, #d946ef);
    --grad-line: linear-gradient(90deg, transparent, #8b5cf6, #d946ef, #22d3ee, transparent);
  }
  /* título com gradiente cósmico (a linha de cima fica branca, a de baixo pinta) */
  .cosmos-grad {
    background: var(--grad-hero); -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent; color: transparent;
  }
  /* moldura de vidro com halo — usada nas seções e nos cards de destaque */
  .cosmos-frame { position: relative; }
  .cosmos-frame::before {
    content: ""; position: absolute; inset: -1px; border-radius: inherit; pointer-events: none;
    background: var(--grad-line); opacity: .28;
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude; padding: 1px;
  }
  /* divisor de seção no estilo da referência (cantos recortados + régua) */
  .cosmos-divider {
    position: relative; height: 1px; margin: 34px 0 26px; background: var(--grad-line); opacity: .5;
  }
  .cosmos-divider::before, .cosmos-divider::after {
    content: ""; position: absolute; top: -5px; width: 11px; height: 11px;
    border-top: 1px solid var(--violet); opacity: .8;
  }
  .cosmos-divider::before { left: 0; border-left: 1px solid var(--violet); }
  .cosmos-divider::after { right: 0; border-right: 1px solid var(--violet); }
  /* arte de fundo posicionada */
  .cosmos-hero-art {
    position: absolute; right: -4%; top: -14%; width: min(58%, 720px); pointer-events: none;
    z-index: 0; opacity: .95;
  }
  .cosmos-hero-art svg { width: 100%; height: auto; display: block; }
  .cosmos-orb {
    position: absolute; pointer-events: none; z-index: 0; opacity: .5;
  }
  @media (max-width: 900px) { .cosmos-hero-art { display: none; } }
"""


# ----------------------------------------------------------------------- hero
def hero_svg(w=760, h=560, seed=20260801):
    """Nebulosa com disco de acreção + buraco negro + cometa. Puramente
    decorativo (aria-hidden) — não representa nenhum dado."""
    estrelas = _starfield(w, h, 190, seed)
    cx, cy = w * 0.60, h * 0.40
    return f"""<svg viewBox="0 0 {w} {h}" aria-hidden="true" focusable="false">
  <defs>
    <radialGradient id="cx-neb1" cx="50%" cy="50%">
      <stop offset="0%" stop-color="#c084fc" stop-opacity=".55"/>
      <stop offset="45%" stop-color="#7c3aed" stop-opacity=".28"/>
      <stop offset="100%" stop-color="#4c1d95" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="cx-neb2" cx="50%" cy="50%">
      <stop offset="0%" stop-color="#f0abfc" stop-opacity=".42"/>
      <stop offset="55%" stop-color="#d946ef" stop-opacity=".18"/>
      <stop offset="100%" stop-color="#a21caf" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="cx-neb3" cx="50%" cy="50%">
      <stop offset="0%" stop-color="#67e8f9" stop-opacity=".34"/>
      <stop offset="60%" stop-color="#0891b2" stop-opacity=".14"/>
      <stop offset="100%" stop-color="#164e63" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="cx-disk" x1="0%" y1="50%" x2="100%" y2="50%">
      <stop offset="0%" stop-color="#22d3ee" stop-opacity=".05"/>
      <stop offset="18%" stop-color="#818cf8" stop-opacity=".55"/>
      <stop offset="42%" stop-color="#f5d0fe" stop-opacity=".95"/>
      <stop offset="58%" stop-color="#fdba74" stop-opacity=".9"/>
      <stop offset="80%" stop-color="#c026d3" stop-opacity=".5"/>
      <stop offset="100%" stop-color="#7c3aed" stop-opacity=".05"/>
    </linearGradient>
    <linearGradient id="cx-disk2" x1="0%" y1="50%" x2="100%" y2="50%">
      <stop offset="0%" stop-color="#a78bfa" stop-opacity="0"/>
      <stop offset="35%" stop-color="#fef3c7" stop-opacity=".85"/>
      <stop offset="65%" stop-color="#fbcfe8" stop-opacity=".7"/>
      <stop offset="100%" stop-color="#22d3ee" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="cx-comet" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fff" stop-opacity="0"/>
      <stop offset="70%" stop-color="#a5f3fc" stop-opacity=".65"/>
      <stop offset="100%" stop-color="#fff" stop-opacity=".95"/>
    </linearGradient>
    <radialGradient id="cx-glow" cx="50%" cy="50%">
      <stop offset="0%" stop-color="#fff" stop-opacity=".9"/>
      <stop offset="35%" stop-color="#e9d5ff" stop-opacity=".35"/>
      <stop offset="100%" stop-color="#a855f7" stop-opacity="0"/>
    </radialGradient>
    <filter id="cx-blur"><feGaussianBlur stdDeviation="9"/></filter>
    <filter id="cx-blur-s"><feGaussianBlur stdDeviation="2.4"/></filter>
  </defs>

  <!-- nuvens de nebulosa -->
  <ellipse cx="{cx - 40}" cy="{cy - 20}" rx="{w * .48}" ry="{h * .40}" fill="url(#cx-neb1)"/>
  <ellipse cx="{cx + 120}" cy="{cy + 90}" rx="{w * .34}" ry="{h * .28}" fill="url(#cx-neb2)"/>
  <ellipse cx="{cx - 170}" cy="{cy + 130}" rx="{w * .30}" ry="{h * .24}" fill="url(#cx-neb3)"/>

  <!-- estrelas -->
  <g>{estrelas}</g>

  <!-- disco de acreção: elipses achatadas em perspectiva -->
  <g transform="translate({cx} {cy}) rotate(-22)">
    <ellipse rx="252" ry="74" fill="none" stroke="url(#cx-disk)" stroke-width="30" opacity=".5" filter="url(#cx-blur)"/>
    <ellipse rx="234" ry="62" fill="none" stroke="url(#cx-disk)" stroke-width="15" opacity=".92"/>
    <ellipse rx="206" ry="47" fill="none" stroke="url(#cx-disk2)" stroke-width="7" opacity=".85"/>
    <ellipse rx="182" ry="35" fill="none" stroke="#fff7ed" stroke-width="2.2" opacity=".5"/>
    <!-- halo de fóton -->
    <circle r="96" fill="none" stroke="#fde68a" stroke-width="2" opacity=".45" filter="url(#cx-blur-s)"/>
    <circle r="88" fill="none" stroke="#fff" stroke-width="1.1" opacity=".55"/>
    <!-- horizonte de eventos -->
    <circle r="82" fill="#04010c"/>
    <circle r="82" fill="none" stroke="#c4b5fd" stroke-width=".8" opacity=".35"/>
  </g>

  <!-- planeta secundário -->
  <g transform="translate({w * .90} {h * .60})">
    <circle r="30" fill="url(#cx-glow)" opacity=".5"/>
    <circle r="21" fill="#150b2e"/>
    <path d="M-21 0a21 21 0 0 1 42 0" fill="#3b1f6b" opacity=".85"/>
    <circle r="21" fill="none" stroke="#a78bfa" stroke-width=".7" opacity=".5"/>
  </g>

  <!-- cometa -->
  <g transform="translate({w * .74} {h * .80}) rotate(38)">
    <path d="M-190 0 L0 0" stroke="url(#cx-comet)" stroke-width="3.2" stroke-linecap="round"/>
    <path d="M-120 0 L0 0" stroke="#fff" stroke-width="1.2" stroke-linecap="round" opacity=".8"/>
    <circle r="18" fill="url(#cx-glow)"/>
    <circle r="4.2" fill="#fff"/>
  </g>
</svg>"""


def nebula_strip_svg(w=1240, h=180, seed=7723):
    """Faixa suave de nebulosa — fundo discreto para uma seção larga."""
    estrelas = _starfield(w, h, 90, seed, r_max=1.0, opac=(0.15, 0.7))
    return f"""<svg viewBox="0 0 {w} {h}" aria-hidden="true" focusable="false" preserveAspectRatio="none">
  <defs>
    <radialGradient id="cs-s1" cx="50%" cy="50%">
      <stop offset="0%" stop-color="#a855f7" stop-opacity=".34"/>
      <stop offset="100%" stop-color="#6d28d9" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="cs-s2" cx="50%" cy="50%">
      <stop offset="0%" stop-color="#22d3ee" stop-opacity=".22"/>
      <stop offset="100%" stop-color="#0e7490" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="cs-s3" cx="50%" cy="50%">
      <stop offset="0%" stop-color="#d946ef" stop-opacity=".26"/>
      <stop offset="100%" stop-color="#86198f" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <ellipse cx="{w * .22}" cy="{h * .5}" rx="{w * .28}" ry="{h * .8}" fill="url(#cs-s1)"/>
  <ellipse cx="{w * .58}" cy="{h * .42}" rx="{w * .24}" ry="{h * .7}" fill="url(#cs-s3)"/>
  <ellipse cx="{w * .87}" cy="{h * .58}" rx="{w * .22}" ry="{h * .75}" fill="url(#cs-s2)"/>
  <g>{estrelas}</g>
</svg>"""


def planet_svg(size=120, tom="violet"):
    """Orbe decorativo para canto de seção."""
    cores = {
        "violet": ("#2e1065", "#7c3aed", "#c4b5fd"),
        "magenta": ("#4a044e", "#c026d3", "#f5d0fe"),
        "cyan": ("#083344", "#0891b2", "#a5f3fc"),
    }
    escuro, medio, claro = cores.get(tom, cores["violet"])
    uid = tom
    return f"""<svg viewBox="0 0 100 100" width="{size}" height="{size}" aria-hidden="true" focusable="false">
  <defs>
    <radialGradient id="pl-{uid}" cx="34%" cy="30%">
      <stop offset="0%" stop-color="{claro}" stop-opacity=".95"/>
      <stop offset="45%" stop-color="{medio}" stop-opacity=".7"/>
      <stop offset="100%" stop-color="{escuro}" stop-opacity=".95"/>
    </radialGradient>
    <radialGradient id="plg-{uid}" cx="50%" cy="50%">
      <stop offset="60%" stop-color="{medio}" stop-opacity=".35"/>
      <stop offset="100%" stop-color="{medio}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <circle cx="50" cy="50" r="46" fill="url(#plg-{uid})"/>
  <circle cx="50" cy="50" r="30" fill="url(#pl-{uid})"/>
  <ellipse cx="50" cy="50" rx="45" ry="12" fill="none" stroke="{claro}" stroke-width="1.4"
           opacity=".55" transform="rotate(-18 50 50)"/>
  <ellipse cx="50" cy="50" rx="45" ry="12" fill="none" stroke="{medio}" stroke-width="3"
           opacity=".3" transform="rotate(-18 50 50)"/>
</svg>"""
