#!/usr/bin/env python3
"""
Desempenho próprio (Google Ads / Meta Ads / GA4, via Windsor.ai) — enriquece a war
room com KPIs REAIS da própria marca, para calibrar a reação a um alerta de
concorrência com o CPA/ROAS/conversão que a marca já está tendo naquele produto, em
vez de só a premissa de elasticidade.

Este script NÃO coleta dados sozinho — ele não tem acesso a Google Ads/Meta/GA4. Quem
coleta é o agente Claude, via o MCP do Windsor.ai (get_fields + get_data), e grava aqui
o JSON bruto por conector (um arquivo por fonte). Este script só agrega por campanha e
mapeia para os produtos do config.

Dois grupos de métrica, porque GA4 não é uma plataforma de anúncio (não tem
impressões/cliques/gasto — tem sessões/engajamento/conversão):
  - google_ads / facebook: impressions, clicks, spend, conversions, conversions_value
    → CTR, CPC, CPA, ROAS.
  - googleanalytics4: sessions, engaged_sessions, conversions, transactions
    → taxa de engajamento, taxa de conversão. Útil inclusive para tráfego pago do
    Meta quando o conector do Meta não está disponível: a sessão chega com o nome da
    campanha via UTM mesmo sem o Meta Ads estar conectado no Windsor.ai.

Uso:
    python own_performance.py --input google-ads-30d.json --input ga4-30d.json \
        --config config.json --out ../outputs/own-performance-por-produto.json

Formato esperado de cada --input (o que sai de Windsor.ai get_data, embrulhado com o
nome do conector):
    {"connector": "google_ads", "registros": [{"campaign": "...", "impressions": 123,
      "clicks": 4, "spend": 88.0, "conversions": 1.0, "conversions_value": 50.0, ...}]}
    {"connector": "googleanalytics4", "registros": [{"campaign": "...", "sessions": 100,
      "engaged_sessions": 40, "conversions": 5.0, "transactions": 1, ...}]}
"""
import argparse
import json
import os
from collections import defaultdict

GA4_CONNECTOR = "googleanalytics4"

# (métrica, "queda"|"alta" indica a direção RUIM, rótulo pra humano)
METRICAS_MONITORADAS = [
    ("roas", "queda", "ROAS"),
    ("cpa", "alta", "CPA"),
    ("ctr_pct", "queda", "CTR"),
    ("ga4_conversao_pct", "queda", "Taxa de conversão (GA4)"),
    ("ga4_engajamento_pct", "queda", "Taxa de engajamento (GA4)"),
]


def norm(s):
    return " ".join((s or "").lower().split())


def load_records(paths):
    all_recs = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        connector = doc.get("connector", "desconhecido")
        for r in doc.get("registros", []):
            r = dict(r)
            r["_connector"] = connector
            all_recs.append(r)
    return all_recs


def aggregate_by_campaign(records):
    ads_agg = defaultdict(lambda: {"impressions": 0.0, "clicks": 0.0, "spend": 0.0,
                                    "conversions": 0.0, "conversions_value": 0.0})
    ga4_agg = defaultdict(lambda: {"sessions": 0.0, "engaged_sessions": 0.0,
                                    "conversions": 0.0, "transactions": 0.0})
    for r in records:
        conector = r["_connector"]
        campanha = r.get("campaign") or r.get("campaign_name") or "(sem nome)"
        if conector == GA4_CONNECTOR:
            a = ga4_agg[campanha]
            a["sessions"] += float(r.get("sessions") or 0)
            a["engaged_sessions"] += float(r.get("engaged_sessions") or 0)
            a["conversions"] += float(r.get("conversions") or 0)
            a["transactions"] += float(r.get("transactions") or 0)
        else:
            a = ads_agg[(conector, campanha)]
            a["impressions"] += float(r.get("impressions") or 0)
            a["clicks"] += float(r.get("clicks") or 0)
            a["spend"] += float(r.get("spend") or 0)
            a["conversions"] += float(r.get("conversions") or 0)
            a["conversions_value"] += float(r.get("conversions_value") or 0)

    out = []
    for (conector, campanha), v in ads_agg.items():
        ctr = v["clicks"] / v["impressions"] * 100 if v["impressions"] else 0
        cpc = v["spend"] / v["clicks"] if v["clicks"] else 0
        cpa = v["spend"] / v["conversions"] if v["conversions"] else None
        roas = v["conversions_value"] / v["spend"] if v["spend"] else None
        out.append({"conector": conector, "campanha": campanha, **v,
                     "ctr_pct": ctr, "cpc": cpc, "cpa": cpa, "roas": roas})
    for campanha, v in ga4_agg.items():
        taxa_engajamento = v["engaged_sessions"] / v["sessions"] * 100 if v["sessions"] else 0
        taxa_conversao = v["conversions"] / v["sessions"] * 100 if v["sessions"] else 0
        out.append({"conector": GA4_CONNECTOR, "campanha": campanha, **v,
                     "taxa_engajamento_pct": taxa_engajamento, "taxa_conversao_pct": taxa_conversao})
    return out


