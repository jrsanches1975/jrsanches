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
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

APIFY_BASE = "https://api.apify.com/v2/acts"
ML_ACTOR = "viralanalyzer~mercadolivre-scraper"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")

SEVERIDADE_POR_NIVEL = {
    "agressiva": "alta", "forte": "alta",
    "moderada": "media", "moderado": "media",
    "leve": "baixa", "default": "media",
}


# ----------------------------------------------------------------------------- infra
def get_token(config, cli_token):
    return os.environ.get("APIFY_TOKEN") or cli_token or config.get("apify_token") or ""


def apify_run(actor, payload, token, timeout=240):
    url = f"{APIFY_BASE}/{actor}/run-sync-get-dataset-items?token={token}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        return [], f"HTTP {e.code}: {body}"
    except Exception as e:
        return [], repr(e)


def norm(s):
    return " ".join((s or "").lower().split())


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


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
SEV_LABEL = {"alta": "ALTA", "media": "MÉDIA", "baixa": "BAIXA"}


def render_card(a):
    estrategia_html = "".join(f"<li>{s}</li>" for s in a["estrategia"])
    kpis_html = "".join(f'<span class="kpi">{k}</span>' for k in a["kpis"])
    link = (f'<a href="{a["evidencia_url"]}" target="_blank" rel="noopener">evidência ↗</a>'
            if a.get("evidencia_url") else "")
    return f"""
    <article class="card sev-{a['severidade']}">
      <div class="card-head">
        <span class="badge">{SEV_LABEL.get(a['severidade'], a['severidade'].upper())}</span>
        <span class="tipo">{a['tipo'].replace('_', ' ')} · {a['nivel']}</span>
      </div>
      <h3>{a['produto']} <span class="vs">×</span> {a['concorrente']}</h3>
      <p class="resumo">{a['resumo']}</p>
      <p><span class="label">Impacto na concorrência</span>{a['impacto_concorrencia']}</p>
      <p><span class="label">Impacto estimado no volume</span>{a['impacto_volume']}</p>
      <p class="label">Estratégia imediata</p>
      <ul>{estrategia_html}</ul>
      <div class="kpis">{kpis_html}</div>
      <div class="foot"><span>{a['data']}</span>{link}</div>
    </article>"""


def render_own_kpi(produto, v):
    cpa = f"R$ {v['cpa']:.2f}" if v.get("cpa") else "—"
    roas = f"{v['roas']:.2f}×" if v.get("roas") is not None else "—"
    return f"""
    <div class="own-kpi">
      <div class="own-kpi-produto">{produto}</div>
      <div class="own-kpi-row"><span>Invest.</span><strong>R$ {v.get('spend', 0):,.2f}</strong></div>
      <div class="own-kpi-row"><span>CTR</span><strong>{v.get('ctr_pct', 0):.2f}%</strong></div>
      <div class="own-kpi-row"><span>CPA</span><strong>{cpa}</strong></div>
      <div class="own-kpi-row"><span>ROAS</span><strong>{roas}</strong></div>
    </div>"""


def write_html(alertas_rodada, config, meta, path, own_perf=None):
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    cards = "".join(render_card(a) for a in sorted(alertas_rodada, key=lambda x: ordem[x["severidade"]]))
    if not cards:
        cards = ('<div class="empty">Nenhuma mudança detectada nesta rodada '
                  '(ou é a linha de base da 1ª execução).</div>')

    own_kpi_section = ""
    if own_perf:
        own_cards = "".join(render_own_kpi(p, v) for p, v in own_perf.items())
        own_kpi_section = f"""
<section class="own-kpi-strip">
  <h2>Desempenho próprio — Google/Meta Ads (últimos dados importados)</h2>
  <div class="own-kpi-grid">{own_cards}</div>
</section>"""

    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>War Room — {config.get('marca', '')}</title>
