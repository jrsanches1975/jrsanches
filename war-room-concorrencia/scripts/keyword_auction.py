#!/usr/bin/env python3
"""
Monitor de leilão por palavra-chave (Google Ads, via Windsor.ai) — quando o
desempenho de uma keyword cai, traz quem está ganhando o leilão na mesma campanha
(Auction Insight), o CPC envolvido e a estratégia de combate.

*** STATUS: VERIFICADO COM DADO REAL *** (diferente de meta_ads.py/
google_ads_transparency.py/google_trends.py, que são beta). Os campos abaixo foram
testados ao vivo na conta Google Ads da Joie via Windsor.ai (connector google_ads):
  - keyword_text, campaign, impressions, clicks, ctr, cpc, quality_score,
    search_impression_share, search_rank_lost_impression_share,
    first_page_cpc, position_estimates_top_of_page_cpc_micros
    → combinam entre si numa única chamada get_data.
  - auction_insight_domain (com date, campaign) → NÃO combina com métricas de
    performance na mesma chamada (o Google Ads recusa: "unsupported metrics" quando
    misturado com impressions/search_impression_share/etc). Por isso é sempre uma
    chamada SEPARADA, e o script cruza os dois por campanha.
  - Na conta testada, first_page_cpc e position_estimates_top_of_page_cpc_micros
    vieram NULL para o período (comum em termos de baixo volume — o Google não
    populou estimativa de lance). O script reporta isso honestamente, nunca inventa
    um valor de CPC.

Este script NÃO chama a API sozinho — quem coleta é o agente Claude, via MCP do
Windsor.ai (get_fields + get_data), que grava os dois JSONs brutos abaixo:
  --keywords-json: {"connector": "google_ads", "registros": [{date, campaign,
      keyword_text, impressions, clicks, ctr, cpc, quality_score,
      search_impression_share, search_rank_lost_impression_share, first_page_cpc,
      position_estimates_top_of_page_cpc_micros}, ...]}
  --auction-json: {"connector": "google_ads", "registros": [{date, campaign,
      auction_insight_domain}, ...]}

Uso:
    python keyword_auction.py --config config.json \
        --keywords-json keywords-7d.json --auction-json auction-7d.json \
        --history-dir ../outputs/demo-history --out ../outputs/quedas-keyword.json
"""
import argparse
import sys
from collections import defaultdict

from apify_common import load_json, norm, save_json


def carregar_registros(path):
    return load_json(path, {}).get("registros", [])


def agregar_keywords(registros):
    """Retorna {(campanha, keyword): {métricas médias/somadas}}."""
    agg = defaultdict(lambda: {
        "impressions": 0, "clicks": 0, "cpc_soma": 0.0, "cpc_n": 0,
        "qs_soma": 0.0, "qs_n": 0, "is_soma": 0.0, "is_n": 0,
        "rank_lost_soma": 0.0, "rank_lost_n": 0,
        "first_page_cpc": None, "top_of_page_cpc_micros": None,
    })
    for r in registros:
        chave = (r.get("campaign") or "(sem campanha)", r.get("keyword_text") or "(sem termo)")
        a = agg[chave]
        a["impressions"] += r.get("impressions") or 0
        a["clicks"] += r.get("clicks") or 0
        if r.get("cpc") is not None:
            a["cpc_soma"] += r["cpc"]; a["cpc_n"] += 1
        if r.get("quality_score") is not None:
            a["qs_soma"] += r["quality_score"]; a["qs_n"] += 1
        if r.get("search_impression_share") is not None:
            a["is_soma"] += r["search_impression_share"]; a["is_n"] += 1
        if r.get("search_rank_lost_impression_share") is not None:
            a["rank_lost_soma"] += r["search_rank_lost_impression_share"]; a["rank_lost_n"] += 1
        if r.get("first_page_cpc") is not None:
            a["first_page_cpc"] = r["first_page_cpc"]
        if r.get("position_estimates_top_of_page_cpc_micros") is not None:
            a["top_of_page_cpc_micros"] = r["position_estimates_top_of_page_cpc_micros"]

    resultado = {}
    for (campanha, keyword), a in agg.items():
        resultado[f"{campanha}||{keyword}"] = {
            "campanha": campanha,
            "keyword": keyword,
            "impressions": a["impressions"],
            "clicks": a["clicks"],
            "cpc_medio": (a["cpc_soma"] / a["cpc_n"]) if a["cpc_n"] else None,
            "quality_score_medio": (a["qs_soma"] / a["qs_n"]) if a["qs_n"] else None,
            "impression_share_medio": (a["is_soma"] / a["is_n"]) if a["is_n"] else None,
            "rank_lost_medio": (a["rank_lost_soma"] / a["rank_lost_n"]) if a["rank_lost_n"] else None,
            "first_page_cpc": a["first_page_cpc"],
            "top_of_page_cpc": (a["top_of_page_cpc_micros"] / 1_000_000) if a["top_of_page_cpc_micros"] else None,
        }
    return resultado