def match_produto(conector, campanha, produtos_cfg):
    """GA4 tenta casar tanto contra campanhas_google_ads quanto campanhas_meta_ads —
    a sessão chega com o nome de campanha de qualquer canal pago que a originou."""
    chaves = {
        "google_ads": ["campanhas_google_ads"],
        "facebook": ["campanhas_meta_ads"],
        GA4_CONNECTOR: ["campanhas_google_ads", "campanhas_meta_ads"],
    }.get(conector, [])
    c = norm(campanha)
    for p in produtos_cfg:
        for chave in chaves:
            for termo in p.get(chave, []):
                if norm(termo) in c:
                    return p["nome"]
    return None


def aggregate_by_produto(campanhas_agg, config):
    produtos_cfg = config.get("produtos_monitorados", [])
    por_produto = defaultdict(lambda: {
        "impressions": 0.0, "clicks": 0.0, "spend": 0.0, "conversions": 0.0, "conversions_value": 0.0,
        "ga4_sessions": 0.0, "ga4_engaged_sessions": 0.0, "ga4_conversions": 0.0, "ga4_transactions": 0.0,
        "campanhas": [],
    })
    nao_mapeadas = []
    for c in campanhas_agg:
        produto = match_produto(c["conector"], c["campanha"], produtos_cfg)
        if not produto:
            nao_mapeadas.append(c)
            continue
        d = por_produto[produto]
        if c["conector"] == GA4_CONNECTOR:
            d["ga4_sessions"] += c["sessions"]
            d["ga4_engaged_sessions"] += c["engaged_sessions"]
            d["ga4_conversions"] += c["conversions"]
            d["ga4_transactions"] += c["transactions"]
        else:
            d["impressions"] += c["impressions"]
            d["clicks"] += c["clicks"]
            d["spend"] += c["spend"]
            d["conversions"] += c["conversions"]
            d["conversions_value"] += c["conversions_value"]
        d["campanhas"].append(f"{c['conector']}:{c['campanha']}")

    resultado = {}
    for produto, v in por_produto.items():
        ctr = v["clicks"] / v["impressions"] * 100 if v["impressions"] else 0
        cpc = v["spend"] / v["clicks"] if v["clicks"] else 0
        cpa = v["spend"] / v["conversions"] if v["conversions"] else None
        roas = v["conversions_value"] / v["spend"] if v["spend"] else None
        ga4_engajamento = v["ga4_engaged_sessions"] / v["ga4_sessions"] * 100 if v["ga4_sessions"] else None
        ga4_conversao = v["ga4_conversions"] / v["ga4_sessions"] * 100 if v["ga4_sessions"] else None
        resultado[produto] = {**v, "ctr_pct": ctr, "cpc": cpc, "cpa": cpa, "roas": roas,
                               "ga4_engajamento_pct": ga4_engajamento, "ga4_conversao_pct": ga4_conversao}
    return resultado, nao_mapeadas


