#!/usr/bin/env python3
"""
Compila o desempenho do META ADS na mesma lógica da aba GA4 — funil, criativos,
diagnóstico e medidas a tomar — a partir de DUAS fontes possíveis, que este
script mantém explicitamente separadas porque têm status de confiança diferente:

  FONTE A — "GA4 (lado do site)": REAL e disponível hoje. As campanhas do Meta
    aparecem na GA4 via UTM (`source: Facebook`), com sessões, engajamento,
    carrinho, checkout, compras e receita. É medido de verdade, mas **não tem
    gasto, impressão, clique, CTR, CPM nem criativo** — a GA4 não vê o lado da
    plataforma de anúncio.

  FONTE B — "Meta Ads (lado da plataforma)": traz gasto/impressões/cliques/CTR/
    CPM/frequência e a imagem do criativo. Requer o conector `facebook` do
    Windsor.ai conectado — que nesta integração está **DESCONECTADO** (ver
    references/fontes-e-limitacoes.md). Enquanto estiver assim, passe
    `--simulado` para deixar isso gritante no relatório.

O script NUNCA soma métrica de A com métrica de B como se fossem a mesma coisa,
e NUNCA calcula ROAS de plataforma a partir de receita de GA4 sem avisar que são
janelas de atribuição diferentes.

Uso (só com o que é real hoje):
    python meta_ads_performance.py --ga4-campanhas examples/ga4-real/ga4-campanhas.json \
        --out ../outputs/meta-ads.json

Uso (com o lado da plataforma, quando o conector estiver ligado):
    python meta_ads_performance.py --ga4-campanhas ga4-campanhas.json \
        --plataforma meta-insights.json --criativos criativos.json \
        --out ../outputs/meta-ads.json
"""
import argparse
import re
import statistics
import sys

from apify_common import load_json, save_json

# marcas de origem que indicam Meta no campo source da GA4
FONTES_META = ("facebook", "instagram", "ig", "fb", "meta")


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _div(a, b):
    return (a / b) if (isinstance(a, (int, float)) and isinstance(b, (int, float)) and b) else None


def _linhas(path):
    d = load_json(path, None) if path else None
    if d is None:
        return []
    if isinstance(d, dict):
        return d.get("result") or d.get("registros") or []
    return d if isinstance(d, list) else []


def _e_meta(source, medium):
    s = (source or "").strip().lower()
    m = (medium or "").strip().lower()
    if any(f == s or f in s for f in FONTES_META):
        # referral de facebook.com é tráfego orgânico/compartilhado, não anúncio
        return m in ("cpc", "ppc", "paid", "paidsocial", "paid_social", "social") or m.startswith("cpc")
    return False


def _limpar_nome(nome):
    """Os nomes de campanha da conta vêm com emoji e marcações de padronização
    (ex.: '🟩 - [[Conv]] - [Colágeno] - Carrossel'). Extrai objetivo, produto e
    formato quando o padrão existir — sem inventar quando não existir."""
    bruto = (nome or "").replace("+", " ").strip()
    limpo = re.sub(r"^[^\w\[]+", "", bruto).strip(" -")
    objetivo = produto = formato = None
    tags = re.findall(r"\[\[?([^\]]+?)\]?\]", bruto)
    if tags:
        objetivo = tags[0].strip()
        if len(tags) > 1:
            produto = tags[1].strip()
        if len(tags) > 2:
            formato = tags[2].strip()
    # o que sobra depois do último ']' costuma ser o formato/variação
    resto = bruto.split("]")[-1].strip(" -")
    if resto and not formato:
        formato = resto
    return {"nome": bruto, "nome_limpo": limpo or bruto,
            "objetivo": objetivo, "produto": produto, "formato": formato}


