#!/usr/bin/env python3
"""
Compila os KPIs da GA4 numa leitura de GESTOR DE TRÁFEGO — funil de compra,
jornada por canal, device, landing page e série temporal — e exporta o JSON que
alimenta a aba "GA4 · Jornada" do war_room.py.

*** STATUS: VERIFICADO COM DADO REAL *** — os campos abaixo foram testados ao
vivo na propriedade GA4 da Joie (connector `googleanalytics4`, conta 304174518)
via MCP do Windsor.ai. Achados técnicos confirmados:
  · A GA4 aceita no MÁXIMO 10 métricas por chamada `get_data` (erro explícito:
    "GA4 allows at most 10 metrics per request"). Por isso a coleta é dividida
    em blocos — este script NÃO chama a API sozinho; quem coleta é o agente
    Claude, que grava cada bloco num JSON e passa aqui.
  · O funil de e-commerce da conta existe de verdade e é medido:
    item_view_events → add_to_carts → checkouts → ecommerce_purchases.
    A conta tem inclusive um funil nomeado
    (`conversions_funil_jornada_de_compra___ecommerce`).
  · `bounce_rate` e `engagement_rate` vêm como fração (0-1), não porcentagem.

O que este script FAZ (e o que deliberadamente não faz):
  · Calcula taxas de passagem entre etapas do funil e aponta onde está o maior
    vazamento — cálculo aritmético sobre dado medido, não estimativa.
  · Classifica canais em quadrantes (volume × eficiência) usando as MEDIANAS do
    próprio período como corte — nunca um benchmark de mercado inventado.
  · NÃO projeta receita futura, NÃO inventa benchmark de mercado, e quando uma
    métrica não vem na coleta ela aparece como "n/d" em vez de zero.

Uso (os JSONs de entrada são os retornos crus de get_data, um por bloco):
    python ga4_jornada.py --overview ga4-overview.json --funil ga4-funil.json \
        --canais ga4-canais.json --devices ga4-devices.json \
        --landing ga4-landing.json --serie ga4-serie.json \
        --out ../outputs/ga4-jornada.json
"""
import argparse
import json
import os
import statistics
import sys

from apify_common import load_json, save_json


def _linhas(path):
    """Aceita tanto {"result": [...]} (retorno cru do Windsor) quanto uma lista."""
    if not path:
        return []
    dados = load_json(path, None)
    if dados is None:
        return []
    if isinstance(dados, dict):
        return dados.get("result") or dados.get("registros") or []
    return dados if isinstance(dados, list) else []


def _um(path):
    linhas = _linhas(path)
    return linhas[0] if linhas else {}


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _pct(parte, todo):
    """Taxa de passagem — None quando não dá para calcular (nunca 0 por falta de dado)."""
    if not isinstance(parte, (int, float)) or not isinstance(todo, (int, float)) or not todo:
        return None
    return parte / todo


def montar_funil(overview, funil):
    """Monta as etapas do funil de compra com a taxa de passagem de cada uma e
    marca a etapa com o MAIOR vazamento relativo — o ponto onde um gestor de
    tráfego age primeiro."""
    sessions = _num(overview.get("sessions"))
    etapas = [
        {"chave": "sessions", "nome": "Sessões", "valor": sessions,
         "desc": "tráfego que entrou no site"},
        {"chave": "item_view_events", "nome": "Viu produto", "valor": _num(funil.get("item_view_events")),
         "desc": "visualizações de item (view_item)"},
        {"chave": "add_to_carts", "nome": "Add ao carrinho", "valor": _num(funil.get("add_to_carts")),
         "desc": "add_to_cart"},
        {"chave": "checkouts", "nome": "Checkout", "valor": _num(funil.get("checkouts")),
         "desc": "begin_checkout"},
        {"chave": "ecommerce_purchases", "nome": "Compra", "valor": _num(funil.get("ecommerce_purchases")),
         "desc": "purchase"},
    ]
    topo = next((e["valor"] for e in etapas if e["valor"]), None)
    anterior = None
    for e in etapas:
        e["pct_do_topo"] = _pct(e["valor"], topo)
        e["pct_da_anterior"] = _pct(e["valor"], anterior) if anterior is not None else None
        e["perda_abs"] = (anterior - e["valor"]) if (isinstance(anterior, (int, float))
                                                     and isinstance(e["valor"], (int, float))) else None
        anterior = e["valor"] if isinstance(e["valor"], (int, float)) else anterior

    # maior vazamento = menor taxa de passagem entre etapas consecutivas
    candidatos = [e for e in etapas if e["pct_da_anterior"] is not None]
    if candidatos:
        pior = min(candidatos, key=lambda e: e["pct_da_anterior"])
        pior["maior_vazamento"] = True
    return etapas


