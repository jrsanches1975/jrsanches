#!/usr/bin/env python3
"""
Compila METAS × REALIZADO e monta a base do quadro de planejamento/evolução.

A ideia central: todo o racional de ação do war room (as "medidas a tomar" da
GA4 e do Meta) precisa apontar para uma meta concreta. Este script transforma as
metas declaradas em `config["metas"]` no confronto com o que foi **medido** e
calcula o que falta — incluindo o *ritmo necessário* para o resto do período.

Honestidade — o que este script faz e o que NÃO faz:
  · Realizado vem SEMPRE de dado medido (GA4 e/ou vendas informadas). Nunca é
    estimado.
  · Projeção linear (`projecao_fim_periodo`) é rotulada como projeção e usa uma
    premissa explícita: mantém o ritmo médio observado até aqui. Não é previsão
    estatística, não tem sazonalidade embutida, e está marcada como premissa.
  · Se a meta não foi declarada no config, o item aparece como "sem meta
    definida" em vez de inventar um alvo.
  · Unidades por produto só aparecem se você informar as vendas por produto
    (`--vendas-produto-json`) — a GA4 não devolve isso no recorte que usamos.

Uso:
    python metas.py --config config.json --ga4-json ../outputs/ga4-jornada.json \
        --vendas-produto-json vendas-por-produto.json \
        --dia-do-periodo 30 --dias-do-periodo 30 \
        --out ../outputs/metas.json
"""
import argparse
import json
import os
import sys

from apify_common import load_json, save_json


def _num(v):
    return v if isinstance(v, (int, float)) else None


def _div(a, b):
    return (a / b) if (isinstance(a, (int, float)) and isinstance(b, (int, float)) and b) else None


def montar_indicador(rotulo, realizado, meta, unidade, dia, dias, maior_melhor=True,
                     desc="", fonte=""):
    """Um indicador do quadro de metas. `falta`, `pct` e a projeção só existem
    quando há meta e realizado — nunca são preenchidos com zero por falta de
    dado."""
    pct = _div(realizado, meta)
    falta = (meta - realizado) if (isinstance(meta, (int, float))
                                    and isinstance(realizado, (int, float))) else None
    ritmo_dia = _div(realizado, dia)
    projecao = (ritmo_dia * dias) if (ritmo_dia is not None and dias) else None
    # ritmo necessário no que resta para bater a meta
    dias_restantes = max(0, (dias or 0) - (dia or 0))
    ritmo_necessario = _div(falta, dias_restantes) if (falta and falta > 0 and dias_restantes) else None
    # ideal proporcional ao dia do período (a "linha de ritmo")
    ideal_ate_agora = (meta * (dia / dias)) if (isinstance(meta, (int, float)) and dia and dias) else None
    if ideal_ate_agora and isinstance(realizado, (int, float)):
        aderencia = _div(realizado, ideal_ate_agora)
    else:
        aderencia = None

    if pct is None:
        status = "sem meta definida" if meta is None else "sem realizado"
    elif aderencia is None:
        status = "no alvo" if pct >= 1 else "abaixo"
    elif aderencia >= 1.0:
        status = "no ritmo"
    elif aderencia >= 0.85:
        status = "atenção"
    else:
        status = "fora do ritmo"

    return {
        "rotulo": rotulo, "realizado": realizado, "meta": meta, "unidade": unidade,
        "pct_da_meta": pct, "falta": falta, "ritmo_dia": ritmo_dia,
        "projecao_fim_periodo": projecao, "ritmo_necessario_dia": ritmo_necessario,
        "ideal_ate_agora": ideal_ate_agora, "aderencia_ao_ritmo": aderencia,
        "dias_restantes": dias_restantes, "status": status,
        "maior_melhor": maior_melhor, "desc": desc, "fonte": fonte,
    }


def montar_serie_acumulada(serie_ga4, meta_faturamento, dias):
    """Curva de realizado acumulado × linha de meta, para o gráfico de evolução.
    O acumulado é dado medido; a linha de meta é a meta distribuída linearmente
    no período (premissa declarada na legenda do gráfico)."""
    pontos, acc = [], 0.0
    n = len(serie_ga4)
    for i, d in enumerate(serie_ga4, start=1):
        r = _num(d.get("receita")) or 0
        acc += r
        alvo = (meta_faturamento * (i / (dias or n))) if isinstance(meta_faturamento, (int, float)) else None
        pontos.append({
            "data": d.get("data"), "dia": i,
            "receita_dia": r, "acumulado": round(acc, 2),
            "meta_acumulada": round(alvo, 2) if alvo is not None else None,
            "compras_dia": _num(d.get("compras")), "sessions_dia": _num(d.get("sessions")),
        })
    return pontos


