#!/usr/bin/env python3
"""
War Room de Concorrência — monitor de preço/desconto (Mercado Livre) + sinais de
atividade em ads (Meta/Google/Mercado Ads, via captura manual), com diff contra a
rodada anterior, classificação de severidade, e o pacote de resposta (impacto na
concorrência, impacto estimado no volume, estratégia imediata, KPIs impactados) para
cada mudança detectada.

Fonte automatizada: Mercado Livre (mesmo actor do radar-keywords-concorrentes,
viralanalyzer/mercadolivre-scraper). Gasto real de ads NÃO é capturável em nenhuma
plataforma — ver references/fontes-e-limitacoes.md. O que dá para automatizar é preço,
desconto e posição/visibilidade no Mercado Livre; atividade em Meta Ad Library e Google
Ads Transparency Center entra via --ads-manual (contagem de anúncios ativos, capturada
à mão nos painéis públicos).

Uso:
    python war_room.py --config config.json --out ../outputs/war-room.xlsx \
        --html ../outputs/war-room.html

    # incluindo os sinais manuais de ads:
    python war_room.py --config config.json --ads-manual ads-manual.json \
        --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
"""
import argparse
import json
import os
import sys
import urllib.parse
from datetime import datetime, timezone

from _fonts import FONT_ORBITRON_B64, FONT_SHARETECH_B64
from apify_common import apify_run, get_token, load_json, norm, save_json

ML_ACTOR = "viralanalyzer~mercadolivre-scraper"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")

SEVERIDADE_POR_NIVEL = {
    "agressiva": "alta", "forte": "alta", "critica": "alta",
    "moderada": "media", "moderado": "media",
    "leve": "baixa", "default": "media",
}


# ----------------------------------------------------------------------------- infra
def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# --------------------------------------------------------------------------- coleta
def match_competitor(nickname, concorrentes):
    n = norm(nickname)
    for c in concorrentes:
        for seller in c.get("sellers_ml", []):
            if norm(seller) in n:
                return c["nome"]
    return None


def collect_snapshot(config, token, produtos_filter, per_produto):
    """Retorna {produto_nome: {concorrente_nome: {seller, title, price, original_price,
    discount_pct, position, reviews, rating, url, total_listagens}}}."""
    concorrentes = config.get("concorrentes", [])
    produtos = config.get("produtos_monitorados", [])
    if produtos_filter:
        produtos = [p for p in produtos if p["nome"] in produtos_filter]

    snapshot = {}
    for prod in produtos:
        termo = prod["termo_busca_ml"]
        print(f"  buscando '{termo}' no Mercado Livre...", file=sys.stderr)
        items, err = apify_run(ML_ACTOR, {"searchQuery": termo, "maxItems": per_produto}, token)
        if err:
            print(f"  ERRO ao buscar '{termo}': {err}", file=sys.stderr)
        por_concorrente = {}
        for idx, item in enumerate(items or []):
            seller = item.get("seller") or {}
            nick = seller.get("nickname") if isinstance(seller, dict) else (seller or "")
            nome_conc = match_competitor(nick, concorrentes)
            if not nome_conc:
                continue
            position = idx + 1
            if nome_conc in por_concorrente:
                por_concorrente[nome_conc]["total_listagens"] += 1
                if position < por_concorrente[nome_conc]["position"]:
                    por_concorrente[nome_conc]["position"] = position
                continue
            por_concorrente[nome_conc] = {
                "seller": nick,
                "title": item.get("title"),
                "price": item.get("price"),
                "original_price": item.get("original_price"),
                "discount_pct": item.get("discount_pct"),
                "position": position,
                "reviews": item.get("reviews_count"),
                "rating": item.get("average_rating"),
                "url": item.get("url"),
                "total_listagens": 1,
            }
        snapshot[prod["nome"]] = por_concorrente
    return snapshot