def _quadrante(sessions, taxa, med_sessions, med_taxa):
    """Quadrante volume × eficiência, com corte na MEDIANA do próprio período
    (não em benchmark de mercado, que seria invenção)."""
    if sessions is None or taxa is None:
        return "sem dado"
    alto_vol = sessions >= med_sessions
    alta_ef = taxa >= med_taxa
    if alto_vol and alta_ef:
        return "escalar"          # volume e converte:投 mais verba
    if alto_vol and not alta_ef:
        return "corrigir"         # volume mas não converte: maior perda absoluta
    if not alto_vol and alta_ef:
        return "testar aumento"   # converte mas é pequeno: cabe teste de verba
    return "revisar ou cortar"


def montar_canais(canais):
    """Enriquece cada canal com taxa de conversão de sessão, receita por sessão,
    ticket médio e o quadrante de decisão."""
    linhas = []
    for c in canais:
        s = _num(c.get("sessions"))
        compras = _num(c.get("ecommerce_purchases"))
        receita = _num(c.get("purchase_revenue"))
        linhas.append({
            "canal": c.get("default_channel_group") or c.get("channel") or "(sem canal)",
            "sessions": s,
            "engaged_sessions": _num(c.get("engaged_sessions")),
            "engagement_rate": _num(c.get("engagement_rate")),
            "add_to_carts": _num(c.get("add_to_carts")),
            "checkouts": _num(c.get("checkouts")),
            "compras": compras,
            "receita": receita,
            "tx_conversao": _pct(compras, s),
            "receita_por_sessao": (receita / s) if (isinstance(receita, (int, float)) and s) else None,
            "ticket_medio": (receita / compras) if (isinstance(receita, (int, float))
                                                     and isinstance(compras, (int, float)) and compras) else None,
            "tx_carrinho": _pct(_num(c.get("add_to_carts")), s),
            "tx_checkout_p_carrinho": _pct(_num(c.get("checkouts")), _num(c.get("add_to_carts"))),
            "tx_compra_p_checkout": _pct(compras, _num(c.get("checkouts"))),
        })
    vols = [l["sessions"] for l in linhas if l["sessions"]]
    txs = [l["tx_conversao"] for l in linhas if l["tx_conversao"] is not None]
    med_v = statistics.median(vols) if vols else 0
    med_t = statistics.median(txs) if txs else 0
    for l in linhas:
        l["quadrante"] = _quadrante(l["sessions"], l["tx_conversao"], med_v, med_t)
    linhas.sort(key=lambda l: -(l["receita"] or 0))
    return linhas, {"mediana_sessoes": med_v, "mediana_tx_conversao": med_t}


def montar_devices(devices):
    linhas = []
    for d in devices:
        s = _num(d.get("sessions"))
        compras = _num(d.get("ecommerce_purchases"))
        receita = _num(d.get("purchase_revenue"))
        linhas.append({
            "device": d.get("devicecategory") or "(sem device)",
            "sessions": s, "engagement_rate": _num(d.get("engagement_rate")),
            "add_to_carts": _num(d.get("add_to_carts")), "checkouts": _num(d.get("checkouts")),
            "compras": compras, "receita": receita,
            "tx_conversao": _pct(compras, s),
            "receita_por_sessao": (receita / s) if (isinstance(receita, (int, float)) and s) else None,
        })
    linhas.sort(key=lambda l: -(l["sessions"] or 0))
    return linhas