def montar_produtos(metas_produtos, vendas_produto):
    """Unidades vendidas por produto × meta. Só entra produto que tenha meta
    declarada OU venda informada — nunca inventa linha."""
    # chaves de comentário nos JSONs de exemplo não são produto
    def _reais(d):
        return {k: v for k, v in (d or {}).items() if not k.startswith("_")}

    metas_produtos, vendas_produto = _reais(metas_produtos), _reais(vendas_produto)
    nomes = set(metas_produtos) | set(vendas_produto)
    linhas = []
    for nome in sorted(nomes):
        cfg = metas_produtos.get(nome) or {}
        meta_un = _num(cfg.get("unidades")) if isinstance(cfg, dict) else _num(cfg)
        meta_fat = _num(cfg.get("faturamento")) if isinstance(cfg, dict) else None
        real = vendas_produto.get(nome) or {}
        real = real if isinstance(real, dict) else {}
        un = _num(real.get("unidades"))
        fat = _num(real.get("faturamento"))
        linhas.append({
            "produto": nome,
            "unidades_realizado": un, "unidades_meta": meta_un,
            "unidades_pct": _div(un, meta_un),
            "faturamento_realizado": fat, "faturamento_meta": meta_fat,
            "faturamento_pct": _div(fat, meta_fat),
            "ticket_medio": _div(fat, un),
        })
    linhas.sort(key=lambda l: -(l["faturamento_realizado"] or l["unidades_realizado"] or 0))
    return linhas


def montar_alavancas(kpis, metas, indicadores):
    """As alavancas do funil: quanto cada variável precisa mudar, ISOLADAMENTE,
    para fechar a lacuna de faturamento. É aritmética reversa sobre o realizado —
    o objetivo é dar ordem de grandeza para priorizar ação, não prometer
    resultado."""
    fat = next((i for i in indicadores if i["rotulo"] == "Faturamento"), None)
    if not fat or not fat.get("falta") or fat["falta"] <= 0:
        return []
    falta = fat["falta"]
    sessions = _num(kpis.get("sessions"))
    conv = _num(kpis.get("tx_conversao"))
    ticket = _num(kpis.get("ticket_medio"))
    compras = _num(kpis.get("compras"))
    alavancas = []

    if sessions and conv and ticket:
        sess_extra = falta / (conv * ticket)
        alavancas.append({
            "variavel": "Tráfego (sessões)",
            "atual": sessions,
            "necessario": round(sessions + sess_extra),
            "delta_pct": _div(sess_extra, sessions),
            "leitura": (f"Mantendo conversão ({conv * 100:.2f}%) e ticket ({ticket:,.0f}) atuais, "
                         f"faltam ~{sess_extra:,.0f} sessões no período."),
        })
    if sessions and ticket and conv:
        conv_nec = (falta / (sessions * ticket)) + conv
        alavancas.append({
            "variavel": "Taxa de conversão",
            "atual": conv, "necessario": conv_nec,
            "delta_pct": _div(conv_nec - conv, conv),
            "leitura": (f"Com o mesmo tráfego e ticket, a conversão precisaria ir de "
                         f"{conv * 100:.2f}% para {conv_nec * 100:.2f}%."),
        })
    if compras and ticket:
        ticket_nec = (falta / compras) + ticket
        alavancas.append({
            "variavel": "Ticket médio",
            "atual": ticket, "necessario": ticket_nec,
            "delta_pct": _div(ticket_nec - ticket, ticket),
            "leitura": (f"Com o mesmo número de compras ({compras}), o ticket precisaria ir de "
                         f"R$ {ticket:,.0f} para R$ {ticket_nec:,.0f}."),
        })
    return alavancas


