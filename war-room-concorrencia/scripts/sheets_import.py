#!/usr/bin/env python3
"""
Importa dados de PLANILHA (Google Sheets / Excel / CSV) para os formatos que o
war room já consome. É a ponte para tudo que hoje vive fora dos conectores:
export do Looker Studio, relatório do ERP, Auction Insights salvo à mão.

POR QUE ISSO EXISTE (e por que não lemos o Looker direto):
o Looker Studio **não expõe API** para listar as fontes de dados de um relatório
nem para ler os dados dos gráficos — a API dele só gerencia permissões de asset.
Verificado também que a URL de um relatório privado responde 403 sem sessão
Google. O caminho que funciona é materializar o dado em planilha (o Looker
agenda entrega para Sheets, ou você exporta o gráfico) e importar aqui.

COMO O CONTEÚDO CHEGA AQUI:
este script não acessa o Google Drive sozinho (não tem credencial). Quem lê a
planilha é o agente Claude, via MCP do Google Drive, e salva o texto num arquivo.
Este script converte esse texto. Aceita três formatos de entrada, detectados
automaticamente: tabela markdown (o que o MCP devolve), TSV e CSV.

AMBIGUIDADE DE NÚMERO — leia antes de confiar no resultado:
planilha em pt-BR usa vírgula decimal e ponto de milhar; em en-US é o contrário.
"1.408" pode ser 1,408 ou 1408. O script detecta o padrão quando dá (se houver
vírgula decimal em qualquer célula, assume pt-BR) e, quando não dá, avisa em vez
de escolher no escuro. Para percentual há `--escala-pct`, porque
"Impression Share = 1.408" pode ser 1,4% ou 14,08% dependendo de como o Google
exportou — e errar aqui muda a leitura toda.

Uso:
    # 1) o agente lê a planilha via MCP e salva em planilha.txt
    # 2) converte para o formato do war room:
    python sheets_import.py --entrada planilha.txt --tipo leilao \\
        --escala-pct auto --out ../outputs/auction-do-sheets.json

    python sheets_import.py --entrada erp.csv --tipo vendas-produto \\
        --out vendas-por-produto.json

Tipos suportados:
    leilao          -> {"result": [...]} no formato de auction_insight_domain,
                       consumível por keyword_auction.py / gerar_relatorio_keywords.py
    campanhas       -> {"result": [...]} no formato de campanha da GA4,
                       consumível por ga4_jornada.py --campanhas e
                       meta_ads_performance.py --ga4-campanhas
    vendas-produto  -> {"Produto": {"unidades": N, "faturamento": R}} para metas.py
    metas           -> {"faturamento": ..., "unidades": ...} para colar no config
    bruto           -> só normaliza e devolve as linhas, para inspeção
"""
import argparse
import json
import os
import re
import sys
import unicodedata

from apify_common import save_json


# --------------------------------------------------------------- normalização
def _sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s))
                    if unicodedata.category(c) != "Mn")


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "_", _sem_acento(str(s)).lower()).strip("_")