def montar_lado_ga4(campanhas):
    """Desempenho das campanhas Meta pelo lado do site (GA4). Dado REAL."""
    linhas = []
    for c in campanhas:
        if not _e_meta(c.get("source"), c.get("medium")):
            continue
        s = _num(c.get("sessions"))
        compras = _num(c.get("ecommerce_purchases"))
        receita = _num(c.get("purchase_revenue"))
        meta_info = _limpar_nome(c.get("campaign"))
        linhas.append({
            **meta_info,
            "source": c.get("source"), "medium": c.get("medium"),
            "sessions": s, "engagement_rate": _num(c.get("engagement_rate")),
            "add_to_carts": _num(c.get("add_to_carts")), "checkouts": _num(c.get("checkouts")),
            "compras": compras, "receita": receita,
            "tx_carrinho": _div(_num(c.get("add_to_carts")), s),
            "tx_checkout_p_carrinho": _div(_num(c.get("checkouts")), _num(c.get("add_to_carts"))),
            "tx_compra_p_checkout": _div(compras, _num(c.get("checkouts"))),
            "tx_conversao": _div(compras, s),
            "receita_por_sessao": _div(receita, s),
            "ticket_medio": _div(receita, compras),
        })
    linhas.sort(key=lambda l: -(l["sessions"] or 0))
    return linhas


def montar_lado_plataforma(insights, criativos):
    """Lado da plataforma: gasto/impressões/cliques/CTR/CPM + criativo. Só existe
    se o conector estiver ligado (ou se vier de fixture marcada como simulada)."""
    mapa_criativo = {}
    for c in (criativos or {}).items() if isinstance(criativos, dict) else []:
        chave, val = c
        if not chave.startswith("_"):
            mapa_criativo[chave] = val
    linhas = []
    for r in insights:
        nome = r.get("campaign_name") or r.get("campaign") or r.get("ad_name") or "(sem nome)"
        gasto = _num(r.get("spend"))
        impr = _num(r.get("impressions"))
        cliques = _num(r.get("clicks"))
        compras_plat = _num(r.get("purchases")) or _num(r.get("conversions"))
        receita_plat = _num(r.get("purchase_value")) or _num(r.get("conversions_value"))
        crea = mapa_criativo.get(r.get("ad_id")) or mapa_criativo.get(nome) or {}
        linhas.append({
            **_limpar_nome(nome),
            "ad_id": r.get("ad_id"), "adset": r.get("adset_name"),
            "status": r.get("status") or r.get("effective_status"),
            "gasto": gasto, "impressions": impr, "clicks": cliques,
            "ctr": _div(cliques, impr), "cpm": (_div(gasto, impr) * 1000) if _div(gasto, impr) else None,
            "cpc": _div(gasto, cliques), "frequencia": _num(r.get("frequency")),
            "compras_plataforma": compras_plat, "receita_plataforma": receita_plat,
            "roas_plataforma": _div(receita_plat, gasto),
            "cpa_plataforma": _div(gasto, compras_plat),
            "criativo_imagem": crea.get("imagem_url") or r.get("creative_thumbnail_url"),
            "criativo_titulo": crea.get("titulo") or r.get("creative_title"),
            "criativo_corpo": crea.get("corpo") or r.get("creative_body"),
            "criativo_formato": crea.get("formato"),
            "criativo_url": crea.get("url_anuncio") or r.get("ad_permalink"),
        })
    linhas.sort(key=lambda l: -(l["gasto"] or 0))
    return linhas


def montar_funil(lado_ga4):
    """Funil agregado das campanhas Meta, pelo lado do site."""
    tot = lambda k: sum((c.get(k) or 0) for c in lado_ga4)
    sess, cart, chk, comp = tot("sessions"), tot("add_to_carts"), tot("checkouts"), tot("compras")
    etapas = [
        ("Sessões do Meta", sess, "tráfego que chegou pelas campanhas Meta (UTM)"),
        ("Add ao carrinho", cart, "add_to_cart"),
        ("Checkout", chk, "begin_checkout"),
        ("Compra", comp, "purchase"),
    ]
    out, anterior = [], None
    for nome, val, desc in etapas:
        out.append({
            "nome": nome, "valor": val, "desc": desc,
            "pct_do_topo": _div(val, sess),
            "pct_da_anterior": _div(val, anterior) if anterior is not None else None,
            "perda_abs": (anterior - val) if anterior is not None else None,
        })
        anterior = val
    cands = [e for e in out if e["pct_da_anterior"] is not None]
    if cands:
        min(cands, key=lambda e: e["pct_da_anterior"])["maior_vazamento"] = True
    return out