<style>
  :root {{
    --bg: #f5f4f0; --surface: #ffffff; --surface-2: #ece9e2; --border: #dcd8ce;
    --text: #181c22; --text-muted: #5b6270; --accent: #d9622b;
    --sev-alta: #b3261e; --sev-media: #a15c00; --sev-baixa: #1e6b3f;
    --sev-alta-bg: #fbe9e7; --sev-media-bg: #fbeed9; --sev-baixa-bg: #e3f1e9;
    color-scheme: light dark;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0b0f14; --surface: #131a23; --surface-2: #1a222c; --border: #2a333f;
      --text: #e7e5df; --text-muted: #97a1af; --accent: #ff8a3d;
      --sev-alta: #ff6b5e; --sev-media: #ffb454; --sev-baixa: #5fd694;
      --sev-alta-bg: #2a1614; --sev-media-bg: #2a2013; --sev-baixa-bg: #12241b;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #0b0f14; --surface: #131a23; --surface-2: #1a222c; --border: #2a333f;
    --text: #e7e5df; --text-muted: #97a1af; --accent: #ff8a3d;
    --sev-alta: #ff6b5e; --sev-media: #ffb454; --sev-baixa: #5fd694;
    --sev-alta-bg: #2a1614; --sev-media-bg: #2a2013; --sev-baixa-bg: #12241b;
  }}
  :root[data-theme="light"] {{
    --bg: #f5f4f0; --surface: #ffffff; --surface-2: #ece9e2; --border: #dcd8ce;
    --text: #181c22; --text-muted: #5b6270; --accent: #d9622b;
    --sev-alta: #b3261e; --sev-media: #a15c00; --sev-baixa: #1e6b3f;
    --sev-alta-bg: #fbe9e7; --sev-media-bg: #fbeed9; --sev-baixa-bg: #e3f1e9;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--text);
    font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .mono {{ font-family: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Menlo, monospace; }}
  header {{
    display: flex; flex-direction: column; gap: 4px; padding: 22px 32px;
    border-bottom: 1px solid var(--border); background: var(--surface);
  }}
  .eyebrow {{
    font-family: ui-monospace, "SF Mono", "Roboto Mono", monospace; font-size: .72rem;
    letter-spacing: .12em; text-transform: uppercase; color: var(--accent); font-weight: 600;
  }}
  header h1 {{ margin: 2px 0 0; font-size: 1.5rem; font-family: ui-monospace, "SF Mono", "Roboto Mono", monospace;
               font-weight: 700; text-wrap: balance; }}
  header p {{ margin: 4px 0 0; color: var(--text-muted); font-size: .82rem; font-variant-numeric: tabular-nums; }}
  .own-kpi-strip {{ padding: 18px 32px; border-bottom: 1px solid var(--border); background: var(--surface); }}
  .own-kpi-strip h2 {{
    font-family: ui-monospace, "SF Mono", "Roboto Mono", monospace; font-size: .74rem;
    text-transform: uppercase; letter-spacing: .08em; color: var(--text-muted); margin: 0 0 12px; font-weight: 600;
  }}
  .own-kpi-grid {{ display: flex; flex-wrap: wrap; gap: 12px; }}
  .own-kpi {{ background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px;
              padding: 10px 14px; min-width: 160px; }}
  .own-kpi-produto {{ font-weight: 700; font-size: .82rem; margin-bottom: 6px; }}
  .own-kpi-row {{ display: flex; justify-content: space-between; gap: 12px; font-size: .78rem;
                  color: var(--text-muted); font-variant-numeric: tabular-nums; }}
  .own-kpi-row strong {{ color: var(--text); font-family: ui-monospace, "SF Mono", "Roboto Mono", monospace; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
           gap: 16px; padding: 24px 32px; }}
  .card {{
    background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--border);
    border-radius: 6px; padding: 16px 18px;
  }}
  .card.sev-alta {{ border-left-color: var(--sev-alta); }}
  .card.sev-media {{ border-left-color: var(--sev-media); }}
  .card.sev-baixa {{ border-left-color: var(--sev-baixa); }}
  .card-head {{ display: flex; align-items: center; gap: 8px; }}
  .badge {{
    font-family: ui-monospace, "SF Mono", "Roboto Mono", monospace; font-size: .68rem; font-weight: 700;
    padding: 2px 8px; border-radius: 4px; letter-spacing: .06em;
  }}
  .sev-alta .badge {{ background: var(--sev-alta-bg); color: var(--sev-alta); }}
  .sev-media .badge {{ background: var(--sev-media-bg); color: var(--sev-media); }}
  .sev-baixa .badge {{ background: var(--sev-baixa-bg); color: var(--sev-baixa); }}
  .tipo {{ font-size: .76rem; color: var(--text-muted); text-transform: capitalize; }}
  .card h3 {{ margin: 10px 0 6px; font-size: 1.02rem; text-wrap: balance; }}
  .card .vs {{ color: var(--text-muted); font-weight: 400; }}
  .resumo {{ color: var(--text); opacity: .92; }}
  .card p {{ line-height: 1.45; font-size: .88rem; }}
  .label {{
    display: block; font-family: ui-monospace, "SF Mono", "Roboto Mono", monospace; font-size: .68rem;
    text-transform: uppercase; letter-spacing: .06em; color: var(--text-muted); margin-bottom: 2px;
  }}
  .card ul {{ margin: 4px 0 10px; padding-left: 18px; font-size: .86rem; }}
  .card li {{ margin-bottom: 3px; }}
  .kpis {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }}
  .kpi {{
    font-size: .7rem; background: var(--surface-2); border: 1px solid var(--border);
    padding: 2px 8px; border-radius: 4px; color: var(--text-muted);
  }}
  .foot {{
    margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--border);
    display: flex; justify-content: space-between; font-size: .72rem; color: var(--text-muted);
    font-variant-numeric: tabular-nums;
  }}
  .foot a {{ color: var(--accent); text-decoration: none; }}
  .foot a:hover {{ text-decoration: underline; }}
  .empty {{ padding: 48px; color: var(--text-muted); grid-column: 1 / -1; text-align: center; }}
  .caveat {{ padding: 0 32px 28px; font-size: .78rem; color: var(--text-muted); max-width: 860px; line-height: 1.5; }}
  a:focus-visible, button:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
  @media (prefers-reduced-motion: reduce) {{ * {{ animation: none !important; transition: none !important; }} }}
</style></head>
<body>
<header>
  <span class="eyebrow">War Room · Concorrência</span>
  <h1>{config.get('marca', '')}</h1>
  <p>Gerado em {meta['data']} · cadência configurada: {config.get('cadencia_sugerida_horas')}h ·
     {len(alertas_rodada)} alerta(s) nesta rodada</p>
</header>
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
