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
import math
import os
import sys
import urllib.parse
from datetime import datetime, timezone

from _fonts import FONT_ORBITRON_B64, FONT_SHARETECH_B64, FONT_SORA_B64
from _effects import EFFECTS_CSS, EFFECTS_BODY_HTML, EFFECTS_JS
from _fx_neon import FX_CSS, FX_BODY, FX_JS
from apify_common import apify_run, get_token, load_json, norm, save_json

ML_ACTOR = "viralanalyzer~mercadolivre-scraper"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")

SEVERIDADE_POR_NIVEL = {
    "agressiva": "alta", "forte": "alta", "critica": "alta",
    "moderada": "media", "moderado": "media",
    "leve": "baixa", "default": "media",
}

# Carregado uma vez em main() via load_agentes(); make_alert() lê daqui quando não
# recebe `agentes` explicitamente, para não precisar passar o parâmetro por todas as
# funções de diff/ingest que chamam make_alert().
AGENTES = {}


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


def match_oficial(nickname, official_sellers):
    n = norm(nickname)
    return any(norm(o) in n for o in official_sellers)


def extrair_patrocinado(item):
    """Best-effort: tenta achar um campo de 'é anúncio patrocinado' no item bruto do
    scraper. O actor documentado (viralanalyzer/mercadolivre-scraper) NÃO confirma
    isso de forma confiável — ver references/fontes-e-limitacoes.md. Retorna
    'sim'/'nao'/'desconhecido', nunca inventa quando o campo não existe."""
    for chave in ("is_ad", "sponsored", "is_sponsored", "patrocinado"):
        v = item.get(chave)
        if isinstance(v, bool):
            return "sim" if v else "nao"
    tags = item.get("tags") or item.get("listing_type")
    if isinstance(tags, (list, str)) and "ad" in norm(str(tags)):
        return "sim"
    return "desconhecido"


def _campos_listagem(item, position):
    ship = item.get("shipping") or {}
    return {
        "title": item.get("title"),
        "price": item.get("price"),
        "original_price": item.get("original_price"),
        "discount_pct": item.get("discount_pct"),
        "position": position,
        "reviews": item.get("reviews_count"),
        "rating": item.get("average_rating"),
        "frete_gratis": ship.get("free_shipping") if isinstance(ship, dict) else None,
        "patrocinado": extrair_patrocinado(item),
        "url": item.get("url"),
    }


def collect_snapshot(config, token, produtos_filter, per_produto):
    """Retorna (snapshot_concorrentes, snapshot_proprio).

    snapshot_concorrentes: {produto: {concorrente: {seller, title, price,
    original_price, discount_pct, position, reviews, rating, frete_gratis,
    patrocinado, url, total_listagens}}} — usado no diff/alertas, como sempre.

    snapshot_proprio: {produto: {seller, ...mesmos campos...}} — o NOSSO anúncio
    (casado por config['official_sellers']), para o Radar de Posição no Mercado
    Livre. Não participa do diff de alertas, é só para exibição lado a lado."""
    concorrentes = config.get("concorrentes", [])
    official_sellers = config.get("official_sellers", [])
    produtos = config.get("produtos_monitorados", [])
    if produtos_filter:
        produtos = [p for p in produtos if p["nome"] in produtos_filter]

    snapshot, snapshot_proprio = {}, {}
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
            position = idx + 1

            if official_sellers and match_oficial(nick, official_sellers) and prod["nome"] not in snapshot_proprio:
                snapshot_proprio[prod["nome"]] = {"seller": nick, "total_listagens": 1,
                                                   **_campos_listagem(item, position)}
                continue

            nome_conc = match_competitor(nick, concorrentes)
            if not nome_conc:
                continue
            if nome_conc in por_concorrente:
                por_concorrente[nome_conc]["total_listagens"] += 1
                if position < por_concorrente[nome_conc]["position"]:
                    por_concorrente[nome_conc]["position"] = position
                continue
            por_concorrente[nome_conc] = {"seller": nick, "total_listagens": 1,
                                           **_campos_listagem(item, position)}
        snapshot[prod["nome"]] = por_concorrente
    return snapshot, snapshot_proprio


