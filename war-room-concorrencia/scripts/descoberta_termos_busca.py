#!/usr/bin/env python3
"""
Agente de termos de busca — deriva/valida `termo_busca_ml` (o mesmo termo usado
na busca de Google Shopping) de cada produto a partir do que a Joie JÁ COMPROVA
que funciona: as keywords reais do Google Ads, rankeadas por clique/impressão.

Por que isso importa: o nome de categoria de um produto (ex. "Colágeno") às
vezes NÃO é o termo que os clientes de verdade buscam — o ativo/variante
específico costuma ser (ex. "colágeno verisol"). Termo genérico demais traz
concorrente genérico demais, ou nenhum — foi exatamente o que aconteceu na
primeira coleta real de Google Shopping (2026-08-02): Faciderm/Amaze/Linha
Joie Fit não acharam Black Skull nem Growth Supplements com os termos hoje
configurados, porque quem aparece pra esses termos são farmácias/marketplaces
(Amazon, Drogasil, DrogaRaia), não os concorrentes diretos vigiados.

Este agente NÃO adivinha o termo — ele MINERA o dado real já coletado
(`outputs/gads-keywords.json`, `keyword_text` por campanha, real desde
2026-08-02) e recomenda o termo com mais clique/impressão real dentro das
campanhas daquele produto (`campanhas_google_ads`/`campanhas_meta_ads`),
comparando contra o `termo_busca_ml` já configurado. Só considera registros do
conector `google_ads` — é o único que tem `keyword_text` de verdade (Pmax,
Shopping e Demand Gen não são campanhas por keyword, isso não é dado ausente
por bug, é o tipo de campanha).

Uso:
    python descoberta_termos_busca.py --config config.json \
        --gads-keywords-json ../outputs/gads-keywords.json \
        --out ../outputs/descoberta-termos.xlsx \
        --export-json ../outputs/descoberta-termos.json
"""
import argparse
import sys
import unicodedata
from collections import defaultdict

from apify_common import load_json, norm, save_json
from own_performance import match_produto


def _sem_acento(s):
    s = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def match_produto_por_keyword(keyword, produtos_cfg):
    """Casa a keyword diretamente contra o NOME do produto — mais específico do
    que casar por campanha, e necessário porque uma campanha pode cobrir mais de
    um produto (achado real: 'Search - Linha Joie Fit' mistura keywords de whey
    E de colágeno na mesma campanha — casar só por campanha atribuiria a keyword
    'Colageno' ao produto errado). Sem acento dos dois lados (norm() do resto do
    projeto NÃO tira acento, e o dado real tem 'Colageno' e 'colágeno' juntos)."""
    k = _sem_acento(keyword)
    for p in produtos_cfg:
        nome_s = _sem_acento(p["nome"])
        if nome_s and nome_s in k:
            return p["nome"]
    return None


def melhores_keywords_por_produto(registros, produtos_cfg):
    """{produto: [{keyword, campanha, impressions, clicks}, ...]}, ordenado por
    clique desc e depois impressão desc — o clique é priorizado porque indica
    intenção de busca validada, não só exposição.

    O casamento tenta primeiro a keyword contra o NOME do produto (mais
    específico) e só cai pra campanha se a keyword não citar nenhum produto —
    ver match_produto_por_keyword() sobre por que isso é necessário."""
    por_produto = defaultdict(list)
    for r in registros:
        keyword = r.get("keyword_text")
        if not keyword:
            continue
        campanha = r.get("campaign") or ""
        produto = (match_produto_por_keyword(keyword, produtos_cfg)
                   or match_produto("google_ads", campanha, produtos_cfg))
        if not produto:
            continue
        por_produto[produto].append({
            "keyword": keyword,
            "campanha": campanha,
            "impressions": r.get("impressions") or 0,
            "clicks": r.get("clicks") or 0,
        })
    for produto in por_produto:
        por_produto[produto].sort(key=lambda k: (-k["clicks"], -k["impressions"]))
    return dict(por_produto)