def montar_landing(landing, limiar_sessions=100):
    """Landing pages com sessão suficiente para a taxa significar algo. Marca as
    que têm tráfego alto e conversão zerada — a lista de correção prioritária."""
    linhas = []
    for p in landing:
        s = _num(p.get("sessions"))
        if s is None or s < limiar_sessions:
            continue
        compras = _num(p.get("ecommerce_purchases"))
        receita = _num(p.get("purchase_revenue"))
        linhas.append({
            "pagina": p.get("landing_page") or "(sem página)",
            "sessions": s,
            "engagement_rate": _num(p.get("engagement_rate")),
            "bounce_rate": _num(p.get("bounce_rate")),
            "add_to_carts": _num(p.get("add_to_carts")),
            "compras": compras, "receita": receita,
            "tx_conversao": _pct(compras, s),
            "tx_carrinho": _pct(_num(p.get("add_to_carts")), s),
            "vazamento": bool(s and compras == 0),
        })
    linhas.sort(key=lambda l: -(l["sessions"] or 0))
    return linhas


def montar_serie(serie):
    linhas = []
    for d in serie:
        s = _num(d.get("sessions"))
        compras = _num(d.get("ecommerce_purchases"))
        linhas.append({
            "data": d.get("date"), "sessions": s,
            "add_to_carts": _num(d.get("add_to_carts")), "checkouts": _num(d.get("checkouts")),
            "compras": compras, "receita": _num(d.get("purchase_revenue")),
            "engagement_rate": _num(d.get("engagement_rate")),
            "tx_conversao": _pct(compras, s),
        })
    linhas.sort(key=lambda l: l["data"] or "")
    return linhas


def montar_kpis(overview, funil, serie_linhas):
    """Cartões de topo — o que um gestor de tráfego olha primeiro."""
    sessions = _num(overview.get("sessions"))
    usuarios = _num(overview.get("totalusers"))
    novos = _num(overview.get("newusers"))
    compras = _num(funil.get("ecommerce_purchases"))
    receita = _num(funil.get("purchase_revenue"))
    compradores = _num(funil.get("total_purchasers"))
    primeira_compra = _num(funil.get("first_time_purchasers"))
    return {
        "sessions": sessions,
        "usuarios": usuarios,
        "novos_usuarios": novos,
        "pct_novos": _pct(novos, usuarios),
        "engagement_rate": _num(overview.get("engagement_rate")),
        "bounce_rate": _num(overview.get("bounce_rate")),
        "duracao_media_sessao": _num(overview.get("average_session_duration")),
        "pageviews": _num(overview.get("screen_page_views")),
        "pageviews_por_sessao": (_num(overview.get("screen_page_views")) / sessions)
                                 if (_num(overview.get("screen_page_views")) and sessions) else None,
        "compras": compras,
        "receita": receita,
        "tx_conversao": _pct(compras, sessions),
        "ticket_medio": (receita / compras) if (isinstance(receita, (int, float))
                                                 and isinstance(compras, (int, float)) and compras) else None,
        "receita_por_sessao": (receita / sessions) if (isinstance(receita, (int, float)) and sessions) else None,
        "compradores": compradores,
        "primeira_compra": primeira_compra,
        "pct_primeira_compra": _pct(primeira_compra, compradores),
        "dias_na_serie": len(serie_linhas),
    }