def main():
    ap = argparse.ArgumentParser(description="Metas × realizado e base do quadro de evolução.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--ga4-json", help="saída de ga4_jornada.py (realizado medido)")
    ap.add_argument("--vendas-produto-json",
                     help='JSON {"Produto": {"unidades": N, "faturamento": R}} — vendas reais por '
                          "produto (a GA4 não devolve isso no recorte usado; informe do ERP/loja)")
    ap.add_argument("--dia-do-periodo", type=int, default=None,
                     help="quantos dias do período já correram (default: nº de dias na série da GA4)")
    ap.add_argument("--dias-do-periodo", type=int, default=None,
                     help="duração total do período de meta (default: igual ao dia corrente)")
    ap.add_argument("--out", default="metas.json")
    args = ap.parse_args()

    config = load_json(args.config, {})
    metas = config.get("metas") or {}
    if not metas:
        print("AVISO: config sem a chave 'metas' — o quadro vai aparecer como 'sem meta definida'. "
              "Ver config.example.json.", file=sys.stderr)

    ga4 = load_json(args.ga4_json, {}) if args.ga4_json else {}
    kpis = ga4.get("kpis") or {}
    serie = ga4.get("serie") or []
    vendas_produto = load_json(args.vendas_produto_json, {}) if args.vendas_produto_json else {}

    dia = args.dia_do_periodo or len(serie) or 0
    dias = args.dias_do_periodo or dia or 0

    indicadores = [
        montar_indicador("Faturamento", _num(kpis.get("receita")), _num(metas.get("faturamento")),
                          "BRL", dia, dias, desc="receita medida no período", fonte="GA4"),
        montar_indicador("Unidades vendidas", _num(kpis.get("compras")), _num(metas.get("unidades")),
                          "un", dia, dias, desc="compras concluídas (purchase)", fonte="GA4"),
        montar_indicador("Ticket médio", _num(kpis.get("ticket_medio")), _num(metas.get("ticket_medio")),
                          "BRL", dia, dias, desc="receita ÷ compras", fonte="GA4"),
        montar_indicador("Sessões", _num(kpis.get("sessions")), _num(metas.get("sessoes")),
                          "sess", dia, dias, desc="tráfego total", fonte="GA4"),
        montar_indicador("Taxa de conversão", _num(kpis.get("tx_conversao")),
                          _num(metas.get("tx_conversao")), "pct", dia, dias,
                          desc="compras ÷ sessões", fonte="GA4"),
        montar_indicador("Receita por sessão", _num(kpis.get("receita_por_sessao")),
                          _num(metas.get("receita_por_sessao")), "BRL", dia, dias,
                          desc="o quanto cada visita vale", fonte="GA4"),
    ]
    # ticket médio e taxas não são acumuláveis — a "linha de ritmo" não se aplica
    for ind in indicadores:
        if ind["rotulo"] in ("Ticket médio", "Taxa de conversão", "Receita por sessão"):
            ind["ideal_ate_agora"] = None
            ind["aderencia_ao_ritmo"] = None
            ind["projecao_fim_periodo"] = None
            ind["ritmo_necessario_dia"] = None
            ind["acumulavel"] = False
            if ind["pct_da_meta"] is not None:
                ind["status"] = "no alvo" if ind["pct_da_meta"] >= 1 else (
                    "atenção" if ind["pct_da_meta"] >= 0.85 else "abaixo")
        else:
            ind["acumulavel"] = True

    saida = {
        "periodo": ga4.get("periodo") or "período coletado",
        "dia_do_periodo": dia, "dias_do_periodo": dias,
        "indicadores": indicadores,
        "produtos": montar_produtos(metas.get("produtos"), vendas_produto),
        "evolucao": montar_serie_acumulada(serie, _num(metas.get("faturamento")), dias),
        "alavancas": montar_alavancas(kpis, metas, indicadores),
        "base_simulador": {
            "sessions": _num(kpis.get("sessions")), "tx_conversao": _num(kpis.get("tx_conversao")),
            "ticket_medio": _num(kpis.get("ticket_medio")), "receita": _num(kpis.get("receita")),
            "compras": _num(kpis.get("compras")),
            "meta_faturamento": _num(metas.get("faturamento")),
            "meta_unidades": _num(metas.get("unidades")),
        },
        "tem_vendas_por_produto": bool(vendas_produto),
    }
    save_json(args.out, saida)

    print(f"OK -> {args.out} (dia {dia} de {dias})", file=sys.stderr)
    for i in saida["indicadores"]:
        pct = f"{i['pct_da_meta'] * 100:.0f}%" if i["pct_da_meta"] is not None else "n/d"
        print(f"  {i['rotulo']}: {pct} da meta — {i['status']}", file=sys.stderr)
    for a in saida["alavancas"]:
        print(f"  alavanca [{a['variavel']}]: {a['leitura']}", file=sys.stderr)


if __name__ == "__main__":
    main()