# ------------------------------------------------------------------------ playbook
def load_playbook(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def playbook_entry(playbook, tipo, nivel):
    bloco = playbook.get(tipo, {})
    return bloco.get(nivel) or bloco.get("default") or {
        "impacto_concorrencia": "", "impacto_volume": "", "estrategia": [], "kpis": [],
    }


def impacto_volume_estimado(pct_variacao_preco, elasticidade, own_kpis=None):
    impacto = elasticidade * pct_variacao_preco
    sinal = "a favor do concorrente" if impacto < 0 else "a seu favor"
    texto = (f"Estimativa: {impacto:+.1f}% de deslocamento de demanda ({sinal}), "
             f"usando elasticidade configurada ({elasticidade}) x variação de preço "
             f"observada ({pct_variacao_preco:+.1f}%). Premissa, não dado medido.")
    if own_kpis and own_kpis.get("cpa") and own_kpis.get("roas") is not None:
        texto += (f" Desempenho próprio atual no produto (Google/Meta Ads, últimos dados "
                  f"importados): CPA R$ {own_kpis['cpa']:.2f}, ROAS {own_kpis['roas']:.2f}, "
                  f"CTR {own_kpis['ctr_pct']:.2f}% — use como referência real para decidir "
                  f"quanto de margem cabe sacrificar num price-match.")
    return texto


def make_alert(tipo, nivel, produto, concorrente, resumo, detalhes, evidencia_url, playbook,
               impacto_volume_real=None):
    entry = playbook_entry(playbook, tipo, nivel)
    impacto_volume = entry.get("impacto_volume", "")
    if impacto_volume_real:
        impacto_volume = f"{impacto_volume} {impacto_volume_real}"
    return {
        "data": now_iso(),
        "tipo": tipo,
        "nivel": nivel,
        "severidade": SEVERIDADE_POR_NIVEL.get(nivel, "media"),
        "produto": produto,
        "concorrente": concorrente,
        "resumo": resumo,
        "detalhes": detalhes,
        "impacto_concorrencia": entry.get("impacto_concorrencia", ""),
        "impacto_volume": impacto_volume,
        "estrategia": entry.get("estrategia", []),
        "kpis": entry.get("kpis", []),
        "evidencia_url": evidencia_url,
    }


# --------------------------------------------------------------------------- diff
def classificar_queda(pct_queda, limiares):
    if pct_queda >= limiares["queda_preco_moderada_pct"]:
        return "agressiva"
    if pct_queda >= limiares["queda_preco_leve_pct"]:
        return "moderada"
    return "leve"


def classificar_aumento(pct_aumento, limiares):
    if pct_aumento >= limiares["aumento_preco_moderado_pct"]:
        return "agressiva"
    if pct_aumento >= limiares["aumento_preco_leve_pct"]:
        return "moderada"
    return "leve"


def diff_precos(old_snap, new_snap, config, playbook, own_perf=None):
    limiares = config["limiares"]
    elasticidade = config.get("elasticidade_estimada", -1.5)
    own_perf = own_perf or {}
    alertas = []

    for produto, novos in new_snap.items():
        antigos = old_snap.get(produto, {})

        for conc, novo in novos.items():
            if conc not in antigos:
                alertas.append(make_alert(
                    "novo_entrante", "default", produto, conc,
                    f"{conc} apareceu pela 1a vez na busca de '{produto}' (posição {novo['position']}).",
                    {"position": novo["position"], "price": novo["price"]},
                    novo["url"], playbook))
                continue

            antigo = antigos[conc]

            # preço
            kpis_proprios = own_perf.get(produto)
            if antigo.get("price") and novo.get("price") and antigo["price"] > 0:
                pct = (novo["price"] - antigo["price"]) / antigo["price"] * 100
                if pct <= -limiares["queda_preco_leve_pct"]:
                    nivel = classificar_queda(-pct, limiares)
                    estimativa = impacto_volume_estimado(pct, elasticidade, kpis_proprios)
                    alertas.append(make_alert(
                        "queda_preco", nivel, produto, conc,
                        f"{conc} baixou o preço de '{produto}' de R$ {antigo['price']:.2f} "
                        f"para R$ {novo['price']:.2f} ({pct:+.1f}%).",
                        {"price_antigo": antigo["price"], "price_novo": novo["price"], "pct": pct},
                        novo["url"], playbook, impacto_volume_real=estimativa))
                elif pct >= limiares["aumento_preco_leve_pct"]:
                    nivel = classificar_aumento(pct, limiares)
                    estimativa = impacto_volume_estimado(pct, elasticidade, kpis_proprios)
                    alertas.append(make_alert(
                        "aumento_preco_concorrente", nivel, produto, conc,
                        f"{conc} subiu o preço de '{produto}' de R$ {antigo['price']:.2f} "
                        f"para R$ {novo['price']:.2f} ({pct:+.1f}%).",
                        {"price_antigo": antigo["price"], "price_novo": novo["price"], "pct": pct},
                        novo["url"], playbook, impacto_volume_real=estimativa))

            # desconto
            d_antigo = antigo.get("discount_pct") or 0
            d_novo = novo.get("discount_pct") or 0
            if d_novo > d_antigo and (d_novo - d_antigo) >= 3:
                alertas.append(make_alert(
                    "novo_desconto", "default", produto, conc,
                    f"{conc} passou a oferecer {d_novo:.0f}% de desconto em '{produto}' "
                    f"(antes {d_antigo:.0f}%).",
                    {"discount_antigo": d_antigo, "discount_novo": d_novo},
                    novo["url"], playbook))

            # visibilidade: posição ou reviews
            pos_antiga = antigo.get("position")
            pos_nova = novo.get("position")
            salto_posicao = (pos_antiga is not None and pos_nova is not None
                              and (pos_antiga - pos_nova) >= limiares["salto_posicao_min"])

            rev_antigo = antigo.get("reviews") or 0
            rev_novo = novo.get("reviews") or 0
            salto_reviews = False
            if rev_antigo >= 5:
                cresc = (rev_novo - rev_antigo) / rev_antigo * 100
                salto_reviews = cresc >= limiares["crescimento_reviews_pct"]

            if salto_posicao or salto_reviews:
                motivo = []
                if salto_posicao:
                    motivo.append(f"subiu da posição {pos_antiga} para {pos_nova}")
                if salto_reviews:
                    motivo.append(f"reviews de {rev_antigo} para {rev_novo}")
                alertas.append(make_alert(
                    "salto_visibilidade_ml", "default", produto, conc,
                    f"{conc} ganhou visibilidade em '{produto}': " + " e ".join(motivo) + ".",
                    {"position_antiga": pos_antiga, "position_nova": pos_nova,
                     "reviews_antigo": rev_antigo, "reviews_novo": rev_novo},
                    novo["url"], playbook))

        for conc, antigo in antigos.items():
            if conc not in novos:
                alertas.append(make_alert(
                    "concorrente_sumiu", "default", produto, conc,
                    f"{conc} sumiu da busca de '{produto}' (estava na posição {antigo.get('position')}). "
                    f"Hipótese: ruptura de estoque ou pausa de campanha — não confirmado.",
                    {"ultima_position": antigo.get("position")},
                    antigo.get("url"), playbook))

    return alertas


def load_ads_manual(path):
    entries = load_json(path, [])
    validas = []
    for e in entries:
        if all(k in e for k in ("data", "concorrente", "canal", "anuncios_ativos")):
            validas.append(e)
    return validas


def diff_ads(entries, ads_history, config, playbook):
    limiares = config["limiares"]
    alertas = []
    atual_por_chave = {}
    for e in entries:
        chave = f"{e['concorrente']}|{e['canal']}"
        atual = atual_por_chave.get(chave)
        if not atual or e["data"] >= atual["data"]:
            atual_por_chave[chave] = e

    for chave, atual in atual_por_chave.items():
        anterior = ads_history.get(chave)
        if anterior:
            delta = atual["anuncios_ativos"] - anterior["anuncios_ativos"]
            dobrou = anterior["anuncios_ativos"] > 0 and atual["anuncios_ativos"] >= anterior["anuncios_ativos"] * 2
            if dobrou:
                nivel = "forte"
            elif delta >= limiares["aumento_ads_min_unidades"]:
                nivel = "moderado"
            else:
                nivel = None
            if nivel:
                alertas.append(make_alert(
                    "aumento_atividade_ads", nivel, "(todos os produtos)", atual["concorrente"],
                    f"{atual['concorrente']} passou de {anterior['anuncios_ativos']} para "
                    f"{atual['anuncios_ativos']} anúncios ativos em {atual['canal']} "
                    f"(sinal de atividade, não de valor gasto).",
                    {"canal": atual["canal"], "anterior": anterior["anuncios_ativos"],
                     "atual": atual["anuncios_ativos"]},
                    None, playbook))
        ads_history[chave] = {"data": atual["data"], "anuncios_ativos": atual["anuncios_ativos"]}
    return alertas, ads_history


def build_manual_links(config):
    links = []
    for c in config.get("concorrentes", []):
        meta_q = urllib.parse.quote(c.get("meta_page", c["nome"]))
        google_dom = c.get("dominio_site", "")
        links.append({
            "concorrente": c["nome"],
            "meta_ad_library": f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=BR&q={meta_q}",
            "google_ads_transparency": f"https://adstransparency.google.com/?region=BR&domain={google_dom}" if google_dom else None,
        })
    return links


def ingest_novos_criativos(path, canal_label, playbook, analises=None):
    """Lê a saída de meta_ads.py ou google_ads_transparency.py (novos_anuncios) e
    converte cada anúncio novo num alerta com o pacote completo do playbook.

    `analises` (opcional) é um dict {ad_id: {"gancho":..., "oferta":..., "formato":...,
    "cta":..., "observacao":...}} escrito pelo AGENTE depois de olhar a evidência
    (imagem/vídeo) de um criativo que está impactando o rendimento — nunca inventado
    sem a evidência em mãos. Ver SKILL.md, passo 6."""
    analises = analises or {}
    data = load_json(path, {})
    alertas = []
    for n in data.get("novos_anuncios", []):
        texto = (n.get("titulo") or n.get("corpo") or n.get("descricao") or "(sem texto capturado)")
        resumo = f"{n['concorrente']} lançou novo anúncio ativo em {canal_label}: \"{texto[:90]}\""
        detalhes = {k: v for k, v in n.items() if k != "concorrente"}
        analise = analises.get(n.get("ad_id"))
        if analise:
            detalhes["analise"] = analise
            resumo += " — ANÁLISE DE CRIATIVO ANEXADA (ver battlecard)"
        evidencia = n.get("url_anuncio") or n.get("imagem_url") or n.get("video_url")
        alertas.append(make_alert("novo_criativo_concorrente", "default", "(todos os produtos)",
                                   n["concorrente"], resumo, detalhes, evidencia, playbook))
    return alertas


def fmt_pct(v):
    return f"{v * 100:.1f}%" if v is not None else "n/d"


def ingest_quedas_keyword(path, playbook):
    """Lê a saída de keyword_auction.py (quedas) e converte cada queda de keyword
    num alerta com os pontos de interferência (leilão), CPC e estratégia de combate."""
    data = load_json(path, {})
    alertas = []
    for q in data.get("quedas", []):
        doms = q.get("pontos_de_interferencia") or []
        doms_txt = ", ".join(f"{d['dominio']} ({d['aparicoes_no_periodo']}x)" for d in doms) or "nenhum domínio capturado no período"
        cpc_txt = f"R$ {q['cpc_medio']:.2f}" if q.get("cpc_medio") is not None else "n/d"
        topo_txt = (f"R$ {q['top_of_page_cpc']:.2f} (estimativa do Google)"
                    if q.get("top_of_page_cpc") is not None else "não disponível para este termo/período")
        resumo = (f"'{q['keyword']}' ({q['campanha']}) perdeu impression share: "
                  f"{fmt_pct(q.get('impression_share_antes'))} → {fmt_pct(q.get('impression_share_agora'))} "
                  f"(rank lost {fmt_pct(q.get('rank_lost_antes'))} → {fmt_pct(q.get('rank_lost_agora'))}). "
                  f"Pontos de interferência no leilão: {doms_txt}. "
                  f"CPC atual pago: {cpc_txt}. CPC de topo de página: {topo_txt}.")
        detalhes = {k: v for k, v in q.items() if k != "keyword"}
        alertas.append(make_alert("queda_performance_keyword", q.get("nivel", "moderada"),
                                   q["keyword"], "(leilão — ver pontos de interferência)",
                                   resumo, detalhes, None, playbook))
    return alertas


def ingest_picos_trends(path, playbook):
    """Lê a saída de google_trends.py (picos) e converte cada pico num alerta."""
    data = load_json(path, {})
    alertas = []
    for p in data.get("picos", []):
        resumo = (f"Interesse de busca por '{p['termo']}' subiu de {p['media_antiga']:.0f} "
                  f"para {p['media_nova']:.0f} ({p['pct']:+.0f}%).")
        alertas.append(make_alert("pico_interesse_busca", "default", p["termo"], "(Google Trends)",
                                   resumo, p, None, playbook))
    return alertas


# ------------------------------------------------------------------------- console
def print_console(alertas):
    print("\n" + "=" * 74)
    print("WAR ROOM DE CONCORRÊNCIA")
    print("=" * 74)
    if not alertas:
        print("Nenhuma mudança detectada nesta rodada (ou é a linha de base — 1a execução).")
        print("=" * 74 + "\n")
        return
    altas = [a for a in alertas if a["severidade"] == "alta"]
    medias = [a for a in alertas if a["severidade"] == "media"]
    baixas = [a for a in alertas if a["severidade"] == "baixa"]
    print(f"Alertas: {len(altas)} alta(s), {len(medias)} média(s), {len(baixas)} baixa(s)\n")
    for a in altas:
        print("!" * 74)
        print(f"ALERTA ALTA — {a['tipo']} ({a['nivel']}) — {a['produto']} x {a['concorrente']}")
        print(f"  {a['resumo']}")
        print(f"  Impacto na concorrência: {a['impacto_concorrencia']}")
        print(f"  Impacto no volume: {a['impacto_volume']}")
        print(f"  Estratégia imediata: {'; '.join(a['estrategia'])}")
        print(f"  KPIs impactados: {', '.join(a['kpis'])}")
        print("!" * 74)
    for a in medias + baixas:
        print(f"  [{a['severidade']}] {a['tipo']}/{a['nivel']} — {a['resumo']}")
    print("\n(!) Investimento real em ads NÃO é dado público em nenhuma plataforma — os")
    print("    sinais de 'aumento_atividade_ads' são contagem de anúncios ativos, não gasto.")
    print("=" * 74 + "\n")


# --------------------------------------------------------------------------- xlsx
def write_xlsx(alertas_rodada, alertas_log, snapshot, ads_entries, ads_history, config, meta, path,
               own_perf=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    NAVY = "1F2A44"; RED = "C0392B"; AMBER = "E67E22"; GREEN = "27AE60"
    hfont = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill("solid", fgColor=NAVY)
    sev_fill = {"alta": RED, "media": AMBER, "baixa": GREEN}

    def style_header(ws, ncols, row=1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = hfont
            cell.fill = hfill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    wb = Workbook()

    # -- Resumo
    ws = wb.active
    ws.title = "Resumo"
    ws["A1"] = f"War Room — {config.get('marca', '')}"
    ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    ws["A2"] = f"Gerado em {meta['data']} | cadência sugerida: {config.get('cadencia_sugerida_horas')}h"
    ws["A2"].font = Font(italic=True, color="555555", size=10)
    n_alta = sum(1 for a in alertas_rodada if a["severidade"] == "alta")
    n_media = sum(1 for a in alertas_rodada if a["severidade"] == "media")
    n_baixa = sum(1 for a in alertas_rodada if a["severidade"] == "baixa")
    rows = [
        ("", ""), ("INDICADOR", "VALOR"),
        ("Alertas nesta rodada — severidade ALTA", n_alta),
        ("Alertas nesta rodada — severidade MÉDIA", n_media),
        ("Alertas nesta rodada — severidade BAIXA", n_baixa),
        ("Total de alertas acumulados no histórico", len(alertas_log)),
        ("Produtos monitorados", len(config.get("produtos_monitorados", []))),
        ("Concorrentes monitorados", len(config.get("concorrentes", []))),
        ("Investimento real em ads capturado", "0 — não é dado público (ver aba Limitações)"),
    ]
    start = 4
    for i, (a, b) in enumerate(rows):
        ws.cell(row=start + i, column=1, value=a)
        ws.cell(row=start + i, column=2, value=b)
    style_header(ws, 2, row=start + 1)
    ws.column_dimensions["A"].width = 50
    ws.column_dimensions["B"].width = 48

    # -- Battlecards (rodada atual)
    ws = wb.create_sheet("Battlecards")
    cols = ["severidade", "tipo", "nivel", "produto", "concorrente", "resumo",
            "impacto_concorrencia", "impacto_volume", "estrategia_imediata", "kpis_impactados", "evidencia_url"]
    ws.append([c.upper() for c in cols])
    style_header(ws, len(cols))
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    for a in sorted(alertas_rodada, key=lambda x: ordem[x["severidade"]]):
        ws.append([a["severidade"], a["tipo"], a["nivel"], a["produto"], a["concorrente"], a["resumo"],
                   a["impacto_concorrencia"], a["impacto_volume"],
                   "; ".join(a["estrategia"]), ", ".join(a["kpis"]), a["evidencia_url"]])
        sf = sev_fill.get(a["severidade"])
        if sf:
            cell = ws.cell(row=ws.max_row, column=1)
            cell.fill = PatternFill("solid", fgColor=sf)
            cell.font = Font(color="FFFFFF", bold=True)
    widths = [11, 22, 12, 22, 20, 46, 40, 40, 55, 40, 45]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"

    # -- Alertas (log histórico acumulado)
    ws = wb.create_sheet("Alertas (histórico)")
    ws.append([c.upper() for c in cols[:1] + ["data"] + cols[1:]])
    style_header(ws, len(cols) + 1)
    log_ordenado = sorted(alertas_log, key=lambda x: x.get("data", ""), reverse=True)
    for a in log_ordenado:
        ws.append([a["severidade"], a.get("data"), a["tipo"], a["nivel"], a["produto"], a["concorrente"],
                   a["resumo"], a["impacto_concorrencia"], a["impacto_volume"],
                   "; ".join(a["estrategia"]), ", ".join(a["kpis"]), a.get("evidencia_url")])
        sf = sev_fill.get(a["severidade"])
        if sf:
            cell = ws.cell(row=ws.max_row, column=1)
            cell.fill = PatternFill("solid", fgColor=sf)
            cell.font = Font(color="FFFFFF", bold=True)
    for i, w in enumerate([11, 18, 22, 12, 22, 20, 46, 40, 40, 55, 40, 45], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    # -- Precos Atuais
    ws = wb.create_sheet("Preços Atuais")
    cols2 = ["produto", "concorrente", "seller", "price", "original_price", "discount_pct",
             "position", "total_listagens", "reviews", "rating", "url"]
    ws.append([c.upper() for c in cols2])
    style_header(ws, len(cols2))
    for produto, por_conc in snapshot.items():
        for conc, dados in por_conc.items():
            ws.append([produto, conc, dados.get("seller"), dados.get("price"), dados.get("original_price"),
                       dados.get("discount_pct"), dados.get("position"), dados.get("total_listagens"),
                       dados.get("reviews"), dados.get("rating"), dados.get("url")])
    for i, w in enumerate([24, 20, 26, 9, 13, 12, 9, 12, 9, 8, 45], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"

    # -- Ads (manual)
    if ads_entries:
        ws = wb.create_sheet("Ads (manual)")
        cols3 = ["data", "concorrente", "canal", "anuncios_ativos"]
        ws.append([c.upper() for c in cols3])
        style_header(ws, len(cols3))
        for e in ads_entries:
            ws.append([e["data"], e["concorrente"], e["canal"], e["anuncios_ativos"]])
        for i, w in enumerate([12, 22, 24, 16], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    # -- Desempenho Próprio (Google Ads / Meta Ads, via Windsor.ai)
    if own_perf:
        ws = wb.create_sheet("Desempenho Próprio")
        cols4 = ["produto", "spend", "impressions", "clicks", "ctr_pct", "cpc",
                 "conversions", "conversions_value", "cpa", "roas", "campanhas"]
        ws.append([c.upper() for c in cols4])
        style_header(ws, len(cols4))
        for produto, v in own_perf.items():
            ws.append([produto, v.get("spend"), v.get("impressions"), v.get("clicks"),
                       v.get("ctr_pct"), v.get("cpc"), v.get("conversions"),
                       v.get("conversions_value"), v.get("cpa"), v.get("roas"),
                       "; ".join(v.get("campanhas", []))])
        for i, w in enumerate([22, 12, 13, 10, 10, 10, 12, 16, 10, 8, 55], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    # -- Limitacoes
    ws = wb.create_sheet("Limitações")
    notas = [
        ("O que este relatório CAPTURA automaticamente", ""),
        ("Mercado Livre", "Preço, preço original, desconto, posição na busca e reviews de cada "
                          "concorrente cadastrado, comparados com a rodada anterior."),
        ("", ""),
        ("O que NÃO captura", ""),
        ("Investimento real (R$) em Google Ads ou Meta Ads", "Não existe fonte pública para o "
                          "gasto de terceiros em nenhuma plataforma. Não é estimado, não é inventado."),
        ("Anúncios pagos do Google na SERP", "O scraper de SERP usado não retorna paidResults/"
                          "paidProducts — confirmado vazio mesmo em termos com anúncio comprovado."),
        ("Contagem de anúncios ativos (Meta Ad Library / Google Ads Transparency Center)",
                          "É sinal de ATIVIDADE, não de valor gasto, e hoje é capturado manualmente "
                          "via --ads-manual (o script não navega esses painéis sozinho)."),
        ("Posição no Mercado Livre = patrocinado?", "O scraper não confirma se um item específico "
                          "é Mercado Ads ou orgânico — subida de posição é tratada como proxy, não prova."),
        ("", ""),
        ("Como cobrir melhor o pago", "Veja references/fontes-e-limitacoes.md e a skill "
                          "brand-bidding-monitor para os métodos manuais completos (SERP, Ad Library, "
                          "Ads Transparency Center, Auction Insights)."),
    ]
    for a, b in notas:
        ws.append([a, b])
        if b == "" and a:
            ws.cell(row=ws.max_row, column=1).font = Font(bold=True, color=NAVY, size=12)
    ws.column_dimensions["A"].width = 44
    ws.column_dimensions["B"].width = 95
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    wb.save(path)


# ---------------------------------------------------------------------------- html
SEV_LABEL = {"alta": "CRÍTICO", "media": "ATENÇÃO", "baixa": "NOMINAL"}
SEV_ICON = {"alta": "▲", "media": "◆", "baixa": "●"}


def render_creative(detalhes):
    """Embute a imagem/vídeo do criativo (Meta/Google) quando a evidência trouxer isso."""
    img = detalhes.get("imagem_url")
    vid = detalhes.get("video_url")
    if not img and not vid:
        return ""
    imagem_html = f'<img src="{img}" alt="Criativo do concorrente" loading="lazy">' if img else ""
    video_html = (f'<a class="video-link" href="{vid}" target="_blank" rel="noopener">▶ ver vídeo do anúncio</a>'
                  if vid else "")
    return f'<div class="creative">{imagem_html}{video_html}</div>'


def render_analise_criativo(detalhes):
    analise = detalhes.get("analise")
    if not analise:
        return ""
    linhas = "".join(
        f'<div class="analise-row"><span>{campo}</span><p>{valor}</p></div>'
        for campo, valor in (
            ("Gancho", analise.get("gancho")), ("Oferta", analise.get("oferta")),
            ("Formato", analise.get("formato")), ("CTA", analise.get("cta")),
            ("Observação", analise.get("observacao")),
        ) if valor
    )
    return f'<p class="label">// análise do criativo</p><div class="analise-criativo">{linhas}</div>'


def render_pontos_interferencia(detalhes):
    pontos = detalhes.get("pontos_de_interferencia")
    if not pontos:
        return ""
    chips = "".join(f'<span class="kpi">{p["dominio"]} · {p["aparicoes_no_periodo"]}x</span>' for p in pontos)
    return f'<p class="label">// concorrentes no leilão (pontos de interferência)</p><div class="kpis">{chips}</div>'


def render_card(a, idx):
    estrategia_html = "".join(f"<li>{s}</li>" for s in a["estrategia"])
    kpis_html = "".join(f'<span class="kpi">{k}</span>' for k in a["kpis"])
    link = (f'<a href="{a["evidencia_url"]}" target="_blank" rel="noopener">◈ ver evidência</a>'
            if a.get("evidencia_url") else "<span></span>")
    delay = f"{min(idx, 10) * 0.05:.2f}s"
    creative_html = render_creative(a.get("detalhes") or {})
    analise_html = render_analise_criativo(a.get("detalhes") or {})
    interferencia_html = render_pontos_interferencia(a.get("detalhes") or {})
    return f"""
    <article class="card sev-{a['severidade']}" style="--d:{delay}">
      <div class="card-head">
        <span class="badge"><span class="badge-ico">{SEV_ICON.get(a['severidade'], '●')}</span>{SEV_LABEL.get(a['severidade'], a['severidade'].upper())}</span>
        <span class="tipo">{a['tipo'].replace('_', ' ')} · nível {a['nivel']}</span>
      </div>
      <h3><span class="crosshair" aria-hidden="true"></span>{a['produto']} <span class="vs">vs</span> {a['concorrente']}</h3>
      <p class="resumo">{a['resumo']}</p>
      {creative_html}
      {analise_html}
      {interferencia_html}
      <p><span class="label">// impacto na concorrência</span>{a['impacto_concorrencia']}</p>
      <p><span class="label">// impacto estimado no volume</span>{a['impacto_volume']}</p>
      <p class="label">// estratégia imediata</p>
      <ul>{estrategia_html}</ul>
      <div class="kpis">{kpis_html}</div>
      <div class="foot"><span>{a['data']}</span>{link}</div>
    </article>"""


def render_own_kpi(produto, v):
    cpa = f"R$ {v['cpa']:.2f}" if v.get("cpa") else "—"
    roas = f"{v['roas']:.2f}×" if v.get("roas") is not None else "—"
    ctr = v.get("ctr_pct", 0)
    barra = max(2, min(100, ctr * 10))
    return f"""
    <div class="gauge">
      <div class="gauge-produto">{produto}</div>
      <div class="gauge-main">
        <span class="gauge-value">{roas}</span><span class="gauge-tag">ROAS</span>
      </div>
      <div class="gauge-row"><span>CPA</span><strong>{cpa}</strong></div>
      <div class="gauge-row"><span>INVEST.</span><strong>R$ {v.get('spend', 0):,.0f}</strong></div>
      <div class="gauge-row"><span>CTR</span><strong>{ctr:.2f}%</strong></div>
      <div class="signal-bar"><span style="width:{barra}%"></span></div>
    </div>"""


def write_html(alertas_rodada, config, meta, path, own_perf=None):
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    ordenados = sorted(alertas_rodada, key=lambda x: ordem[x["severidade"]])
    cards = "".join(render_card(a, i) for i, a in enumerate(ordenados))
    if not cards:
        cards = ('<div class="empty">❖ NENHUM ALVO NO RADAR NESTA VARREDURA<br>'
                  '<span>(sem mudanças em relação à última rodada, ou é a linha de base)</span></div>')

    n_alta = sum(1 for a in alertas_rodada if a["severidade"] == "alta")
    n_media = sum(1 for a in alertas_rodada if a["severidade"] == "media")
    if n_alta:
        mc_level, mc_text = "alta", f"MASTER WARNING — {n_alta} ALERTA(S) CRÍTICO(S) — AÇÃO IMEDIATA"
    elif n_media:
        mc_level, mc_text = "media", f"CAUTION — {n_media} ALERTA(S) EM ATENÇÃO — REVISAR"
    else:
        mc_level, mc_text = "ok", "TODOS OS SISTEMAS NOMINAIS — NENHUMA AMEAÇA DETECTADA"

    own_kpi_section = ""
    if own_perf:
        own_cards = "".join(render_own_kpi(p, v) for p, v in own_perf.items())
        own_kpi_section = f"""
<section class="gauge-strip">
  <h2>// desempenho próprio — google/meta ads (últimos dados importados)</h2>
  <div class="gauge-grid">{own_cards}</div>
</section>"""

    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>War Room — {config.get('marca', '')}</title>
<style>
  @font-face {{
    font-family: 'Orbitron'; font-weight: 400 900; font-style: normal; font-display: swap;
    src: url(data:font/woff2;base64,{FONT_ORBITRON_B64}) format('woff2');
  }}
  @font-face {{
    font-family: 'Share Tech Mono'; font-weight: 400; font-style: normal; font-display: swap;
    src: url(data:font/woff2;base64,{FONT_SHARETECH_B64}) format('woff2');
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
  .frame {{ position: relative; z-index: 1; }}
  header.frame {{
    display: flex; flex-direction: column; gap: 8px; padding: 20px 32px;
    border-bottom: 1px solid var(--line); background: linear-gradient(180deg, var(--panel), transparent);
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
  .master-caution {{
    margin: 10px 32px 0; padding: 9px 16px; border-radius: 4px; font-size: .78rem; font-weight: 700;
    letter-spacing: .05em; text-transform: uppercase; display: flex; align-items: center; gap: 10px;
    border: 1px solid; z-index: 1; position: relative;
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
  .signal-bar {{ margin-top: 10px; height: 3px; background: rgba(255,255,255,.06); border-radius: 2px; overflow: hidden; }}
  .signal-bar span {{ display: block; height: 100%; background: var(--hud); box-shadow: 0 0 6px var(--hud-soft); }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px; padding: 24px 32px; position: relative; z-index: 1;
  }}
  .card {{
    position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: 4px;
    padding: 16px 18px; animation: rise .5s ease both; animation-delay: var(--d, 0s);
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
  .creative {{
    margin: 10px 0; border: 1px solid var(--line); border-radius: 4px; overflow: hidden;
    background: var(--panel-2);
  }}
  .creative img {{ display: block; width: 100%; max-height: 260px; object-fit: cover; }}
  .video-link {{
    display: block; padding: 10px 12px; font-size: .8rem; text-decoration: none;
    color: var(--hud); text-align: center;
  }}
  .analise-criativo {{
    margin: 6px 0 10px; padding: 10px 12px; border-left: 2px solid var(--hud-soft);
    background: var(--panel-2); border-radius: 0 4px 4px 0;
  }}
  .analise-row {{ display: flex; gap: 8px; font-size: .82rem; margin-bottom: 4px; }}
  .analise-row:last-child {{ margin-bottom: 0; }}
  .analise-row span {{
    flex: none; width: 84px; color: var(--hud); font-size: .68rem; text-transform: uppercase;
    letter-spacing: .04em; padding-top: 2px;
  }}
  .analise-row p {{ margin: 0; font-size: .82rem; }}
  .foot {{
    margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--line);
    display: flex; justify-content: space-between; font-size: .7rem; color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }}
  .foot a {{ text-decoration: none; }}
  .foot a:hover {{ text-decoration: underline; }}
  .empty {{
    padding: 60px 20px; color: var(--text-dim); grid-column: 1 / -1; text-align: center;
    font-size: 1rem; letter-spacing: .04em;
  }}
  .empty span {{ display: block; margin-top: 8px; font-size: .78rem; opacity: .7; }}
  .caveat {{
    padding: 0 32px 30px; font-size: .76rem; color: var(--text-dim); max-width: 860px;
    line-height: 1.6; position: relative; z-index: 1;
  }}
  a:focus-visible, button:focus-visible {{ outline: 2px solid var(--hud); outline-offset: 2px; }}
  @media (prefers-reduced-motion: reduce) {{
    .scan-band {{ display: none; }}
    * {{ animation: none !important; transition: none !important; }}
  }}
</style></head>
<body>
<div class="scan-band"></div>
<header class="frame">
  <div class="hud-top-row">
    <span class="eyebrow">◈ sistema de guerra competitiva</span>
    <span class="radar-badge"><span class="radar"></span> monitorando</span>
  </div>
  <h1>{config.get('marca', '')}</h1>
  <div class="hud-meta">
    <span>ÚLTIMA VARREDURA <strong>{meta['data']}</strong></span>
    <span>CADÊNCIA <strong>{config.get('cadencia_sugerida_horas')}h</strong></span>
    <span>ALERTAS NESTA RODADA <strong>{len(alertas_rodada)}</strong></span>
  </div>
</header>
<div class="master-caution {mc_level}"><span class="mc-dot"></span>{mc_text}</div>
{own_kpi_section}
<div class="grid">{cards}</div>
<p class="caveat">Investimento real (R$) em ads não é dado público em nenhuma plataforma — os
sinais de atividade em ads (Meta Ad Library / Google Ads Transparency Center) refletem
contagem de anúncios ativos capturada manualmente, não valor gasto. Ver
references/fontes-e-limitacoes.md.</p>
</body></html>"""

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


# ------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="War Room de monitoramento de concorrência.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="war-room.xlsx")
    ap.add_argument("--html", default="war-room.html")
    ap.add_argument("--ads-manual", default=None, help="JSON com contagem manual de anúncios ativos")
    ap.add_argument("--own-performance", default=None,
                     help="JSON {'por_produto': {...}} gerado por own_performance.py "
                          "(desempenho real de Google/Meta Ads, via Windsor.ai)")
    ap.add_argument("--produtos", default=None, help="lista separada por vírgula p/ limitar a coleta")
    ap.add_argument("--per-produto", type=int, default=15)
    ap.add_argument("--history-dir", default=DEFAULT_HISTORY_DIR)
    ap.add_argument("--token", default=None)
    ap.add_argument("--simulate-ml", default=None,
                     help="JSON com um snapshot pronto (mesmo formato interno de collect_snapshot) "
                          "para testar/demonstrar o pipeline sem gastar Apify nem precisar de token. "
                          "Ver scripts/examples/.")
    ap.add_argument("--meta-ads-json", default=None,
                     help="saída de meta_ads.py (novos_anuncios) — vira alertas 'novo_criativo_concorrente'")
    ap.add_argument("--google-ads-transparency-json", default=None,
                     help="saída de google_ads_transparency.py (novos_anuncios) — idem, canal Google")
    ap.add_argument("--trends-json", default=None,
                     help="saída de google_trends.py (picos) — vira alertas 'pico_interesse_busca'")
    ap.add_argument("--keyword-auction-json", default=None,
                     help="saída de keyword_auction.py (quedas) — vira alertas 'queda_performance_keyword' "
                          "com pontos de interferência (leilão), CPC e estratégia de combate")
    ap.add_argument("--creative-analysis-json", default=None,
                     help="JSON {ad_id: {gancho, oferta, formato, cta, observacao}} escrito pelo agente "
                          "depois de olhar a evidência de um criativo novo que está impactando o rendimento")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    config.setdefault("limiares", {})
    config.setdefault("concorrentes", [])
    config.setdefault("produtos_monitorados", [])

    token = None
    if not args.simulate_ml:
        token = get_token(config, args.token)
        if not token:
            print("ERRO: sem token Apify. Exporte APIFY_TOKEN, passe --token, ou use --simulate-ml "
                  "para testar sem coleta real.", file=sys.stderr)
            sys.exit(1)

    playbook = load_playbook(os.path.join(SCRIPT_DIR, "playbook.json"))
    marca = config.get("marca", "marca")
    hist_dir = args.history_dir
    snap_path = os.path.join(hist_dir, f"{marca}-snapshot.json")
    log_path = os.path.join(hist_dir, f"{marca}-alerts-log.json")
    ads_hist_path = os.path.join(hist_dir, f"{marca}-ads-history.json")
    current_run_path = os.path.join(hist_dir, "alerts.json")

    produtos_filter = [p.strip() for p in args.produtos.split(",")] if args.produtos else None

    if args.simulate_ml:
        print(f"[SIMULAÇÃO] carregando snapshot de {args.simulate_ml} (sem coleta real)", file=sys.stderr)
        snapshot_novo = load_json(args.simulate_ml, {})
    else:
        print(f"Coletando snapshot atual ({marca})...", file=sys.stderr)
        snapshot_novo = collect_snapshot(config, token, produtos_filter, args.per_produto)
    primeira_rodada = not os.path.exists(snap_path)
    snapshot_antigo = load_json(snap_path, {})

    own_perf = {}
    if args.own_performance:
        own_perf = load_json(args.own_performance, {}).get("por_produto", {})

    if primeira_rodada:
        print("Linha de base — snapshot salvo, sem diffs (é a 1a execução para este marca/history-dir).",
              file=sys.stderr)
        alertas = []
    else:
        alertas = diff_precos(snapshot_antigo, snapshot_novo, config, playbook, own_perf=own_perf)

    ads_entries = []
    if args.ads_manual:
        ads_entries = load_ads_manual(args.ads_manual)
        ads_history = load_json(ads_hist_path, {})
        alertas_ads, ads_history = diff_ads(ads_entries, ads_history, config, playbook)
        alertas += alertas_ads
        save_json(ads_hist_path, ads_history)

    analises_criativo = load_json(args.creative_analysis_json, {}) if args.creative_analysis_json else {}
    if args.meta_ads_json:
        alertas += ingest_novos_criativos(args.meta_ads_json, "Meta Ad Library", playbook, analises_criativo)
    if args.google_ads_transparency_json:
        alertas += ingest_novos_criativos(args.google_ads_transparency_json, "Google Ads Transparency Center",
                                           playbook, analises_criativo)
    if args.trends_json:
        alertas += ingest_picos_trends(args.trends_json, playbook)
    if args.keyword_auction_json:
        alertas += ingest_quedas_keyword(args.keyword_auction_json, playbook)

    alertas_log = load_json(log_path, [])
    alertas_log += alertas

    save_json(snap_path, snapshot_novo)
    save_json(log_path, alertas_log)
    save_json(current_run_path, alertas)

    meta = {"data": now_iso()}
    write_xlsx(alertas, alertas_log, snapshot_novo, ads_entries, load_json(ads_hist_path, {}), config, meta, args.out,
               own_perf=own_perf)
    write_html(alertas, config, meta, args.html, own_perf=own_perf)
    print_console(alertas)

    if not args.ads_manual:
        print("Links para checagem manual de atividade em ads (alimente com --ads-manual):", file=sys.stderr)
        for link in build_manual_links(config):
            print(f"  {link['concorrente']}: {link['meta_ad_library']}", file=sys.stderr)
            if link["google_ads_transparency"]:
                print(f"    {link['google_ads_transparency']}", file=sys.stderr)

    print(f"OK -> {args.out} | {args.html}", file=sys.stderr)


if __name__ == "__main__":
    main()