def montar_campanhas(campanhas, criativos=None):
    """Desempenho por campanha (dado REAL da GA4) com o criativo anexado quando
    houver — a imagem do criativo NÃO vem da GA4, vem do Meta/Google (ou de um
    mapa manual); sem esse arquivo a linha aparece sem imagem, nunca com
    placeholder passando por criativo real."""
    criativos = {k: v for k, v in (criativos or {}).items() if not k.startswith("_")}
    linhas = []
    for c in campanhas:
        nome = c.get("campaign") or "(sem campanha)"
        s = _num(c.get("sessions"))
        compras = _num(c.get("ecommerce_purchases"))
        receita = _num(c.get("purchase_revenue"))
        crea = criativos.get(nome) or {}
        linhas.append({
            "campanha": nome, "source": c.get("source"), "medium": c.get("medium"),
            "pago": (c.get("medium") or "").lower() in ("cpc", "ppc", "paid", "paidsocial", "display"),
            "sessions": s, "engagement_rate": _num(c.get("engagement_rate")),
            "add_to_carts": _num(c.get("add_to_carts")), "checkouts": _num(c.get("checkouts")),
            "compras": compras, "receita": receita,
            "tx_conversao": _pct(compras, s),
            "tx_carrinho": _pct(_num(c.get("add_to_carts")), s),
            "receita_por_sessao": (receita / s) if (isinstance(receita, (int, float)) and s) else None,
            "ticket_medio": (receita / compras) if (isinstance(receita, (int, float))
                                                     and isinstance(compras, (int, float)) and compras) else None,
            "criativo_imagem": crea.get("imagem_url"),
            "criativo_titulo": crea.get("titulo"),
            "criativo_corpo": crea.get("corpo"),
            "criativo_formato": crea.get("formato"),
            "criativo_url": crea.get("url_anuncio"),
        })
    linhas.sort(key=lambda l: -(l["receita"] or 0))
    return linhas