def detectar_quedas_kpi(atual, anterior, limiar_pct):
    """Compara o desempenho atual com o snapshot da rodada anterior e sinaliza
    queda relevante em qualquer uma das METRICAS_MONITORADAS. Isto é o gatilho do
    'diagnóstico completo quando o KPI cai' — ver references/protocolo-diagnostico.md."""
    alertas = []
    for produto, v in atual.items():
        b = anterior.get(produto)
        if not b:
            continue
        for metrica, direcao_ruim, rotulo in METRICAS_MONITORADAS:
            va, vb = v.get(metrica), b.get(metrica)
            if va is None or vb in (None, 0):
                continue
            delta_pct = (va - vb) / abs(vb) * 100
            piorou = (direcao_ruim == "queda" and delta_pct <= -limiar_pct) or \
                     (direcao_ruim == "alta" and delta_pct >= limiar_pct)
            if piorou:
                alertas.append({
                    "produto": produto, "metrica": metrica, "rotulo": rotulo,
                    "valor_antes": vb, "valor_agora": va, "delta_pct": delta_pct,
                })
    return alertas


def main():
    ap = argparse.ArgumentParser(description="Agrega desempenho próprio (Windsor.ai) por produto.")
    ap.add_argument("--input", action="append", required=True,
                     help="JSON {'connector':..., 'registros':[...]}. Repita por conector.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="own-performance-por-produto.json")
    ap.add_argument("--history-dir", default=None,
                     help="se fornecido, compara com a rodada anterior e grava "
                          "queda-kpi-proprio.json com as quedas detectadas (gatilho do "
                          "diagnóstico completo — ver SKILL.md passo 8)")
    ap.add_argument("--queda-kpi-json", default=None,
                     help="caminho de saída das quedas (default: <history-dir>/queda-kpi-proprio.json)")
    ap.add_argument("--limiar-pct", type=float, default=20.0,
                     help="variação mínima (%%) pra considerar queda relevante (default 20%%)")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    marca = config.get("marca", "marca")

    records = load_records(args.input)
    campanhas_agg = aggregate_by_campaign(records)
    por_produto, nao_mapeadas = aggregate_by_produto(campanhas_agg, config)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"por_produto": por_produto, "por_campanha": campanhas_agg}, f, ensure_ascii=False, indent=2)

    print(f"OK -> {args.out}")
    print(f"Produtos com desempenho próprio mapeado: {len(por_produto)}")
    if nao_mapeadas:
        print(f"AVISO: {len(nao_mapeadas)} campanha(s) não mapeadas a nenhum produto "
              f"(adicione o nome em 'campanhas_google_ads'/'campanhas_meta_ads' no config):")
        for c in nao_mapeadas[:10]:
            print(f"  - [{c['conector']}] {c['campanha']}")

    if args.history_dir:
        snap_path = os.path.join(args.history_dir, f"{marca}-own-performance-snapshot.json")
        anterior = {}
        if os.path.exists(snap_path):
            with open(snap_path, encoding="utf-8") as f:
                anterior = json.load(f)
        quedas = detectar_quedas_kpi(por_produto, anterior, args.limiar_pct) if anterior else []
        os.makedirs(args.history_dir, exist_ok=True)
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(por_produto, f, ensure_ascii=False, indent=2)
        out_quedas = args.queda_kpi_json or os.path.join(args.history_dir, "queda-kpi-proprio.json")
        with open(out_quedas, "w", encoding="utf-8") as f:
            json.dump({"quedas": quedas}, f, ensure_ascii=False, indent=2)
        if not anterior:
            print("[queda kpi] linha de base (1a execução) — sem diffs ainda.")
        print(f"[queda kpi] {len(quedas)} queda(s) de KPI próprio detectada(s) -> {out_quedas}")
        for q in quedas:
            print(f"  • {q['produto']} — {q['rotulo']}: {q['valor_antes']:.2f} → {q['valor_agora']:.2f} "
                  f"({q['delta_pct']:+.1f}%) — RODAR PROTOCOLO DE DIAGNÓSTICO COMPLETO")


if __name__ == "__main__":
    main()
