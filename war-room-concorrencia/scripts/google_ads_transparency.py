#!/usr/bin/env python3
"""
Monitor de Google Ads Transparency Center — detecta anúncios NOVOS dos concorrentes
no Google (Search/Display/YouTube/Shopping), via Apify.

*** STATUS: BETA, NÃO TESTADO AO VIVO *** (mesma ressalva de meta_ads.py — ver lá e
references/fontes-e-limitacoes.md). Rode com --debug-raw na 1a execução real e ajuste
extrair_campos()/montar_input() conforme o schema real do actor escolhido.

Mesma lógica de meta_ads.py: detecta "anúncio novo" por diff de IDs (ou hash estável
do conteúdo) entre rodadas, não por campo de data do actor.

Uso:
    python google_ads_transparency.py --config config.json \
        --out ../outputs/google-ads-transparency-novos.json \
        --history-dir ../outputs/demo-history --debug-raw
"""
import argparse
import hashlib
import os
import sys

from apify_common import apify_run, get_token, is_billing_error, load_json, norm, save_json

DEFAULT_ACTOR = "unseenuser~google-ads"

CAMPOS_ESPERADOS = {
    "id": ["adId", "ad_id", "id", "creativeId"],
    "anunciante": ["advertiserName", "advertiser_name", "advertiser"],
    "titulo": ["headline", "title", "headlines.0"],
    "descricao": ["description", "descriptions.0", "body"],
    "formato": ["format", "adFormat", "type"],
    "imagem_url": ["imageUrl", "image_url", "creativeUrl"],
    "video_url": ["videoUrl", "video_url"],
    "regiao": ["region", "targetedRegions.0"],
    "inicio": ["firstShown", "startDate", "first_shown"],
    "url_anuncio": ["url", "adUrl", "previewUrl"],
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


def id_estavel(campos):
    if campos.get("id"):
        return str(campos["id"])
    blob = norm(f"{campos.get('anunciante')}|{campos.get('titulo')}|{campos.get('descricao')}")
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def montar_input(concorrente, config):
    """Payload best-effort — NÃO confirmado. A maioria desses actors busca por
    domínio OU nome de anunciante; mandamos os dois e deixamos o actor escolher."""
    return {
        "domain": concorrente.get("dominio_site"),
        "advertiserName": concorrente.get("google_advertiser") or concorrente["nome"],
        "region": "BR",
        "maxItems": config.get("google_ads_transparency_max_por_concorrente", 30),
    }


def coletar(config, token, actor, debug_raw=False):
    resultado = {}
    for c in config.get("concorrentes", []):
        nome = c["nome"]
        payload = montar_input(c, config)
        print(f"  [google ads transparency] buscando anúncios ativos de '{nome}'...", file=sys.stderr)
        items, err = apify_run(actor, payload, token)
        if err:
            print(f"  [google ads transparency] ERRO em '{nome}': {err}", file=sys.stderr)
            resultado[nome] = {"anuncios": {}, "erro": err}
            continue
        if debug_raw and items:
            print(f"\n[DEBUG --debug-raw] primeiro item bruto para '{nome}':", file=sys.stderr)
            print(items[0], file=sys.stderr)
            print(file=sys.stderr)
        anuncios = {}
        for it in items or []:
            campos = extrair_campos(it)
            aid = id_estavel(campos)
            anuncios[aid] = campos
        resultado[nome] = {"anuncios": anuncios, "erro": None}
    return resultado


def diff_novos(snapshot_antigo, snapshot_novo):
    novos = []
    for concorrente, dados in snapshot_novo.items():
        antigos_ids = set((snapshot_antigo.get(concorrente) or {}).get("anuncios", {}).keys())
        for aid, campos in dados.get("anuncios", {}).items():
            if aid not in antigos_ids:
                novos.append({"concorrente": concorrente, "ad_id": aid, **campos})
    return novos


def main():
    ap = argparse.ArgumentParser(description="Monitor de Google Ads Transparency Center (beta, não testado).")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="google-ads-transparency-novos.json")
    ap.add_argument("--history-dir", required=True)
    ap.add_argument("--actor", default=None, help="sobrescreve o actor (default: config ou unseenuser~google-ads)")
    ap.add_argument("--token", default=None)
    ap.add_argument("--debug-raw", action="store_true")
    args = ap.parse_args()

    config = load_json(args.config, {})
    token = get_token(config, args.token)
    if not token:
        print("ERRO: sem token Apify. Exporte APIFY_TOKEN.", file=sys.stderr)
        sys.exit(1)

    actor = args.actor or config.get("apify_actors", {}).get("google_ads_transparency", DEFAULT_ACTOR)
    marca = config.get("marca", "marca")
    snap_path = os.path.join(args.history_dir, f"{marca}-google-ads-transparency-snapshot.json")

    snapshot_antigo = load_json(snap_path, {})
    snapshot_novo = coletar(config, token, actor)

    erros = [d["erro"] for d in snapshot_novo.values() if d.get("erro")]
    if erros and is_billing_error(erros[0]):
        print("AVISO: erro de saldo/limite Apify — relatório pode sair vazio.", file=sys.stderr)

    novos = diff_novos(snapshot_antigo, snapshot_novo) if snapshot_antigo else []
    if not snapshot_antigo:
        print("[google ads transparency] linha de base (1a execução) — sem diffs ainda.", file=sys.stderr)

    save_json(snap_path, snapshot_novo)
    save_json(args.out, {"novos_anuncios": novos, "actor_usado": actor})

    print(f"[google ads transparency] {len(novos)} anúncio(s) novo(s) detectado(s) -> {args.out}", file=sys.stderr)
    for n in novos[:10]:
        print(f"  • {n['concorrente']}: {(n.get('titulo') or n.get('descricao') or '(sem texto capturado)')[:70]}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