def montar_medidas(kpis, etapas, canais, landings, devices):
    """Medidas a tomar — cada uma amarrada a um número medido e à meta que move.
    Recomendação, nunca execução: qualquer ação de escrita (verba, campanha,
    preço) exige autorização explícita do usuário."""
    medidas = []
    vaz = next((e for e in etapas if e.get("maior_vazamento")), None)
    if vaz and vaz["pct_da_anterior"] is not None:
        nome = (vaz["nome"] or "").lower()
        if "checkout" in nome:
            como = ("Reduzir campos do checkout, mostrar frete e prazo ANTES da última etapa, oferecer PIX "
                     "com desconto, salvar carrinho e disparar recuperação em 1h/24h. Medir novamente a "
                     "passagem carrinho→checkout depois de cada mudança, uma por vez.")
        elif "carrinho" in nome:
            como = ("Prova social e garantia na página do produto, frete calculado na própria página, "
                     "kit/combo para elevar percepção de valor. Testar botão fixo de compra no mobile.")
        elif "produto" in nome:
            como = ("Melhorar a navegação da home e das categorias para o produto certo aparecer em menos "
                     "cliques; revisar busca interna (a página /busca está com rejeição alta).")
        else:
            como = "Instrumentar a etapa e testar uma hipótese por vez, medindo a passagem depois de cada uma."
        medidas.append({
            "prioridade": 1, "esforco": "médio", "impacto": "alto",
            "acao": f"Corrigir a etapa '{vaz['nome']}' — maior vazamento do funil",
            "porque": (f"Só {vaz['pct_da_anterior'] * 100:.1f}% da etapa anterior chega em "
                        f"'{vaz['nome']}': {vaz['perda_abs']:,} pessoas perdidas no período. "
                        "Ganho aqui é mais barato que comprar tráfego novo."),
            "como": como, "meta_afetada": "Unidades vendidas / Faturamento",
        })

    zerados = [c for c in canais if c["sessions"] and c["sessions"] >= 500 and (c["compras"] or 0) == 0]
    if zerados:
        medidas.append({
            "prioridade": 2, "esforco": "baixo", "impacto": "alto",
            "acao": "Auditar rastreamento dos canais com volume e zero compra",
            "porque": ("; ".join(f"{c['canal']}: {c['sessions']:,} sessões, {c['compras']} compra(s)"
                                  for c in zerados)
                        + ". Volume alto com zero conversão é sintoma de tag/atribuição antes de ser "
                          "sintoma de audiência."),
            "como": ("Validar disparo do evento purchase nessas origens, checar se a UTM não sobrescreve o "
                      "canal e comparar com o relatório da plataforma de origem antes de cortar verba."),
            "meta_afetada": "Faturamento",
        })

    vazando = [p for p in landings if p["vazamento"]]
    if vazando:
        top = sorted(vazando, key=lambda p: -(p["sessions"] or 0))[:3]
        perdidas = sum(p["sessions"] or 0 for p in vazando)
        medidas.append({
            "prioridade": 3, "esforco": "médio", "impacto": "alto",
            "acao": "Recuperar as landing pages que recebem tráfego e não vendem",
            "porque": (f"{len(vazando)} página(s) somam {perdidas:,} sessões sem nenhuma compra. Maiores: "
                        + "; ".join(f"{p['pagina']} ({p['sessions']:,})" for p in top)),
            "como": ("Ir uma a uma pela ordem de sessão perdida: conferir preço/estoque visíveis, imagem, "
                      "botão de compra acima da dobra no mobile, e se a promessa do anúncio bate com a página. "
                      "Página com muito add-to-cart e zero compra aponta problema DEPOIS do carrinho."),
            "meta_afetada": "Taxa de conversão",
        })

    # mobile pior que desktop com a maior parte do tráfego
    mob = next((d for d in devices if (d["device"] or "").lower() == "mobile"), None)
    desk = next((d for d in devices if (d["device"] or "").lower() == "desktop"), None)
    if (mob and desk and mob["tx_conversao"] is not None and desk["tx_conversao"] is not None
            and mob["sessions"] and desk["sessions"] and mob["tx_conversao"] < desk["tx_conversao"] * 0.9):
        gap = (desk["tx_conversao"] - mob["tx_conversao"]) * (mob["sessions"] or 0)
        medidas.append({
            "prioridade": 4, "esforco": "médio", "impacto": "alto",
            "acao": "Priorizar correções de mobile",
            "porque": (f"Mobile converte {mob['tx_conversao'] * 100:.2f}% contra "
                        f"{desk['tx_conversao'] * 100:.2f}% do desktop, com {mob['sessions']:,} sessões. "
                        f"Igualar as duas taxas valeria ~{gap:.0f} compra(s) no período."),
            "como": ("Medir Core Web Vitals no 4G, reduzir peso de imagem, botão de compra fixo, "
                      "checkout em uma coluna e teclado numérico nos campos de número."),
            "meta_afetada": "Taxa de conversão / Faturamento",
        })

    if kpis.get("pct_primeira_compra") is not None and kpis["pct_primeira_compra"] > 0.7:
        medidas.append({
            "prioridade": 5, "esforco": "baixo", "impacto": "médio",
            "acao": "Montar recompra para reduzir dependência de aquisição",
            "porque": (f"{kpis['pct_primeira_compra'] * 100:.0f}% dos compradores são de primeira compra: "
                        "o faturamento está apoiado em mídia paga, não em base."),
            "como": ("Fluxo de pós-compra por e-mail/WhatsApp na janela de recompra do produto (suplemento "
                      "tem ciclo previsível), com oferta de assinatura ou kit de reposição."),
            "meta_afetada": "Faturamento / Ticket médio",
        })
    medidas.sort(key=lambda m: m["prioridade"])
    return medidas