# ------------------------------------------------------------------------ playbook
def load_playbook(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_agentes(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def agente_do_tipo(tipo, agentes):
    """Acha qual agente de combate é o dono deste tipo de alerta (fallback: comandante)."""
    for chave, dados in agentes.items():
        if chave in ("comandante", "_comentario") or not isinstance(dados, dict):
            continue
        if tipo in dados.get("gatilhos", []):
            return chave, dados
    comandante = agentes.get("comandante", {})
    return "comandante", comandante if isinstance(comandante, dict) else {}


def status_inicial(severidade, agente_dados):
    if severidade == "alta" and agente_dados.get("acao_requer_autorizacao"):
        return "aguardando_autorizacao"
    if severidade == "alta":
        return "investigando"
    return "monitorando"


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
               impacto_volume_real=None, agentes=None):
    entry = playbook_entry(playbook, tipo, nivel)
    impacto_volume = entry.get("impacto_volume", "")
    if impacto_volume_real:
        impacto_volume = f"{impacto_volume} {impacto_volume_real}"
    severidade = SEVERIDADE_POR_NIVEL.get(nivel, "media")

    ag = agentes if agentes is not None else AGENTES
    agente_chave, agente_dados = (None, {})
    if ag:
        agente_chave, agente_dados = agente_do_tipo(tipo, ag)

    return {
        "data": now_iso(),
        "tipo": tipo,
        "nivel": nivel,
        "severidade": severidade,
        "produto": produto,
        "concorrente": concorrente,
        "resumo": resumo,
        "detalhes": detalhes,
        "impacto_concorrencia": entry.get("impacto_concorrencia", ""),
        "impacto_volume": impacto_volume,
        "estrategia": entry.get("estrategia", []),
        "kpis": entry.get("kpis", []),
        "evidencia_url": evidencia_url,
        "agente_chave": agente_chave,
        "agente_nome": agente_dados.get("nome"),
        "agente_emblema": agente_dados.get("emblema"),
        "status_acao": status_inicial(severidade, agente_dados) if agente_chave else None,
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


def montar_radar_ml(snapshot_concorrentes, snapshot_proprio):
    """Junta o nosso anúncio (snapshot_proprio) com os concorrentes
    (snapshot_concorrentes) por produto, ordenado por posição na busca — é a fonte
    do painel 'Radar de Posição — Mercado Livre'."""
    radar = {}
    produtos = set(snapshot_concorrentes) | set(snapshot_proprio)
    for produto in produtos:
        entradas = []
        proprio = snapshot_proprio.get(produto)
        if proprio:
            entradas.append({"proprio": True, "concorrente": None, **proprio})
        for concorrente, dados in snapshot_concorrentes.get(produto, {}).items():
            entradas.append({"proprio": False, "concorrente": concorrente, **dados})
        entradas.sort(key=lambda e: e.get("position") if e.get("position") is not None else 999)
        radar[produto] = entradas
    return radar


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


def ingest_quedas_kpi_proprio(path, playbook):
    """Lê a saída de own_performance.py --history-dir (queda-kpi-proprio.json) e
    converte cada queda de KPI próprio num alerta que aciona o protocolo de
    diagnóstico completo (references/protocolo-diagnostico.md) em vez de uma
    estratégia tática — a causa não é conhecida até o agente investigar."""
    data = load_json(path, {})
    alertas = []
    for q in data.get("quedas", []):
        nivel = "critica" if abs(q["delta_pct"]) >= 40 else "moderada"
        resumo = (f"{q['rotulo']} de '{q['produto']}' variou de {q['valor_antes']:.2f} "
                  f"para {q['valor_agora']:.2f} ({q['delta_pct']:+.1f}%) — piora relevante. "
                  f"REQUER DIAGNÓSTICO COMPLETO antes de qualquer ação (ver "
                  f"references/protocolo-diagnostico.md).")
        alertas.append(make_alert("queda_kpi_proprio", nivel, q["produto"], "(a investigar)",
                                   resumo, q, None, playbook))
    return alertas


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
               own_perf=None, radar_ml=None, descoberta=None, keywords_data=None, marketplaces=None,
               historico=None, ga4=None):
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

    # -- Esquadrão de Combate
    ws = wb.create_sheet("Esquadrão de Combate")
    cols_esq = ["agente", "status", "tipo_alerta", "produto", "concorrente", "resumo"]
    ws.append([c.upper() for c in cols_esq])
    style_header(ws, len(cols_esq))
    ordem_status = {"aguardando_autorizacao": 0, "investigando": 1, "monitorando": 2}
    for a in sorted([x for x in alertas_rodada if x.get("agente_nome")],
                     key=lambda x: ordem_status.get(x.get("status_acao"), 9)):
        ws.append([a.get("agente_nome"), STATUS_LABEL.get(a.get("status_acao"), (a.get("status_acao"),))[0],
                   a["tipo"], a["produto"], a["concorrente"], a["resumo"]])
        sf = sev_fill.get(STATUS_LABEL.get(a.get("status_acao"), (None, "baixa"))[1])
        if sf:
            cell = ws.cell(row=ws.max_row, column=2)
            cell.fill = PatternFill("solid", fgColor=sf)
            cell.font = Font(color="FFFFFF", bold=True)
    for i, w in enumerate([32, 24, 22, 22, 20, 55], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
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

    # -- Radar ML (nós vs. concorrência)
    if radar_ml:
        ws = wb.create_sheet("Radar ML")
        cols_radar = ["produto", "quem", "position", "price", "discount_pct", "reviews",
                      "rating", "frete_gratis", "patrocinado"]
        ws.append([c.upper() for c in cols_radar])
        style_header(ws, len(cols_radar))
        for produto, entradas in radar_ml.items():
            for e in entradas:
                quem = "NÓS" if e["proprio"] else e["concorrente"]
                ws.append([produto, quem, e.get("position"), e.get("price"), e.get("discount_pct"),
                           e.get("reviews"), e.get("rating"), e.get("frete_gratis"), e.get("patrocinado")])
                if e["proprio"]:
                    for c in range(1, len(cols_radar) + 1):
                        ws.cell(row=ws.max_row, column=c).font = Font(bold=True)
        for i, w in enumerate([24, 22, 10, 10, 13, 10, 8, 12, 16], 1):
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

    # -- Desempenho Próprio (Google Ads / Meta Ads / GA4, via Windsor.ai)
    if own_perf:
        ws = wb.create_sheet("Desempenho Próprio")
        cols4 = ["produto", "spend", "impressions", "clicks", "ctr_pct", "cpc",
                 "conversions", "conversions_value", "cpa", "roas",
                 "ga4_sessions", "ga4_engajamento_pct", "ga4_conversao_pct", "campanhas"]
        ws.append([c.upper() for c in cols4])
        style_header(ws, len(cols4))
        for produto, v in own_perf.items():
            ws.append([produto, v.get("spend"), v.get("impressions"), v.get("clicks"),
                       v.get("ctr_pct"), v.get("cpc"), v.get("conversions"),
                       v.get("conversions_value"), v.get("cpa"), v.get("roas"),
                       v.get("ga4_sessions"), v.get("ga4_engajamento_pct"), v.get("ga4_conversao_pct"),
                       "; ".join(v.get("campanhas", []))])
        for i, w in enumerate([22, 12, 13, 10, 10, 10, 12, 16, 10, 8, 12, 15, 14, 55], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    # -- Google Shopping (quando fornecido, ver montar_radar_marketplaces)
    gshopping = (marketplaces or {}).get("Google Shopping")
    if gshopping:
        ws = wb.create_sheet("Google Shopping")
        cols_gs = ["produto", "quem", "position", "price", "discount_pct", "reviews",
                   "rating", "frete_gratis", "patrocinado"]
        ws.append([c.upper() for c in cols_gs])
        style_header(ws, len(cols_gs))
        for produto, entradas in gshopping.items():
            for e in entradas:
                quem = "NÓS" if e["proprio"] else e["concorrente"]
                ws.append([produto, quem, e.get("position"), e.get("price"), e.get("discount_pct"),
                           e.get("reviews"), e.get("rating"), e.get("frete_gratis"), e.get("patrocinado")])
                if e["proprio"]:
                    for c in range(1, len(cols_gs) + 1):
                        ws.cell(row=ws.max_row, column=c).font = Font(bold=True)
        for i, w in enumerate([24, 22, 10, 10, 13, 10, 8, 12, 16], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    # -- Keywords & Leilão (JSON exportado por gerar_relatorio_keywords.py)
    if keywords_data and keywords_data.get("keywords"):
        ws = wb.create_sheet("Keywords & Leilão")
        dominios_por_campanha = keywords_data.get("dominios_por_campanha", {})
        cols_kw = ["campanha", "keyword", "impressions", "clicks", "cpc_medio", "quality_score",
                   "impression_share", "rank_lost", "dominios_no_leilao"]
        ws.append([c.upper() for c in cols_kw])
        style_header(ws, len(cols_kw))
        linhas_kw = sorted(keywords_data["keywords"].values(), key=lambda a: -(a.get("impressions") or 0))
        for a in linhas_kw:
            doms = dominios_por_campanha.get(a["campanha"], [])
            doms_txt = ", ".join(f"{d} ({n}x)" for d, n in doms[:5]) or "—"
            ws.append([
                a["campanha"], a["keyword"], a.get("impressions"), a.get("clicks"),
                round(a["cpc_medio"], 2) if a.get("cpc_medio") is not None else "N/D",
                round(a["quality_score_medio"], 1) if a.get("quality_score_medio") is not None else "N/D",
                round(a["impression_share_medio"] * 100, 1) if a.get("impression_share_medio") is not None else "N/D",
                round(a["rank_lost_medio"] * 100, 1) if a.get("rank_lost_medio") is not None else "N/D",
                doms_txt,
            ])
        for i, w in enumerate([22, 26, 12, 10, 11, 13, 15, 12, 46], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"
        if keywords_data.get("simulado"):
            ws_aviso = wb.create_sheet("⚠ Keywords é simulado", 0)
            ws_aviso.append(["Este relatório de keywords usa DADO SIMULADO — o Google Ads ainda não está "
                              "conectado no Windsor.ai desta integração. Ver references/fontes-e-limitacoes.md."])
            ws_aviso.column_dimensions["A"].width = 110
            ws_aviso.cell(row=1, column=1).font = Font(bold=True, color="B00020", size=12)
            ws_aviso["A1"].alignment = Alignment(wrap_text=True, vertical="top")

    # -- Concorrentes Descobertos (JSON exportado por descoberta_concorrentes.py)
    if descoberta and (descoberta.get("por_produto") or descoberta.get("globais")):
        ws = wb.create_sheet("Concorrentes Descobertos")
        cols_desc = ["produto", "candidato", "score", "origem", "titulo_variante", "componentes_sem_dado"]
        ws.append([c.upper() for c in cols_desc])
        style_header(ws, len(cols_desc))
        for produto, candidatos in (descoberta.get("por_produto") or {}).items():
            for cand, pont in sorted(candidatos, key=lambda t: -(t[1].get("score_final") or -1)):
                score = round(pont["score_final"], 3) if pont.get("score_final") is not None else "N/D"
                ws.append([produto, cand.get("nome") or cand.get("seller"), score,
                           ", ".join(cand.get("origem", [])), cand.get("title") or cand.get("dominio_site") or "",
                           ", ".join(pont.get("componentes_indisponiveis", []))])
        for cand, pont in sorted(descoberta.get("globais") or [], key=lambda t: -(t[1].get("score_final") or -1)):
            score = round(pont["score_final"], 3) if pont.get("score_final") is not None else "N/D"
            ws.append(["(global — leilão)", cand.get("nome"), score, ", ".join(cand.get("origem", [])),
                       cand.get("dominio_site", ""), ", ".join(pont.get("componentes_indisponiveis", []))])
        for i, w in enumerate([20, 26, 9, 26, 30, 34], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"

    # -- Histórico Preço x Ads
    if historico:
        ws = wb.create_sheet("Histórico Preço x Ads")
        cols_h = ["produto", "concorrente", "data", "preco", "tem_ads", "nossa_posicao",
                  "concorrente_posicao", "disputando_direto", "kpi_queda"]
        ws.append([c.upper() for c in cols_h])
        style_header(ws, len(cols_h))
        for produto, por_conc in historico.items():
            for concorrente, pontos in por_conc.items():
                for p in pontos:
                    ws.append([produto, concorrente, p.get("data"), p.get("preco"),
                               p.get("tem_ads"), p.get("nossa_posicao"), p.get("concorrente_posicao"),
                               p.get("disputando_direto"), p.get("kpi_queda")])
                    if p.get("disputando_direto"):
                        for c in range(1, len(cols_h) + 1):
                            ws.cell(row=ws.max_row, column=c).fill = PatternFill("solid", fgColor="FCE4E4")
        for i, w in enumerate([20, 22, 12, 10, 10, 12, 16, 16, 12], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

    # -- GA4: funil, canais, devices, landing pages (dado medido pela GA4)
    if ga4 and ga4.get("kpis"):
        ws = wb.create_sheet("GA4 Funil")
        ws.append(["ETAPA", "VALOR", "% DO TOPO", "% DA ANTERIOR", "PERDIDOS", "MAIOR VAZAMENTO", "EVENTO"])
        style_header(ws, 7)
        for e in ga4.get("funil", []):
            ws.append([e["nome"], e.get("valor"),
                       round(e["pct_do_topo"], 4) if e.get("pct_do_topo") is not None else "n/d",
                       round(e["pct_da_anterior"], 4) if e.get("pct_da_anterior") is not None else "n/d",
                       e.get("perda_abs"), "SIM" if e.get("maior_vazamento") else "", e.get("desc")])
            if e.get("maior_vazamento"):
                for c in range(1, 8):
                    ws.cell(row=ws.max_row, column=c).fill = PatternFill("solid", fgColor="FCE4E4")
        for i, w in enumerate([20, 14, 12, 15, 12, 18, 34], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

        ws = wb.create_sheet("GA4 Canais")
        cols_gc = ["canal", "decisao", "sessions", "engagement_rate", "tx_carrinho",
                   "tx_checkout_p_carrinho", "tx_compra_p_checkout", "tx_conversao",
                   "compras", "receita", "receita_por_sessao", "ticket_medio"]
        ws.append([c.upper() for c in cols_gc])
        style_header(ws, len(cols_gc))
        for c in ga4.get("canais", []):
            ws.append([c["canal"], c["quadrante"], c["sessions"], c["engagement_rate"],
                       c["tx_carrinho"], c["tx_checkout_p_carrinho"], c["tx_compra_p_checkout"],
                       c["tx_conversao"], c["compras"], c["receita"], c["receita_por_sessao"],
                       c["ticket_medio"]])
        for i, w in enumerate([22, 18, 12, 14, 13, 18, 18, 14, 10, 14, 16, 14], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

        ws = wb.create_sheet("GA4 Landing Pages")
        cols_gl = ["pagina", "sessions", "engagement_rate", "bounce_rate", "tx_carrinho",
                   "compras", "tx_conversao", "receita", "sem_compra"]
        ws.append([c.upper() for c in cols_gl])
        style_header(ws, len(cols_gl))
        for p in ga4.get("landing_pages", []):
            ws.append([p["pagina"], p["sessions"], p["engagement_rate"], p["bounce_rate"],
                       p["tx_carrinho"], p["compras"], p["tx_conversao"], p["receita"],
                       "SIM" if p["vazamento"] else ""])
            if p["vazamento"]:
                for c in range(1, len(cols_gl) + 1):
                    ws.cell(row=ws.max_row, column=c).fill = PatternFill("solid", fgColor="FFF4E0")
        for i, w in enumerate([64, 12, 14, 12, 13, 10, 14, 14, 12], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A2"

        ws = wb.create_sheet("GA4 Diagnóstico")
        ws.append(["NÍVEL", "ACHADO", "DETALHE"])
        style_header(ws, 3)
        for a in ga4.get("diagnostico", []):
            ws.append([a["nivel"].upper(), a["titulo"], a["detalhe"]])
            sf = sev_fill.get(a["nivel"])
            if sf:
                cell = ws.cell(row=ws.max_row, column=1)
                cell.fill = PatternFill("solid", fgColor=sf); cell.font = Font(color="FFFFFF", bold=True)
        for i, w in enumerate([12, 42, 100], 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"

    # -- Catálogo (Produtos + Concorrentes) — inclui os candidatos manuais
    ws = wb.create_sheet("Catálogo")
    ws.append(["TIPO", "NOME", "MONITORANDO?", "DETALHE"])
    style_header(ws, 4)
    for p in montar_catalogo_produtos(config):
        ws.append(["Produto", p.get("nome"), "sim" if p["monitorando"] else "candidato", p.get("termo_busca_ml", "")])
    for c in montar_catalogo_concorrentes(config):
        detalhe = c.get("dominio_site") or ", ".join(c.get("sellers_ml", []))
        ws.append(["Concorrente", c.get("nome"), "sim" if c["monitorando"] else "candidato", detalhe])
    for i, w in enumerate([14, 26, 16, 40], 1):
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
    <article class="card sev-{a['severidade']}" style="--d:{delay}" data-alerta-idx="{idx}"
             aria-label="Battlecard {a['produto']} contra {a['concorrente']} — abrir detalhe">
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
    # o contador animado só entra quando existe número real (nunca anima um "—")
    roas_count = (f' data-count="{v["roas"]:.2f}" data-count-dec="2" data-count-suf="×"'
                  if v.get("roas") is not None else "")
    ctr = v.get("ctr_pct", 0)
    barra = max(2, min(100, ctr * 10))
    ga4_html = ""
    if v.get("ga4_sessions"):
        eng = v.get("ga4_engajamento_pct")
        conv = v.get("ga4_conversao_pct")
        ga4_html = f"""
      <div class="gauge-ga4">
        <div class="gauge-row"><span>GA4 SESSÕES</span><strong>{v['ga4_sessions']:,.0f}</strong></div>
        <div class="gauge-row"><span>ENGAJAMENTO</span><strong>{eng:.1f}%</strong></div>
        <div class="gauge-row"><span>CONVERSÃO</span><strong>{conv:.1f}%</strong></div>
      </div>"""
    return f"""
    <div class="gauge">
      <div class="gauge-produto">{produto}</div>
      <div class="gauge-main">
        <span class="gauge-value"{roas_count}>{roas}</span><span class="gauge-tag">ROAS</span>
      </div>
      <div class="gauge-row"><span>CPA</span><strong>{cpa}</strong></div>
      <div class="gauge-row"><span>INVEST.</span><strong>R$ {v.get('spend', 0):,.0f}</strong></div>
      <div class="gauge-row"><span>CTR</span><strong>{ctr:.2f}%</strong></div>
      <div class="signal-bar"><span style="width:{barra}%"></span></div>
      {ga4_html}
    </div>"""


STATUS_LABEL = {
    "aguardando_autorizacao": ("AGUARDANDO AUTORIZAÇÃO", "alta"),
    "investigando": ("INVESTIGANDO", "media"),
    "monitorando": ("MONITORANDO", "baixa"),
}
STATUS_PRIORIDADE = {"aguardando_autorizacao": 0, "investigando": 1, "monitorando": 2}


def render_esquadrao(alertas_rodada):
    """Painel 'Esquadrão de Combate' — agrupa os alertas da rodada por agente
    responsável, mostrando quantas ações cada um tem e o status mais urgente."""
    por_agente = {}
    for a in alertas_rodada:
        chave = a.get("agente_chave")
        if not chave:
            continue
        grupo = por_agente.setdefault(chave, {
            "nome": a.get("agente_nome"), "emblema": a.get("agente_emblema"),
            "alertas": [], "status": a.get("status_acao"),
        })
        grupo["alertas"].append(a)
        if STATUS_PRIORIDADE.get(a["status_acao"], 9) < STATUS_PRIORIDADE.get(grupo["status"], 9):
            grupo["status"] = a["status_acao"]

    if not por_agente:
        return ""

    cards = []
    for dados in sorted(por_agente.values(), key=lambda g: STATUS_PRIORIDADE.get(g["status"], 9)):
        label, sev = STATUS_LABEL.get(dados["status"], (dados["status"], "baixa"))
        itens = "".join(f"<li>{a['resumo'][:80]}</li>" for a in dados["alertas"][:4])
        cards.append(f"""
    <div class="squadron-card sev-{sev}">
      <div class="squadron-head">
        <span class="squadron-emblema">{dados['emblema'] or '●'}</span>
        <span class="squadron-nome">{dados['nome']}</span>
      </div>
      <span class="squadron-status">{label}</span>
      <div class="squadron-count">{len(dados['alertas'])} ação(ões) atribuída(s)</div>
      <ul class="squadron-list">{itens}</ul>
    </div>""")

    return f"""
<section class="squadron-strip">
  <h2>// esquadrão de combate — ações em andamento por agente</h2>
  <div class="squadron-grid">{''.join(cards)}</div>
</section>"""


def render_ml_radar(radar_ml):
    """Painel 'Radar de Posição — Mercado Livre': nosso anúncio vs. cada concorrente,
    lado a lado, por produto. radar_ml vem de montar_radar_ml()."""
    if not radar_ml:
        return ""
    linhas = []
    for produto, entradas in radar_ml.items():
        for e in entradas:
            quem = "NÓS" if e["proprio"] else e["concorrente"]
            classe = "radar-proprio" if e["proprio"] else "radar-concorrente"
            preco = f"R$ {e['price']:.2f}" if e.get("price") is not None else "—"
            desconto = f"{e['discount_pct']:.0f}%" if e.get("discount_pct") else "—"
            ads = {"sim": "SIM", "nao": "não", "desconhecido": "n/d"}.get(e.get("patrocinado", "desconhecido"))
            linhas.append(f"""
        <tr class="{classe}">
          <td>{produto}</td><td class="quem">{quem}</td><td>#{e.get('position', '—')}</td>
          <td>{preco}</td><td>{desconto}</td><td>{e.get('reviews', '—')}</td>
          <td>{e.get('rating', '—')}</td><td>{'sim' if e.get('frete_gratis') else 'não'}</td>
          <td class="ads-flag">{ads}</td>
        </tr>""")
    return f"""
<section class="ml-radar">
  <h2>// radar de posição — mercado livre (nós vs. concorrência)</h2>
  <div class="ml-radar-table-wrap">
    <table class="ml-radar-table">
      <thead><tr>
        <th>Produto</th><th>Quem</th><th>Posição</th><th>Preço</th><th>Desconto</th>
        <th>Reviews</th><th>Rating</th><th>Frete grátis</th><th>Anúncio patrocinado?</th>
      </tr></thead>
      <tbody>{''.join(linhas)}</tbody>
    </table>
  </div>
  <p class="ml-radar-note">"Anúncio patrocinado?" é best-effort — o scraper usado não confirma
  de forma confiável se um item é Mercado Ads ou orgânico (ver references/fontes-e-limitacoes.md);
  "n/d" significa que essa informação não veio na captura.</p>
</section>"""


# ------------------------------------------------------------- marketplaces (ML + Google Shopping)
def montar_radar_marketplaces(radar_ml, snapshot_gs_concorrentes=None, snapshot_gs_proprio=None):
    """Generaliza montar_radar_ml() para incluir também o Google Shopping (quando
    fornecido) — {canal: {produto: [entradas...]}}. Não recalcula nada do Mercado
    Livre (recebe radar_ml pronto); só monta o Google Shopping do mesmo jeito e
    junta os dois canais. É a fonte da aba 'Marketplaces'."""
    marketplaces = {"Mercado Livre": radar_ml or {}}
    if snapshot_gs_concorrentes is not None or snapshot_gs_proprio is not None:
        marketplaces["Google Shopping"] = montar_radar_ml(snapshot_gs_concorrentes or {}, snapshot_gs_proprio or {})
    return marketplaces


# ------------------------------------------------------------- histórico preço × ads (por concorrente)
def atualizar_historico_preco_ads(hist_path, radar_ml, alertas_rodada, data_rodada):
    """Acumula, por produto×concorrente, um ponto de histórico a cada execução
    real: preço do concorrente, se está rodando ads (best-effort, via o mesmo
    campo 'patrocinado' do Radar ML), a posição de cada lado, se o concorrente
    está DISPUTANDO DIRETO (posição dele à nossa frente no mesmo produto) e se
    nosso KPI caiu nesta mesma rodada (queda_kpi_proprio). É a fonte do gráfico
    'Histórico Preço × Atividade de Ads' — não pede nenhuma coleta nova, só
    persiste o que o Radar ML e os alertas já calculam a cada rodada."""
    historico = load_json(hist_path, {})
    produtos_com_queda_kpi = {a["produto"] for a in alertas_rodada if a["tipo"] == "queda_kpi_proprio"}
    for produto, entradas in (radar_ml or {}).items():
        proprio = next((e for e in entradas if e.get("proprio")), None)
        nossa_posicao = proprio.get("position") if proprio else None
        for e in entradas:
            if e.get("proprio") or e.get("price") is None:
                continue
            concorrente = e["concorrente"]
            ads_flag = {"sim": True, "nao": False}.get(e.get("patrocinado"))  # None = "desconhecido"
            conc_posicao = e.get("position")
            disputando = (nossa_posicao is not None and conc_posicao is not None and conc_posicao < nossa_posicao)
            ponto = {
                "data": data_rodada, "preco": e.get("price"), "tem_ads": ads_flag,
                "nossa_posicao": nossa_posicao, "concorrente_posicao": conc_posicao,
                "disputando_direto": disputando, "kpi_queda": produto in produtos_com_queda_kpi,
            }
            historico.setdefault(produto, {}).setdefault(concorrente, []).append(ponto)
    save_json(hist_path, historico)
    return historico


def render_historico_chart(historico):
    """Gráfico(s) 'Histórico Preço × Atividade de Ads' — SVG, um por par
    produto×concorrente com pelo menos 2 pontos acumulados. Sombreia o período em
    que o concorrente disputa direto (posição dele à nossa frente) e marca com um
    traço vermelho os pontos em que nosso KPI caiu na mesma janela — a correlação
    que embasa o protocolo de diagnóstico (references/protocolo-diagnostico.md)."""
    if not historico:
        return ('<p class="hist-empty">Ainda sem histórico acumulado — acumula automaticamente a cada '
                'execução real do war_room.py (ou carregue um de demonstração via '
                '--simulate-historico-preco-ads).</p>')
    W, H = 720, 210
    PAD_L, PAD_R, PAD_T, PAD_B = 50, 16, 18, 34
    plot_w, plot_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B

    blocos = []
    for produto, por_concorrente in historico.items():
        for concorrente, pontos in por_concorrente.items():
            pontos = [p for p in pontos if p.get("preco") is not None]
            n = len(pontos)
            if n < 2:
                continue
            precos = [p["preco"] for p in pontos]
            lo, hi = min(precos), max(precos)
            if lo == hi:
                lo, hi = lo * 0.95, hi * 1.05
            span = hi - lo

            def x_de(i, _n=n):
                return PAD_L + (i / (_n - 1)) * plot_w

            def y_de(preco, _lo=lo, _span=span):
                return PAD_T + (1 - (preco - _lo) / _span) * plot_h

            faixas, ini = [], None
            for i, p in enumerate(pontos):
                if p.get("disputando_direto") and ini is None:
                    ini = i
                elif not p.get("disputando_direto") and ini is not None:
                    faixas.append((ini, i - 1)); ini = None
            if ini is not None:
                faixas.append((ini, n - 1))
            faixas_svg = "".join(
                f'<rect x="{max(x_de(a) - 8, PAD_L):.1f}" y="{PAD_T}" '
                f'width="{min(x_de(b) + 8, PAD_L + plot_w) - max(x_de(a) - 8, PAD_L):.1f}" '
                f'height="{plot_h}" class="faixa-disputa" />'
                for a, b in faixas
            )

            pos = [(x_de(i), y_de(p["preco"])) for i, p in enumerate(pontos)]
            linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pos)

            marcas = []
            for i, (p, (x, y)) in enumerate(zip(pontos, pos)):
                ads = p.get("tem_ads")
                classe = "marca-ads-on" if ads is True else ("marca-ads-off" if ads is False else "marca-ads-nd")
                ads_txt = "com ads" if ads is True else ("sem ads" if ads is False else "ads: n/d")
                titulo = (f"{p['data']} — R$ {p['preco']:.2f} — {ads_txt}"
                          + (" — DISPUTANDO DIRETO (posição à nossa frente)" if p.get("disputando_direto") else "")
                          + (" — nosso KPI caiu nesta janela" if p.get("kpi_queda") else ""))
                marcas.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" class="{classe}"><title>{titulo}</title></circle>')
                if p.get("kpi_queda"):
                    marcas.append(f'<circle cx="{x:.1f}" cy="{PAD_T - 7:.1f}" r="3" class="marca-kpi"><title>{titulo}</title></circle>')

            labels_x = "".join(
                f'<text x="{x_de(i):.1f}" y="{H - 10}" class="eixo-label" text-anchor="middle">{p["data"][5:]}</text>'
                for i, p in enumerate(pontos) if i in (0, n - 1, n // 2)
            )
            blocos.append(f"""
    <div class="hist-chart-card">
      <div class="hist-chart-head">
        <span class="hist-chart-title">{produto} <span class="vs">×</span> {concorrente}</span>
        <span class="hist-chart-legend">
          <span class="leg-item"><span class="leg-swatch swatch-ads-on"></span>com ads</span>
          <span class="leg-item"><span class="leg-swatch swatch-ads-off"></span>sem ads</span>
          <span class="leg-item"><span class="leg-swatch swatch-disputa"></span>disputando direto</span>
          <span class="leg-item"><span class="leg-swatch swatch-kpi"></span>nosso KPI caiu</span>
        </span>
      </div>
      <svg viewBox="0 0 {W} {H}" class="hist-chart-svg" role="img"
           aria-label="Histórico de preço de {concorrente} em {produto}, com atividade de ads e disputa direta">
        {faixas_svg}
        <polyline points="{linha}" class="hist-linha" />
        {''.join(marcas)}
        <text x="{PAD_L - 8}" y="{PAD_T + 4}" class="eixo-label" text-anchor="end">R$ {hi:.0f}</text>
        <text x="{PAD_L - 8}" y="{PAD_T + plot_h}" class="eixo-label" text-anchor="end">R$ {lo:.0f}</text>
        {labels_x}
      </svg>
    </div>""")

    if not blocos:
        return ('<p class="hist-empty">Histórico ainda insuficiente (menos de 2 rodadas acumuladas por '
                'concorrente) — acumula automaticamente a cada execução real do war_room.py.</p>')
    return f'<div class="hist-chart-grid">{"".join(blocos)}</div>'


# ------------------------------------------------------------- keywords & leilão (aba)
def render_keywords_tab(data):
    """Aba 'Keywords & Leilão' a partir do JSON exportado por
    gerar_relatorio_keywords.py (--export-json) — não recalcula nada, só tabula."""
    if not data or not data.get("keywords"):
        return ('<p class="hist-empty">Nenhum relatório de keywords carregado — rode '
                'gerar_relatorio_keywords.py --export-json e passe o caminho em '
                '--keywords-relatorio-json.</p>')
    aviso = ""
    if data.get("simulado"):
        aviso = ('<div class="tab-aviso">⚠ Dado SIMULADO — o Google Ads ainda não está conectado no '
                  'Windsor.ai desta integração. Ver references/fontes-e-limitacoes.md.</div>')
    dominios_por_campanha = data.get("dominios_por_campanha", {})
    linhas = sorted(data["keywords"].values(), key=lambda a: -(a.get("impressions") or 0))
    rows = []
    for a in linhas:
        doms = dominios_por_campanha.get(a["campanha"], [])
        doms_txt = ", ".join(f"{d} ({n}×)" for d, n in doms[:4]) or "—"
        is_pct = f"{a['impression_share_medio'] * 100:.1f}%" if a.get("impression_share_medio") is not None else "N/D"
        rl_pct = f"{a['rank_lost_medio'] * 100:.1f}%" if a.get("rank_lost_medio") is not None else "N/D"
        qs = f"{a['quality_score_medio']:.1f}" if a.get("quality_score_medio") is not None else "N/D"
        cpc = f"R$ {a['cpc_medio']:.2f}" if a.get("cpc_medio") is not None else "N/D"
        rows.append(f"""
        <tr>
          <td>{a['campanha']}</td><td class="quem">{a['keyword']}</td>
          <td>{a.get('impressions', 0):,}</td><td>{a.get('clicks', 0):,}</td>
          <td>{cpc}</td><td>{qs}</td><td>{is_pct}</td><td>{rl_pct}</td>
          <td>{doms_txt}</td>
        </tr>""")
    return f"""
{aviso}
<div class="data-table-wrap">
  <table class="data-table">
    <thead><tr>
      <th>Campanha</th><th>Keyword</th><th>Impressões</th><th>Cliques</th><th>CPC médio</th>
      <th>Quality Score</th><th>Impression share</th><th>Rank lost</th><th>Domínios no leilão</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
<p class="tab-note">CPC de topo de página/1ª página fica N/D quando o Google não estima (comum em termos de
baixo volume) — nunca é inventado. "Domínios no leilão" vem do Auction Insight, coletado em chamada separada
das métricas de performance (o Google Ads recusa combinar os dois na mesma consulta).</p>"""


# ------------------------------------------------------------- concorrentes descobertos (aba)
def render_descoberta_tab(data):
    """Aba 'Concorrentes Descobertos' a partir do JSON exportado por
    descoberta_concorrentes.py (--export-json) — não recalcula nada, só tabula."""
    if not data or (not data.get("por_produto") and not data.get("globais")):
        return ('<p class="hist-empty">Nenhuma descoberta carregada — rode descoberta_concorrentes.py '
                '--export-json e passe o caminho em --descoberta-json.</p>')

    def linha_candidato(cand, pont, extra=""):
        score = f"{pont['score_final']:.2f}" if pont.get("score_final") is not None else "N/D"
        comp = pont.get("componentes", {})
        nd = ", ".join(pont.get("componentes_indisponiveis", [])) or "—"
        return f"""
        <tr>
          <td class="quem">{cand.get('nome') or cand.get('seller')}</td><td>{score}</td>
          <td>{extra}</td>
          <td>{', '.join(cand.get('origem', [])) or '—'}</td>
          <td>{cand.get('title') or cand.get('dominio_site') or '—'}</td>
          <td class="tab-note-cell">{nd}</td>
        </tr>"""

    blocos = []
    for produto, candidatos in (data.get("por_produto") or {}).items():
        candidatos = sorted(candidatos, key=lambda t: -(t[1].get("score_final") or -1))
        linhas = "".join(linha_candidato(c, p) for c, p in candidatos)
        blocos.append(f"""
    <div class="descoberta-bloco">
      <h3 class="descoberta-produto">{produto}</h3>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Candidato</th><th>Score</th><th></th><th>Origem</th><th>Variante/Título</th><th>Sem dado</th></tr></thead>
          <tbody>{linhas}</tbody>
        </table>
      </div>
    </div>""")

    globais = sorted(data.get("globais") or [], key=lambda t: -(t[1].get("score_final") or -1))
    globais_html = ""
    if globais:
        linhas_g = "".join(linha_candidato(c, p, extra=f"{c.get('aparicoes_leilao', '—')}× no leilão") for c, p in globais)
        globais_html = f"""
    <div class="descoberta-bloco">
      <h3 class="descoberta-produto">Candidatos globais (Auction Insight — não ligados a um produto específico)</h3>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr><th>Candidato</th><th>Score</th><th>Aparições</th><th>Origem</th><th>Domínio</th><th>Sem dado</th></tr></thead>
          <tbody>{linhas_g}</tbody>
        </table>
      </div>
    </div>"""

    return f"""{''.join(blocos)}{globais_html}
<p class="tab-note">Score renormalizado entre os componentes DISPONÍVEIS nesta rodada — um componente sem
dado sai do somatório em vez de virar 0 (ver metodologia completa em descoberta.xlsx / SKILL.md, passo 11).</p>"""


# ------------------------------------------------------------- marketplaces (aba, ML + Google Shopping)
def render_marketplaces_tab(marketplaces):
    """Aba 'Marketplaces' — Mercado Livre + Google Shopping (quando fornecido),
    lado a lado por canal. marketplaces vem de montar_radar_marketplaces()."""
    if not marketplaces or not any(marketplaces.values()):
        return ""
    blocos = []
    for canal, radar in marketplaces.items():
        if not radar:
            blocos.append(f"""
    <div class="marketplace-bloco">
      <h3 class="descoberta-produto">{canal}</h3>
      <p class="hist-empty">Ainda não coletado neste canal.</p>
    </div>""")
            continue
        linhas = []
        for produto, entradas in radar.items():
            for e in entradas:
                quem = "NÓS" if e["proprio"] else e["concorrente"]
                classe = "radar-proprio" if e["proprio"] else "radar-concorrente"
                preco = f"R$ {e['price']:.2f}" if e.get("price") is not None else "—"
                desconto = f"{e['discount_pct']:.0f}%" if e.get("discount_pct") else "—"
                ads = {"sim": "SIM", "nao": "não", "desconhecido": "n/d"}.get(e.get("patrocinado", "desconhecido"), "n/d")
                linhas.append(f"""
            <tr class="{classe}">
              <td>{produto}</td><td class="quem">{quem}</td><td>#{e.get('position', '—')}</td>
              <td>{preco}</td><td>{desconto}</td><td>{e.get('reviews', '—')}</td>
              <td>{e.get('rating', '—')}</td><td>{'sim' if e.get('frete_gratis') else 'não'}</td>
              <td class="ads-flag">{ads}</td>
            </tr>""")
        blocos.append(f"""
    <div class="marketplace-bloco">
      <h3 class="descoberta-produto">{canal}</h3>
      <div class="data-table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>Produto</th><th>Quem</th><th>Posição</th><th>Preço</th><th>Desconto</th>
            <th>Reviews</th><th>Rating</th><th>Frete grátis</th><th>Anúncio patrocinado?</th>
          </tr></thead>
          <tbody>{''.join(linhas)}</tbody>
        </table>
      </div>
    </div>""")
    return f"""{''.join(blocos)}
<p class="tab-note">"Anúncio patrocinado?" é best-effort (ver references/fontes-e-limitacoes.md). Google
Shopping aparece só quando uma coleta para esse canal foi fornecida — sem isso, a aba mostra "ainda não
coletado" em vez de inventar posição/preço.</p>"""


# ------------------------------------------------------------- seleção manual (aba, produtos + concorrentes)
def montar_catalogo_produtos(config):
    catalogo = []
    for p in config.get("produtos_monitorados", []):
        item = dict(p); item["monitorando"] = True
        catalogo.append(item)
    for p in config.get("produtos_candidatos_manual", []):
        item = dict(p); item["monitorando"] = False
        catalogo.append(item)
    return catalogo


def montar_catalogo_concorrentes(config):
    catalogo = []
    for c in config.get("concorrentes", []):
        item = dict(c); item["monitorando"] = True
        catalogo.append(item)
    for c in config.get("candidatos_concorrentes_manual", []):
        item = dict(c); item["monitorando"] = False
        catalogo.append(item)
    return catalogo


def render_selecao_manual_tab(config):
    """Aba 'Seleção Manual' embutida no próprio war-room.html — liga/desliga
    produtos e concorrentes monitorados, adiciona/remove, e exporta o config.json
    atualizado. Sem backend: nada se grava sozinho, o botão baixa o arquivo."""
    catalogo_produtos = montar_catalogo_produtos(config)
    catalogo_concorrentes = montar_catalogo_concorrentes(config)
    return f"""
<div class="selecao-grid">
  <div class="selecao-coluna">
    <div class="selecao-head">
      <h3 class="descoberta-produto">Produtos monitorados</h3>
      <span class="selecao-stat"><strong id="sel-prod-on">0</strong> / <span id="sel-prod-total">0</span></span>
    </div>
    <div class="toolbar-mini">
      <button class="btn-mini" id="btn-add-produto-toggle" type="button">+ produto</button>
    </div>
    <div class="add-form-mini" id="add-produto-form" style="display:none">
      <input type="text" id="new-produto-nome" placeholder="nome">
      <input type="text" id="new-produto-termo" placeholder="termo de busca (ML)">
      <input type="number" step="0.01" id="new-produto-preco" placeholder="preço (opcional)">
      <button class="btn-mini primary" id="btn-add-produto-confirm" type="button">adicionar</button>
    </div>
    <div class="selecao-lista" id="lista-produtos"></div>
  </div>
  <div class="selecao-coluna">
    <div class="selecao-head">
      <h3 class="descoberta-produto">Concorrentes monitorados</h3>
      <span class="selecao-stat"><strong id="sel-conc-on">0</strong> / <span id="sel-conc-total">0</span></span>
    </div>
    <div class="toolbar-mini">
      <button class="btn-mini" id="btn-add-concorrente-toggle" type="button">+ concorrente</button>
    </div>
    <div class="add-form-mini" id="add-concorrente-form" style="display:none">
      <input type="text" id="new-concorrente-nome" placeholder="nome">
      <input type="text" id="new-concorrente-dominio" placeholder="domínio do site (opcional)">
      <input type="text" id="new-concorrente-seller" placeholder="seller(s) no ML, separados por vírgula">
      <button class="btn-mini primary" id="btn-add-concorrente-confirm" type="button">adicionar</button>
    </div>
    <div class="selecao-lista" id="lista-concorrentes"></div>
  </div>
</div>
<div class="toolbar" style="margin-top:16px">
  <button class="btn primary" id="btn-export-config" type="button">⭳ Exportar config.json atualizado</button>
  <button class="btn" id="btn-copy-config" type="button">⧉ Copiar JSON</button>
</div>
<p class="tab-note">Sem backend: nada se grava sozinho. Ao terminar, exporte e salve o arquivo por cima do
seu <code>scripts/config.json</code> antes da próxima rodada.</p>
<textarea id="config-json-preview" class="json-preview" readonly></textarea>
<script id="selecao-manual-data" type="application/json">{json.dumps({
        "produtos": catalogo_produtos, "concorrentes": catalogo_concorrentes,
    }, ensure_ascii=False)}</script>"""


def render_seal(config):
    """Selo circular do cabeçalho (motivo da referência visual) — texto em volta do
    círculo + a cadência configurada no centro. Só dado real do config."""
    cadencia = config.get("cadencia_sugerida_horas", "—")
    # ticks radiais no anel externo (decoração estrutural do selo, como na referência)
    ticks = []
    for g in range(0, 360, 15):
        rad = math.radians(g)
        x1, y1 = 64 + 57 * math.cos(rad), 64 + 57 * math.sin(rad)
        x2, y2 = 64 + 61 * math.cos(rad), 64 + 61 * math.sin(rad)
        ticks.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" class="seal-tick" />')
    return f"""
      <svg class="seal" viewBox="0 0 128 128" role="img"
           aria-label="Monitoramento por polling, cadência de {cadencia} horas">
        <defs>
          <path id="seal-arc" d="M 22 64 A 42 42 0 0 1 106 64" />
          <radialGradient id="seal-sweep-grad">
            <stop offset="0%" stop-color="#55aeff" stop-opacity=".38" />
            <stop offset="100%" stop-color="#55aeff" stop-opacity="0" />
          </radialGradient>
        </defs>
        <path class="seal-sweep" d="M 64 64 L 64 19 A 45 45 0 0 1 96 32 Z" />
        <circle cx="64" cy="64" r="62" class="seal-ring" />
        <circle cx="64" cy="64" r="47" class="seal-ring" />
        <g class="seal-spin">{''.join(ticks)}</g>
        <text class="seal-text"><textPath href="#seal-arc" startOffset="50%" text-anchor="middle">
          Polling · Diff</textPath></text>
        <text x="64" y="70" class="seal-value">{cadencia}h</text>
        <text x="64" y="83" class="seal-label">cadência</text>
        <text x="64" y="106" class="seal-label">dado real</text>
      </svg>"""


def render_pipeline(alertas_rodada, primeira_rodada=False):
    """Pipeline de etapas do cabeçalho (motivo-assinatura da referência: caixas com
    seta entre elas, a etapa corrente acesa). Reflete o ESTADO REAL da rodada, não
    é decoração: a etapa acesa é a mais avançada que de fato aconteceu."""
    n_alertas = len(alertas_rodada)
    agentes_acionados = {a.get("agente_chave") for a in alertas_rodada if a.get("agente_chave")}
    aguardando = [a for a in alertas_rodada if a.get("status_acao") == "aguardando_autorizacao"]

    etapas = [
        ("◈", "COLETA", "snapshot capturado", True),
        ("◇", "DIFF", "linha de base" if primeira_rodada else "comparado c/ rodada anterior", True),
        ("▲", "ALERTA", f"{n_alertas} detectado(s)", n_alertas > 0),
        ("⬢", "AGENTE", f"{len(agentes_acionados)} acionado(s)", bool(agentes_acionados)),
        ("⬣", "AÇÃO", f"{len(aguardando)} aguardando você" if aguardando else "nada pendente", bool(aguardando)),
    ]
    # a etapa "acesa" é a última que de fato aconteceu
    idx_on = max((i for i, e in enumerate(etapas) if e[3]), default=0)

    partes = []
    for i, (ico, nome, sub, _) in enumerate(etapas):
        if i:
            partes.append(f'<span class="pipe-arrow" aria-hidden="true" style="--pd:{i * 0.34:.2f}s">»</span>')
        on = " on" if i == idx_on else ""
        partes.append(f"""
    <div class="pipe-step{on}">
      <span class="pipe-ico" aria-hidden="true">{ico}</span>
      <span class="pipe-name">{nome}</span>
      <span class="pipe-sub">{sub}</span>
    </div>""")
    return f'<div class="pipeline">{"".join(partes)}</div>'


def render_credbar(config, own_perf=None, keywords_data=None):
    """Barra de credenciais do rodapé (3 células separadas por régua fina, como na
    referência) — cada célula é um fato verificável da rodada, não slogan."""
    n_prod = len(config.get("produtos_monitorados", []))
    n_cand_prod = len(config.get("produtos_candidatos_manual", []))
    n_conc = len(config.get("concorrentes", []))
    n_cand_conc = len(config.get("candidatos_concorrentes_manual", []))
    fontes = ["Mercado Livre"]
    if own_perf:
        fontes.append("Google Ads/GA4")
    if keywords_data and keywords_data.get("keywords"):
        fontes.append("Auction Insight" + (" (simulado)" if keywords_data.get("simulado") else ""))
    return f"""
<div class="credbar">
  <div class="cred-cell">
    <span class="cred-ico" aria-hidden="true">▣</span>
    <span><span class="cred-label">{n_prod} produto(s) monitorado(s)</span>
    <span class="cred-sub">+ {n_cand_prod} candidato(s) em avaliação</span></span>
  </div>
  <div class="cred-cell">
    <span class="cred-ico" aria-hidden="true">◎</span>
    <span><span class="cred-label">{n_conc} concorrente(s) na mira</span>
    <span class="cred-sub">+ {n_cand_conc} candidato(s) manual(is)</span></span>
  </div>
  <div class="cred-cell">
    <span class="cred-ico" aria-hidden="true">⛁</span>
    <span><span class="cred-label">Fontes ativas nesta rodada</span>
    <span class="cred-sub">{' · '.join(fontes)}</span></span>
  </div>
</div>"""


# =============================================================== GA4 · Jornada
def _f_int(v):
    return f"{v:,.0f}".replace(",", ".") if isinstance(v, (int, float)) else "n/d"


def _f_pct(v, dec=1):
    return f"{v * 100:.{dec}f}%" if isinstance(v, (int, float)) else "n/d"


def _f_brl(v, dec=2):
    if not isinstance(v, (int, float)):
        return "n/d"
    s = f"{v:,.{dec}f}"
    return "R$ " + s.replace(",", "@").replace(".", ",").replace("@", ".")


def _f_dur(seg):
    if not isinstance(seg, (int, float)):
        return "n/d"
    m, s = int(seg // 60), int(seg % 60)
    return f"{m}m {s:02d}s"


def render_ga4_kpis(k):
    """Cartões de topo da aba GA4 — o bloco que um gestor de tráfego lê primeiro."""
    cards = [
        ("Sessões", _f_int(k.get("sessions")), f"{_f_int(k.get('usuarios'))} usuários · "
         f"{_f_pct(k.get('pct_novos'), 0)} novos", k.get("sessions"), 0, ""),
        ("Taxa de conversão", _f_pct(k.get("tx_conversao"), 2),
         f"{_f_int(k.get('compras'))} compras", k.get("tx_conversao"), 2, "%"),
        ("Receita", _f_brl(k.get("receita"), 0),
         f"ticket médio {_f_brl(k.get('ticket_medio'))}", None, 0, ""),
        ("Receita por sessão", _f_brl(k.get("receita_por_sessao")),
         "o quanto cada visita vale", None, 0, ""),
        ("Engajamento", _f_pct(k.get("engagement_rate")),
         f"rejeição {_f_pct(k.get('bounce_rate'))}", k.get("engagement_rate"), 1, "%"),
        ("Duração média", _f_dur(k.get("duracao_media_sessao")),
         f"{k.get('pageviews_por_sessao'):.1f} páginas/sessão"
         if isinstance(k.get("pageviews_por_sessao"), (int, float)) else "n/d", None, 0, ""),
        ("Compradores", _f_int(k.get("compradores")),
         f"{_f_pct(k.get('pct_primeira_compra'), 0)} na 1ª compra", k.get("compradores"), 0, ""),
    ]
    html = []
    for titulo, valor, sub, count, dec, suf in cards:
        # o contador animado só entra quando existe número real por trás
        attr = ""
        if isinstance(count, (int, float)):
            base = count * 100 if suf == "%" else count
            attr = f' data-count="{base:.{dec}f}" data-count-dec="{dec}" data-count-suf="{suf}"'
        html.append(f"""
    <div class="ga4-kpi">
      <div class="ga4-kpi-label">{titulo}</div>
      <div class="ga4-kpi-value"{attr}>{valor}</div>
      <div class="ga4-kpi-sub">{sub}</div>
    </div>""")
    return f'<div class="ga4-kpi-grid">{"".join(html)}</div>'


def render_ga4_funil(etapas):
    """Funil de compra em barras proporcionais, com taxa de passagem entre etapas
    e a etapa de maior vazamento destacada."""
    if not etapas:
        return '<p class="hist-empty">Funil não carregado.</p>'
    topo = next((e["valor"] for e in etapas if e.get("valor")), 1) or 1
    linhas = []
    for i, e in enumerate(etapas):
        largura = max(2.5, (e["valor"] / topo * 100) if isinstance(e["valor"], (int, float)) else 0)
        vaz = " vazamento" if e.get("maior_vazamento") else ""
        passagem = ""
        if e.get("pct_da_anterior") is not None:
            perda = f" · −{_f_int(e.get('perda_abs'))} perdidos" if e.get("perda_abs") else ""
            passagem = (f'<span class="ga4-funil-passagem{vaz}">'
                        f'{_f_pct(e["pct_da_anterior"])} da etapa anterior{perda}</span>')
        linhas.append(f"""
      <div class="ga4-funil-linha{vaz}">
        <div class="ga4-funil-head">
          <span class="ga4-funil-nome">{i + 1}. {e['nome']}</span>
          <span class="ga4-funil-valor">{_f_int(e['valor'])}</span>
        </div>
        <div class="ga4-funil-track">
          <div class="ga4-funil-bar" style="--w:{largura:.2f}%"></div>
          <span class="ga4-funil-topo">{_f_pct(e.get('pct_do_topo'), 1)} do topo</span>
        </div>
        <div class="ga4-funil-foot"><span class="ga4-funil-desc">{e['desc']}</span>{passagem}</div>
      </div>""")
    return f'<div class="ga4-funil">{"".join(linhas)}</div>'


def render_ga4_quadrantes(canais, cortes):
    """Matriz de decisão volume × conversão. O corte é a MEDIANA do próprio
    período (não benchmark de mercado) — está escrito na legenda."""
    if not canais:
        return ""
    grupos = {"escalar": [], "corrigir": [], "testar aumento": [], "revisar ou cortar": [], "sem dado": []}
    for c in canais:
        grupos.setdefault(c["quadrante"], []).append(c)
    rotulos = [
        ("escalar", "▲ Escalar", "volume alto + converte acima da mediana", "q-escalar"),
        ("corrigir", "◆ Corrigir primeiro", "volume alto + converte abaixo da mediana", "q-corrigir"),
        ("testar aumento", "◇ Testar aumento", "converte bem, volume baixo", "q-testar"),
        ("revisar ou cortar", "○ Revisar ou cortar", "volume baixo + converte abaixo", "q-cortar"),
    ]
    cels = []
    for chave, titulo, desc, cls in rotulos:
        itens = sorted(grupos.get(chave, []), key=lambda c: -(c["sessions"] or 0))
        if not itens:
            corpo = '<li class="ga4-q-vazio">nenhum canal aqui neste período</li>'
        else:
            corpo = "".join(
                f'<li><span class="ga4-q-canal">{c["canal"]}</span>'
                f'<span class="ga4-q-num">{_f_int(c["sessions"])} sess · {_f_pct(c["tx_conversao"], 2)}</span></li>'
                for c in itens)
        cels.append(f"""
      <div class="ga4-quad {cls}">
        <div class="ga4-quad-head"><span class="ga4-quad-titulo">{titulo}</span>
        <span class="ga4-quad-desc">{desc}</span></div>
        <ul class="ga4-quad-lista">{corpo}</ul>
      </div>""")
    return f"""
<div class="ga4-quad-grid">{''.join(cels)}</div>
<p class="tab-note">Corte dos quadrantes = mediana do próprio período
({_f_int(cortes.get('mediana_sessoes'))} sessões e {_f_pct(cortes.get('mediana_tx_conversao'), 2)} de
conversão entre os canais). Não é benchmark de mercado — é a comparação dos seus canais entre si.</p>"""


def render_ga4_serie(serie):
    """Série diária: sessões (área) + compras (linha) + receita nas barras de
    fundo. Um eixo por grandeza é impossível num só gráfico sem enganar, então
    cada grandeza vira sua própria faixa normalizada e o número real vem no
    tooltip — nunca dois eixos y no mesmo desenho."""
    pontos = [p for p in serie if p.get("sessions") is not None]
    n = len(pontos)
    if n < 2:
        return '<p class="hist-empty">Série diária insuficiente.</p>'
    W, H = 980, 260
    PL, PR, PT, PB = 54, 18, 16, 40
    pw, ph = W - PL - PR, H - PT - PB

    max_s = max(p["sessions"] for p in pontos) or 1
    max_r = max((p.get("receita") or 0) for p in pontos) or 1
    max_c = max((p.get("compras") or 0) for p in pontos) or 1

    def x(i):
        return PL + (i / (n - 1)) * pw

    bw = max(2.0, pw / n * 0.42)
    barras = "".join(
        f'<rect class="ga4-bar" x="{x(i) - bw / 2:.1f}" y="{PT + ph - ((p.get("receita") or 0) / max_r * ph * .92):.1f}" '
        f'width="{bw:.1f}" height="{((p.get("receita") or 0) / max_r * ph * .92):.1f}" rx="1.5">'
        f'<title>{p["data"]} — receita {_f_brl(p.get("receita"), 0)}</title></rect>'
        for i, p in enumerate(pontos))

    ptos_s = [(x(i), PT + ph - (p["sessions"] / max_s * ph * .92)) for i, p in enumerate(pontos)]
    area = (f'M {ptos_s[0][0]:.1f},{PT + ph:.1f} '
            + " ".join(f"L {px:.1f},{py:.1f}" for px, py in ptos_s)
            + f" L {ptos_s[-1][0]:.1f},{PT + ph:.1f} Z")
    linha_s = " ".join(f"{px:.1f},{py:.1f}" for px, py in ptos_s)

    ptos_c = [(x(i), PT + ph - ((p.get("compras") or 0) / max_c * ph * .92)) for i, p in enumerate(pontos)]
    linha_c = " ".join(f"{px:.1f},{py:.1f}" for px, py in ptos_c)
    marcas_c = "".join(
        f'<circle class="ga4-dot-compras" cx="{px:.1f}" cy="{py:.1f}" r="3.4">'
        f'<title>{pontos[i]["data"]} — {_f_int(pontos[i].get("compras"))} compra(s) — '
        f'{_f_int(pontos[i].get("sessions"))} sessões — conv. {_f_pct(pontos[i].get("tx_conversao"), 2)} — '
        f'receita {_f_brl(pontos[i].get("receita"), 0)}</title></circle>'
        for i, (px, py) in enumerate(ptos_c))

    rotulos = "".join(
        f'<text class="eixo-label" x="{x(i):.1f}" y="{H - 12}" text-anchor="middle">{pontos[i]["data"][5:]}</text>'
        for i in (0, n // 3, 2 * n // 3, n - 1))
    grade = "".join(
        f'<line class="ga4-grid" x1="{PL}" y1="{PT + ph * k:.1f}" x2="{W - PR}" y2="{PT + ph * k:.1f}" />'
        for k in (0, .25, .5, .75, 1))

    return f"""
<div class="ga4-serie-card">
  <div class="hist-chart-head">
    <span class="hist-chart-title">Evolução diária <span class="vs">· {n} dias</span></span>
    <span class="hist-chart-legend">
      <span class="leg-item"><span class="leg-swatch sw-sessoes"></span>sessões</span>
      <span class="leg-item"><span class="leg-swatch sw-compras"></span>compras</span>
      <span class="leg-item"><span class="leg-swatch sw-receita"></span>receita</span>
    </span>
  </div>
  <svg viewBox="0 0 {W} {H}" class="ga4-serie-svg hist-chart-svg" role="img"
       aria-label="Evolução diária de sessões, compras e receita nos últimos {n} dias">
    {grade}{barras}
    <path class="ga4-area" d="{area}" />
    <polyline class="ga4-linha-sessoes hist-linha" points="{linha_s}" />
    <polyline class="ga4-linha-compras" points="{linha_c}" />
    {marcas_c}
    <text class="eixo-label" x="{PL - 8}" y="{PT + 6}" text-anchor="end">{_f_int(max_s)}</text>
    <text class="eixo-label" x="{PL - 8}" y="{PT + ph}" text-anchor="end">0</text>
    {rotulos}
  </svg>
  <p class="tab-note">Três grandezas com escalas diferentes: cada uma tem a própria faixa normalizada
  (nunca dois eixos Y no mesmo desenho, que distorce a leitura). Os valores absolutos aparecem ao passar
  o mouse em cada ponto/barra.</p>
</div>"""


def render_ga4_tabela_canais(canais):
    if not canais:
        return ""
    rows = []
    for c in canais:
        badge = {"escalar": "q-escalar", "corrigir": "q-corrigir",
                 "testar aumento": "q-testar"}.get(c["quadrante"], "q-cortar")
        rows.append(f"""
        <tr>
          <td class="quem">{c['canal']}</td>
          <td><span class="ga4-badge {badge}">{c['quadrante']}</span></td>
          <td>{_f_int(c['sessions'])}</td><td>{_f_pct(c['engagement_rate'])}</td>
          <td>{_f_pct(c['tx_carrinho'], 2)}</td><td>{_f_pct(c['tx_checkout_p_carrinho'], 1)}</td>
          <td>{_f_pct(c['tx_compra_p_checkout'], 1)}</td>
          <td>{_f_pct(c['tx_conversao'], 2)}</td>
          <td>{_f_brl(c['receita'], 0)}</td><td>{_f_brl(c['receita_por_sessao'])}</td>
          <td>{_f_brl(c['ticket_medio'], 0)}</td>
        </tr>""")
    return f"""
<div class="data-table-wrap">
  <table class="data-table">
    <thead><tr>
      <th>Canal</th><th>Decisão</th><th>Sessões</th><th>Engajamento</th>
      <th>Sessão→carrinho</th><th>Carrinho→checkout</th><th>Checkout→compra</th>
      <th>Conversão total</th><th>Receita</th><th>R$/sessão</th><th>Ticket médio</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>"""


def render_ga4_devices(devices):
    if not devices:
        return ""
    total_r = sum(d["receita"] or 0 for d in devices) or 1
    cards = []
    for d in devices:
        share = (d["receita"] or 0) / total_r
        cards.append(f"""
    <div class="ga4-dev">
      <div class="ga4-dev-head"><span class="ga4-dev-nome">{d['device']}</span>
        <span class="ga4-dev-share">{_f_pct(share, 0)} da receita</span></div>
      <div class="ga4-dev-track"><div class="ga4-dev-bar" style="--w:{share * 100:.1f}%"></div></div>
      <div class="gauge-row"><span>Sessões</span><strong>{_f_int(d['sessions'])}</strong></div>
      <div class="gauge-row"><span>Conversão</span><strong>{_f_pct(d['tx_conversao'], 2)}</strong></div>
      <div class="gauge-row"><span>Engajamento</span><strong>{_f_pct(d['engagement_rate'])}</strong></div>
      <div class="gauge-row"><span>R$/sessão</span><strong>{_f_brl(d['receita_por_sessao'])}</strong></div>
    </div>""")
    return f'<div class="ga4-dev-grid">{"".join(cards)}</div>'


def render_ga4_landing(landings, limiar):
    if not landings:
        return '<p class="hist-empty">Nenhuma landing page acima do limiar de sessões.</p>'
    rows = []
    for p in landings:
        flag = '<span class="ga4-badge q-corrigir">sem compra</span>' if p["vazamento"] else ""
        rows.append(f"""
        <tr>
          <td class="quem">{p['pagina'] or '(vazio)'}</td>
          <td>{_f_int(p['sessions'])}</td><td>{_f_pct(p['engagement_rate'])}</td>
          <td>{_f_pct(p['bounce_rate'])}</td><td>{_f_pct(p['tx_carrinho'], 2)}</td>
          <td>{_f_int(p['compras'])} {flag}</td>
          <td>{_f_pct(p['tx_conversao'], 2)}</td><td>{_f_brl(p['receita'], 0)}</td>
        </tr>""")
    return f"""
<div class="data-table-wrap">
  <table class="data-table">
    <thead><tr>
      <th>Landing page</th><th>Sessões</th><th>Engajamento</th><th>Rejeição</th>
      <th>Sessão→carrinho</th><th>Compras</th><th>Conversão</th><th>Receita</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
<p class="tab-note">Só páginas com pelo menos {limiar} sessões no período — abaixo disso a taxa oscila
demais para embasar decisão. "Sem compra" marca tráfego que chega e não fecha: é a fila de correção,
ordenada por sessão perdida.</p>"""


def render_ga4_diagnostico(achados):
    if not achados:
        return ""
    cards = []
    for a in achados:
        cards.append(f"""
    <div class="ga4-diag sev-{a['nivel']}">
      <span class="ga4-diag-nivel">{ {'alta': 'Prioridade alta', 'media': 'Atenção',
                                        'baixa': 'Contexto'}.get(a['nivel'], a['nivel']) }</span>
      <div class="ga4-diag-titulo">{a['titulo']}</div>
      <p class="ga4-diag-detalhe">{a['detalhe']}</p>
    </div>""")
    return f'<div class="ga4-diag-grid">{"".join(cards)}</div>'


def render_ga4_tab(ga4):
    """A aba inteira. Sem dado carregado, explica como carregar em vez de quebrar."""
    if not ga4 or not ga4.get("kpis"):
        return ('<p class="hist-empty">GA4 não carregada — rode <code>ga4_jornada.py</code> com os '
                'retornos de <code>get_data</code> (connector <code>googleanalytics4</code>) e passe o '
                'resultado em <code>--ga4-json</code>.</p>')
    k = ga4["kpis"]
    return f"""
<section>
  <h2>Visão do gestor de tráfego — {ga4.get('periodo', 'período coletado')}</h2>
  {render_ga4_kpis(k)}
</section>
<section>
  <h2>Diagnóstico — onde agir primeiro</h2>
  {render_ga4_diagnostico(ga4.get('diagnostico', []))}
</section>
<section>
  <h2>Funil de compra — jornada completa</h2>
  {render_ga4_funil(ga4.get('funil', []))}
</section>
<section>
  <h2>Evolução diária</h2>
  {render_ga4_serie(ga4.get('serie', []))}
</section>
<section>
  <h2>Matriz de decisão por canal — volume × conversão</h2>
  {render_ga4_quadrantes(ga4.get('canais', []), ga4.get('cortes_quadrante', {}))}
</section>
<section>
  <h2>Funil por canal — onde cada origem perde a venda</h2>
  {render_ga4_tabela_canais(ga4.get('canais', []))}
</section>
<section>
  <h2>Dispositivos</h2>
  {render_ga4_devices(ga4.get('devices', []))}
</section>
<section>
  <h2>Landing pages — porta de entrada</h2>
  {render_ga4_landing(ga4.get('landing_pages', []), ga4.get('limiar_landing_sessions', 100))}
</section>
<p class="caveat">Tudo nesta aba é dado <strong>medido pela GA4</strong> da propriedade, não estimativa:
sessões, engajamento, etapas do funil (view_item → add_to_cart → begin_checkout → purchase), receita e
suas divisões por canal, dispositivo e página. As taxas e os quadrantes são aritmética sobre esses
números, com o corte na mediana do próprio período. Onde a GA4 não devolveu valor, aparece "n/d" —
nunca zero disfarçado. Limitação conhecida: a GA4 aceita no máximo 10 métricas por consulta, então a
coleta é feita em blocos (ver ga4_jornada.py).</p>"""


def write_html(alertas_rodada, config, meta, path, own_perf=None, radar_ml=None,
               descoberta=None, keywords_data=None, marketplaces=None, historico=None,
               primeira_rodada=False, ga4=None):
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    ordenados = sorted(alertas_rodada, key=lambda x: ordem[x["severidade"]])
    cards = "".join(render_card(a, i) for i, a in enumerate(ordenados))
    if not cards:
        cards = ('<div class="empty">Nenhum alvo nesta varredura<br>'
                  '<span>(sem mudanças em relação à última rodada, ou é a linha de base)</span></div>')

    n_alta = sum(1 for a in alertas_rodada if a["severidade"] == "alta")
    n_media = sum(1 for a in alertas_rodada if a["severidade"] == "media")
    if n_alta:
        mc_level, mc_text = "alta", f"{n_alta} alerta(s) crítico(s) — ação imediata recomendada"
    elif n_media:
        mc_level, mc_text = "media", f"{n_media} alerta(s) em atenção — revisar"
    else:
        mc_level, mc_text = "ok", "Todos os sinais nominais — nenhuma ameaça detectada"

    own_kpi_section = ""
    if own_perf:
        own_cards = "".join(render_own_kpi(p, v) for p, v in own_perf.items())
        own_kpi_section = f"""
<section class="gauge-strip">
  <h2>Desempenho próprio — Google/Meta Ads + GA4</h2>
  <div class="gauge-grid">{own_cards}</div>
</section>"""

    # payload p/ o popup de detalhe do battlecard — a MESMA lista de alertas já
    # calculada, na MESMA ordem dos cards (por severidade), sem recomputar nada.
    alertas_json = json.dumps([
        {k: a.get(k) for k in ("severidade", "nivel", "tipo", "produto", "concorrente", "resumo",
                                "impacto_concorrencia", "impacto_volume", "estrategia", "kpis",
                                "evidencia_url", "data", "agente_nome", "agente_emblema", "status_acao")}
        for a in ordenados
    ], ensure_ascii=False)

    esquadrao_section = render_esquadrao(alertas_rodada)
    seal_svg = render_seal(config)
    pipeline_html = render_pipeline(alertas_rodada, primeira_rodada)
    credbar_html = render_credbar(config, own_perf, keywords_data)
    marketplaces_html = render_marketplaces_tab(marketplaces or {"Mercado Livre": radar_ml or {}})
    descoberta_html = render_descoberta_tab(descoberta)
    keywords_html = render_keywords_tab(keywords_data)
    historico_html = render_historico_chart(historico)
    selecao_html = render_selecao_manual_tab(config)
    ga4_html = render_ga4_tab(ga4)

    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>War Room — {config.get('marca', '')}</title>
<style>
  @font-face {{
    font-family: 'Sora'; font-weight: 100 800; font-style: normal; font-display: swap;
    src: url(data:font/woff2;base64,{FONT_SORA_B64}) format('woff2');
  }}
  :root {{
    --bg: #040814; --bg-2: #070e1e;
    --surface: rgba(9,20,40,.72); --surface-2: rgba(13,28,54,.8); --surface-3: rgba(18,38,70,.9);
    --border: rgba(17,135,240,.2); --border-strong: rgba(17,135,240,.45);
    --text: #f2f7fd; --text-dim: #93a8c4; --text-mute: #5e7391;
    --accent: #1187f0; --accent-soft: rgba(17,135,240,.14); --accent-strong: #55aeff;
    --good: #0ca30c; --good-bg: rgba(12,163,12,.14);
    --warning: #fab219; --warning-bg: rgba(250,178,25,.14);
    --critical: #e0426b; --critical-bg: rgba(224,66,107,.16);
    /* paleta categórica p/ gráficos (dataviz skill) — NÃO reordenar, ordem é o que garante */
    /* separação segura p/ daltonismo; a identidade visual usa --accent, não estas cores. */
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500;
    --s5: #d55181; --s6: #29a329; --s7: #9085e9; --s8: #e66767;
    color-scheme: dark;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ background: var(--bg); }}
  body {{
    margin: 0; color: var(--text); min-height: 100vh; position: relative;
    font-family: 'Sora', ui-sans-serif, -apple-system, "Segoe UI", Roboto, sans-serif;
    background-image:
      linear-gradient(rgba(17,135,240,.055) 1px, transparent 1px),
      linear-gradient(90deg, rgba(17,135,240,.055) 1px, transparent 1px);
    background-size: 44px 44px;
  }}
  body::before {{
    content: ""; position: fixed; inset: 0; z-index: -1; pointer-events: none;
    background:
      radial-gradient(900px 560px at 50% -12%, rgba(17,135,240,.22), transparent 62%),
      radial-gradient(700px 500px at 88% 8%, rgba(17,135,240,.12), transparent 60%),
      linear-gradient(180deg, var(--bg-2), var(--bg) 42%);
  }}
  a {{ color: var(--accent-strong); }}
  h1, h2, h3, .gauge-value, .stat-value, .brand-mark {{ font-family: 'Sora', ui-sans-serif, sans-serif; }}
  .shell {{ max-width: 1240px; margin: 0 auto; padding: 0 28px 56px; position: relative; z-index: 1; }}

  /* --- cabeçalho no estilo "capa técnica": eyebrow em pill, título bicolor, selo circular --- */
  header.top {{ max-width: 1240px; margin: 0 auto; padding: 34px 28px 22px; position: relative; z-index: 1; }}
  .head-grid {{ display: flex; flex-wrap: wrap; align-items: flex-start; justify-content: space-between; gap: 26px; }}
  .pill-badge {{
    display: inline-flex; align-items: center; gap: 9px; padding: 6px 15px; border-radius: 999px;
    border: 1px solid var(--border-strong); color: var(--accent-strong);
    font-size: .64rem; font-weight: 700; letter-spacing: .17em; text-transform: uppercase;
  }}
  h1.cover-title {{
    margin: 16px 0 0; font-size: clamp(2.1rem, 4.6vw, 3.4rem); font-weight: 800; line-height: 1.02;
    letter-spacing: -.03em; color: var(--text); text-wrap: balance;
  }}
  h1.cover-title em {{ font-style: normal; color: var(--accent); display: block; }}
  .rule {{ height: 1px; width: 190px; margin: 18px 0 16px; background: linear-gradient(90deg, var(--accent), transparent); }}
  .cover-sub {{ margin: 0; font-size: .95rem; color: var(--text-dim); max-width: 46ch; line-height: 1.55; }}
  .cover-sub b {{ color: var(--accent-strong); font-weight: 600; }}
  .head-right {{ display: flex; flex-direction: column; align-items: flex-end; gap: 18px; }}
  .seal {{ width: 142px; height: 142px; flex: none; }}
  .seal-ring {{ fill: none; stroke: var(--border-strong); stroke-width: 1; }}
  .seal-text {{ fill: var(--accent-strong); font-size: 7.6px; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }}
  .seal-value {{ fill: var(--text); font-size: 21px; font-weight: 800; text-anchor: middle; }}
  .seal-label {{ fill: var(--text-mute); font-size: 7.2px; font-weight: 700; letter-spacing: .16em; text-anchor: middle; text-transform: uppercase; }}
  .seal-tick {{ stroke: var(--border-strong); stroke-width: 1; }}
  .top-stats {{ display: flex; flex-wrap: wrap; gap: 26px; justify-content: flex-end; }}
  .top-stat {{ text-align: right; }}
  .top-stat-label {{ display: block; font-size: .6rem; text-transform: uppercase; letter-spacing: .14em; color: var(--text-mute); font-weight: 700; }}
  .top-stat-value {{ font-size: 1.05rem; font-weight: 700; font-variant-numeric: tabular-nums; }}

  /* --- pipeline de etapas (motivo-assinatura da referência) --- */
  .pipeline {{
    display: flex; align-items: stretch; gap: 0; flex-wrap: wrap; margin: 0 auto 26px;
    max-width: 1240px; padding: 0 28px; position: relative; z-index: 1;
  }}
  .pipe-step {{
    flex: 1 1 150px; min-width: 138px; border: 1px solid var(--border); border-radius: 10px;
    background: var(--surface); padding: 13px 14px 12px; text-align: center;
  }}
  .pipe-step.on {{
    border-color: var(--accent); background: rgba(17,135,240,.13);
    box-shadow: 0 0 0 1px var(--accent) inset, 0 0 26px -6px rgba(17,135,240,.75);
  }}
  .pipe-ico {{ font-size: 1.05rem; line-height: 1; display: block; margin-bottom: 8px; color: var(--accent-strong); }}
  .pipe-step.on .pipe-ico {{ color: #fff; }}
  .pipe-name {{
    display: block; font-size: .64rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase;
    color: var(--text); margin-bottom: 5px;
  }}
  .pipe-sub {{ display: block; font-size: .68rem; color: var(--text-mute); line-height: 1.3; }}
  .pipe-step.on .pipe-sub {{ color: var(--accent-strong); }}
  .pipe-arrow {{
    flex: none; display: flex; align-items: center; padding: 0 9px; color: var(--border-strong);
    font-size: .9rem; font-weight: 700; letter-spacing: -.12em;
  }}

  /* --- barra de credenciais do rodapé (3 células separadas por régua fina) --- */
  .credbar {{
    display: flex; flex-wrap: wrap; margin-top: 34px; border: 1px solid var(--border); border-radius: 12px;
    background: var(--surface); overflow: hidden;
  }}
  .cred-cell {{
    flex: 1 1 210px; display: flex; align-items: center; gap: 12px; padding: 14px 18px;
    border-left: 1px solid var(--border);
  }}
  .cred-cell:first-child {{ border-left: none; }}
  .cred-ico {{ font-size: 1.15rem; color: var(--accent-strong); flex: none; }}
  .cred-label {{ display: block; font-size: .68rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--text); }}
  .cred-sub {{ display: block; font-size: .7rem; color: var(--text-mute); margin-top: 2px; }}
  .brand-text .eyebrow {{
    display: block; font-size: .68rem; letter-spacing: .1em; text-transform: uppercase; color: var(--text-mute);
    font-weight: 600; margin-bottom: 2px;
  }}
  h1 {{ margin: 0; font-size: 1.5rem; font-weight: 700; letter-spacing: -.01em; }}
  .top-stats {{ display: flex; flex-wrap: wrap; gap: 22px; }}
  .top-stat {{ text-align: right; }}
  .top-stat-label {{ display: block; font-size: .66rem; text-transform: uppercase; letter-spacing: .07em; color: var(--text-mute); }}
  .top-stat-value {{ font-size: 1.15rem; font-weight: 700; font-variant-numeric: tabular-nums; }}
  .status-banner {{
    display: flex; align-items: center; gap: 10px; margin: 0 auto 22px; max-width: 1240px; padding: 0 28px;
  }}
  .status-pill {{
    display: inline-flex; align-items: center; gap: 9px; padding: 8px 16px; border-radius: 999px;
    font-size: .82rem; font-weight: 600; border: 1px solid;
  }}
  .status-pill .dot {{ width: 8px; height: 8px; border-radius: 50%; flex: none; }}
  .status-pill.alta {{ color: #ff9c96; border-color: rgba(224,66,107,.5); background: var(--critical-bg); }}
  .status-pill.alta .dot {{ background: var(--critical); box-shadow: 0 0 0 4px rgba(224,66,107,.18); }}
  .status-pill.media {{ color: #ffd68a; border-color: rgba(250,178,25,.5); background: var(--warning-bg); }}
  .status-pill.media .dot {{ background: var(--warning); box-shadow: 0 0 0 4px rgba(250,178,25,.18); }}
  .status-pill.ok {{ color: #8fe38f; border-color: rgba(12,163,12,.5); background: var(--good-bg); }}
  .status-pill.ok .dot {{ background: var(--good); box-shadow: 0 0 0 4px rgba(12,163,12,.18); }}

  .tabs {{
    display: flex; gap: 6px; flex-wrap: wrap; padding: 6px; margin: 0 auto 24px; max-width: 1240px;
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; position: sticky; top: 12px; z-index: 20;
  }}
  .tab-btn {{
    font-family: inherit; font-size: .82rem; font-weight: 600; color: var(--text-dim); background: transparent;
    border: none; border-radius: 10px; padding: 10px 16px; cursor: pointer; transition: background .15s, color .15s;
  }}
  .tab-btn:hover {{ color: var(--text); background: var(--surface-2); }}
  .tab-btn.active {{
    color: #fff; background: rgba(17,135,240,.16); border: 1px solid var(--accent);
    padding: 9px 15px; box-shadow: 0 0 22px -6px rgba(17,135,240,.7);
  }}
  .tab-panel {{ display: none; }}
  .tab-panel.active {{ display: block; animation: fade-in .25s ease; }}
  @keyframes fade-in {{ from {{ opacity: 0; transform: translateY(4px); }} to {{ opacity: 1; transform: none; }} }}

  section {{ margin-bottom: 28px; }}
  h2 {{
    font-size: .68rem; text-transform: uppercase; letter-spacing: .16em; color: var(--accent-strong);
    font-weight: 700; margin: 0 0 14px; display: flex; align-items: center; gap: 12px;
  }}
  h2::after {{ content: ""; flex: 1; height: 1px; background: linear-gradient(90deg, var(--border), transparent); }}
  h3.descoberta-produto {{
    font-size: .78rem; font-weight: 800; margin: 0 0 10px; color: var(--text);
    text-transform: uppercase; letter-spacing: .1em;
  }}

  .gauge-grid, .squadron-grid {{ display: flex; flex-wrap: wrap; gap: 14px; }}
  .gauge, .squadron-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px;
    min-width: 190px; box-shadow: 0 8px 24px -14px rgba(0,0,0,.6);
  }}
  .gauge {{ min-width: 178px; }}
  .gauge-produto {{ font-size: .72rem; letter-spacing: .03em; text-transform: uppercase; color: var(--text-mute); margin-bottom: 10px; }}
  .gauge-main {{ display: flex; align-items: baseline; gap: 6px; margin-bottom: 10px; }}
  .gauge-value {{ font-size: 1.7rem; font-weight: 700; color: var(--text); }}
  .gauge-tag {{ font-size: .66rem; color: var(--text-mute); letter-spacing: .06em; }}
  .gauge-row {{ display: flex; justify-content: space-between; gap: 12px; font-size: .78rem;
                color: var(--text-dim); font-variant-numeric: tabular-nums; margin-top: 4px; }}
  .gauge-row strong {{ color: var(--text); font-weight: 600; }}
  .signal-bar {{ margin-top: 12px; height: 5px; background: var(--surface-3); border-radius: 3px; overflow: hidden; }}
  .signal-bar span {{ display: block; height: 100%; background: var(--accent); border-radius: 3px; }}
  .gauge-ga4 {{ margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border); }}

  .squadron-card {{ border-left: 3px solid var(--border-strong); min-width: 230px; max-width: 320px; }}
  .squadron-card.sev-alta {{ border-left-color: var(--critical); }}
  .squadron-card.sev-media {{ border-left-color: var(--warning); }}
  .squadron-card.sev-baixa {{ border-left-color: var(--good); }}
  .squadron-head {{ display: flex; align-items: center; gap: 9px; margin-bottom: 8px; }}
  .squadron-emblema {{ font-size: 1.15rem; }}
  .squadron-nome {{ font-size: .86rem; font-weight: 700; }}
  .squadron-status {{
    display: inline-block; font-size: .64rem; letter-spacing: .04em; text-transform: uppercase;
    padding: 3px 9px; border-radius: 999px; background: var(--surface-2); color: var(--text-dim);
    border: 1px solid var(--border); margin-bottom: 8px; font-weight: 600;
  }}
  .sev-alta .squadron-status {{ color: #ff9c96; border-color: rgba(224,66,107,.5); background: var(--critical-bg); }}
  .sev-media .squadron-status {{ color: #ffd68a; border-color: rgba(250,178,25,.5); background: var(--warning-bg); }}
  .squadron-count {{ font-size: .74rem; color: var(--text-mute); margin-bottom: 8px; }}
  .squadron-list {{ list-style: none; margin: 0; padding: 0; font-size: .78rem; color: var(--text-dim); }}
  .squadron-list li {{ padding: 5px 0; border-top: 1px solid var(--border); }}
  .squadron-list li:first-child {{ border-top: none; padding-top: 0; }}

  .data-table-wrap, .ml-radar-table-wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: 10px; }}
  table.data-table, table.ml-radar-table {{ width: 100%; border-collapse: collapse; font-size: .82rem; white-space: nowrap; }}
  .data-table th, .ml-radar-table th {{
    text-align: left; padding: 11px 14px; background: var(--surface-2); color: var(--text-dim);
    font-size: .66rem; text-transform: uppercase; letter-spacing: .05em; font-weight: 700;
    border-bottom: 1px solid var(--border); position: sticky; top: 0;
  }}
  .data-table td, .ml-radar-table td {{
    padding: 10px 14px; border-bottom: 1px solid var(--border); color: var(--text-dim);
    font-variant-numeric: tabular-nums; background: var(--surface);
  }}
  .data-table tr:last-child td, .ml-radar-table tr:last-child td {{ border-bottom: none; }}
  tr.radar-proprio td {{ background: var(--accent-soft); }}
  tr.radar-proprio td.quem {{ color: var(--accent-strong); font-weight: 700; }}
  td.quem {{ color: var(--text); font-weight: 600; }}
  td.ads-flag {{ text-transform: uppercase; font-size: .72rem; }}
  td.tab-note-cell {{ color: var(--text-mute); font-size: .74rem; white-space: normal; }}
  .marketplace-bloco, .descoberta-bloco {{ margin-bottom: 24px; }}
  .marketplace-bloco:last-child, .descoberta-bloco:last-child {{ margin-bottom: 0; }}

  .tab-aviso {{
    background: var(--warning-bg); border: 1px solid rgba(250,178,25,.4); color: #ffd68a;
    border-radius: 12px; padding: 12px 16px; font-size: .82rem; font-weight: 600; margin-bottom: 16px;
  }}
  .tab-note {{ margin-top: 14px; font-size: .78rem; color: var(--text-mute); line-height: 1.6; max-width: 860px; }}
  .hist-empty {{ color: var(--text-mute); font-size: .86rem; padding: 30px; text-align: center;
                 border: 1px dashed var(--border); border-radius: 10px; }}

  .hist-chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; }}
  .hist-chart-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px 6px;
    box-shadow: 0 8px 24px -14px rgba(0,0,0,.6);
  }}
  .hist-chart-head {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }}
  .hist-chart-title {{ font-size: .88rem; font-weight: 700; }}
  .hist-chart-title .vs {{ color: var(--text-mute); font-weight: 400; }}
  .hist-chart-legend {{ display: flex; flex-wrap: wrap; gap: 12px; font-size: .68rem; color: var(--text-mute); }}
  .leg-item {{ display: inline-flex; align-items: center; gap: 5px; }}
  .leg-swatch {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex: none; }}
  .swatch-ads-on {{ background: var(--accent); }}
  .swatch-ads-off {{ background: transparent; border: 1.5px solid var(--text-mute); }}
  .swatch-disputa {{ background: var(--critical-bg); border: 1px solid var(--critical); border-radius: 3px; }}
  .swatch-kpi {{ background: var(--critical); }}
  .hist-chart-svg {{ width: 100%; height: auto; display: block; }}
  .faixa-disputa {{ fill: var(--critical); opacity: .1; }}
  .hist-linha {{ fill: none; stroke: var(--accent); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }}
  .marca-ads-on {{ fill: var(--accent); stroke: var(--surface); stroke-width: 1.5; }}
  .marca-ads-off {{ fill: var(--surface); stroke: var(--text-mute); stroke-width: 1.5; }}
  .marca-ads-nd {{ fill: var(--text-mute); opacity: .5; stroke: none; }}
  .marca-kpi {{ fill: var(--critical); }}
  .eixo-label {{ fill: var(--text-mute); font-size: 9px; font-family: 'Sora', sans-serif; }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }}
  .card {{
    position: relative; background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 18px 20px; animation: rise .4s ease backwards; animation-delay: var(--d, 0s);
    box-shadow: 0 10px 28px -16px rgba(0,0,0,.65); transition: transform .2s ease, box-shadow .2s ease;
  }}
  .card:hover {{
    transform: translateY(-3px); border-color: var(--border-strong);
    box-shadow: 0 16px 34px -16px rgba(0,0,0,.8), 0 0 26px -10px rgba(17,135,240,.45);
  }}
  .card.sev-alta {{ border-color: rgba(224,66,107,.4); }}
  .card.sev-media {{ border-color: rgba(250,178,25,.35); }}
  @keyframes rise {{ from {{ opacity: 0; transform: translateY(10px); }} to {{ opacity: 1; transform: none; }} }}
  .card-head {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
  .badge {{
    display: inline-flex; align-items: center; gap: 5px; font-size: .68rem; font-weight: 700;
    padding: 4px 10px; border-radius: 999px; letter-spacing: .04em; border: 1px solid;
  }}
  .badge-ico {{ font-size: .62rem; }}
  .sev-alta .badge {{ background: var(--critical-bg); color: #ff9c96; border-color: rgba(224,66,107,.5); }}
  .sev-media .badge {{ background: var(--warning-bg); color: #ffd68a; border-color: rgba(250,178,25,.5); }}
  .sev-baixa .badge {{ background: var(--good-bg); color: #8fe38f; border-color: rgba(12,163,12,.5); }}
  .tipo {{ font-size: .74rem; color: var(--text-mute); text-transform: capitalize; }}
  .card h3 {{
    margin: 14px 0 6px; font-size: 1.04rem; text-wrap: balance; font-weight: 700;
    display: flex; align-items: center; gap: 8px;
  }}
  .crosshair {{ display: none; }}
  .card .vs {{ color: var(--text-mute); font-size: .82rem; font-weight: 400; }}
  .resumo {{ opacity: .92; }}
  .card p {{ line-height: 1.55; font-size: .87rem; color: var(--text-dim); }}
  .label {{
    display: block; font-size: .68rem; text-transform: uppercase; letter-spacing: .05em;
    color: var(--accent-strong); margin-bottom: 4px; font-weight: 700;
  }}
  .card ul {{ list-style: none; margin: 6px 0 10px; padding: 0; font-size: .86rem; color: var(--text-dim); }}
  .card li {{ margin-bottom: 6px; padding-left: 16px; position: relative; }}
  .card li::before {{ content: "→"; position: absolute; left: 0; color: var(--accent-strong); }}
  .kpis {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }}
  .kpi {{
    font-size: .68rem; background: var(--surface-2); border: 1px solid var(--border);
    padding: 3px 10px; border-radius: 999px; color: var(--text-dim);
  }}
  .creative {{ margin: 12px 0; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; background: var(--surface-2); }}
  .creative img {{ display: block; width: 100%; max-height: 260px; object-fit: cover; }}
  .video-link {{ display: block; padding: 10px 12px; font-size: .8rem; text-decoration: none; color: var(--accent-strong); text-align: center; }}
  .analise-criativo {{
    margin: 8px 0 10px; padding: 12px 14px; border-left: 2px solid var(--accent); background: var(--surface-2);
    border-radius: 0 12px 12px 0;
  }}
  .analise-row {{ display: flex; gap: 8px; font-size: .82rem; margin-bottom: 5px; }}
  .analise-row:last-child {{ margin-bottom: 0; }}
  .analise-row span {{ flex: none; width: 84px; color: var(--accent-strong); font-size: .68rem; text-transform: uppercase;
                        letter-spacing: .03em; padding-top: 2px; font-weight: 700; }}
  .analise-row p {{ margin: 0; font-size: .82rem; color: var(--text-dim); }}
  .foot {{
    margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border);
    display: flex; justify-content: space-between; font-size: .72rem; color: var(--text-mute);
    font-variant-numeric: tabular-nums;
  }}
  .foot a {{ text-decoration: none; }}
  .foot a:hover {{ text-decoration: underline; }}
  .empty {{ padding: 60px 20px; color: var(--text-mute); grid-column: 1 / -1; text-align: center; font-size: 1rem; }}
  .empty span {{ display: block; margin-top: 8px; font-size: .78rem; opacity: .8; }}
  .caveat {{ font-size: .78rem; color: var(--text-mute); max-width: 860px; line-height: 1.6; }}

  .toolbar, .toolbar-mini {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .toolbar-mini {{ margin: 10px 0; }}
  .btn, .btn-mini {{
    font-family: inherit; font-weight: 600; cursor: pointer; background: var(--surface-2); color: var(--text);
    border: 1px solid var(--border); border-radius: 10px; letter-spacing: .01em;
  }}
  .btn {{ font-size: .84rem; padding: 10px 16px; }}
  .btn-mini {{ font-size: .76rem; padding: 6px 12px; }}
  .btn:hover, .btn-mini:hover {{ border-color: var(--border-strong); }}
  .btn.primary, .btn-mini.primary {{
    background: rgba(17,135,240,.16); border-color: var(--accent); color: #fff;
    box-shadow: 0 0 22px -6px rgba(17,135,240,.7);
  }}
  .selecao-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; }}
  .selecao-coluna {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px;
  }}
  .selecao-head {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }}
  .selecao-stat {{ font-size: .78rem; color: var(--text-dim); font-variant-numeric: tabular-nums; }}
  .add-form-mini {{
    display: flex; flex-wrap: wrap; gap: 8px; background: var(--surface-2); border: 1px dashed var(--border-strong);
    border-radius: 10px; padding: 10px; margin-bottom: 10px;
  }}
  .add-form-mini input {{
    flex: 1 1 120px; font-family: inherit; font-size: .8rem; color: var(--text); background: var(--surface);
    border: 1px solid var(--border); border-radius: 8px; padding: 7px 10px;
  }}
  .selecao-lista {{ display: flex; flex-direction: column; gap: 8px; }}
  .selecao-item {{
    display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: 10px;
    background: var(--surface-2); border: 1px solid var(--border); border-radius: 10px; padding: 9px 12px;
  }}
  .selecao-item.off {{ opacity: .6; }}
  .selecao-toggle {{
    position: relative; width: 36px; height: 20px; flex: none; border-radius: 12px; border: 1px solid var(--border);
    background: var(--surface-3); cursor: pointer; appearance: none; -webkit-appearance: none;
  }}
  .selecao-toggle::after {{
    content: ""; position: absolute; top: 2px; left: 2px; width: 14px; height: 14px; border-radius: 50%;
    background: var(--text-mute); transition: transform .15s ease, background .15s ease;
  }}
  .selecao-toggle:checked {{ border-color: var(--accent); background: var(--accent-soft); }}
  .selecao-toggle:checked::after {{ transform: translateX(16px); background: var(--accent); }}
  .selecao-nome {{ font-size: .84rem; font-weight: 600; }}
  .selecao-sub {{ display: block; font-size: .7rem; color: var(--text-mute); font-weight: 400; }}
  .selecao-tag {{
    font-size: .62rem; text-transform: uppercase; letter-spacing: .04em; padding: 3px 8px; border-radius: 999px;
    background: var(--surface-3); color: var(--text-dim); white-space: nowrap;
  }}
  .selecao-item.on .selecao-tag {{ color: var(--accent-strong); background: var(--accent-soft); }}
  .selecao-remove {{ background: transparent; border: none; color: var(--text-mute); cursor: pointer; font-size: .9rem; padding: 2px 4px; }}
  .selecao-remove:hover {{ color: #ff9c96; }}
  .json-preview {{
    display: none; width: 100%; height: 220px; margin-top: 12px; font-family: ui-monospace, "SF Mono", monospace;
    font-size: .74rem; color: var(--text); background: var(--surface-2); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px; resize: vertical;
  }}

  a:focus-visible, button:focus-visible, input:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  .card:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px; }}

  /* ------------------------------------------------------------ GA4 · Jornada */
  .ga4-kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(178px, 1fr)); gap: 12px; }}
  .ga4-kpi {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 15px 16px;
    position: relative; overflow: hidden;
  }}
  .ga4-kpi::before {{
    content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 2px; background: var(--accent);
    opacity: .55;
  }}
  .ga4-kpi-label {{
    font-size: .6rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase;
    color: var(--text-mute); margin-bottom: 9px;
  }}
  .ga4-kpi-value {{
    font-size: 1.55rem; font-weight: 800; letter-spacing: -.02em; color: var(--text);
    font-variant-numeric: tabular-nums; line-height: 1.05;
  }}
  .ga4-kpi-sub {{ font-size: .7rem; color: var(--text-dim); margin-top: 7px; line-height: 1.4; }}

  .ga4-funil {{ display: flex; flex-direction: column; gap: 4px; }}
  .ga4-funil-linha {{
    border: 1px solid var(--border); border-radius: 10px; padding: 12px 15px; background: var(--surface);
  }}
  .ga4-funil-linha.vazamento {{ border-color: rgba(224,66,107,.5); background: rgba(224,66,107,.06); }}
  .ga4-funil-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }}
  .ga4-funil-nome {{ font-size: .8rem; font-weight: 700; letter-spacing: .02em; }}
  .ga4-funil-valor {{ font-size: 1.1rem; font-weight: 800; font-variant-numeric: tabular-nums; }}
  .ga4-funil-track {{
    position: relative; height: 26px; margin: 9px 0 7px; background: rgba(255,255,255,.04);
    border-radius: 5px; overflow: hidden; display: flex; align-items: center;
  }}
  .ga4-funil-bar {{
    height: 100%; width: var(--w); border-radius: 5px;
    background: linear-gradient(90deg, rgba(17,135,240,.85), rgba(85,174,255,.5));
    box-shadow: 0 0 18px -4px rgba(17,135,240,.8);
    animation: ga4-grow 1s cubic-bezier(.2,.8,.3,1) both;
  }}
  .ga4-funil-linha.vazamento .ga4-funil-bar {{
    background: linear-gradient(90deg, rgba(224,66,107,.85), rgba(255,140,170,.45));
    box-shadow: 0 0 18px -4px rgba(224,66,107,.85);
  }}
  @keyframes ga4-grow {{ from {{ width: 0; }} to {{ width: var(--w); }} }}
  .ga4-funil-topo {{
    position: absolute; right: 10px; font-size: .66rem; font-weight: 700; color: var(--text-dim);
    font-variant-numeric: tabular-nums;
  }}
  .ga4-funil-foot {{ display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
  .ga4-funil-desc {{ font-size: .68rem; color: var(--text-mute); }}
  .ga4-funil-passagem {{ font-size: .68rem; font-weight: 700; color: var(--accent-strong); }}
  .ga4-funil-passagem.vazamento {{ color: #ff9c96; }}

  .ga4-quad-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 12px; }}
  .ga4-quad {{
    border: 1px solid var(--border); border-radius: 10px; padding: 13px 15px; background: var(--surface);
    border-top: 2px solid var(--border-strong);
  }}
  .ga4-quad.q-escalar {{ border-top-color: var(--good); }}
  .ga4-quad.q-corrigir {{ border-top-color: var(--critical); }}
  .ga4-quad.q-testar {{ border-top-color: var(--accent); }}
  .ga4-quad.q-cortar {{ border-top-color: var(--text-mute); }}
  .ga4-quad-head {{ margin-bottom: 10px; }}
  .ga4-quad-titulo {{ display: block; font-size: .76rem; font-weight: 800; letter-spacing: .04em; }}
  .ga4-quad-desc {{ display: block; font-size: .66rem; color: var(--text-mute); margin-top: 3px; }}
  .ga4-quad-lista {{ list-style: none; margin: 0; padding: 0; }}
  .ga4-quad-lista li {{
    display: flex; justify-content: space-between; gap: 10px; padding: 6px 0;
    border-top: 1px solid var(--border); font-size: .76rem;
  }}
  .ga4-quad-lista li:first-child {{ border-top: none; }}
  .ga4-q-canal {{ color: var(--text); font-weight: 600; }}
  .ga4-q-num {{ color: var(--text-mute); font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .ga4-q-vazio {{ color: var(--text-mute); font-style: italic; }}

  .ga4-badge {{
    display: inline-block; font-size: .58rem; font-weight: 800; letter-spacing: .06em; text-transform: uppercase;
    padding: 3px 8px; border-radius: 999px; border: 1px solid; white-space: nowrap;
  }}
  .ga4-badge.q-escalar {{ color: #8fe38f; border-color: rgba(12,163,12,.55); background: var(--good-bg); }}
  .ga4-badge.q-corrigir {{ color: #ff9c96; border-color: rgba(224,66,107,.55); background: var(--critical-bg); }}
  .ga4-badge.q-testar {{ color: var(--accent-strong); border-color: var(--border-strong); background: var(--accent-soft); }}
  .ga4-badge.q-cortar {{ color: var(--text-mute); border-color: var(--border); background: var(--surface-2); }}

  .ga4-serie-card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px 8px;
  }}
  .ga4-serie-svg {{ width: 100%; height: auto; display: block; }}
  .ga4-grid {{ stroke: rgba(255,255,255,.055); stroke-width: 1; }}
  .ga4-bar {{ fill: rgba(85,174,255,.2); transition: fill .15s ease; }}
  .ga4-bar:hover {{ fill: rgba(85,174,255,.55); }}
  .ga4-area {{ fill: url(#ga4-area-grad); opacity: .3; }}
  .ga4-linha-sessoes {{ fill: none; stroke: var(--accent); stroke-width: 2; stroke-linejoin: round; }}
  .ga4-linha-compras {{ fill: none; stroke: #ffd68a; stroke-width: 2; stroke-dasharray: 5 3; stroke-linejoin: round; }}
  .ga4-dot-compras {{ fill: #ffd68a; stroke: #0a1526; stroke-width: 1.4; cursor: crosshair; }}
  .leg-swatch.sw-sessoes {{ background: var(--accent); }}
  .leg-swatch.sw-compras {{ background: #ffd68a; }}
  .leg-swatch.sw-receita {{ background: rgba(85,174,255,.4); border-radius: 2px; }}

  .ga4-dev-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }}
  .ga4-dev {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 14px 16px; }}
  .ga4-dev-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 10px; margin-bottom: 8px; }}
  .ga4-dev-nome {{ font-size: .82rem; font-weight: 700; text-transform: capitalize; }}
  .ga4-dev-share {{ font-size: .68rem; color: var(--accent-strong); font-weight: 700; }}
  .ga4-dev-track {{ height: 5px; background: rgba(255,255,255,.05); border-radius: 3px; overflow: hidden; margin-bottom: 10px; }}
  .ga4-dev-bar {{
    height: 100%; width: var(--w); background: var(--accent); border-radius: 3px;
    box-shadow: 0 0 12px -2px rgba(17,135,240,.9); animation: ga4-grow .9s cubic-bezier(.2,.8,.3,1) both;
  }}

  .ga4-diag-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 12px; }}
  .ga4-diag {{
    background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--text-mute);
    border-radius: 10px; padding: 14px 16px;
  }}
  .ga4-diag.sev-alta {{ border-left-color: var(--critical); }}
  .ga4-diag.sev-media {{ border-left-color: var(--warning); }}
  .ga4-diag.sev-baixa {{ border-left-color: var(--accent); }}
  .ga4-diag-nivel {{
    display: inline-block; font-size: .58rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase;
    color: var(--text-mute); margin-bottom: 6px;
  }}
  .ga4-diag.sev-alta .ga4-diag-nivel {{ color: #ff9c96; }}
  .ga4-diag.sev-media .ga4-diag-nivel {{ color: #ffd68a; }}
  .ga4-diag-titulo {{ font-size: .88rem; font-weight: 700; margin-bottom: 6px; }}
  .ga4-diag-detalhe {{ margin: 0; font-size: .8rem; color: var(--text-dim); line-height: 1.55; }}
  @media (prefers-reduced-motion: reduce) {{
    .card, .tab-panel.active, .status-pill {{ animation: none !important; }}
  }}
{FX_CSS}
</style></head>
<body>
{FX_BODY}
<header class="top">
  <div class="head-grid">
    <div>
      <span class="pill-badge">War Room · Inteligência Competitiva · {meta['data'][:10]}</span>
      <h1 class="cover-title">{config.get('marca', '')}<em>Monitoramento Competitivo</em></h1>
      <div class="rule"></div>
      <p class="cover-sub">Preço, desconto e posição da concorrência em marketplaces, cruzados com o
      <b>desempenho real</b> das nossas campanhas — com <b>diagnóstico antes de qualquer ação</b>.</p>
    </div>
    <div class="head-right">
      {seal_svg}
      <div class="top-stats">
        <div class="top-stat"><span class="top-stat-label">Última varredura</span><span class="top-stat-value">{meta['data']}</span></div>
        <div class="top-stat"><span class="top-stat-label">Alertas na rodada</span><span class="top-stat-value" data-count="{len(alertas_rodada)}">{len(alertas_rodada)}</span></div>
      </div>
    </div>
  </div>
</header>
{pipeline_html}
<div class="status-banner"><span class="status-pill {mc_level}"><span class="dot"></span>{mc_text}</span></div>

<nav class="tabs" role="tablist" aria-label="Seções da war room">
  <button class="tab-btn active" data-tab="visao-geral" role="tab" aria-selected="true">Visão Geral</button>
  <button class="tab-btn" data-tab="marketplaces" role="tab" aria-selected="false">Marketplaces</button>
  <button class="tab-btn" data-tab="concorrentes" role="tab" aria-selected="false">Concorrentes</button>
  <button class="tab-btn" data-tab="ga4" role="tab" aria-selected="false">GA4 · Jornada</button>
  <button class="tab-btn" data-tab="keywords" role="tab" aria-selected="false">Keywords &amp; Leilão</button>
  <button class="tab-btn" data-tab="historico" role="tab" aria-selected="false">Histórico Preço × Ads</button>
  <button class="tab-btn" data-tab="selecao" role="tab" aria-selected="false">Seleção Manual</button>
</nav>

<div class="shell">
  <div class="tab-panel active" data-tab="visao-geral">
    {esquadrao_section}
    {own_kpi_section}
    <section>
      <h2>Battlecards — mudanças detectadas nesta rodada</h2>
      <div class="grid">{cards}</div>
    </section>
    <p class="caveat">Investimento real (R$) em ads não é dado público em nenhuma plataforma — os sinais de
    atividade em ads (Meta Ad Library / Google Ads Transparency Center) refletem contagem de anúncios ativos
    capturada manualmente, não valor gasto. Ver references/fontes-e-limitacoes.md.</p>
    {credbar_html}
  </div>

  <div class="tab-panel" data-tab="marketplaces">
    <section><h2>Radar de posição — Mercado Livre + Google Shopping (nós vs. concorrência)</h2>{marketplaces_html}</section>
  </div>

  <div class="tab-panel" data-tab="concorrentes">
    <section><h2>Motor de descoberta e composição de concorrentes</h2>{descoberta_html}</section>
  </div>

  <div class="tab-panel" data-tab="ga4">
    <svg width="0" height="0" aria-hidden="true" style="position:absolute">
      <defs><linearGradient id="ga4-area-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#1187f0" stop-opacity=".85" />
        <stop offset="100%" stop-color="#1187f0" stop-opacity="0" />
      </linearGradient></defs>
    </svg>
    {ga4_html}
  </div>

  <div class="tab-panel" data-tab="keywords">
    <section><h2>Relação completa de keywords das campanhas + valor do leilão</h2>{keywords_html}</section>
  </div>

  <div class="tab-panel" data-tab="historico">
    <section>
      <h2>Histórico preço × atividade de ads (marca disputa direta e correlação com queda de KPI)</h2>
      {historico_html}
      <p class="tab-note">Acumula automaticamente a cada rodada real (Radar de Marketplaces + alertas) — sem
      coleta nova. "Disputando direto" = o concorrente está em posição melhor que a nossa no mesmo produto,
      no mesmo momento. Ver references/protocolo-diagnostico.md para a análise completa quando isso coincide
      com queda de KPI.</p>
    </section>
  </div>

  <div class="tab-panel" data-tab="selecao">
    <section>
      <h2>Seleção manual — produtos e concorrentes monitorados</h2>
      {selecao_html}
    </section>
  </div>
</div>

<script>
(function () {{
  var btns = document.querySelectorAll('.tab-btn');
  var panels = document.querySelectorAll('.tab-panel');
  btns.forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      btns.forEach(function (b) {{ b.classList.remove('active'); b.setAttribute('aria-selected', 'false'); }});
      panels.forEach(function (p) {{ p.classList.remove('active'); }});
      btn.classList.add('active'); btn.setAttribute('aria-selected', 'true');
      document.querySelector('.tab-panel[data-tab="' + btn.dataset.tab + '"]').classList.add('active');
    }});
  }});
}})();

(function () {{
  var dataEl = document.getElementById('selecao-manual-data');
  if (!dataEl) return;
  var seed = JSON.parse(dataEl.textContent);
  var produtos = seed.produtos;
  var concorrentes = seed.concorrentes;

  function renderLista(container, itens, tipo) {{
    if (!itens.length) {{
      container.innerHTML = '<p class="tab-note">Nenhum item ainda — adicione acima.</p>';
      return;
    }}
    container.innerHTML = itens.map(function (item, i) {{
      var nome = item.nome;
      var sub = tipo === 'produto' ? (item.termo_busca_ml || '') : (item.dominio_site || (item.sellers_ml || []).join(', '));
      return '<div class="selecao-item ' + (item.monitorando ? 'on' : 'off') + '">' +
        '<input type="checkbox" class="selecao-toggle" data-idx="' + i + '" data-tipo="' + tipo + '" ' + (item.monitorando ? 'checked' : '') + ' aria-label="Monitorar ' + nome + '">' +
        '<span class="selecao-nome">' + nome + (sub ? '<span class="selecao-sub">' + sub + '</span>' : '') + '</span>' +
        '<span class="selecao-tag">' + (item.monitorando ? 'monitorando' : 'candidato') + '</span>' +
        '<button class="selecao-remove" data-remove="' + i + '" data-tipo="' + tipo + '" title="Remover" aria-label="Remover ' + nome + '">✕</button>' +
        '</div>';
    }}).join('');
  }}

  function atualizarStats() {{
    document.getElementById('sel-prod-on').textContent = produtos.filter(function (p) {{ return p.monitorando; }}).length;
    document.getElementById('sel-prod-total').textContent = produtos.length;
    document.getElementById('sel-conc-on').textContent = concorrentes.filter(function (c) {{ return c.monitorando; }}).length;
    document.getElementById('sel-conc-total').textContent = concorrentes.length;
  }}

  function render() {{
    renderLista(document.getElementById('lista-produtos'), produtos, 'produto');
    renderLista(document.getElementById('lista-concorrentes'), concorrentes, 'concorrente');
    atualizarStats();
  }}

  document.addEventListener('change', function (e) {{
    if (!e.target.classList.contains('selecao-toggle')) return;
    var idx = parseInt(e.target.dataset.idx, 10);
    var lista = e.target.dataset.tipo === 'produto' ? produtos : concorrentes;
    lista[idx].monitorando = e.target.checked;
    render();
  }});

  document.addEventListener('click', function (e) {{
    if (e.target.dataset.remove !== undefined) {{
      var idx = parseInt(e.target.dataset.remove, 10);
      var lista = e.target.dataset.tipo === 'produto' ? produtos : concorrentes;
      var nome = lista[idx].nome;
      if (confirm('Remover "' + nome + '" do catálogo?')) {{ lista.splice(idx, 1); render(); }}
    }}
  }});

  var addProdutoForm = document.getElementById('add-produto-form');
  document.getElementById('btn-add-produto-toggle').addEventListener('click', function () {{
    addProdutoForm.style.display = addProdutoForm.style.display === 'none' ? 'flex' : 'none';
  }});
  document.getElementById('btn-add-produto-confirm').addEventListener('click', function () {{
    var nome = document.getElementById('new-produto-nome').value.trim();
    var termo = document.getElementById('new-produto-termo').value.trim();
    var preco = document.getElementById('new-produto-preco').value;
    if (!nome || !termo) return;
    produtos.push({{nome: nome, termo_busca_ml: termo, preco_proprio: preco ? parseFloat(preco) : null,
                    ticket_medio: preco ? parseFloat(preco) : null, monitorando: true}});
    document.getElementById('new-produto-nome').value = '';
    document.getElementById('new-produto-termo').value = '';
    document.getElementById('new-produto-preco').value = '';
    addProdutoForm.style.display = 'none';
    render();
  }});

  var addConcForm = document.getElementById('add-concorrente-form');
  document.getElementById('btn-add-concorrente-toggle').addEventListener('click', function () {{
    addConcForm.style.display = addConcForm.style.display === 'none' ? 'flex' : 'none';
  }});
  document.getElementById('btn-add-concorrente-confirm').addEventListener('click', function () {{
    var nome = document.getElementById('new-concorrente-nome').value.trim();
    var dominio = document.getElementById('new-concorrente-dominio').value.trim();
    var sellers = document.getElementById('new-concorrente-seller').value.trim();
    if (!nome) return;
    concorrentes.push({{nome: nome, dominio_site: dominio || undefined,
                        sellers_ml: sellers ? sellers.split(',').map(function (s) {{ return s.trim(); }}) : [],
                        monitorando: true}});
    document.getElementById('new-concorrente-nome').value = '';
    document.getElementById('new-concorrente-dominio').value = '';
    document.getElementById('new-concorrente-seller').value = '';
    addConcForm.style.display = 'none';
    render();
  }});

  function limpo(item) {{
    var c = Object.assign({{}}, item);
    delete c.monitorando;
    Object.keys(c).forEach(function (k) {{ if (c[k] === null || c[k] === '' || c[k] === undefined) delete c[k]; }});
    return c;
  }}

  function montarConfigAtualizado() {{
    var novo = {json.dumps({k: v for k, v in config.items() if not k.startswith("_comentario")}, ensure_ascii=False)};
    novo.produtos_monitorados = produtos.filter(function (p) {{ return p.monitorando; }}).map(limpo);
    novo.produtos_candidatos_manual = produtos.filter(function (p) {{ return !p.monitorando; }}).map(limpo);
    novo.concorrentes = concorrentes.filter(function (c) {{ return c.monitorando; }}).map(limpo);
    novo.candidatos_concorrentes_manual = concorrentes.filter(function (c) {{ return !c.monitorando; }}).map(limpo);
    return novo;
  }}

  document.getElementById('btn-export-config').addEventListener('click', function () {{
    var texto = JSON.stringify(montarConfigAtualizado(), null, 2);
    var blob = new Blob([texto], {{type: 'application/json'}});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = 'config.json';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }});
  document.getElementById('btn-copy-config').addEventListener('click', async function () {{
    var texto = JSON.stringify(montarConfigAtualizado(), null, 2);
    var preview = document.getElementById('config-json-preview');
    preview.value = texto; preview.style.display = 'block';
    try {{ await navigator.clipboard.writeText(texto); }} catch (err) {{ preview.select(); }}
  }});

  render();
}})();
</script>
<script id="fx-alertas-data" type="application/json">{alertas_json}</script>
{FX_JS}
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
    ap.add_argument("--queda-kpi-json", default=None,
                     help="saída de own_performance.py --history-dir (queda-kpi-proprio.json) — vira "
                          "alertas 'queda_kpi_proprio' que acionam o protocolo de diagnóstico completo")
    ap.add_argument("--simulate-ml-proprio", default=None,
                     help="JSON {produto: {...}} com o NOSSO anúncio simulado (mesmo formato que "
                          "collect_snapshot produz em snapshot_proprio), para testar o Radar de "
                          "Posição sem coleta real. Só usado junto com --simulate-ml.")
    ap.add_argument("--descoberta-json", default=None,
                     help="saída de descoberta_concorrentes.py --export-json — vira a aba 'Concorrentes' "
                          "(Concorrentes Descobertos, na xlsx)")
    ap.add_argument("--keywords-relatorio-json", default=None,
                     help="saída de gerar_relatorio_keywords.py --export-json — vira a aba 'Keywords & Leilão'")
    ap.add_argument("--simulate-google-shopping", default=None,
                     help="JSON com snapshot de concorrentes no Google Shopping (mesmo formato de "
                          "--simulate-ml) — vira o canal 'Google Shopping' na aba Marketplaces")
    ap.add_argument("--simulate-google-shopping-proprio", default=None,
                     help="JSON com o NOSSO anúncio simulado no Google Shopping (mesmo formato de "
                          "--simulate-ml-proprio). Só usado junto com --simulate-google-shopping.")
    ap.add_argument("--ga4-json", default=None,
                     help="saída de ga4_jornada.py — vira a aba 'GA4 · Jornada' (KPIs, funil de compra, "
                          "matriz de decisão por canal, devices, landing pages e diagnóstico)")
    ap.add_argument("--simulate-historico-preco-ads", default=None,
                     help="JSON {produto: {concorrente: [pontos...]}} pronto para semear/sobrescrever o "
                          "histórico acumulado de preço×ads (demonstração — em produção ele acumula "
                          "sozinho a cada rodada real via Radar de Marketplaces + alertas)")
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
    global AGENTES
    AGENTES = load_agentes(os.path.join(SCRIPT_DIR, "agentes.json"))
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
        snapshot_proprio = load_json(args.simulate_ml_proprio, {}) if args.simulate_ml_proprio else {}
    else:
        print(f"Coletando snapshot atual ({marca})...", file=sys.stderr)
        snapshot_novo, snapshot_proprio = collect_snapshot(config, token, produtos_filter, args.per_produto)
    primeira_rodada = not os.path.exists(snap_path)
    snapshot_antigo = load_json(snap_path, {})
    radar_ml = montar_radar_ml(snapshot_novo, snapshot_proprio)

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
    if args.queda_kpi_json:
        alertas += ingest_quedas_kpi_proprio(args.queda_kpi_json, playbook)

    alertas_log = load_json(log_path, [])
    alertas_log += alertas

    save_json(snap_path, snapshot_novo)
    save_json(log_path, alertas_log)
    save_json(current_run_path, alertas)

    snapshot_gs = load_json(args.simulate_google_shopping, {}) if args.simulate_google_shopping else None
    snapshot_gs_proprio = (load_json(args.simulate_google_shopping_proprio, {})
                           if args.simulate_google_shopping_proprio else None)
    marketplaces = montar_radar_marketplaces(radar_ml, snapshot_gs, snapshot_gs_proprio)

    meta = {"data": now_iso()}

    hist_preco_ads_path = os.path.join(hist_dir, f"{marca}-historico-preco-ads.json")
    if args.simulate_historico_preco_ads:
        historico = load_json(args.simulate_historico_preco_ads, {})
        print(f"[SIMULAÇÃO] histórico preço×ads carregado de {args.simulate_historico_preco_ads} "
              "(não acumulado a partir desta rodada)", file=sys.stderr)
    else:
        historico = atualizar_historico_preco_ads(hist_preco_ads_path, radar_ml, alertas, meta["data"])

    descoberta = load_json(args.descoberta_json, {}) if args.descoberta_json else {}
    keywords_data = load_json(args.keywords_relatorio_json, {}) if args.keywords_relatorio_json else {}
    ga4 = load_json(args.ga4_json, {}) if args.ga4_json else {}

    write_xlsx(alertas, alertas_log, snapshot_novo, ads_entries, load_json(ads_hist_path, {}), config, meta, args.out,
               own_perf=own_perf, radar_ml=radar_ml, descoberta=descoberta, keywords_data=keywords_data,
               marketplaces=marketplaces, historico=historico, ga4=ga4)
    write_html(alertas, config, meta, args.html, own_perf=own_perf, radar_ml=radar_ml, descoberta=descoberta,
               keywords_data=keywords_data, marketplaces=marketplaces, historico=historico,
               primeira_rodada=primeira_rodada, ga4=ga4)
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
