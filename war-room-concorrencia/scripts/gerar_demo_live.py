#!/usr/bin/env python3
"""
Gera um dashboard de DEMONSTRAÇÃO com reprodução ao vivo: os mesmos cartões que o
war_room.py gera, só que aparecem um a um (via JS), como se a war room estivesse
monitorando em tempo real — pensado para apresentação/pitch, não para operação.

Reaproveita 100% do motor real (make_alert, playbook, render_card, render_own_kpi)
via import de war_room.py — não reimplementa nada, só monta uma sequência curada de
eventos com dados simulados (auto-contido, não depende de nenhum export real do
Windsor.ai) e troca o HTML final por um com JS de "replay".

Uso:
    python gerar_demo_live.py --config config.example.json --out ../outputs/war-room-live-demo.html
"""
import argparse
import json
import os

import war_room as wr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def montar_sequencia(config, playbook):
    eventos = []

    # --- 1-6: mudanças de Mercado Livre (mesmas fixtures do skill) ---
    ex_dir = os.path.join(SCRIPT_DIR, "examples")
    snap1 = wr.load_json(os.path.join(ex_dir, "ml-simulado-rodada1.json"), {})
    snap2 = wr.load_json(os.path.join(ex_dir, "ml-simulado-rodada2.json"), {})
    own_perf = {
        "Faciderm": {"spend": 6896.95, "impressions": 244496, "clicks": 7431, "ctr_pct": 3.04,
                     "cpc": 0.93, "conversions": 85.76, "conversions_value": 31292.95,
                     "cpa": 80.42, "roas": 4.54, "ga4_sessions": 1912, "ga4_engajamento_pct": 47.9,
                     "ga4_conversao_pct": 19.1, "campanhas": ["google_ads:Pmax - Faciderm."]},
        "Amaze": {"spend": 4615.59, "impressions": 199644, "clicks": 4403, "ctr_pct": 2.21,
                  "cpc": 1.05, "conversions": 43.68, "conversions_value": 16435.63,
                  "cpa": 105.66, "roas": 3.56, "ga4_sessions": 1011, "ga4_engajamento_pct": 53.4,
                  "ga4_conversao_pct": 23.6, "campanhas": ["google_ads:Pmax - Amaze."]},
        "Linha Joie Fit": {"spend": 5412.55, "impressions": 157051, "clicks": 5521, "ctr_pct": 3.52,
                           "cpc": 0.98, "conversions": 72.20, "conversions_value": 22413.58,
                           "cpa": 74.97, "roas": 4.14, "ga4_sessions": 1543, "ga4_engajamento_pct": 44.2,
                           "ga4_conversao_pct": 7.9, "campanhas": ["google_ads:Pmax - Linha Joie Fit"]},
    }
    ordem = {"queda_preco": 0, "novo_desconto": 1, "novo_entrante": 2,
             "salto_visibilidade_ml": 3, "concorrente_sumiu": 4, "aumento_preco_concorrente": 5}
    ml_alertas = wr.diff_precos(snap1, snap2, config, playbook, own_perf=own_perf)
    ml_alertas.sort(key=lambda a: ordem.get(a["tipo"], 99))
    eventos += ml_alertas

    # --- 7: criativo novo de concorrente, com imagem + análise ---
    meta_path = "/tmp/_demo_meta_ads.json"
    wr.save_json(meta_path, {"novos_anuncios": [{
        "concorrente": "Black Skull", "ad_id": "999",
        "titulo": "Faciderm Turbo Lançamento",
        "corpo": "Novo sérum com 40% mais ativo — só essa semana",
        "imagem_url": "https://picsum.photos/seed/faciderm/640/360",
        "url_anuncio": "https://facebook.com/ads/library/?id=999",
    }]})
    analises = {"999": {
        "gancho": "Urgência + prova de resultado (\"40% mais ativo\")",
        "oferta": "Lançamento com preço promocional só na semana",
        "formato": "Imagem única, produto em destaque com selo de novidade",
        "cta": "Comprar agora",
        "observacao": "Mesmo ângulo de 'fórmula turbinada' que a Joie já usa no Faciderm.",
    }}
    eventos += wr.ingest_novos_criativos(meta_path, "Meta Ad Library", playbook, analises)

    # --- 8: pico de interesse (Google Trends) ---
    trends_path = "/tmp/_demo_trends.json"
    wr.save_json(trends_path, {"picos": [
        {"termo": "Black Skull", "media_antiga": 30, "media_nova": 68, "pct": 126.7},
    ]})
    eventos += wr.ingest_picos_trends(trends_path, playbook)

    # --- 9: queda de performance de keyword (leilão) ---
    kw_path = "/tmp/_demo_keyword.json"
    wr.save_json(kw_path, {"quedas": [{
        "campanha": "Search.", "keyword": "whey protein", "nivel": "critica",
        "impression_share_antes": 0.35, "impression_share_agora": 0.0999,
        "rank_lost_antes": 0.20, "rank_lost_agora": 0.45,
        "quality_score_antes": 5.0, "quality_score_agora": 1.0,
        "cpc_medio": 1.22, "first_page_cpc": None, "top_of_page_cpc": None,
        "impressions": 43, "clicks": 6,
        "pontos_de_interferencia": [
            {"dominio": "vitafor.com.br", "aparicoes_no_periodo": 2},
            {"dominio": "mercadolivre.com.br", "aparicoes_no_periodo": 1},
            {"dominio": "gsuplementos.com.br", "aparicoes_no_periodo": 1},
            {"dominio": "shopee.com.br", "aparicoes_no_periodo": 1},
        ],
    }]})
    eventos += wr.ingest_quedas_keyword(kw_path, playbook)

    # --- 10: queda de KPI próprio (aciona o protocolo de diagnóstico) ---
    kpi_path = "/tmp/_demo_kpi.json"
    wr.save_json(kpi_path, {"quedas": [
        {"produto": "Faciderm", "metrica": "roas", "rotulo": "ROAS", "valor_antes": 6.0,
         "valor_agora": 2.0, "delta_pct": -66.7},
    ]})
    eventos += wr.ingest_quedas_kpi_proprio(kpi_path, playbook)

    for p in (meta_path, trends_path, kw_path, kpi_path):
        os.remove(p)

    return eventos, own_perf


