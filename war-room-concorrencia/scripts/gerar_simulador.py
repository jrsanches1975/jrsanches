#!/usr/bin/env python3
"""
Gera o SIMULADOR interativo da war room — diferente de gerar_demo_live.py (que só
reproduz uma sequência fixa em replay): aqui você dispara qualquer evento, na ordem
que quiser, pelo painel de controle, e vê o dashboard inteiro reagir ao vivo —
cartão novo, feed, "master caution", Esquadrão de Combate (recalculado por agente) e
Radar de Posição no Mercado Livre (a linha do concorrente afetado se atualiza).

Reaproveita 100% do motor real (make_alert, playbook, agentes, render_card,
render_own_kpi, diff_precos, os ingest_*) via import de war_room.py. Todos os dados
são simulados e autocontidos — não depende de nenhum export real do Windsor.ai/Apify.

Uso:
    python gerar_simulador.py --config config.example.json --out ../outputs/war-room-simulador.html
"""
import argparse
import json
import os

import war_room as wr

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EX_DIR = os.path.join(SCRIPT_DIR, "examples")

OWN_PERF = {
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


def campos(seller, title, price, original_price=None, discount_pct=0, position=1,
           reviews=0, rating=4.5, frete_gratis=True, patrocinado="desconhecido", url="#"):
    return {"seller": seller, "title": title, "price": price,
            "original_price": original_price or price, "discount_pct": discount_pct,
            "position": position, "reviews": reviews, "rating": rating,
            "frete_gratis": frete_gratis, "patrocinado": patrocinado, "url": url,
            "total_listagens": 1}


def alerta_ml(produto, concorrente, antigo, novo, config, playbook, own_perf=None):
    """Roda o diff real (wr.diff_precos) num par isolado de snapshot — devolve os
    alertas de fato gerados (0, 1 ou 2, conforme o que mudou)."""
    snap_a = {produto: {concorrente: antigo}} if antigo else {produto: {}}
    snap_b = {produto: {concorrente: novo}} if novo else {produto: {}}
    return wr.diff_precos(snap_a, snap_b, config, playbook, own_perf=own_perf)


def radar_update_de(alerta):
    """Deriva a atualização de linha do Radar ML a partir de um alerta de preço/
    visibilidade/entrada/saída — None se o tipo não afeta o radar."""
    tipo, d, produto, concorrente = alerta["tipo"], alerta["detalhes"], alerta["produto"], alerta["concorrente"]
    if tipo in ("queda_preco", "aumento_preco_concorrente"):
        return {"produto": produto, "concorrente": concorrente, "acao": "atualizar",
                "campos": {"price": d["price_novo"]}}
    if tipo == "novo_desconto":
        return {"produto": produto, "concorrente": concorrente, "acao": "atualizar",
                "campos": {"discount_pct": d["discount_novo"]}}
    if tipo == "salto_visibilidade_ml":
        campos_novos = {}
        if d.get("position_nova") is not None:
            campos_novos["position"] = d["position_nova"]
        if d.get("reviews_novo") is not None:
            campos_novos["reviews"] = d["reviews_novo"]
        return {"produto": produto, "concorrente": concorrente, "acao": "atualizar", "campos": campos_novos}
    if tipo == "novo_entrante":
        return {"produto": produto, "concorrente": concorrente, "acao": "adicionar",
                "campos": {"position": d.get("position"), "price": d.get("price")}}
    if tipo == "concorrente_sumiu":
        return {"produto": produto, "concorrente": concorrente, "acao": "remover", "campos": {}}
    return None


def montar_biblioteca(config, playbook):
    """Devolve a lista de (alerta, radar_update) disponíveis no simulador — o
    usuário dispara cada um manualmente, na ordem que quiser, pelo painel."""
    eventos = []

    def add(alertas):
        for a in alertas:
            eventos.append((a, radar_update_de(a)))

    # -- preço / desconto / visibilidade (Mercado Livre) --
    add(alerta_ml("Faciderm", "Black Skull",
                   campos("BLACK SKULL", "Sérum Facial Vitamina C Black Skull 30ml", 89.90, position=2, reviews=340, rating=4.6),
                   campos("BLACK SKULL", "Sérum Facial Vitamina C Black Skull 30ml", 71.90, 89.90, 20, 1, 365, 4.6),
                   config, playbook, OWN_PERF))
    add(alerta_ml("Amaze", "Black Skull",
                   campos("BLACK SKULL", "Multivitamínico Black Skull", 84.90, position=4, reviews=60, rating=4.3),
                   campos("BLACK SKULL", "Multivitamínico Black Skull", 84.90, position=1, reviews=95, rating=4.3),
                   config, playbook, OWN_PERF))
    add(alerta_ml("Linha Joie Fit", "Black Skull",
                   campos("BLACK SKULL", "Whey Protein Isolado Black Skull 900g", 119.90, position=1, reviews=900, rating=4.8),
                   campos("BLACK SKULL", "Whey Protein Isolado Black Skull 900g", 129.90, position=1, reviews=910, rating=4.8),
                   config, playbook, OWN_PERF))
    add(alerta_ml("Faciderm", "Growth Supplements", None,
                   campos("GROWTH SUPPLEMENTS", "Sérum Vitamina C Growth 30ml", 68.90, position=2, reviews=12, rating=4.4),
                   config, playbook, OWN_PERF))
    add(alerta_ml("Amaze", "Growth Supplements",
                   campos("GROWTH SUPPLEMENTS", "Polivitamínico Feminino Growth", 79.90, position=1, reviews=520, rating=4.7),
                   None, config, playbook, OWN_PERF))
    add(alerta_ml("Amaze", "Growth Supplements",
                   campos("GROWTH SUPPLEMENTS", "Polivitamínico Feminino Growth", 79.90, position=3, reviews=520, rating=4.7),
                   campos("GROWTH SUPPLEMENTS", "Polivitamínico Feminino Growth", 75.00, 79.90, 6, 3, 540, 4.7),
                   config, playbook, OWN_PERF))
    add(alerta_ml("Amaze", "Growth Supplements",
                   campos("GROWTH SUPPLEMENTS", "Polivitamínico Feminino Growth", 79.90, position=3, reviews=520, rating=4.7),
                   campos("GROWTH SUPPLEMENTS", "Polivitamínico Feminino Growth", 79.90, discount_pct=15, position=3, reviews=520, rating=4.7),
                   config, playbook, OWN_PERF))
    add(alerta_ml("Linha Joie Fit", "Growth Supplements",
                   campos("GROWTH SUPPLEMENTS", "Whey Growth 900g", 109.90, position=6, reviews=40, rating=4.2),
                   campos("GROWTH SUPPLEMENTS", "Whey Growth 900g", 109.90, position=2, reviews=88, rating=4.2),
                   config, playbook, OWN_PERF))

    # -- criativo novo de concorrente (Meta/Google), com e sem análise --
    meta_path = "/tmp/_sim_meta1.json"
    wr.save_json(meta_path, {"novos_anuncios": [{
        "concorrente": "Black Skull", "ad_id": "999", "titulo": "Faciderm Turbo Lançamento",
        "corpo": "Novo sérum com 40% mais ativo — só essa semana",
        "imagem_url": "https://picsum.photos/seed/faciderm/640/360",
        "url_anuncio": "https://facebook.com/ads/library/?id=999"}]})
    analises = {"999": {"gancho": "Urgência + prova de resultado (\"40% mais ativo\")",
                         "oferta": "Lançamento com preço promocional só na semana",
                         "formato": "Imagem única, produto em destaque com selo de novidade",
                         "cta": "Comprar agora",
                         "observacao": "Mesmo ângulo de 'fórmula turbinada' que a Joie já usa no Faciderm."}}
    add(wr.ingest_novos_criativos(meta_path, "Meta Ad Library", playbook, analises))

    meta_path2 = "/tmp/_sim_meta2.json"
    wr.save_json(meta_path2, {"novos_anuncios": [{
        "concorrente": "Growth Supplements", "ad_id": "888",
        "titulo": "Growth Whey — combo com 2 unidades",
        "url_anuncio": "https://facebook.com/ads/library/?id=888"}]})
    add(wr.ingest_novos_criativos(meta_path2, "Meta Ad Library", playbook))

    google_ads_path = "/tmp/_sim_googleads.json"
    wr.save_json(google_ads_path, {"novos_anuncios": [{
        "concorrente": "Black Skull", "ad_id": "777", "titulo": "Suplementos Black Skull — Frete Grátis",
        "descricao": "Toda a linha com frete grátis para todo o Brasil",
        "url_anuncio": "https://adstransparency.google.com/advertiser/AR000"}]})
    add(wr.ingest_novos_criativos(google_ads_path, "Google Ads Transparency Center", playbook))

    # -- pico de interesse (Google Trends) --
    trends_path = "/tmp/_sim_trends.json"
    wr.save_json(trends_path, {"picos": [
        {"termo": "Black Skull", "media_antiga": 30, "media_nova": 68, "pct": 126.7},
        {"termo": "Growth Supplements", "media_antiga": 22, "media_nova": 34, "pct": 54.5},
    ]})
    add(wr.ingest_picos_trends(trends_path, playbook))

    # -- queda de performance de keyword (leilão) --
    kw_path = "/tmp/_sim_keyword.json"
    wr.save_json(kw_path, {"quedas": [
        {"campanha": "Search.", "keyword": "whey protein", "nivel": "critica",
         "impression_share_antes": 0.35, "impression_share_agora": 0.0999,
         "rank_lost_antes": 0.20, "rank_lost_agora": 0.45,
         "quality_score_antes": 5.0, "quality_score_agora": 1.0,
         "cpc_medio": 1.22, "first_page_cpc": None, "top_of_page_cpc": None,
         "impressions": 43, "clicks": 6,
         "pontos_de_interferencia": [
             {"dominio": "vitafor.com.br", "aparicoes_no_periodo": 2},
             {"dominio": "mercadolivre.com.br", "aparicoes_no_periodo": 1},
             {"dominio": "gsuplementos.com.br", "aparicoes_no_periodo": 1},
             {"dominio": "shopee.com.br", "aparicoes_no_periodo": 1}]},
        {"campanha": "Search - Linha Joie Fit", "keyword": "creatina monohidratada", "nivel": "moderada",
         "impression_share_antes": 0.42, "impression_share_agora": 0.28,
         "rank_lost_antes": 0.15, "rank_lost_agora": 0.30,
         "quality_score_antes": 6.0, "quality_score_agora": 4.0,
         "cpc_medio": 0.95, "first_page_cpc": None, "top_of_page_cpc": None,
         "impressions": 210, "clicks": 18,
         "pontos_de_interferencia": [
             {"dominio": "maxtitanium.com.br", "aparicoes_no_periodo": 3},
             {"dominio": "gsuplementos.com.br", "aparicoes_no_periodo": 2}]},
    ]})
    add(wr.ingest_quedas_keyword(kw_path, playbook))

    # -- queda de KPI próprio (aciona o protocolo de diagnóstico) --
    kpi_path = "/tmp/_sim_kpi.json"
    wr.save_json(kpi_path, {"quedas": [
        {"produto": "Faciderm", "metrica": "roas", "rotulo": "ROAS", "valor_antes": 6.0,
         "valor_agora": 2.0, "delta_pct": -66.7},
        {"produto": "Amaze", "metrica": "ctr_pct", "rotulo": "CTR", "valor_antes": 3.2,
         "valor_agora": 2.4, "delta_pct": -25.0},
    ]})
    add(wr.ingest_quedas_kpi_proprio(kpi_path, playbook))

    for p in (meta_path, meta_path2, google_ads_path, trends_path, kw_path, kpi_path):
        os.remove(p)

    return eventos


CATEGORIA_DO_TIPO = {
    "queda_preco": "Preço", "aumento_preco_concorrente": "Preço", "novo_desconto": "Preço",
    "novo_entrante": "Mercado Livre", "concorrente_sumiu": "Mercado Livre", "salto_visibilidade_ml": "Mercado Livre",
    "novo_criativo_concorrente": "Criativo", "pico_interesse_busca": "Trends",
    "queda_performance_keyword": "Leilão (Keyword)", "queda_kpi_proprio": "KPI Próprio",
}


def render_simulador(eventos, radar_ml_inicial, own_perf, config, meta, path):
    botoes_por_categoria = {}
    eventos_js = []
    for i, (a, radar_upd) in enumerate(eventos):
        cat = CATEGORIA_DO_TIPO.get(a["tipo"], "Outro")
        botoes_por_categoria.setdefault(cat, []).append((i, a))
        eventos_js.append({
            "card": wr.render_card(a, 0),
            "resumo": f"{a['tipo'].replace('_', ' ')} · {a['produto']} × {a['concorrente']}",
            "severidade": a["severidade"],
            "agenteChave": a.get("agente_chave"), "agenteNome": a.get("agente_nome"),
            "agenteEmblema": a.get("agente_emblema"), "statusAcao": a.get("status_acao"),
            "radar": radar_upd,
        })

    botoes_html = []
    for cat, itens in botoes_por_categoria.items():
        btns = "".join(
            f'<button class="ev-btn sev-{a["severidade"]}" data-idx="{i}" onclick="dispararEvento({i}, this)">'
            f'<span class="ev-btn-sev">{wr.SEV_ICON.get(a["severidade"], "●")}</span>'
            f'{a["produto"]} × {a["concorrente"]}<br><small>{a["tipo"].replace("_", " ")} · {a["nivel"]}</small>'
            f'</button>'
            for i, a in itens
        )
        botoes_html.append(f'<div class="ev-group"><h3>{cat}</h3><div class="ev-buttons">{btns}</div></div>')

    own_cards = "".join(wr.render_own_kpi(p, v) for p, v in own_perf.items())
    eventos_json = json.dumps(eventos_js)
    radar_inicial_json = json.dumps(radar_ml_inicial)

    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>War Room — {config.get('marca', '')} · SIMULADOR</title>
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
    background-image: linear-gradient(var(--hud-dim) 1px, transparent 1px),
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
  h1, h2, h3, .gauge-value {{ font-family: 'Orbitron', sans-serif; }}
  header.frame {{
    display: flex; flex-direction: column; gap: 8px; padding: 20px 32px;
    border-bottom: 1px solid var(--line); background: linear-gradient(180deg, var(--panel), transparent);
    position: relative; z-index: 1;
  }}
  .hud-top-row {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }}
  .eyebrow {{ font-size: .72rem; letter-spacing: .16em; text-transform: uppercase; color: var(--hud); font-weight: 600; opacity: .9; }}
  .radar-badge {{ display: inline-flex; align-items: center; gap: 8px; font-size: .7rem; letter-spacing: .1em; text-transform: uppercase; color: var(--text-dim); }}
  .radar {{ width: 14px; height: 14px; border-radius: 50%; border: 1px solid var(--hud-soft); position: relative;
            background: radial-gradient(circle, rgba(41,255,224,.18), transparent 70%); }}
  .radar::before {{ content: ""; position: absolute; inset: 0; border-radius: 50%;
                     background: conic-gradient(from 0deg, var(--hud), transparent 35%); animation: spin 2.2s linear infinite; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  h1 {{ margin: 0; font-size: clamp(1.6rem, 4vw, 2.3rem); font-weight: 800; letter-spacing: .02em;
        text-transform: uppercase; color: var(--hud); text-shadow: 0 0 10px var(--hud-soft), 0 0 30px rgba(41,255,224,.2);
        text-wrap: balance; }}
  .hud-meta {{ display: flex; flex-wrap: wrap; gap: 18px; font-size: .78rem; color: var(--text-dim); font-variant-numeric: tabular-nums; }}
  .hud-meta strong {{ color: var(--text); }}
  .demo-controls {{ display: flex; gap: 10px; align-items: center; }}
  .demo-btn {{ font-family: 'Share Tech Mono', monospace; font-size: .74rem; letter-spacing: .06em; text-transform: uppercase;
               background: var(--panel-2); color: var(--hud); border: 1px solid var(--hud-soft); padding: 7px 14px; border-radius: 4px; cursor: pointer; }}
  .demo-btn:hover {{ background: var(--hud-dim); }}
  .master-caution {{ margin: 10px 32px 0; padding: 9px 16px; border-radius: 4px; font-size: .78rem; font-weight: 700;
                      letter-spacing: .05em; text-transform: uppercase; display: flex; align-items: center; gap: 10px;
                      border: 1px solid; z-index: 1; position: relative; transition: all .3s ease; }}
  .master-caution .mc-dot {{ width: 8px; height: 8px; border-radius: 50%; flex: none; }}
  .master-caution.alta {{ color: var(--alta); border-color: var(--alta); background: var(--alta-bg); animation: warn-pulse 1.4s ease-in-out infinite; }}
  .master-caution.alta .mc-dot {{ background: var(--alta); box-shadow: 0 0 8px var(--alta); }}
  .master-caution.media {{ color: var(--media); border-color: var(--media); background: var(--media-bg); }}
  .master-caution.media .mc-dot {{ background: var(--media); box-shadow: 0 0 8px var(--media); }}
  .master-caution.ok {{ color: var(--baixa); border-color: rgba(57,255,157,.3); background: var(--baixa-bg); }}
  .master-caution.ok .mc-dot {{ background: var(--baixa); box-shadow: 0 0 8px var(--baixa); }}
  @keyframes warn-pulse {{ 0%, 100% {{ box-shadow: 0 0 0 rgba(255,59,82,0); }} 50% {{ box-shadow: 0 0 22px -4px var(--alta); }} }}

  .control-panel {{ padding: 16px 32px; border-bottom: 1px solid var(--line); position: relative; z-index: 1; background: var(--panel); }}
  .control-panel h2 {{ font-family: 'Share Tech Mono', monospace; font-size: .72rem; text-transform: uppercase;
                        letter-spacing: .08em; color: var(--text-dim); margin: 0 0 12px; font-weight: 400; }}
  .ev-group {{ margin-bottom: 14px; }}
  .ev-group h3 {{ font-size: .7rem; text-transform: uppercase; letter-spacing: .06em; color: var(--hud); margin: 0 0 8px; font-weight: 700; }}
  .ev-buttons {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .ev-btn {{
    font-family: 'Share Tech Mono', monospace; text-align: left; cursor: pointer; color: var(--text);
    background: var(--panel-2); border: 1px solid var(--line); border-radius: 4px; padding: 8px 12px;
    font-size: .74rem; line-height: 1.5; min-width: 190px; transition: transform .12s ease, border-color .12s ease;
  }}
  .ev-btn:hover {{ border-color: var(--hud-soft); transform: translateY(-1px); }}
  .ev-btn:disabled {{ opacity: .35; cursor: default; transform: none; }}
  .ev-btn small {{ color: var(--text-dim); text-transform: capitalize; }}
  .ev-btn-sev {{ margin-right: 4px; }}
  .ev-btn.sev-alta .ev-btn-sev {{ color: var(--alta); }}
  .ev-btn.sev-media .ev-btn-sev {{ color: var(--media); }}
  .ev-btn.sev-baixa .ev-btn-sev {{ color: var(--baixa); }}

  .feed {{ margin: 14px 32px 0; padding: 10px 14px; border: 1px solid var(--line); border-radius: 4px;
            background: var(--panel); font-size: .76rem; max-height: 130px; overflow-y: auto; position: relative; z-index: 1; }}
  .feed-line {{ display: flex; gap: 10px; padding: 2px 0; color: var(--text-dim); animation: rise .3s ease both; }}
  .feed-line .ts {{ color: var(--hud); flex: none; }}
  .feed-line .sev-alta {{ color: var(--alta); }} .feed-line .sev-media {{ color: var(--media); }} .feed-line .sev-baixa {{ color: var(--baixa); }}
  .feed-empty {{ opacity: .5; }}

  .squadron-strip {{ padding: 18px 32px; border-bottom: 1px solid var(--line); position: relative; z-index: 1; }}
  .squadron-strip h2 {{ font-family: 'Share Tech Mono', monospace; font-size: .72rem; text-transform: uppercase;
                         letter-spacing: .08em; color: var(--text-dim); margin: 0 0 14px; font-weight: 400; }}
  .squadron-grid {{ display: flex; flex-wrap: wrap; gap: 14px; }}
  .squadron-card {{ position: relative; background: var(--panel); border: 1px solid var(--line); border-left: 3px solid var(--line);
                     border-radius: 4px; padding: 12px 16px; min-width: 220px; max-width: 300px; }}
  .squadron-card.sev-alta {{ border-left-color: var(--alta); }}
  .squadron-card.sev-media {{ border-left-color: var(--media); }}
  .squadron-card.sev-baixa {{ border-left-color: var(--baixa); }}
  .squadron-head {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
  .squadron-emblema {{ font-size: 1rem; color: var(--hud); }}
  .squadron-nome {{ font-size: .82rem; font-weight: 700; }}
  .squadron-status {{ display: inline-block; font-size: .64rem; letter-spacing: .05em; text-transform: uppercase;
                       padding: 2px 7px; border-radius: 3px; background: var(--panel-2); color: var(--text-dim);
                       border: 1px solid var(--line); margin-bottom: 6px; }}
  .squadron-card.sev-alta .squadron-status {{ color: var(--alta); border-color: var(--alta); }}
  .squadron-card.sev-media .squadron-status {{ color: var(--media); border-color: var(--media); }}
  .squadron-count {{ font-size: .72rem; color: var(--text-dim); margin-bottom: 6px; }}
  .squadron-list {{ list-style: none; margin: 0; padding: 0; font-size: .74rem; color: var(--text-dim); }}
  .squadron-list li {{ padding: 2px 0; border-top: 1px dashed var(--line); }}
  .squadron-list li:first-child {{ border-top: none; }}
  .squadron-empty {{ color: var(--text-dim); font-size: .8rem; opacity: .6; }}

  .gauge-strip {{ padding: 18px 32px; border-bottom: 1px solid var(--line); position: relative; z-index: 1; }}
  .gauge-strip h2 {{ font-family: 'Share Tech Mono', monospace; font-size: .72rem; text-transform: uppercase;
                      letter-spacing: .08em; color: var(--text-dim); margin: 0 0 14px; font-weight: 400; }}
  .gauge-grid {{ display: flex; flex-wrap: wrap; gap: 14px; }}
  .gauge {{ position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 12px 16px; min-width: 168px; }}
  .gauge::before, .gauge::after {{ content: ""; position: absolute; width: 10px; height: 10px; }}
  .gauge::before {{ top: -1px; left: -1px; border-top: 2px solid var(--hud-soft); border-left: 2px solid var(--hud-soft); }}
  .gauge::after {{ bottom: -1px; right: -1px; border-bottom: 2px solid var(--hud-soft); border-right: 2px solid var(--hud-soft); }}
  .gauge-produto {{ font-size: .74rem; letter-spacing: .04em; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px; }}
  .gauge-main {{ display: flex; align-items: baseline; gap: 6px; margin-bottom: 8px; }}
  .gauge-value {{ font-size: 1.7rem; font-weight: 700; color: var(--hud); text-shadow: 0 0 12px var(--hud-soft); }}
  .gauge-tag {{ font-size: .66rem; color: var(--text-dim); letter-spacing: .08em; }}
  .gauge-row {{ display: flex; justify-content: space-between; gap: 12px; font-size: .76rem; color: var(--text-dim);
                font-variant-numeric: tabular-nums; margin-top: 2px; }}
  .gauge-row strong {{ color: var(--text); }}
  .gauge-ga4 {{ margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--line); }}
  .signal-bar {{ margin-top: 10px; height: 3px; background: rgba(255,255,255,.06); border-radius: 2px; overflow: hidden; }}
  .signal-bar span {{ display: block; height: 100%; background: var(--hud); box-shadow: 0 0 6px var(--hud-soft); }}

  .ml-radar {{ padding: 18px 32px; border-bottom: 1px solid var(--line); position: relative; z-index: 1; }}
  .ml-radar h2 {{ font-family: 'Share Tech Mono', monospace; font-size: .72rem; text-transform: uppercase;
                  letter-spacing: .08em; color: var(--text-dim); margin: 0 0 14px; font-weight: 400; }}
  .ml-radar-table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 4px; }}
  .ml-radar-table {{ width: 100%; border-collapse: collapse; font-size: .78rem; white-space: nowrap; }}
  .ml-radar-table th {{ text-align: left; padding: 8px 12px; background: var(--panel-2); color: var(--hud);
                         font-size: .66rem; text-transform: uppercase; letter-spacing: .05em; font-weight: 600; border-bottom: 1px solid var(--line); }}
  .ml-radar-table td {{ padding: 7px 12px; border-bottom: 1px dashed var(--line); color: var(--text-dim); font-variant-numeric: tabular-nums; }}
  .ml-radar-table tr.radar-proprio {{ background: var(--hud-dim); }}
  .ml-radar-table tr.radar-proprio td.quem {{ color: var(--hud); font-weight: 700; }}
  .ml-radar-table td.quem {{ color: var(--text); }}
  .ml-radar-table td.updated {{ animation: flash-update 1.2s ease; }}
  @keyframes flash-update {{ 0% {{ background: rgba(41,255,224,.35); }} 100% {{ background: transparent; }} }}
  .ml-radar-note {{ margin: 10px 0 0; font-size: .72rem; color: var(--text-dim); line-height: 1.5; }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; padding: 24px 32px;
           position: relative; z-index: 1; min-height: 140px; }}
  .card {{ position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 4px; padding: 16px 18px; animation: rise .5s ease both; }}
  .card::before, .card::after {{ content: ""; position: absolute; width: 14px; height: 14px; }}
  .card::before {{ top: -1px; left: -1px; border-top: 2px solid; border-left: 2px solid; }}
  .card::after {{ bottom: -1px; right: -1px; border-bottom: 2px solid; border-right: 2px solid; }}
  .card.sev-alta::before, .card.sev-alta::after {{ border-color: var(--alta); }}
  .card.sev-media::before, .card.sev-media::after {{ border-color: var(--media); }}
  .card.sev-baixa::before, .card.sev-baixa::after {{ border-color: var(--baixa); }}
  .card.sev-alta {{ animation: rise .5s ease both, pulse-alta 2.4s ease-in-out .5s infinite; }}
  @keyframes pulse-alta {{ 0%, 100% {{ box-shadow: 0 0 0 rgba(255,59,82,0); }} 50% {{ box-shadow: 0 0 18px -3px var(--alta); }} }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
  .card-head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .badge {{ display: inline-flex; align-items: center; gap: 5px; font-size: .68rem; font-weight: 700; padding: 3px 9px;
            border-radius: 3px; letter-spacing: .08em; border: 1px solid; }}
  .badge-ico {{ font-size: .6rem; }}
  .sev-alta .badge {{ background: var(--alta-bg); color: var(--alta); border-color: var(--alta); }}
  .sev-media .badge {{ background: var(--media-bg); color: var(--media); border-color: var(--media); }}
  .sev-baixa .badge {{ background: var(--baixa-bg); color: var(--baixa); border-color: var(--baixa); }}
  .tipo {{ font-size: .74rem; color: var(--text-dim); text-transform: capitalize; }}
  .card h3 {{ margin: 12px 0 6px; font-size: 1.02rem; text-wrap: balance; font-weight: 400; display: flex; align-items: center;
              gap: 8px; font-family: 'Share Tech Mono', monospace; }}
  .crosshair {{ width: 12px; height: 12px; flex: none; position: relative; opacity: .7; border: 1px solid var(--hud-soft); border-radius: 50%; }}
  .crosshair::before, .crosshair::after {{ content: ""; position: absolute; background: var(--hud-soft); }}
  .crosshair::before {{ left: 50%; top: -3px; width: 1px; height: 4px; transform: translateX(-50%); }}
  .crosshair::after {{ left: 50%; bottom: -3px; width: 1px; height: 4px; transform: translateX(-50%); }}
  .card .vs {{ color: var(--text-dim); font-size: .8rem; }}
  .resumo {{ opacity: .92; }}
  .card p {{ line-height: 1.5; font-size: .87rem; }}
  .label {{ display: block; font-size: .68rem; text-transform: uppercase; letter-spacing: .05em; color: var(--hud); opacity: .75; margin-bottom: 3px; }}
  .card ul {{ list-style: none; margin: 6px 0 10px; padding: 0; font-size: .86rem; }}
  .card li {{ margin-bottom: 5px; padding-left: 16px; position: relative; }}
  .card li::before {{ content: "▸"; position: absolute; left: 0; color: var(--hud); }}
  .kpis {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
  .kpi {{ font-size: .68rem; background: var(--panel-2); border: 1px solid var(--line); padding: 2px 8px; border-radius: 3px; color: var(--text-dim); }}
  .creative {{ margin: 10px 0; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; background: var(--panel-2); }}
  .creative img {{ display: block; width: 100%; max-height: 260px; object-fit: cover; }}
  .analise-criativo {{ margin: 6px 0 10px; padding: 10px 12px; border-left: 2px solid var(--hud-soft); background: var(--panel-2); border-radius: 0 4px 4px 0; }}
  .analise-row {{ display: flex; gap: 8px; font-size: .82rem; margin-bottom: 4px; }}
  .analise-row:last-child {{ margin-bottom: 0; }}
  .analise-row span {{ flex: none; width: 84px; color: var(--hud); font-size: .68rem; text-transform: uppercase; letter-spacing: .04em; padding-top: 2px; }}
  .analise-row p {{ margin: 0; font-size: .82rem; }}
  .foot {{ margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--line); display: flex; justify-content: space-between;
           font-size: .7rem; color: var(--text-dim); font-variant-numeric: tabular-nums; }}
  .foot a {{ text-decoration: none; }} .foot a:hover {{ text-decoration: underline; }}
  .empty {{ padding: 60px 20px; color: var(--text-dim); grid-column: 1 / -1; text-align: center; font-size: 1rem; letter-spacing: .04em; }}
  .caveat {{ padding: 0 32px 30px; font-size: .76rem; color: var(--text-dim); max-width: 860px; line-height: 1.6; position: relative; z-index: 1; }}
  a:focus-visible, button:focus-visible {{ outline: 2px solid var(--hud); outline-offset: 2px; }}
  @media (prefers-reduced-motion: reduce) {{ .scan-band {{ display: none; }} * {{ animation: none !important; transition: none !important; }} }}
</style></head>
<body>
<div class="scan-band"></div>
<header class="frame">
  <div class="hud-top-row">
    <span class="eyebrow">◈ sistema de guerra competitiva · simulador interativo</span>
    <div class="demo-controls">
      <span class="radar-badge"><span class="radar"></span> em espera</span>
      <button class="demo-btn" id="btn-autoplay">▶ disparar tudo em sequência</button>
      <button class="demo-btn" id="btn-reset">↺ reiniciar</button>
    </div>
  </div>
  <h1>{config.get('marca', '')}</h1>
  <div class="hud-meta">
    <span>RELÓGIO <strong id="relogio">--:--:--</strong></span>
    <span>ALERTAS ATIVOS <strong id="contador">0</strong> / {len(eventos_js)}</span>
    <span>CADÊNCIA CONFIGURADA <strong>{config.get('cadencia_sugerida_horas')}h</strong></span>
  </div>
</header>
<div class="control-panel">
  <h2>// painel de controle — dispare qualquer evento, na ordem que quiser</h2>
  {''.join(botoes_html)}
</div>
<div class="master-caution ok" id="master-caution"><span class="mc-dot"></span>TODOS OS SISTEMAS NOMINAIS</div>
<div class="feed" id="feed"><div class="feed-line feed-empty">— nenhum evento ainda —</div></div>
<section class="squadron-strip">
  <h2>// esquadrão de combate — ações em andamento por agente</h2>
  <div class="squadron-grid" id="squadron-grid"><div class="squadron-empty">Nenhum agente acionado ainda.</div></div>
</section>
<section class="gauge-strip">
  <h2>// desempenho próprio — google/meta ads + ga4 (simulado)</h2>
  <div class="gauge-grid">{own_cards}</div>
</section>
<section class="ml-radar">
  <h2>// radar de posição — mercado livre (nós vs. concorrência, atualiza ao vivo)</h2>
  <div class="ml-radar-table-wrap">
    <table class="ml-radar-table" id="ml-radar-table">
      <thead><tr>
        <th>Produto</th><th>Quem</th><th>Posição</th><th>Preço</th><th>Desconto</th>
        <th>Reviews</th><th>Rating</th><th>Frete grátis</th><th>Anúncio patrocinado?</th>
      </tr></thead>
      <tbody id="ml-radar-body"></tbody>
    </table>
  </div>
  <p class="ml-radar-note">Ao disparar um evento de preço/desconto/visibilidade/entrada/saída, a linha do
  concorrente afetado atualiza e pisca. "Anúncio patrocinado?" é best-effort (ver references/fontes-e-limitacoes.md).</p>
</section>
<div class="grid" id="grid"><div class="empty" id="grid-empty">Nenhum evento disparado ainda — use o painel de controle acima.</div></div>
<p class="caveat">Simulador: todos os eventos e dados são simulados (autocontidos, sem dependência de
Windsor.ai/Apify). Cada botão do painel dispara um evento pré-configurado que passa pelo motor REAL do
sistema (mesmo make_alert/playbook/agentes usados em produção) — o que muda aqui é só a origem do dado.
Ver SKILL.md.</p>

<script>
const EVENTOS = {eventos_json};
const RADAR_INICIAL = {radar_inicial_json};
const reduzido = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const grid = document.getElementById('grid');
const feed = document.getElementById('feed');
const caution = document.getElementById('master-caution');
const contador = document.getElementById('contador');
const relogio = document.getElementById('relogio');
const squadronGrid = document.getElementById('squadron-grid');
const radarBody = document.getElementById('ml-radar-body');
const btnAutoplay = document.getElementById('btn-autoplay');
const btnReset = document.getElementById('btn-reset');

let relogioBase, piorSeveridade, disparados, agentesState, radarState;
const rankSev = {{ baixa: 0, media: 1, alta: 2 }};
const STATUS_LABEL = {{
  aguardando_autorizacao: ['AGUARDANDO AUTORIZAÇÃO', 'alta'],
  investigando: ['INVESTIGANDO', 'media'],
  monitorando: ['MONITORANDO', 'baixa'],
}};
const STATUS_PRIORIDADE = {{ aguardando_autorizacao: 0, investigando: 1, monitorando: 2 }};

function fmtRelogio(d) {{ return d.toTimeString().slice(0,8); }}

function estadoInicial() {{
  relogioBase = new Date(2026, 6, 31, 22, 10, 0);
  piorSeveridade = null;
  disparados = new Set();
  agentesState = {{}};
  radarState = JSON.parse(JSON.stringify(RADAR_INICIAL));
}}

function renderRadarTable() {{
  radarBody.innerHTML = '';
  const produtos = Object.keys(radarState).sort();
  for (const produto of produtos) {{
    const entradas = [...radarState[produto]].sort((a,b) => (a.position ?? 999) - (b.position ?? 999));
    for (const e of entradas) {{
      const tr = document.createElement('tr');
      tr.className = e.proprio ? 'radar-proprio' : 'radar-concorrente';
      tr.dataset.produto = produto;
      tr.dataset.concorrente = e.concorrente || '';
      const quem = e.proprio ? 'NÓS' : e.concorrente;
      const preco = (e.price !== null && e.price !== undefined) ? `R$ ${{e.price.toFixed(2)}}` : '—';
      const desconto = e.discount_pct ? `${{e.discount_pct}}%` : '—';
      const ads = ({{sim:'SIM', nao:'não', desconhecido:'n/d'}})[e.patrocinado || 'desconhecido'];
      tr.innerHTML = `<td>${{produto}}</td><td class="quem">${{quem}}</td><td>#${{e.position ?? '—'}}</td>` +
        `<td>${{preco}}</td><td>${{desconto}}</td><td>${{e.reviews ?? '—'}}</td><td>${{e.rating ?? '—'}}</td>` +
        `<td>${{e.frete_gratis ? 'sim' : 'não'}}</td><td class="ads-flag">${{ads}}</td>`;
      radarBody.appendChild(tr);
    }}
  }}
}}

function aplicarRadarUpdate(upd) {{
  if (!upd) return;
  const lista = radarState[upd.produto] || (radarState[upd.produto] = []);
  let entrada = lista.find(e => !e.proprio && e.concorrente === upd.concorrente);
  if (upd.acao === 'remover') {{
    radarState[upd.produto] = lista.filter(e => e.proprio || e.concorrente !== upd.concorrente);
  }} else if (upd.acao === 'adicionar') {{
    if (!entrada) {{
      lista.push({{proprio: false, concorrente: upd.concorrente, patrocinado: 'desconhecido', ...upd.campos}});
    }}
  }} else if (entrada) {{
    Object.assign(entrada, upd.campos);
  }}
  renderRadarTable();
  if (!reduzido) {{
    setTimeout(() => {{
      const row = radarBody.querySelector(`tr[data-produto="${{CSS.escape(upd.produto)}}"][data-concorrente="${{CSS.escape(upd.concorrente||'')}}"]`);
      if (row) row.querySelectorAll('td').forEach(td => td.classList.add('updated'));
    }}, 30);
  }}
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

function renderSquadron() {{
  const chaves = Object.keys(agentesState);
  if (!chaves.length) {{
    squadronGrid.innerHTML = '<div class="squadron-empty">Nenhum agente acionado ainda.</div>';
    return;
  }}
  chaves.sort((a,b) => STATUS_PRIORIDADE[agentesState[a].status] - STATUS_PRIORIDADE[agentesState[b].status]);
  squadronGrid.innerHTML = chaves.map(chave => {{
    const ag = agentesState[chave];
    const [label, sev] = STATUS_LABEL[ag.status] || [ag.status, 'baixa'];
    const itens = ag.resumos.slice(-4).map(r => `<li>${{r.slice(0,80)}}</li>`).join('');
    return `<div class="squadron-card sev-${{sev}}">
      <div class="squadron-head"><span class="squadron-emblema">${{ag.emblema}}</span><span class="squadron-nome">${{ag.nome}}</span></div>
      <span class="squadron-status">${{label}}</span>
      <div class="squadron-count">${{ag.resumos.length}} ação(ões) atribuída(s)</div>
      <ul class="squadron-list">${{itens}}</ul>
    </div>`;
  }}).join('');
}}

function dispararEvento(i, btnEl) {{
  if (disparados.has(i)) return;
  disparados.add(i);
  if (btnEl) btnEl.disabled = true;

  const ev = EVENTOS[i];
  const gridEmpty = document.getElementById('grid-empty');
  if (gridEmpty) gridEmpty.remove();
  const wrap = document.createElement('div');
  wrap.innerHTML = ev.card;
  const card = wrap.firstElementChild;
  grid.appendChild(card);

  relogioBase = new Date(relogioBase.getTime() + (5 + Math.random()*35) * 60000);
  relogio.textContent = fmtRelogio(relogioBase);

  const linha = document.createElement('div');
  linha.className = 'feed-line';
  linha.innerHTML = `<span class="ts">[${{fmtRelogio(relogioBase)}}]</span><span class="sev-${{ev.severidade}}">●</span> ${{ev.resumo}}`;
  if (feed.querySelector('.feed-empty')) feed.innerHTML = '';
  feed.prepend(linha);

  if (piorSeveridade === null || rankSev[ev.severidade] > rankSev[piorSeveridade]) piorSeveridade = ev.severidade;
  atualizarMasterCaution();
  contador.textContent = String(disparados.size);

  if (ev.agenteChave) {{
    const grupo = agentesState[ev.agenteChave] || (agentesState[ev.agenteChave] = {{
      nome: ev.agenteNome, emblema: ev.agenteEmblema, status: ev.statusAcao, resumos: [],
    }});
    grupo.resumos.push(ev.resumo);
    if (STATUS_PRIORIDADE[ev.statusAcao] < STATUS_PRIORIDADE[grupo.status]) grupo.status = ev.statusAcao;
    renderSquadron();
  }}

  aplicarRadarUpdate(ev.radar);

  if (!reduzido) card.scrollIntoView({{behavior: 'smooth', block: 'nearest'}});
}}

function reiniciar() {{
  grid.innerHTML = '<div class="empty" id="grid-empty">Nenhum evento disparado ainda — use o painel de controle acima.</div>';
  feed.innerHTML = '<div class="feed-line feed-empty">— nenhum evento ainda —</div>';
  contador.textContent = '0';
  relogio.textContent = '--:--:--';
  estadoInicial();
  atualizarMasterCaution();
  renderSquadron();
  renderRadarTable();
  document.querySelectorAll('.ev-btn').forEach(b => b.disabled = false);
}}

async function autoplay() {{
  btnAutoplay.disabled = true;
  for (let i = 0; i < EVENTOS.length; i++) {{
    if (disparados.has(i)) continue;
    const btn = document.querySelector(`.ev-btn[data-idx="${{i}}"]`);
    dispararEvento(i, btn);
    await new Promise(r => setTimeout(r, reduzido ? 0 : 900));
  }}
  btnAutoplay.disabled = false;
}}

btnReset.addEventListener('click', reiniciar);
btnAutoplay.addEventListener('click', autoplay);
estadoInicial();
renderRadarTable();
</script>
</body></html>"""

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser(description="Gera o simulador interativo da war room.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="war-room-simulador.html")
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
    wr.AGENTES = wr.load_agentes(os.path.join(SCRIPT_DIR, "agentes.json"))

    eventos = montar_biblioteca(config, playbook)
    proprio = wr.load_json(os.path.join(EX_DIR, "ml-simulado-proprio.json"), {})
    snap_inicial = wr.load_json(os.path.join(EX_DIR, "ml-simulado-rodada1.json"), {})
    radar_inicial = wr.montar_radar_ml(snap_inicial, proprio)

    render_simulador(eventos, radar_inicial, OWN_PERF, config, {"data": wr.now_iso()}, args.out)
    print(f"OK -> {args.out} ({len(eventos)} eventos disponíveis no painel de controle)")


if __name__ == "__main__":
    main()