def agregar_dominios_por_campanha(registros, dominios_proprios):
    """Retorna {campanha: [(dominio, frequencia), ...]} ordenado por frequência,
    excluindo domínios próprios e entradas vazias."""
    contagem = defaultdict(lambda: defaultdict(int))
    proprios = {norm(d) for d in dominios_proprios}
    for r in registros:
        dom = (r.get("auction_insight_domain") or "").strip()
        if not dom or norm(dom) in proprios:
            continue
        contagem[r.get("campaign") or "(sem campanha)"][dom] += 1
    return {campanha: sorted(doms.items(), key=lambda kv: -kv[1]) for campanha, doms in contagem.items()}


def detectar_quedas(atual, anterior, limiares):
    quedas = []
    for chave, a in atual.items():
        b = anterior.get(chave)
        if not b:
            continue  # sem histórico prévio dessa keyword — não dá pra falar de "queda"

        delta_is = None
        if a["impression_share_medio"] is not None and b.get("impression_share_medio") is not None:
            delta_is = a["impression_share_medio"] - b["impression_share_medio"]
        delta_rank_lost = None
        if a["rank_lost_medio"] is not None and b.get("rank_lost_medio") is not None:
            delta_rank_lost = a["rank_lost_medio"] - b["rank_lost_medio"]
        delta_qs = None
        if a["quality_score_medio"] is not None and b.get("quality_score_medio") is not None:
            delta_qs = a["quality_score_medio"] - b["quality_score_medio"]

        gatilho = (
            (delta_is is not None and delta_is <= -limiares["queda_impression_share_pontos"]) or
            (delta_rank_lost is not None and delta_rank_lost >= limiares["aumento_rank_lost_pontos"]) or
            (delta_qs is not None and delta_qs <= -limiares["queda_quality_score_pontos"])
        )
        if not gatilho:
            continue

        critico = (
            (delta_is is not None and delta_is <= -2 * limiares["queda_impression_share_pontos"]) or
            (delta_rank_lost is not None and delta_rank_lost >= 2 * limiares["aumento_rank_lost_pontos"])
        )
        quedas.append({
            "campanha": a["campanha"], "keyword": a["keyword"], "nivel": "critica" if critico else "moderada",
            "impression_share_antes": b.get("impression_share_medio"), "impression_share_agora": a["impression_share_medio"],
            "rank_lost_antes": b.get("rank_lost_medio"), "rank_lost_agora": a["rank_lost_medio"],
            "quality_score_antes": b.get("quality_score_medio"), "quality_score_agora": a["quality_score_medio"],
            "cpc_medio": a["cpc_medio"], "first_page_cpc": a["first_page_cpc"], "top_of_page_cpc": a["top_of_page_cpc"],
            "impressions": a["impressions"], "clicks": a["clicks"],
        })
    return quedas


def main():
    ap = argparse.ArgumentParser(description="Monitor de leilão por palavra-chave (Google Ads, via Windsor.ai).")
    ap.add_argument("--config", required=True)
    ap.add_argument("--keywords-json", required=True)
    ap.add_argument("--auction-json", required=True)
    ap.add_argument("--history-dir", required=True)
    ap.add_argument("--out", default="quedas-keyword.json")
    ap.add_argument("--queda-impression-share-pontos", type=float, default=0.10,
                     help="queda mínima (em fração, ex 0.10 = 10 pontos percentuais) para alertar")
    ap.add_argument("--aumento-rank-lost-pontos", type=float, default=0.10)
    ap.add_argument("--queda-quality-score-pontos", type=float, default=2.0)
    ap.add_argument("--top-dominios", type=int, default=5, help="quantos domínios do leilão mostrar por keyword")
    args = ap.parse_args()

    config = load_json(args.config, {})
    dominios_proprios = config.get("official_domains", []) or [
        c.get("dominio_site", "") for c in config.get("concorrentes", [])
    ]
    marca = config.get("marca", "marca")

    limiares = {
        "queda_impression_share_pontos": args.queda_impression_share_pontos,
        "aumento_rank_lost_pontos": args.aumento_rank_lost_pontos,
        "queda_quality_score_pontos": args.queda_quality_score_pontos,
    }

    keywords_regs = carregar_registros(args.keywords_json)
    auction_regs = carregar_registros(args.auction_json)

    atual = agregar_keywords(keywords_regs)
    dominios_por_campanha = agregar_dominios_por_campanha(auction_regs, dominios_proprios)

    snap_path = f"{args.history_dir}/{marca}-keyword-snapshot.json"
    anterior = load_json(snap_path, {})

    quedas = detectar_quedas(atual, anterior, limiares) if anterior else []
    if not anterior:
        print("[keyword auction] linha de base (1a execução) — sem diffs ainda.", file=sys.stderr)

    for q in quedas:
        top_dominios = dominios_por_campanha.get(q["campanha"], [])[:args.top_dominios]
        q["pontos_de_interferencia"] = [{"dominio": d, "aparicoes_no_periodo": n} for d, n in top_dominios]

    save_json(snap_path, atual)
    save_json(args.out, {"quedas": quedas})

    print(f"[keyword auction] {len(quedas)} queda(s) de performance detectada(s) -> {args.out}", file=sys.stderr)
    for q in quedas:
        doms = ", ".join(d["dominio"] for d in q["pontos_de_interferencia"]) or "(nenhum domínio capturado)"
        print(f"  • [{q['nivel']}] '{q['keyword']}' ({q['campanha']}) — leilão: {doms}", file=sys.stderr)


if __name__ == "__main__":
    main()