def montar_kpis(lado_ga4, lado_plataforma):
    tot = lambda lst, k: sum((x.get(k) or 0) for x in lst)
    sess = tot(lado_ga4, "sessions")
    comp = tot(lado_ga4, "compras")
    rec = tot(lado_ga4, "receita")
    gasto = tot(lado_plataforma, "gasto") if lado_plataforma else None
    return {
        "campanhas": len(lado_ga4),
        "sessions": sess, "compras": comp, "receita": rec,
        "tx_conversao": _div(comp, sess), "ticket_medio": _div(rec, comp),
        "receita_por_sessao": _div(rec, sess),
        "engajamento_medio": (statistics.mean([c["engagement_rate"] for c in lado_ga4
                                                if c["engagement_rate"] is not None])
                               if any(c["engagement_rate"] is not None for c in lado_ga4) else None),
        "gasto_plataforma": gasto or None,
        "impressoes_plataforma": (tot(lado_plataforma, "impressions") or None) if lado_plataforma else None,
        "cliques_plataforma": (tot(lado_plataforma, "clicks") or None) if lado_plataforma else None,
        # ROAS cruzando gasto da plataforma com receita da GA4 — janelas de
        # atribuição DIFERENTES; só é calculado com o aviso que acompanha na aba.
        "roas_cruzado": _div(rec, gasto) if gasto else None,
    }


def montar_diagnostico(kpis, lado_ga4, funil, tem_plataforma):
    achados = []
    vaz = next((e for e in funil if e.get("maior_vazamento")), None)
    if vaz and vaz["pct_da_anterior"] is not None:
        achados.append({
            "nivel": "alta", "titulo": f"Maior vazamento do funil Meta: {vaz['nome']}",
            "detalhe": (f"Só {vaz['pct_da_anterior'] * 100:.1f}% da etapa anterior chega em "
                         f"'{vaz['nome']}' ({vaz['valor']:,} de "
                         f"{vaz['valor'] + (vaz['perda_abs'] or 0):,})."),
        })

    # campanhas com volume e zero compra
    zeradas = [c for c in lado_ga4 if (c["sessions"] or 0) >= 100 and (c["compras"] or 0) == 0]
    if zeradas:
        top = sorted(zeradas, key=lambda c: -(c["sessions"] or 0))[:4]
        achados.append({
            "nivel": "alta",
            "titulo": f"{len(zeradas)} campanha(s) Meta com tráfego e nenhuma compra",
            "detalhe": ("Maiores: " + "; ".join(
                f"{c['nome_limpo']} ({c['sessions']:,} sessões, engaj. "
                f"{(c['engagement_rate'] or 0) * 100:.1f}%)" for c in top)
                + ". Ordene por sessão desperdiçada, não por número de campanhas."),
        })

    # engajamento muito baixo = descasamento criativo/página
    baixas = [c for c in lado_ga4
              if (c["sessions"] or 0) >= 100 and (c["engagement_rate"] or 1) < 0.20]
    if baixas:
        achados.append({
            "nivel": "alta",
            "titulo": f"{len(baixas)} campanha(s) com engajamento abaixo de 20%",
            "detalhe": ("Sinal clássico de clique sem intenção — criativo prometendo algo que a página "
                         "não entrega, ou público frio recebendo oferta de fundo de funil. "
                         + "; ".join(f"{c['nome_limpo']} ({(c['engagement_rate'] or 0) * 100:.1f}%)"
                                      for c in sorted(baixas, key=lambda c: c["engagement_rate"] or 0)[:4])),
        })

    # objetivo tráfego convertendo pior que conversão (o padrão de nomenclatura permite ver)
    por_obj = {}
    for c in lado_ga4:
        if c.get("objetivo"):
            por_obj.setdefault(c["objetivo"].lower(), []).append(c)
    if len(por_obj) > 1:
        resumo = []
        for obj, lst in por_obj.items():
            s = sum(x["sessions"] or 0 for x in lst)
            cp = sum(x["compras"] or 0 for x in lst)
            resumo.append((obj, s, cp, _div(cp, s)))
        resumo.sort(key=lambda t: -(t[1] or 0))
        achados.append({
            "nivel": "media", "titulo": "Comparação por objetivo de campanha",
            "detalhe": " · ".join(
                f"{o}: {s:,} sess → {cp} compra(s)"
                + (f" ({tx * 100:.2f}%)" if tx is not None else "") for o, s, cp, tx in resumo)
            + ". Verba em objetivo de tráfego que não converte é candidata a realocação.",
        })

    if not tem_plataforma:
        achados.append({
            "nivel": "media", "titulo": "Sem o lado da plataforma: falta gasto, CTR e criativo",
            "detalhe": ("Estes números vêm da GA4 (lado do site) e são reais, mas não incluem gasto, "
                         "impressões, cliques, CTR, CPM nem a imagem do criativo — a GA4 não vê isso. "
                         "Sem gasto não há ROAS nem CPA de plataforma. Conecte o conector `facebook` no "
                         "Windsor.ai para completar."),
        })
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    achados.sort(key=lambda a: ordem.get(a["nivel"], 9))
    return achados


