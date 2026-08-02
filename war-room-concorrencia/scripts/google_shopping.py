#!/usr/bin/env python3
"""
Coletor de Google Shopping — mesmo padrão do Radar de Mercado Livre
(`collect_snapshot()` em `war_room.py`): preço, posição, reviews e rating de
cada concorrente + o NOSSO próprio anúncio, por produto monitorado.

*** STATUS: SEM ATOR ESCOLHIDO — leia antes de rodar ***
Diferente de `meta_ads.py` e `google_ads_transparency.py` (que chutaram um
ator específico, de descrição pública no Apify Store, mesmo sem testar ao
vivo), aqui eu NÃO tenho confiança suficiente pra apontar um ator real de
Google Shopping. Inventar um nome que talvez nem exista seria pior que não
ter coletor nenhum: o script rodaria, "funcionaria" tecnicamente, e devolveria
erro ou vazio sem dizer o motivo real. Por isso este script EXIGE o ator via
`config["apify_actors"]["google_shopping"]` ou `--actor` — sem chute de
default.

Como achar um (o mesmo caminho que funcionou para o ator de Mercado Livre,
karamelo~mercadolivre-scraper-brasil-portugues):
  1. Pesquise "google shopping" na Apify Store (apify.com/store?search=google+shopping)
  2. Escolha um com avaliação e uso razoáveis
  3. Rode uma busca de teste pelo painel do Apify (Input > Save & start)
  4. Cole o resultado real aqui no chat — os nomes de campo são confirmados
     antes de você confiar na coleta, do mesmo jeito que fizemos com o
     karamelo (não adivinhe o nome do campo de busca pelo rótulo do
     formulário — teste sempre pela aba "JSON" do Input)

Os nomes de campo abaixo (CAMPOS_ESPERADOS) são um palpite MÚLTIPLO — várias
chaves plausíveis por campo lógico, na ordem em que tentamos — porque atores
diferentes de Shopping usam convenções diferentes. `--debug-raw` mostra o
primeiro item bruto de cada busca, pra conferir contra a lista antes de
confiar em qualquer número.

Formato de saída: idêntico ao snapshot do Radar de ML — {produto:
{concorrente: {...}}} e {produto: {...}} do próprio. NÃO reaproveite os flags
--simulate-google-shopping/--simulate-google-shopping-proprio de war_room.py
para esta saída real: esses dois existem para teste/demo e ficam sem selo de
"real" na aba Marketplaces — quando este coletor estiver confirmado, crie
flags --google-shopping-json/--google-shopping-proprio-json dedicados em
war_room.py (mesmo cuidado já tomado com o Windsor: nunca usar o caminho de
simulação pra dado de verdade).

Uso:
    python google_shopping.py --config config.json --actor SEU_ATOR_TESTADO \
        --token $APIFY_TOKEN --out ../outputs/google-shopping.json \
        --out-proprio ../outputs/google-shopping-proprio.json --debug-raw
"""
import argparse
import sys

from apify_common import apify_run, get_token, load_json, norm, save_json
from war_room import match_oficial

CAMPOS_ESPERADOS = {
    "title": ["title", "productTitle", "name", "productName"],
    "price": ["price", "currentPrice", "salePrice", "priceValue"],
    "original_price": ["originalPrice", "oldPrice", "listPrice", "regularPrice"],
    "seller": ["seller", "merchant", "store", "storeName", "sellerName"],
    "url": ["url", "productUrl", "link", "offerUrl"],
    "rating": ["rating", "reviewScore", "stars", "averageRating"],
    "reviews": ["reviewsCount", "numReviews", "reviews", "ratingCount"],
}


def get_nested(item, path):
    cur = item
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def extrair_campo(item, chaves):
    for k in chaves:
        v = get_nested(item, k)
        if v not in (None, ""):
            return v
    return None