def render_demo(eventos, own_perf, config, meta, path):
    cards_json = json.dumps([wr.render_card(a, i) for i, a in enumerate(eventos)])
    resumos_json = json.dumps([
        f"{a['tipo'].replace('_', ' ')} · {a['produto']} × {a['concorrente']}" for a in eventos
    ])
    severidades_json = json.dumps([a["severidade"] for a in eventos])
    own_cards = "".join(wr.render_own_kpi(p, v) for p, v in own_perf.items())

    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>War Room — {config.get('marca', '')} · DEMO AO VIVO</title>
<style>
  @font-face {{
    font-family: 'Orbitron'; font-weight: 400 900; font-style: normal; font-display: swap;
    src: url(data:font/woff2;base64,{wr.FONT_ORBITRON_B64}) format('woff2');
  }}
  @font-face {{
    font-family: 'Share Tech Mono'; font-weight: 400; font-style: normal; font-display: swap;
    src: url(data:font/woff2;base64,{wr.FONT_SHARETECH_B64}) format('woff2');
  }}
  :root {{
    --void: #05070a; --panel: #0b121a; --panel-2: #0f1922; --line: rgba(70,255,224,.18);
    --hud: #29ffe0; --hud-soft: rgba(41,255,224,.45); --hud-dim: rgba(41,255,224,.08);
    --text: #d8f7f0; --text-dim: #6f8f97;
    --alta: #ff3b52; --alta-bg: rgba(255,59,82,.1);
    --media: #ffb02e; --media-bg: rgba(255,176,46,.1);
    --baixa: #39ff9d; --baixa-bg: rgba(57,255,157,.08);
    color-scheme: dark;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ background: var(--void); }}
  body {{
    margin: 0; color: var(--text); position: relative; min-height: 100vh; overflow-x: hidden;
    font-family: 'Share Tech Mono', ui-monospace, "Roboto Mono", monospace;
    background-image:
      linear-gradient(var(--hud-dim) 1px, transparent 1px),
      linear-gradient(90deg, var(--hud-dim) 1px, transparent 1px);
    background-size: 36px 36px;
  }}
  body::before {{
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 5;
    background: radial-gradient(ellipse at 50% 0%, transparent 45%, rgba(0,0,0,.6) 100%);
  }}
  body::after {{
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 6; opacity: .5;
    background: repeating-linear-gradient(to bottom, rgba(0,0,0,0) 0px, rgba(0,0,0,0) 2px,
                 rgba(0,0,0,.18) 3px, rgba(0,0,0,0) 4px);
  }}
  .scan-band {{
    position: fixed; left: 0; right: 0; top: -30vh; height: 30vh; z-index: 4; pointer-events: none;
    background: linear-gradient(to bottom, transparent, rgba(41,255,224,.06), transparent);
    animation: scan 9s linear infinite;
  }}
  @keyframes scan {{ 0% {{ transform: translateY(0); }} 100% {{ transform: translateY(430vh); }} }}
  a {{ color: var(--hud); }}
  h1, h2, .gauge-value {{ font-family: 'Orbitron', sans-serif; }}
  header.frame {{
    display: flex; flex-direction: column; gap: 8px; padding: 20px 32px;
    border-bottom: 1px solid var(--line); background: linear-gradient(180deg, var(--panel), transparent);
    position: relative; z-index: 1;
  }}
  .hud-top-row {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }}
  .eyebrow {{
    font-size: .72rem; letter-spacing: .16em; text-transform: uppercase; color: var(--hud);
    font-weight: 600; opacity: .9;
  }}
  .radar-badge {{
    display: inline-flex; align-items: center; gap: 8px; font-size: .7rem; letter-spacing: .1em;
    text-transform: uppercase; color: var(--text-dim);
  }}
  .radar {{
    width: 14px; height: 14px; border-radius: 50%; border: 1px solid var(--hud-soft); position: relative;
    background: radial-gradient(circle, rgba(41,255,224,.18), transparent 70%);
  }}
  .radar::before {{
    content: ""; position: absolute; inset: 0; border-radius: 50%;
    background: conic-gradient(from 0deg, var(--hud), transparent 35%);
    animation: spin 2.2s linear infinite;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  h1 {{
    margin: 0; font-size: clamp(1.8rem, 4vw, 2.6rem); font-weight: 800; letter-spacing: .02em;
    text-transform: uppercase; color: var(--hud); text-shadow: 0 0 10px var(--hud-soft), 0 0 30px rgba(41,255,224,.2);
    text-wrap: balance;
  }}
  .hud-meta {{ display: flex; flex-wrap: wrap; gap: 18px; font-size: .78rem; color: var(--text-dim);
               font-variant-numeric: tabular-nums; }}
  .hud-meta strong {{ color: var(--text); }}
  #relogio {{ color: var(--hud); }}
  .demo-controls {{ display: flex; gap: 10px; align-items: center; }}
  .demo-btn {{
    font-family: 'Share Tech Mono', monospace; font-size: .74rem; letter-spacing: .06em;
    text-transform: uppercase; background: var(--panel-2); color: var(--hud); border: 1px solid var(--hud-soft);
    padding: 7px 14px; border-radius: 4px; cursor: pointer;
  }}
  .demo-btn:hover {{ background: var(--hud-dim); }}
  .demo-btn:disabled {{ opacity: .4; cursor: default; }}
  .master-caution {{
    margin: 10px 32px 0; padding: 9px 16px; border-radius: 4px; font-size: .78rem; font-weight: 700;
    letter-spacing: .05em; text-transform: uppercase; display: flex; align-items: center; gap: 10px;
    border: 1px solid; z-index: 1; position: relative; transition: all .3s ease;
  }}
  .master-caution .mc-dot {{ width: 8px; height: 8px; border-radius: 50%; flex: none; }}
  .master-caution.alta {{
    color: var(--alta); border-color: var(--alta); background: var(--alta-bg);
    animation: warn-pulse 1.4s ease-in-out infinite;
  }}
  .master-caution.alta .mc-dot {{ background: var(--alta); box-shadow: 0 0 8px var(--alta); }}
  .master-caution.media {{ color: var(--media); border-color: var(--media); background: var(--media-bg); }}
  .master-caution.media .mc-dot {{ background: var(--media); box-shadow: 0 0 8px var(--media); }}
  .master-caution.ok {{ color: var(--baixa); border-color: rgba(57,255,157,.3); background: var(--baixa-bg); }}
  .master-caution.ok .mc-dot {{ background: var(--baixa); box-shadow: 0 0 8px var(--baixa); }}
  @keyframes warn-pulse {{
    0%, 100% {{ box-shadow: 0 0 0 rgba(255,59,82,0); }} 50% {{ box-shadow: 0 0 22px -4px var(--alta); }}
  }}
  .feed {{
    margin: 14px 32px 0; padding: 10px 14px; border: 1px solid var(--line); border-radius: 4px;
    background: var(--panel); font-size: .76rem; max-height: 130px; overflow-y: auto; position: relative; z-index: 1;
  }}
  .feed-line {{ display: flex; gap: 10px; padding: 2px 0; color: var(--text-dim); animation: rise .3s ease both; }}
  .feed-line .ts {{ color: var(--hud); flex: none; }}
  .feed-line .sev-alta {{ color: var(--alta); }}
  .feed-line .sev-media {{ color: var(--media); }}
  .feed-line .sev-baixa {{ color: var(--baixa); }}
  .feed-empty {{ opacity: .5; }}
  .gauge-strip {{ padding: 18px 32px; border-bottom: 1px solid var(--line); position: relative; z-index: 1; }}
  .gauge-strip h2 {{
    font-family: 'Share Tech Mono', monospace; font-size: .72rem; text-transform: uppercase;
    letter-spacing: .08em; color: var(--text-dim); margin: 0 0 14px; font-weight: 400;
  }}
  .gauge-grid {{ display: flex; flex-wrap: wrap; gap: 14px; }}
  .gauge {{
    position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 4px;
    padding: 12px 16px; min-width: 168px;
  }}
  .gauge::before, .gauge::after {{ content: ""; position: absolute; width: 10px; height: 10px; }}
  .gauge::before {{ top: -1px; left: -1px; border-top: 2px solid var(--hud-soft); border-left: 2px solid var(--hud-soft); }}
  .gauge::after {{ bottom: -1px; right: -1px; border-bottom: 2px solid var(--hud-soft); border-right: 2px solid var(--hud-soft); }}
  .gauge-produto {{ font-size: .74rem; letter-spacing: .04em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px; }}
  .gauge-main {{ display: flex; align-items: baseline; gap: 6px; margin-bottom: 8px; }}
  .gauge-value {{ font-size: 1.7rem; font-weight: 700; color: var(--hud); text-shadow: 0 0 12px var(--hud-soft); }}
  .gauge-tag {{ font-size: .66rem; color: var(--text-dim); letter-spacing: .08em; }}
  .gauge-row {{ display: flex; justify-content: space-between; gap: 12px; font-size: .76rem;
                color: var(--text-dim); font-variant-numeric: tabular-nums; margin-top: 2px; }}
  .gauge-row strong {{ color: var(--text); }}
  .gauge-ga4 {{ margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--line); }}
  .signal-bar {{ margin-top: 10px; height: 3px; background: rgba(255,255,255,.06); border-radius: 2px; overflow: hidden; }}
  .signal-bar span {{ display: block; height: 100%; background: var(--hud); box-shadow: 0 0 6px var(--hud-soft); }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px; padding: 24px 32px; position: relative; z-index: 1; min-height: 140px;
  }}
  .card {{
    position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 4px;
    padding: 16px 18px; animation: rise .5s ease both;
  }}
  .card::before, .card::after {{ content: ""; position: absolute; width: 14px; height: 14px; }}
  .card::before {{ top: -1px; left: -1px; border-top: 2px solid; border-left: 2px solid; }}
  .card::after {{ bottom: -1px; right: -1px; border-bottom: 2px solid; border-right: 2px solid; }}
  .card.sev-alta::before, .card.sev-alta::after {{ border-color: var(--alta); }}
  .card.sev-media::before, .card.sev-media::after {{ border-color: var(--media); }}
  .card.sev-baixa::before, .card.sev-baixa::after {{ border-color: var(--baixa); }}
  .card.sev-alta {{ animation: rise .5s ease both, pulse-alta 2.4s ease-in-out .5s infinite; }}
  @keyframes pulse-alta {{
    0%, 100% {{ box-shadow: 0 0 0 rgba(255,59,82,0); }} 50% {{ box-shadow: 0 0 18px -3px var(--alta); }}
  }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
  .card-head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .badge {{
    display: inline-flex; align-items: center; gap: 5px; font-size: .68rem; font-weight: 700;
    padding: 3px 9px; border-radius: 3px; letter-spacing: .08em; border: 1px solid;
  }}
  .badge-ico {{ font-size: .6rem; }}
  .sev-alta .badge {{ background: var(--alta-bg); color: var(--alta); border-color: var(--alta); }}
  .sev-media .badge {{ background: var(--media-bg); color: var(--media); border-color: var(--media); }}
  .sev-baixa .badge {{ background: var(--baixa-bg); color: var(--baixa); border-color: var(--baixa); }}
  .tipo {{ font-size: .74rem; color: var(--text-dim); text-transform: capitalize; }}
  .card h3 {{
    margin: 12px 0 6px; font-size: 1.02rem; text-wrap: balance; font-weight: 400;
    display: flex; align-items: center; gap: 8px; font-family: 'Share Tech Mono', monospace;
  }}
  .crosshair {{
    width: 12px; height: 12px; flex: none; position: relative; opacity: .7;
    border: 1px solid var(--hud-soft); border-radius: 50%;
  }}
  .crosshair::before, .crosshair::after {{ content: ""; position: absolute; background: var(--hud-soft); }}
  .crosshair::before {{ left: 50%; top: -3px; width: 1px; height: 4px; transform: translateX(-50%); }}
  .crosshair::after {{ left: 50%; bottom: -3px; width: 1px; height: 4px; transform: translateX(-50%); }}
  .card .vs {{ color: var(--text-dim); font-size: .8rem; }}
  .resumo {{ opacity: .92; }}
  .card p {{ line-height: 1.5; font-size: .87rem; }}
  .label {{
    display: block; font-size: .68rem; text-transform: uppercase; letter-spacing: .05em;
    color: var(--hud); opacity: .75; margin-bottom: 3px;
  }}
  .card ul {{ list-style: none; margin: 6px 0 10px; padding: 0; font-size: .86rem; }}
  .card li {{ margin-bottom: 5px; padding-left: 16px; position: relative; }}
  .card li::before {{ content: "▸"; position: absolute; left: 0; color: var(--hud); }}
  .kpis {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
  .kpi {{
    font-size: .68rem; background: var(--panel-2); border: 1px solid var(--line);
    padding: 2px 8px; border-radius: 3px; color: var(--text-dim);
  }}
  .creative {{ margin: 10px 0; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; background: var(--panel-2); }}
  .creative img {{ display: block; width: 100%; max-height: 260px; object-fit: cover; }}
  .analise-criativo {{ margin: 6px 0 10px; padding: 10px 12px; border-left: 2px solid var(--hud-soft); background: var(--panel-2); border-radius: 0 4px 4px 0; }}
  .analise-row {{ display: flex; gap: 8px; font-size: .82rem; margin-bottom: 4px; }}
  .analise-row:last-child {{ margin-bottom: 0; }}
  .analise-row span {{ flex: none; width: 84px; color: var(--hud); font-size: .68rem; text-transform: uppercase; letter-spacing: .04em; padding-top: 2px; }}
  .analise-row p {{ margin: 0; font-size: .82rem; }}
  .foot {{
    margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--line);
    display: flex; justify-content: space-between; font-size: .7rem; color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }}
  .foot a {{ text-decoration: none; }}
  .foot a:hover {{ text-decoration: underline; }}
  .empty {{ padding: 60px 20px; color: var(--text-dim); grid-column: 1 / -1; text-align: center; font-size: 1rem; letter-spacing: .04em; }}
  .caveat {{ padding: 0 32px 30px; font-size: .76rem; color: var(--text-dim); max-width: 860px; line-height: 1.6; position: relative; z-index: 1; }}
  a:focus-visible, button:focus-visible {{ outline: 2px solid var(--hud); outline-offset: 2px; }}
  @media (prefers-reduced-motion: reduce) {{ .scan-band {{ display: none; }} * {{ animation: none !important; transition: none !important; }} }}
</style></head>
<body>
<div class="scan-band"></div>
<header class="frame">
  <div class="hud-top-row">
    <span class="eyebrow">◈ sistema de guerra competitiva · demonstração ao vivo</span>
    <div class="demo-controls">
      <span class="radar-badge"><span class="radar"></span> monitorando</span>
      <button class="demo-btn" id="btn-replay">▶ reiniciar simulação</button>
    </div>
  </div>
  <h1>{config.get('marca', '')}</h1>
  <div class="hud-meta">
    <span id="relogio-linha">RELÓGIO DA SIMULAÇÃO <strong id="relogio">--:--:--</strong></span>
    <span>ALERTAS ATIVOS <strong id="contador">0</strong> / {len(eventos)}</span>
    <span>CADÊNCIA CONFIGURADA <strong>{config.get('cadencia_sugerida_horas')}h</strong></span>
  </div>
</header>
<div class="master-caution ok" id="master-caution"><span class="mc-dot"></span>AGUARDANDO PRIMEIRO EVENTO...</div>
<div class="feed" id="feed"><div class="feed-line feed-empty">— nenhum evento ainda —</div></div>
<section class="gauge-strip">
  <h2>// desempenho próprio — google/meta ads + ga4 (simulado para a demonstração)</h2>
  <div class="gauge-grid">{own_cards}</div>
</section>
<div class="grid" id="grid"><div class="empty" id="grid-empty">Aguardando eventos da simulação...</div></div>
<p class="caveat">Demonstração: os eventos abaixo são os mesmos tipos de alerta reais do sistema (dados
simulados para esta reprodução), exibidos em sequência para simular uma janela de monitoramento com
vários eventos consecutivos. Em operação real, cada evento chega no seu próprio ciclo de verificação —
ver SKILL.md.</p>

<script>
const CARDS = {cards_json};
const RESUMOS = {resumos_json};
const SEVERIDADES = {severidades_json};
const reduzido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const grid = document.getElementById('grid');
const gridEmpty = document.getElementById('grid-empty');
const feed = document.getElementById('feed');
const caution = document.getElementById('master-caution');
const contador = document.getElementById('contador');
const relogio = document.getElementById('relogio');
const btnReplay = document.getElementById('btn-replay');

let relogioBase = new Date(2026, 6, 31, 22, 10, 0);
let piorSeveridade = null;
const rankSev = {{ baixa: 0, media: 1, alta: 2 }};

function fmtRelogio(d) {{
  return d.toTimeString().slice(0,8);
}}

function atualizarMasterCaution() {{
  if (piorSeveridade === 'alta') {{
    caution.className = 'master-caution alta';
    caution.innerHTML = '<span class="mc-dot"></span>MASTER WARNING — ALERTA CRÍTICO ATIVO — AÇÃO IMEDIATA';
  }} else if (piorSeveridade === 'media') {{
    caution.className = 'master-caution media';
    caution.innerHTML = '<span class="mc-dot"></span>CAUTION — ALERTA(S) EM ATENÇÃO — REVISAR';
  }} else {{
    caution.className = 'master-caution ok';
    caution.innerHTML = '<span class="mc-dot"></span>TODOS OS SISTEMAS NOMINAIS';
  }}
}}

function inserirEvento(i) {{
  if (i === 0) gridEmpty.remove();
  const wrap = document.createElement('div');
  wrap.innerHTML = CARDS[i];
  const card = wrap.firstElementChild;
  grid.appendChild(card);

  relogioBase = new Date(relogioBase.getTime() + (7 + Math.random()*40) * 60000);
  relogio.textContent = fmtRelogio(relogioBase);

  const linha = document.createElement('div');
  linha.className = 'feed-line';
  const sev = SEVERIDADES[i];
  linha.innerHTML = `<span class="ts">[${{fmtRelogio(relogioBase)}}]</span><span class="sev-${{sev}}">●</span> ${{RESUMOS[i]}}`;
  if (feed.querySelector('.feed-empty')) feed.innerHTML = '';
  feed.prepend(linha);

  if (piorSeveridade === null || rankSev[sev] > rankSev[piorSeveridade]) {{
    piorSeveridade = sev;
  }}
  atualizarMasterCaution();
  contador.textContent = String(i + 1);

  if (!reduzido) card.scrollIntoView({{behavior: 'smooth', block: 'nearest'}});
}}

function tocarSequencia() {{
  grid.innerHTML = '';
  const vazio = document.createElement('div');
  vazio.className = 'empty'; vazio.id = 'grid-empty';
  vazio.textContent = 'Aguardando eventos da simulação...';
  grid.appendChild(vazio);
  feed.innerHTML = '<div class="feed-line feed-empty">— nenhum evento ainda —</div>';
  contador.textContent = '0';
  piorSeveridade = null;
  atualizarMasterCaution();
  relogio.textContent = '--:--:--';
  relogioBase = new Date(2026, 6, 31, 22, 10, 0);

  btnReplay.disabled = true;
  const atraso = reduzido ? 0 : 2200;
  CARDS.forEach((_, i) => {{
    setTimeout(() => {{
      inserirEvento(i);
      if (i === CARDS.length - 1) btnReplay.disabled = false;
    }}, i * atraso);
  }});
}}

btnReplay.addEventListener('click', tocarSequencia);
window.addEventListener('load', () => setTimeout(tocarSequencia, 600));
</script>
</body></html>"""

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser(description="Gera dashboard de demonstração com replay ao vivo.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="war-room-live-demo.html")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    config.setdefault("concorrentes", [])
    config.setdefault("produtos_monitorados", [])
    config.setdefault("limiares", {
        "queda_preco_leve_pct": 5, "queda_preco_moderada_pct": 15,
        "aumento_preco_leve_pct": 5, "aumento_preco_moderado_pct": 15,
        "salto_posicao_min": 3, "crescimento_reviews_pct": 15, "aumento_ads_min_unidades": 3,
    })
    config.setdefault("elasticidade_estimada", -1.5)

    playbook = wr.load_playbook(os.path.join(SCRIPT_DIR, "playbook.json"))
    eventos, own_perf = montar_sequencia(config, playbook)
    render_demo(eventos, own_perf, config, {"data": wr.now_iso()}, args.out)
    print(f"OK -> {args.out} ({len(eventos)} eventos na sequência)")


if __name__ == "__main__":
    main()