def montar_recomendacoes(por_produto_keywords, produtos_cfg):
    recomendacoes = []
    for p in produtos_cfg:
        nome = p["nome"]
        termo_atual = p.get("termo_busca_ml")
        candidatos = por_produto_keywords.get(nome, [])
        if not candidatos:
            recomendacoes.append({
                "produto": nome,
                "termo_atual": termo_atual,
                "termo_recomendado": None,
                "evidencia": None,
                "outros_candidatos": [],
                "status": "sem keyword real encontrada nas campanhas deste produto — "
                          "mantenha o termo atual (não é evidência de que ele está errado, "
                          "só de que não há keyword do Google Ads pra comparar)",
            })
            continue
        melhor = candidatos[0]
        atual_n, melhor_n = norm(termo_atual or ""), norm(melhor["keyword"])
        bate = bool(atual_n) and (melhor_n in atual_n or atual_n in melhor_n)
        recomendacoes.append({
            "produto": nome,
            "termo_atual": termo_atual,
            "termo_recomendado": melhor["keyword"],
            "evidencia": {"campanha": melhor["campanha"], "impressions": melhor["impressions"],
                          "clicks": melhor["clicks"]},
            "outros_candidatos": candidatos[1:5],
            "status": ("termo atual já bate com a keyword real de mais volume" if bate else
                       "ACHADO: existe keyword real com mais evidência que o termo configurado "
                       "— considerar trocar"),
        })
    return recomendacoes


def write_xlsx(recomendacoes, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    NAVY = "1F2A44"
    hfont = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill("solid", fgColor=NAVY)

    wb = Workbook()
    ws = wb.active
    ws.title = "Termos de busca"
    cols = ["produto", "status", "termo_atual", "termo_recomendado",
            "campanha_evidencia", "impressions_evidencia", "clicks_evidencia", "outros_candidatos"]
    ws.append([c.upper() for c in cols])
    for c in range(1, len(cols) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = hfont
        cell.fill = hfill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    recomendacoes = sorted(
        recomendacoes,
        key=lambda r: (0 if r["status"].startswith("ACHADO") else 1, r["produto"]),
    )
    for r in recomendacoes:
        ev = r["evidencia"] or {}
        outros = ", ".join(f"{o['keyword']} ({o['clicks']:.0f} cliques)" for o in r["outros_candidatos"]) or "—"
        ws.append([
            r["produto"], r["status"], r.get("termo_atual") or "—",
            r.get("termo_recomendado") or "—", ev.get("campanha") or "—",
            ev.get("impressions") if ev.get("impressions") is not None else "—",
            ev.get("clicks") if ev.get("clicks") is not None else "—",
            outros,
        ])
    larguras = [20, 46, 26, 26, 22, 16, 14, 40]
    for i, w in enumerate(larguras, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"

    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    wb.save(path)


def main():
    ap = argparse.ArgumentParser(
        description="Deriva/valida termo_busca_ml de cada produto a partir de keywords reais do Google Ads.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--gads-keywords-json", required=True,
                     help="saída de windsor_api.py / normalizada, com registros {campaign, keyword_text, "
                          "impressions, clicks, ...} do conector google_ads (mesmo arquivo que alimenta "
                          "gerar_relatorio_keywords.py)")
    ap.add_argument("--out", default="descoberta-termos.xlsx")
    ap.add_argument("--export-json", default=None)
    args = ap.parse_args()

    config = load_json(args.config, {})
    produtos_cfg = config.get("produtos_monitorados", []) + config.get("produtos_candidatos_manual", [])

    dados = load_json(args.gads_keywords_json, {})
    registros = dados.get("registros", [])
    if not registros:
        print("AVISO: gads-keywords-json não tem 'registros' ou veio vazio — nenhuma "
              "recomendação pode ser feita nesta rodada.", file=sys.stderr)

    por_produto_keywords = melhores_keywords_por_produto(registros, produtos_cfg)
    recomendacoes = montar_recomendacoes(por_produto_keywords, produtos_cfg)

    write_xlsx(recomendacoes, args.out)
    if args.export_json:
        save_json(args.export_json, {"recomendacoes": recomendacoes})
        print(f"OK -> {args.export_json}", file=sys.stderr)

    n_achados = sum(1 for r in recomendacoes if r["status"].startswith("ACHADO"))
    print(f"OK -> {args.out} ({len(recomendacoes)} produto(s) avaliado(s), "
          f"{n_achados} achado(s) de termo melhor que o configurado)")
    for r in recomendacoes:
        if r["status"].startswith("ACHADO"):
            ev = r["evidencia"]
            print(f"  • {r['produto']}: '{r['termo_atual']}' -> '{r['termo_recomendado']}' "
                  f"({ev['clicks']:.0f} cliques / {ev['impressions']:.0f} impressões reais, "
                  f"campanha '{ev['campanha']}')")


if __name__ == "__main__":
    main()