def detectar_formato(texto):
    linhas = [l for l in texto.splitlines() if l.strip()]
    if not linhas:
        return "vazio"
    if sum(1 for l in linhas[:12] if l.lstrip().startswith("|")) >= 2:
        return "markdown"
    if sum(1 for l in linhas[:12] if "\t" in l) >= max(1, len(linhas[:12]) // 2):
        return "tsv"
    return "csv"


def _limpar_celula(c):
    c = str(c).strip()
    # o MCP do Drive escapa caracteres em markdown: \< \-- &#9; etc.
    c = c.replace("&#9;", "\t").replace("&amp;", "&")
    c = re.sub(r"\\(.)", r"\1", c)
    return c.strip()


def ler_tabelas(texto):
    """Devolve uma lista de tabelas; cada tabela é uma lista de listas de células.
    Uma planilha exportada costuma trazer VÁRIOS blocos (o MCP separa por linha
    em branco) — por isso não assumimos uma tabela só."""
    fmt = detectar_formato(texto)
    tabelas, atual = [], []

    def fechar():
        nonlocal atual
        if atual:
            tabelas.append(atual)
            atual = []

    for linha in texto.splitlines():
        crua = linha.rstrip()
        if not crua.strip():
            fechar()
            continue
        if fmt == "markdown":
            if not crua.lstrip().startswith("|"):
                fechar()
                continue
            # linha separadora (| :-: | :-: |) não é dado
            if re.fullmatch(r"\|[\s:\-|]+\|", crua.strip()):
                continue
            celulas = [_limpar_celula(c) for c in crua.strip().strip("|").split("|")]
        elif fmt == "tsv":
            celulas = [_limpar_celula(c) for c in crua.split("\t")]
        else:
            # delimitador: ';' quando presente (CSV pt-BR, onde ',' é decimal),
            # senão ','. Sem isso, "31.240,50" seria quebrado em duas células.
            delim = ";" if ";" in crua else ","
            celulas = [_limpar_celula(c)
                       for c in re.split(rf"{delim}(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", crua)]
        # célula única contendo TABs escapados = cabeçalho colapsado pelo markdown
        if len(celulas) == 1 and "\t" in celulas[0]:
            celulas = [_limpar_celula(c) for c in celulas[0].split("\t")]
        if any(c for c in celulas):
            atual.append(celulas)
    fechar()
    return [t for t in tabelas if len(t) >= 2]


def _tem_virgula_decimal(tabelas):
    for t in tabelas:
        for linha in t:
            for c in linha:
                if re.fullmatch(r"-?\d{1,3}(\.\d{3})*,\d+", c) or re.fullmatch(r"-?\d+,\d+", c):
                    return True
    return False


def fazer_parser_numero(ptbr):
    """Devolve uma função de parse coerente com o padrão detectado. Nunca chuta
    célula por célula: o padrão vale para a planilha toda."""
    def parse(v):
        s = str(v).strip()
        if not s or s in ("--", "-", "—", "n/d", "N/D", "(not set)"):
            return None
        s = s.replace("R$", "").replace("%", "").replace("\u00a0", " ").strip()
        neg = s.startswith("(") and s.endswith(")")
        s = s.strip("()").strip()
        if not re.search(r"\d", s):
            return None
        if ptbr:
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
        try:
            n = float(s)
        except ValueError:
            return None
        return -n if neg else n
    return parse


def _pct(v, escala):
    """Converte percentual conforme a escala escolhida.
    'fracao'  -> valor já é 0-1 (0,14 = 14%)
    'pontos'  -> valor é 0-100 (14 = 14%)  → divide por 100
    'auto'    -> se <= 1, trata como fração; se > 1, como pontos.
    """
    if v is None:
        return None
    if escala == "fracao":
        return v
    if escala == "pontos":
        return v / 100.0
    return v if v <= 1 else v / 100.0


def montar_registros(tabela):
    """Primeira linha = cabeçalho. Devolve lista de dicts com chaves em slug,
    ignorando colunas sem nome."""
    cab = tabela[0]
    chaves = [_slug(c) for c in cab]
    regs = []
    for linha in tabela[1:]:
        if not any(c for c in linha):
            continue
        reg = {}
        for i, chave in enumerate(chaves):
            if not chave:
                continue
            reg[chave] = linha[i] if i < len(linha) else ""
        # linha que repete o cabeçalho (planilha com cabeçalho no meio)
        if all(_slug(v) == k for k, v in reg.items() if v):
            continue
        regs.append(reg)
    return regs


def escolher_tabela(tabelas, obrigatorias):
    """Escolhe o bloco cujo cabeçalho contém as colunas que o tipo precisa."""
    melhor, score_melhor = None, -1
    for t in tabelas:
        chaves = {_slug(c) for c in t[0]}
        score = sum(1 for grupo in obrigatorias if any(alt in chaves for alt in grupo))
        if score > score_melhor:
            melhor, score_melhor = t, score
    return melhor, score_melhor


def _pega(reg, *alternativas):
    for a in alternativas:
        if a in reg and str(reg[a]).strip():
            return reg[a]
    return None


# ------------------------------------------------------------------ conversores
# preenchido por --campanha: o Auction Insights exportado não traz a campanha, e
# sem ela o cruzamento com o relatório de keywords (que é por campanha) dá zero.
CAMPANHA_PADRAO = ["(do sheets)"]


def conv_leilao(regs, num, escala):
    """Auction Insights -> formato que keyword_auction/gerar_relatorio_keywords
    consomem (auction_insight_domain), preservando as colunas extras do Google."""
    out = []
    for r in regs:
        dominio = _pega(r, "dominio", "domain", "dominio_de_exibicao", "display_url_domain")
        if not dominio or _slug(dominio) in ("voce", "you"):
            # "Você" é a própria conta — não é concorrente; mantemos de fora do
            # leilão para não competir consigo mesma (mesmo critério do war room)
            continue
        out.append({
            "auction_insight_domain": dominio,
            "campaign": _pega(r, "campanha", "campaign") or CAMPANHA_PADRAO[0],
            "date": _pega(r, "data", "date", "timestamp"),
            "impression_share": _pct(num(_pega(r, "impression_share", "parcela_de_impressoes",
                                                 "impressao")), escala),
            "overlap_rate": _pct(num(_pega(r, "overlap_rate", "taxa_de_sobreposicao")), escala),
            "position_above_rate": _pct(num(_pega(r, "taxa_posicao_superior", "position_above_rate",
                                                   "taxa_de_posicao_superior")), escala),
            "top_of_page_rate": _pct(num(_pega(r, "topo_pagina", "top_of_page_rate",
                                                 "taxa_de_topo_da_pagina")), escala),
            "abs_top_of_page_rate": _pct(num(_pega(r, "1a_posicao", "primeira_posicao",
                                                    "abs_top_of_page_rate")), escala),
            "outranking_share": _pct(num(_pega(r, "parcela_vitorias", "outranking_share",
                                                "parcela_de_superacao")), escala),
        })
    return out


def conv_campanhas(regs, num, escala):
    """Planilha de campanha -> formato de campanha da GA4."""
    out = []
    for r in regs:
        camp = _pega(r, "campanha", "campaign", "campaign_name", "nome_da_campanha")
        if not camp:
            continue
        out.append({
            "campaign": camp,
            "source": _pega(r, "origem", "source", "fonte"),
            "medium": _pega(r, "midia", "medium", "meio"),
            "sessions": num(_pega(r, "sessoes", "sessions")),
            "engagement_rate": _pct(num(_pega(r, "taxa_de_engajamento", "engagement_rate",
                                               "engajamento")), escala),
            "add_to_carts": num(_pega(r, "adicoes_ao_carrinho", "add_to_carts", "carrinho")),
            "checkouts": num(_pega(r, "checkouts", "inicios_de_checkout", "checkout")),
            "ecommerce_purchases": num(_pega(r, "compras", "ecommerce_purchases", "transacoes",
                                              "transactions", "conversoes", "conversions")),
            "purchase_revenue": num(_pega(r, "receita", "purchase_revenue", "revenue",
                                           "valor_de_conversao", "faturamento")),
            "spend": num(_pega(r, "custo", "spend", "investimento", "cost")),
            "impressions": num(_pega(r, "impressoes", "impressions")),
            "clicks": num(_pega(r, "cliques", "clicks")),
        })
    return out


def conv_vendas_produto(regs, num, escala):
    """Export do ERP/loja -> {"Produto": {"unidades": N, "faturamento": R}}."""
    out = {}
    for r in regs:
        prod = _pega(r, "produto", "product", "item", "sku", "nome", "descricao")
        if not prod:
            continue
        un = num(_pega(r, "unidades", "quantidade", "qtd", "units", "quantity", "pecas"))
        fat = num(_pega(r, "faturamento", "receita", "revenue", "total", "valor",
                         "valor_total", "vendas"))
        chave = str(prod).strip()
        ant = out.get(chave, {})
        # planilha com uma linha por pedido: soma em vez de sobrescrever
        out[chave] = {
            "unidades": (ant.get("unidades") or 0) + (un or 0) if (un is not None or ant) else None,
            "faturamento": (ant.get("faturamento") or 0) + (fat or 0) if (fat is not None or ant) else None,
        }
    # limpa produto sem nenhum número
    return {k: v for k, v in out.items() if (v.get("unidades") or v.get("faturamento"))}


def conv_metas(regs, num, escala):
    """Planilha de metas (duas colunas: indicador | valor) -> bloco do config."""
    mapa = {
        "faturamento": "faturamento", "receita": "faturamento",
        "unidades": "unidades", "pedidos": "unidades", "vendas": "unidades",
        "ticket_medio": "ticket_medio", "ticket": "ticket_medio",
        "sessoes": "sessoes", "trafego": "sessoes",
        "taxa_de_conversao": "tx_conversao", "conversao": "tx_conversao",
        "tx_conversao": "tx_conversao",
        "receita_por_sessao": "receita_por_sessao",
    }
    out = {}
    for r in regs:
        chaves = list(r.keys())
        if len(chaves) < 2:
            continue
        ind = _slug(r[chaves[0]])
        alvo = mapa.get(ind)
        if not alvo:
            continue
        v = num(r[chaves[1]])
        if v is None:
            continue
        out[alvo] = _pct(v, escala) if alvo == "tx_conversao" else v
    return out


CONVERSORES = {
    "leilao": (conv_leilao, [("dominio", "domain", "dominio_de_exibicao"),
                              ("impression_share", "parcela_de_impressoes")]),
    "campanhas": (conv_campanhas, [("campanha", "campaign", "campaign_name"),
                                    ("sessoes", "sessions", "cliques", "clicks")]),
    "vendas-produto": (conv_vendas_produto, [("produto", "product", "item", "sku"),
                                              ("unidades", "quantidade", "faturamento", "receita")]),
    "metas": (conv_metas, [("indicador", "meta", "kpi", "metrica")]),
    "bruto": (None, []),
}


def main():
    ap = argparse.ArgumentParser(description="Importa planilha (Sheets/CSV/TSV) para o war room.")
    ap.add_argument("--entrada", required=True,
                     help="arquivo com o conteúdo da planilha (markdown do MCP do Drive, TSV ou CSV)")
    ap.add_argument("--tipo", required=True, choices=sorted(CONVERSORES),
                     help="formato de saída desejado")
    ap.add_argument("--out", required=True)
    ap.add_argument("--escala-pct", default="auto", choices=("auto", "fracao", "pontos"),
                     help="como interpretar percentuais: 'fracao' (0,14 = 14%%), 'pontos' (14 = 14%%) "
                          "ou 'auto' (<=1 vira fração, >1 vira pontos). Confira o resumo impresso: "
                          "errar a escala distorce a leitura toda.")
    ap.add_argument("--numero", default="auto", choices=("auto", "ptbr", "enus"),
                     help="padrão numérico da planilha. 'auto' detecta vírgula decimal.")
    ap.add_argument("--campanha", default=None,
                     help="[tipo leilao] nome da campanha a atribuir aos domínios, EXATAMENTE como "
                          "aparece no relatório de keywords (ex.: 'Brand.'). O Auction Insights "
                          "exportado não traz a campanha, e sem ela o cruzamento por campanha dá zero. "
                          "Repita o import uma vez por campanha se o export for de várias.")
    ap.add_argument("--tabela", type=int, default=None,
                     help="índice do bloco de tabela a usar (0-based), quando a planilha tem vários "
                          "e a escolha automática pegar o errado")
    args = ap.parse_args()

    if args.campanha:
        CAMPANHA_PADRAO[0] = args.campanha

    with open(args.entrada, encoding="utf-8") as f:
        texto = f.read()

    tabelas = ler_tabelas(texto)
    if not tabelas:
        print("ERRO: não encontrei nenhuma tabela no arquivo. Formatos aceitos: tabela markdown "
              "(saída do MCP do Google Drive), TSV ou CSV.", file=sys.stderr)
        sys.exit(1)

    ptbr = (args.numero == "ptbr") or (args.numero == "auto" and _tem_virgula_decimal(tabelas))
    num = fazer_parser_numero(ptbr)
    print(f"[sheets_import] {len(tabelas)} bloco(s) de tabela | número: "
          f"{'pt-BR (1.234,56)' if ptbr else 'en-US (1,234.56)'}"
          + ("" if args.numero != "auto" else " [detectado]"), file=sys.stderr)

    if args.tipo == "bruto":
        saida = {"blocos": [{"cabecalho": t[0], "linhas": montar_registros(t)} for t in tabelas]}
        save_json(args.out, saida)
        for i, t in enumerate(tabelas):
            print(f"  bloco {i}: {len(t) - 1} linha(s) — colunas: {', '.join(c for c in t[0] if c)}",
                  file=sys.stderr)
        print(f"OK -> {args.out}", file=sys.stderr)
        return

    conv, obrigatorias = CONVERSORES[args.tipo]
    if args.tabela is not None:
        if args.tabela >= len(tabelas):
            print(f"ERRO: --tabela {args.tabela} não existe (há {len(tabelas)}).", file=sys.stderr)
            sys.exit(1)
        tabela, score = tabelas[args.tabela], None
    else:
        tabela, score = escolher_tabela(tabelas, obrigatorias)
        if score == 0:
            print("AVISO: nenhum bloco tem as colunas esperadas para este tipo. Rode com "
                  "--tipo bruto para ver os cabeçalhos e depois use --tabela N.", file=sys.stderr)

    regs = montar_registros(tabela)
    resultado = conv(regs, num, args.escala_pct)

    if args.tipo in ("leilao", "campanhas"):
        # emite as DUAS chaves: keyword_auction.py lê "registros", os scripts que
        # consomem retorno cru do Windsor leem "result". Assim o arquivo serve
        # para os dois sem conversão extra.
        save_json(args.out, {"registros": resultado, "result": resultado,
                              "origem": "planilha importada via sheets_import.py"})
        n = len(resultado)
    else:
        save_json(args.out, resultado)
        n = len(resultado)

    print(f"OK -> {args.out} ({n} registro(s))", file=sys.stderr)
    # resumo para você conferir a escala ANTES de confiar no dado
    if args.tipo == "leilao" and resultado:
        if not args.campanha and all(r["campaign"] == "(do sheets)" for r in resultado):
            print("  AVISO: sem --campanha, estes domínios NÃO vão cruzar com o relatório de "
                  "keywords (o cruzamento é por nome de campanha). Rode de novo passando "
                  "--campanha 'Nome Exato Da Campanha'.", file=sys.stderr)
        print("  confira a escala dos percentuais:", file=sys.stderr)
        for r in resultado[:5]:
            imp = r.get("impression_share")
            print(f"    {r['auction_insight_domain']}: impression share = "
                  + (f"{imp * 100:.2f}%" if isinstance(imp, (int, float)) else "n/d"), file=sys.stderr)
        print("  se esses números não fazem sentido, rode de novo com --escala-pct "
              "fracao ou pontos.", file=sys.stderr)
    elif args.tipo == "vendas-produto" and resultado:
        for k, v in list(resultado.items())[:6]:
            print(f"    {k}: {v.get('unidades')} un / {v.get('faturamento')}", file=sys.stderr)
    elif args.tipo == "metas" and resultado:
        for k, v in resultado.items():
            print(f"    {k}: {v}", file=sys.stderr)


if __name__ == "__main__":
    main()