def montar_diagnostico(kpis, etapas, canais, landings, devices):
    """Leitura de gestor de tráfego: aponta os pontos de ação com o número que
    sustenta cada um. Só afirma o que sai da aritmética do dado medido."""
    achados = []

    vaz = next((e for e in etapas if e.get("maior_vazamento")), None)
    if vaz and vaz["pct_da_anterior"] is not None:
        achados.append({
            "nivel": "alta",
            "titulo": f"Maior vazamento do funil: {vaz['nome']}",
            "detalhe": (f"Só {vaz['pct_da_anterior'] * 100:.1f}% da etapa anterior chega em "
                         f"'{vaz['nome']}' ({vaz['valor']:,} de "
                         f"{vaz['valor'] + (vaz['perda_abs'] or 0):,}). É onde a correção tem o "
                         f"maior efeito absoluto no número de compras."),
        })

    # canal com muito volume e conversão zero/quase zero = dinheiro parado
    for c in canais:
        if c["sessions"] and c["sessions"] >= 500 and (c["compras"] or 0) == 0:
            achados.append({
                "nivel": "alta",
                "titulo": f"Canal '{c['canal']}' traz volume e não converte",
                "detalhe": (f"{c['sessions']:,} sessões e {c['compras']} compra(s) no período"
                             + (f", com {c['add_to_carts']:,} adições ao carrinho"
                                if c.get("add_to_carts") else "")
                             + ". Checar rastreamento de conversão desse canal antes de concluir que é "
                               "audiência ruim — volume alto com zero compra costuma ser tag/atribuição."),
            })
    # canal com engajamento muito abaixo da mediana
    txs = [c["engagement_rate"] for c in canais if c["engagement_rate"] is not None]
    if txs:
        med = statistics.median(txs)
        for c in canais:
            if (c["engagement_rate"] is not None and c["sessions"] and c["sessions"] >= 500
                    and c["engagement_rate"] < med * 0.6):
                achados.append({
                    "nivel": "media",
                    "titulo": f"Engajamento de '{c['canal']}' muito abaixo da mediana",
                    "detalhe": (f"{c['engagement_rate'] * 100:.1f}% de sessões engajadas contra mediana de "
                                 f"{med * 100:.1f}% entre os canais, sobre {c['sessions']:,} sessões. "
                                 "Sinal clássico de descasamento entre criativo/segmentação e a página de "
                                 "destino."),
                })

    # landing com tráfego e zero compra
    vazando = [p for p in landings if p["vazamento"]]
    if vazando:
        top = sorted(vazando, key=lambda p: -(p["sessions"] or 0))[:3]
        achados.append({
            "nivel": "media",
            "titulo": f"{len(vazando)} landing page(s) com tráfego e nenhuma compra",
            "detalhe": ("Maiores: " + "; ".join(
                f"{p['pagina']} ({p['sessions']:,} sessões"
                + (f", {p['add_to_carts']:,} no carrinho" if p.get("add_to_carts") else "")
                + ")" for p in top)
                + ". Priorize por sessão perdida, não por número de páginas."),
        })

    # concentração de receita em device
    if devices:
        total_rec = sum(d["receita"] or 0 for d in devices)
        if total_rec:
            lider = max(devices, key=lambda d: d["receita"] or 0)
            share = (lider["receita"] or 0) / total_rec
            pior_conv = min((d for d in devices if d["sessions"] and d["sessions"] >= 100),
                             key=lambda d: d["tx_conversao"] if d["tx_conversao"] is not None else 9,
                             default=None)
            det = f"{lider['device']} concentra {share * 100:.0f}% da receita."
            if pior_conv and pior_conv["tx_conversao"] is not None:
                det += (f" Pior conversão entre devices com volume: {pior_conv['device']} "
                        f"({pior_conv['tx_conversao'] * 100:.2f}%).")
            achados.append({"nivel": "baixa", "titulo": "Concentração por dispositivo", "detalhe": det})

    if kpis.get("pct_primeira_compra") is not None:
        achados.append({
            "nivel": "baixa",
            "titulo": "Dependência de cliente novo",
            "detalhe": (f"{kpis['pct_primeira_compra'] * 100:.0f}% dos compradores do período compraram "
                         f"pela primeira vez ({kpis.get('primeira_compra')} de {kpis.get('compradores')}). "
                         "Quanto mais alto, mais o faturamento depende de aquisição paga e menos de base."),
        })

    ordem = {"alta": 0, "media": 1, "baixa": 2}
    achados.sort(key=lambda a: ordem.get(a["nivel"], 9))
    return achados