def montar_medidas(kpis, lado_ga4, funil, tem_plataforma):
    """Medidas a tomar — cada uma amarrada a um número observado e a que meta ela
    move. Ação de escrita (pausar, mudar verba) SEMPRE exige autorização
    explícita: aqui só se recomenda, nunca se executa."""
    medidas = []
    zeradas = [c for c in lado_ga4 if (c["sessions"] or 0) >= 100 and (c["compras"] or 0) == 0]
    desperdicio = sum(c["sessions"] or 0 for c in zeradas)
    if zeradas:
        medidas.append({
            "prioridade": 1, "esforco": "baixo", "impacto": "alto",
            "acao": "Auditar rastreamento das campanhas sem compra antes de mexer em verba",
            "porque": (f"{len(zeradas)} campanha(s) somam {desperdicio:,} sessões e zero compra. "
                        "Volume alto com zero conversão costuma ser tag/UTM/atribuição, não público ruim — "
                        "cortar verba antes de checar pode matar campanha que na verdade converte."),
            "como": ("Conferir se o pixel dispara purchase nessas landing pages, se a UTM não está "
                      "sobrescrevendo o canal, e comparar com o relatório da própria plataforma."),
            "meta_afetada": "Unidades vendidas / Faturamento",
        })
    baixas = [c for c in lado_ga4 if (c["sessions"] or 0) >= 100 and (c["engagement_rate"] or 1) < 0.20]
    if baixas:
        medidas.append({
            "prioridade": 2, "esforco": "médio", "impacto": "alto",
            "acao": "Realinhar criativo × página de destino nas campanhas de engajamento baixo",
            "porque": (f"{len(baixas)} campanha(s) com menos de 20% de sessões engajadas: o clique acontece "
                        "mas a pessoa não reconhece a oferta na página."),
            "como": ("Fazer o criativo e a dobra da página falarem a MESMA promessa (mesmo produto, mesmo "
                      "preço, mesma imagem). Testar levar direto para a página do produto em vez do catálogo."),
            "meta_afetada": "Taxa de conversão",
        })
    vaz = next((e for e in funil if e.get("maior_vazamento")), None)
    if vaz:
        medidas.append({
            "prioridade": 3, "esforco": "médio", "impacto": "alto",
            "acao": f"Atacar a etapa '{vaz['nome']}' do funil Meta",
            "porque": (f"É onde a passagem é a menor ({(vaz['pct_da_anterior'] or 0) * 100:.1f}%), "
                        f"com {vaz['perda_abs']:,} pessoas perdidas. Corrigir aqui rende mais que trazer "
                        "tráfego novo."),
            "como": ("Se for checkout: reduzir campos, mostrar frete/prazo antes, oferecer PIX. "
                      "Se for carrinho: prova social e escassez na página do produto. "
                      "Rodar remarketing só para quem chegou nessa etapa."),
            "meta_afetada": "Unidades vendidas / Faturamento",
        })
    por_obj = {}
    for c in lado_ga4:
        if c.get("objetivo"):
            por_obj.setdefault(c["objetivo"].lower(), []).append(c)
    trafego = [k for k in por_obj if "tráfego" in k or "trafego" in k or "traffic" in k]
    if trafego:
        s = sum(x["sessions"] or 0 for k in trafego for x in por_obj[k])
        cp = sum(x["compras"] or 0 for k in trafego for x in por_obj[k])
        if s >= 200 and cp == 0:
            medidas.append({
                "prioridade": 4, "esforco": "baixo", "impacto": "médio",
                "acao": "Reavaliar as campanhas com objetivo de tráfego",
                "porque": f"Objetivo de tráfego somou {s:,} sessões e {cp} compra(s) no período.",
                "como": ("Tráfego serve para topo de funil e aquecimento de público — se o KPI cobrado é "
                          "venda, migrar verba para objetivo de conversão e usar tráfego só para alimentar "
                          "remarketing, com meta própria (custo por sessão engajada)."),
                "meta_afetada": "Faturamento",
            })
    if not tem_plataforma:
        medidas.append({
            "prioridade": 5, "esforco": "baixo", "impacto": "alto",
            "acao": "Conectar o conector `facebook` no Windsor.ai",
            "porque": ("Sem o lado da plataforma não há gasto, CTR, CPM, frequência nem imagem de criativo — "
                        "ou seja, não há como calcular ROAS/CPA reais nem avaliar fadiga de criativo."),
            "como": ("Autorizar o conector e rodar meta_ads_performance.py com --plataforma e --criativos. "
                      "Ver references/fontes-e-limitacoes.md para o histórico dessa pendência."),
            "meta_afetada": "todas (habilita a medição)",
        })
    medidas.sort(key=lambda m: m["prioridade"])
    return medidas


