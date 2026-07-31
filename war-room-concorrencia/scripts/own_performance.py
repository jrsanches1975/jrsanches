#!/usr/bin/env python3
"""
Desempenho próprio (Google Ads / Meta Ads, via Windsor.ai) — enriquece a war room com
KPIs REAIS da própria marca, para calibrar a reação a um alerta de concorrência com o
CPA/ROAS/conversão que a marca já está tendo naquele produto, em vez de só a premissa
de elasticidade.

Este script NÃO coleta dados sozinho — ele não tem acesso a Google Ads/Meta/GA4. Quem
coleta é o agente Claude, via o MCP do Windsor.ai (get_fields + get_data), e grava aqui
o JSON bruto por conector (um arquivo por fonte). Este script só agrega por campanha e
mapeia para os produtos do config.

Uso:
    python own_performance.py --input google-ads-30d.json --input meta-30d.json \
        --config config.json --out ../outputs/own-performance-por-produto.json

Formato esperado de cada --input (o que sai de Windsor.ai get_data, embrulhado com o
nome do conector):
    {"connector": "google_ads", "registros": [{"campaign": "...", "impressions": 123,
      "clicks": 4, "spend": 88.0, "conversions": 1.0, "conversions_value": 50.0, ...}]}
"""
import argparse
import json
from collections import defaultdict


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
    agg = defaultdict(lambda: {"impressions": 0.0, "clicks": 0.0, "spend": 0.0,
                                "conversions": 0.0, "conversions_value": 0.0})
    for r in records:
        chave = (r["_connector"], r.get("campaign") or r.get("campaign_name") or "(sem nome)")
        a = agg[chave]
        a["impressions"] += float(r.get("impressions") or 0)
        a["clicks"] += float(r.get("clicks") or 0)
        a["spend"] += float(r.get("spend") or 0)
        a["conversions"] += float(r.get("conversions") or 0)
        a["conversions_value"] += float(r.get("conversions_value") or 0)
    out = []
    for (conector, campanha), v in agg.items():
        ctr = v["clicks"] / v["impressions"] * 100 if v["impressions"] else 0
        cpc = v["spend"] / v["clicks"] if v["clicks"] else 0
        cpa = v["spend"] / v["conversions"] if v["conversions"] else None
        roas = v["conversions_value"] / v["spend"] if v["spend"] else None
        out.append({"conector": conector, "campanha": campanha, **v,
                     "ctr_pct": ctr, "cpc": cpc, "cpa": cpa, "roas": roas})
    return out


def match_produto(conector, campanha, produtos_cfg):
    key = {"google_ads": "campanhas_google_ads", "facebook": "campanhas_meta_ads"}.get(conector)
    if not key:
        return None
    c = norm(campanha)
    for p in produtos_cfg:
        for termo in p.get(key, []):
            if norm(termo) in c:
                return p["nome"]
    return None


def aggregate_by_produto(campanhas_agg, config):
    produtos_cfg = config.get("produtos_monitorados", [])
    por_produto = defaultdict(lambda: {"impressions": 0.0, "clicks": 0.0, "spend": 0.0,
                                        "conversions": 0.0, "conversions_value": 0.0,
                                        "campanhas": []})
    nao_mapeadas = []
    for c in campanhas_agg:
        produto = match_produto(c["conector"], c["campanha"], produtos_cfg)
        if not produto:
            nao_mapeadas.append(c)
            continue
        d = por_produto[produto]
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
        resultado[produto] = {**v, "ctr_pct": ctr, "cpc": cpc, "cpa": cpa, "roas": roas}
    return resultado, nao_mapeadas


def main():
    ap = argparse.ArgumentParser(description="Agrega desempenho próprio (Windsor.ai) por produto.")
    ap.add_argument("--input", action="append", required=True,
                     help="JSON {'connector':..., 'registros':[...]}. Repita por conector.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="own-performance-por-produto.json")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

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


if __name__ == "__main__":
    main()