def _num(v):
    """Converte texto de preço (ex. 'R$ 49,90', '49.90') pra float. Ausente vira
    None, nunca 0 — mesma convenção do resto do projeto: 'não medido' e 'zero'
    são coisas diferentes."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").strip()
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def extrair_campos(item, position):
    return {
        "title": extrair_campo(item, CAMPOS_ESPERADOS["title"]),
        "price": _num(extrair_campo(item, CAMPOS_ESPERADOS["price"])),
        "original_price": _num(extrair_campo(item, CAMPOS_ESPERADOS["original_price"])),
        "position": position,
        "reviews": _num(extrair_campo(item, CAMPOS_ESPERADOS["reviews"])),
        "rating": _num(extrair_campo(item, CAMPOS_ESPERADOS["rating"])),
        "url": extrair_campo(item, CAMPOS_ESPERADOS["url"]),
        # nenhum ator de Shopping pesquisado confirma frete/patrocinado de forma
        # que dê pra confiar sem teste real — "não medido" é mais honesto que
        # chutar um campo que pode nem existir na saída
        "frete_gratis": None,
        "patrocinado": "desconhecido",
    }


def match_competitor_shopping(nome_loja, concorrentes):
    """Diferente do match_competitor() do Radar de ML (que só olha sellers_ml,
    nicknames do Mercado Livre): a loja que aparece no Google Shopping tende a
    se parecer mais com o NOME da marca ou com google_advertiser do que com um
    nickname de ML — por isso os três entram como candidatos aqui."""
    n = norm(nome_loja)
    if not n:
        return None
    for c in concorrentes:
        termos = [c.get("nome", ""), c.get("google_advertiser", "")] + c.get("sellers_ml", [])
        for termo in termos:
            t = norm(termo)
            if t and t in n:
                return c["nome"]
    return None


def montar_input(termo, config):
    """Payload best-effort — NÃO confirmado. Ajuste conforme o schema real do
    ator escolhido (mesmo aviso de meta_ads.py: campo com nome errado não dá
    erro, só traz coleta vazia)."""
    return {
        "query": termo,
        "country": "BR",
        "maxItems": config.get("google_shopping_max_por_produto", 20),
    }


def coletar(config, token, actor, debug_raw=False):
    concorrentes = config.get("concorrentes", [])
    official_sellers = config.get("official_sellers", [])
    produtos = config.get("produtos_monitorados", [])

    snapshot, snapshot_proprio = {}, {}
    for prod in produtos:
        nome, termo = prod["nome"], prod["termo_busca_ml"]
        print(f"  [google shopping] buscando '{termo}' (produto '{nome}')...", file=sys.stderr)
        payload = montar_input(termo, config)
        items, err = apify_run(actor, payload, token)
        if err:
            print(f"  [google shopping] ERRO em '{nome}': {err}", file=sys.stderr)
            snapshot[nome] = {}
            continue
        if debug_raw and items:
            print(f"\n[DEBUG --debug-raw] primeiro item bruto para '{nome}':", file=sys.stderr)
            print(items[0], file=sys.stderr)
            print(file=sys.stderr)

        por_concorrente = {}
        for idx, item in enumerate(items or []):
            nick = extrair_campo(item, CAMPOS_ESPERADOS["seller"]) or ""
            position = idx + 1
            campos = extrair_campos(item, position)

            if official_sellers and match_oficial(nick, official_sellers) and nome not in snapshot_proprio:
                snapshot_proprio[nome] = {"seller": nick, "total_listagens": 1, **campos}
                continue

            nome_conc = match_competitor_shopping(nick, concorrentes)
            if not nome_conc:
                continue
            if nome_conc in por_concorrente:
                por_concorrente[nome_conc]["total_listagens"] += 1
                if position < por_concorrente[nome_conc]["position"]:
                    por_concorrente[nome_conc]["position"] = position
                continue
            por_concorrente[nome_conc] = {"seller": nick, "total_listagens": 1, **campos}
        snapshot[nome] = por_concorrente
        if not por_concorrente:
            print(f"  [google shopping] '{nome}': nenhum concorrente configurado apareceu "
                  f"na busca ({len(items or [])} item(ns) bruto(s) recebido(s)).", file=sys.stderr)
    return snapshot, snapshot_proprio


def main():
    ap = argparse.ArgumentParser(
        description="Coletor de Google Shopping (concorrentes + próprio), mesmo formato do Radar de ML. "
                    "BETA — nenhum ator confirmado, ver docstring do arquivo.")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="google-shopping.json")
    ap.add_argument("--out-proprio", default="google-shopping-proprio.json")
    ap.add_argument("--actor", default=None,
                     help="OBRIGATÓRIO (aqui ou em config['apify_actors']['google_shopping']) — "
                          "nenhum default é chutado, ver docstring do arquivo")
    ap.add_argument("--token", default=None)
    ap.add_argument("--debug-raw", action="store_true",
                     help="imprime o 1o item bruto de cada busca, pra conferir os campos")
    args = ap.parse_args()

    config = load_json(args.config, {})
    token = get_token(config, args.token)
    if not token:
        print("ERRO: sem token Apify. Exporte APIFY_TOKEN, ou passe --token.", file=sys.stderr)
        sys.exit(1)

    actor = args.actor or config.get("apify_actors", {}).get("google_shopping")
    if not actor:
        print("ERRO: nenhum ator de Google Shopping configurado. Passe --actor ou "
              "preencha config['apify_actors']['google_shopping'] — ver o cabeçalho "
              "deste arquivo pra como achar um.", file=sys.stderr)
        sys.exit(1)

    snapshot, snapshot_proprio = coletar(config, token, actor, args.debug_raw)

    save_json(args.out, {"registros": snapshot, "actor_usado": actor})
    save_json(args.out_proprio, snapshot_proprio)

    total_concorrentes = sum(len(v) for v in snapshot.values())
    print(f"[google shopping] {total_concorrentes} concorrente(s) encontrado(s) em "
          f"{len(snapshot)} produto(s) -> {args.out}", file=sys.stderr)
    if not total_concorrentes:
        print("  AVISO: veio vazio. Causas comuns: nome de campo errado (rode --debug-raw "
              "e confira contra CAMPOS_ESPERADOS), ator não devolveu resultado pro termo, "
              "ou a loja do concorrente não bate com nome/google_advertiser/sellers_ml "
              "configurados.", file=sys.stderr)


if __name__ == "__main__":
    main()