def main():
    ap = argparse.ArgumentParser(description="Compila KPIs/funil/jornada da GA4 para o war room.")
    ap.add_argument("--overview", help="get_data com sessions/users/engagement/bounce/duração/pageviews")
    ap.add_argument("--funil", help="get_data com item_view_events/add_to_carts/checkouts/purchases/receita")
    ap.add_argument("--canais", help="get_data por default_channel_group")
    ap.add_argument("--devices", help="get_data por devicecategory")
    ap.add_argument("--landing", help="get_data por landing_page")
    ap.add_argument("--serie", help="get_data por date")
    ap.add_argument("--campanhas", help="get_data por campaign/source/medium (desempenho de campanha)")
    ap.add_argument("--criativos", help='JSON {campanha: {imagem_url, titulo, corpo, formato, url_anuncio}} '
                                         "— a imagem do criativo NÃO vem da GA4; venha do Meta/Google ou mapa manual")
    ap.add_argument("--limiar-landing-sessions", type=int, default=100)
    ap.add_argument("--out", default="ga4-jornada.json")
    ap.add_argument("--periodo", default="últimos 30 dias",
                     help="rótulo do período coletado, só para exibição honesta no dashboard")
    args = ap.parse_args()

    overview = _um(args.overview)
    funil_raw = _um(args.funil)
    if not overview and not funil_raw:
        print("ERRO: nada para compilar — passe pelo menos --overview e --funil "
              "(retornos crus de get_data no connector googleanalytics4).", file=sys.stderr)
        sys.exit(1)

    etapas = montar_funil(overview, funil_raw)
    canais, cortes = montar_canais(_linhas(args.canais))
    devices = montar_devices(_linhas(args.devices))
    landings = montar_landing(_linhas(args.landing), args.limiar_landing_sessions)
    serie = montar_serie(_linhas(args.serie))
    kpis = montar_kpis(overview, funil_raw, serie)
    diagnostico = montar_diagnostico(kpis, etapas, canais, landings, devices)
    criativos = load_json(args.criativos, {}) if args.criativos else {}
    campanhas = montar_campanhas(_linhas(args.campanhas), criativos) if args.campanhas else []
    medidas = montar_medidas(kpis, etapas, canais, landings, devices)

    saida = {
        "periodo": args.periodo,
        "kpis": kpis,
        "funil": etapas,
        "canais": canais,
        "cortes_quadrante": cortes,
        "devices": devices,
        "landing_pages": landings,
        "serie": serie,
        "campanhas": campanhas,
        "diagnostico": diagnostico,
        "medidas": medidas,
        "limiar_landing_sessions": args.limiar_landing_sessions,
    }
    save_json(args.out, saida)

    print(f"OK -> {args.out}", file=sys.stderr)
    print(f"  funil: " + " → ".join(
        f"{e['nome']} {e['valor']:,}" for e in etapas if e["valor"] is not None), file=sys.stderr)
    vaz = next((e for e in etapas if e.get("maior_vazamento")), None)
    if vaz:
        print(f"  maior vazamento: {vaz['nome']} ({vaz['pct_da_anterior'] * 100:.1f}% de passagem)",
              file=sys.stderr)
    print(f"  {len(canais)} canal(is), {len(devices)} device(s), {len(landings)} landing(s) "
          f"acima de {args.limiar_landing_sessions} sessões, {len(serie)} dia(s) na série",
          file=sys.stderr)
    for a in diagnostico[:4]:
        print(f"  [{a['nivel']}] {a['titulo']}", file=sys.stderr)


if __name__ == "__main__":
    main()