def main():
    ap = argparse.ArgumentParser(description="Desempenho do Meta Ads (lado GA4 + lado plataforma).")
    ap.add_argument("--ga4-campanhas", help="get_data da GA4 por campaign/source/medium (dado REAL)")
    ap.add_argument("--plataforma", help="insights do Meta Ads (gasto/impressões/cliques/criativo)")
    ap.add_argument("--criativos", help='JSON {ad_id|campanha: {imagem_url, titulo, corpo, formato, url_anuncio}}')
    ap.add_argument("--simulado", action="store_true",
                     help="marca o lado da plataforma como SIMULADO (use sempre que --plataforma não vier "
                          "de coleta real com o conector conectado)")
    ap.add_argument("--out", default="meta-ads.json")
    ap.add_argument("--periodo", default="últimos 30 dias")
    args = ap.parse_args()

    campanhas = _linhas(args.ga4_campanhas)
    if not campanhas and not args.plataforma:
        print("ERRO: nada para compilar — passe --ga4-campanhas (dado real da GA4) e/ou --plataforma.",
              file=sys.stderr)
        sys.exit(1)

    lado_ga4 = montar_lado_ga4(campanhas)
    insights = _linhas(args.plataforma)
    criativos = load_json(args.criativos, {}) if args.criativos else {}
    lado_plataforma = montar_lado_plataforma(insights, criativos) if insights else []
    tem_plataforma = bool(lado_plataforma)

    funil = montar_funil(lado_ga4)
    kpis = montar_kpis(lado_ga4, lado_plataforma)

    saida = {
        "periodo": args.periodo,
        "kpis": kpis, "funil": funil,
        "campanhas_ga4": lado_ga4,
        "campanhas_plataforma": lado_plataforma,
        "tem_plataforma": tem_plataforma,
        "plataforma_simulada": bool(args.simulado and tem_plataforma),
        "diagnostico": montar_diagnostico(kpis, lado_ga4, funil, tem_plataforma),
        "medidas": montar_medidas(kpis, lado_ga4, funil, tem_plataforma),
    }
    save_json(args.out, saida)

    print(f"OK -> {args.out}", file=sys.stderr)
    print(f"  {len(lado_ga4)} campanha(s) Meta identificada(s) via UTM na GA4 (REAL): "
          f"{kpis['sessions']:,} sessões → {kpis['compras']} compra(s)", file=sys.stderr)
    if tem_plataforma:
        marca = " [SIMULADO]" if args.simulado else " [REAL]"
        print(f"  {len(lado_plataforma)} linha(s) do lado da plataforma{marca}", file=sys.stderr)
    else:
        print("  lado da plataforma AUSENTE — sem gasto/CTR/criativo (conector facebook desconectado)",
              file=sys.stderr)
    for a in saida["diagnostico"][:4]:
        print(f"  [{a['nivel']}] {a['titulo']}", file=sys.stderr)


if __name__ == "__main__":
    main()
