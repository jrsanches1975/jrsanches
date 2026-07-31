#!/usr/bin/env python3
"""
Monitor de Meta Ad Library (Facebook/Instagram) — detecta anúncios NOVOS dos
concorrentes, via Apify.

*** STATUS: BETA, NÃO TESTADO AO VIVO ***
O actor e o formato de input/output abaixo vieram de pesquisa (descrição pública do
actor no Apify Store), não de uma chamada real confirmada — ao contrário do actor de
Mercado Livre usado em war_room.py, que foi testado e documentado no
radar-keywords-concorrentes. Bloqueio de rede impediu validar isso ao vivo (ver
references/fontes-e-limitacoes.md). NA PRIMEIRA EXECUÇÃO REAL:
  1. Rode com --debug-raw — o script imprime o primeiro item bruto retornado.
  2. Confira se os nomes de campo batem com CAMPOS_ESPERADOS abaixo.
  3. Se não baterem, ajuste extrair_campos() e/ou o payload em montar_input().
  4. Se o actor configurado não funcionar, troque em config["apify_actors"]["meta_ads"]
     por uma das alternativas listadas no cabeçalho do actor escolhido (ver SKILL.md).

Detecta "anúncio novo" comparando o conjunto de IDs de anúncio ativos desta rodada
contra o snapshot salvo na rodada anterior — não depende de nenhum campo de data
específico do actor.

Uso:
    python meta_ads.py --config config.json --out ../outputs/meta-ads-novos.json \
        --history-dir ../outputs/demo-history --debug-raw
"""
import argparse
import hashlib
import os
import sys

from apify_common import apify_run, get_token, is_billing_error, load_json, norm, save_json

DEFAULT_ACTOR = "apify~facebook-ads-scraper"

# Nomes de campo esperados na saída do actor, na ordem em que tentamos localizá-los —
# como o formato exato não foi confirmado, cada campo tenta várias chaves plausíveis.
CAMPOS_ESPERADOS = {
    "id": ["adArchiveId", "ad_archive_id", "id", "adId"],
    "pagina": ["pageName", "page_name", "advertiser", "advertiserName"],
    "corpo": ["adText", "body", "text", "snapshot.body.text"],
    "titulo": ["title", "headline", "snapshot.title"],
    "imagem_url": ["imageUrl", "image_url", "snapshot.images.0.url"],
    "video_url": ["videoUrl", "video_url", "snapshot.videos.0.videoHdUrl"],
    "inicio": ["startDate", "start_date", "adDeliveryStartTime"],
    "url_anuncio": ["url", "adUrl", "snapshotUrl"],
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


def extrair_campos(item):
    return {campo: extrair_campo(item, chaves) for campo, chaves in CAMPOS_ESPERADOS.items()}


def id_estavel(campos, raw_item):
    """Se o actor não trouxer um ID confiável, deriva um hash estável do conteúdo,
    para ainda dar para diferenciar 'anúncio novo' de 'anúncio já visto'."""
    if campos.get("id"):
        return str(campos["id"])
    blob = norm(f"{campos.get('pagina')}|{campos.get('corpo')}|{campos.get('titulo')}")
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def montar_input(concorrente, config):
    """Payload best-effort — NÃO confirmado. Ajuste conforme o schema real do actor."""
    termo = concorrente.get("meta_page") or concorrente["nome"]
    return {
        "searchTerms": [termo],
        "countryCode": "BR",
        "activeStatus": "active",
        "maxItems": config.get("meta_ads_max_por_concorrente", 30),
    }


def coletar(config, token, actor, debug_raw=False):
    resultado = {}
    for c in config.get("concorrentes", []):
        nome = c["nome"]
        payload = montar_input(c, config)
        print(f"  [meta ads] buscando anúncios ativos de '{nome}'...", file=sys.stderr)
        items, err = apify_run(actor, payload, token)
        if err:
            print(f"  [meta ads] ERRO em '{nome}': {err}", file=sys.stderr)
            resultado[nome] = {"anuncios": {}, "erro": err}
            continue
        if debug_raw and items:
            print(f"\n[DEBUG --debug-raw] primeiro item bruto para '{nome}':", file=sys.stderr)
            print(items[0], file=sys.stderr)
            print(file=sys.stderr)
        anuncios = {}
        for it in items or []:
            campos = extrair_campos(it)
            aid = id_estavel(campos, it)
            anuncios[aid] = campos
        resultado[nome] = {"anuncios": anuncios, "erro": None}
    return resultado


def diff_novos(snapshot_antigo, snapshot_novo):
    """Retorna lista de anúncios NOVOS (apareceram nesta rodada, não existiam na
    anterior) — o sinal que interessa para 'monitorar anúncios novos dos concorrentes'."""
    novos = []
    for concorrente, dados in snapshot_novo.items():
        antigos_ids = set((snapshot_antigo.get(concorrente) or {}).get("anuncios", {}).keys())
        for aid, campos in dados.get("anuncios", {}).items():
            if aid not in antigos_ids:
                novos.append({"concorrente": concorrente, "ad_id": aid, **campos})
    return novos


def main():
    ap = argparse.ArgumentParser(description="Monitor de Meta Ad Library (beta, não testado).")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="meta-ads-novos.json")
    ap.add_argument("--history-dir", required=True)
    ap.add_argument("--actor", default=None, help="sobrescreve o actor (default: config ou apify~facebook-ads-scraper)")
    ap.add_argument("--token", default=None)
    ap.add_argument("--debug-raw", action="store_true", help="imprime o 1o item bruto de cada concorrente")
    args = ap.parse_args()

    config = load_json(args.config, {})
    token = get_token(config, args.token)
    if not token:
        print("ERRO: sem token Apify. Exporte APIFY_TOKEN.", file=sys.stderr)
        sys.exit(1)

    actor = args.actor or config.get("apify_actors", {}).get("meta_ads", DEFAULT_ACTOR)
    marca = config.get("marca", "marca")
    snap_path = os.path.join(args.history_dir, f"{marca}-meta-ads-snapshot.json")

    snapshot_antigo = load_json(snap_path, {})
    snapshot_novo = coletar(config, token, actor)

    erros = [d["erro"] for d in snapshot_novo.values() if d.get("erro")]
    if erros and is_billing_error(erros[0]):
        print("AVISO: erro de saldo/limite Apify — ver mensagem acima. Relatório pode sair vazio.",
              file=sys.stderr)

    novos = diff_novos(snapshot_antigo, snapshot_novo) if snapshot_antigo else []
    if not snapshot_antigo:
        print("[meta ads] linha de base (1a execução) — sem diffs ainda.", file=sys.stderr)

    save_json(snap_path, snapshot_novo)
    save_json(args.out, {"novos_anuncios": novos, "actor_usado": actor})

    print(f"[meta ads] {len(novos)} anúncio(s) novo(s) detectado(s) -> {args.out}", file=sys.stderr)
    for n in novos[:10]:
        print(f"  • {n['concorrente']}: {(n.get('titulo') or n.get('corpo') or '(sem texto capturado)')[:70]}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
