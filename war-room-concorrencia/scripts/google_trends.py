#!/usr/bin/env python3
"""
Monitor de Google Trends — acompanha o interesse de busca da marca, dos produtos e
dos concorrentes ao longo do tempo, via Apify, e alerta sobre picos.

*** STATUS: BETA, NÃO TESTADO AO VIVO *** (mesma ressalva de meta_ads.py — ver
references/fontes-e-limitacoes.md). Rode com --debug-raw na 1a execução real.

Por que via Apify e não pytrends: a lib pytrends (wrapper não-oficial) está com o
repositório arquivado desde abril/2025 (sem manutenção) e sofre rate-limit
imprevisível; a API oficial do Google Trends segue em alfa fechado (allowlist), não
disponível de forma geral em 2026. Preferimos manter tudo no mesmo provedor/token já
usado no resto da skill (Apify) em vez de somar mais uma dependência não confiável.

Sinal: para cada termo, guarda a série retornada e calcula a média da rodada atual vs.
a média salva na rodada anterior; alerta se subir além de `salto_trends_pct` (config).
Não afirme "motivo do pico" — é o papel do agente investigar (lançamento, mídia, viral).

Uso:
    python google_trends.py --config config.json --out ../outputs/trends-alertas.json \
        --history-dir ../outputs/demo-history --debug-raw
"""
import argparse
import os
import sys

from apify_common import apify_run_multi, get_tokens, is_billing_error, load_json, save_json

DEFAULT_ACTOR = "apify~google-trends-scraper"


def termos_padrao(config):
    termos = set()
    if config.get("marca"):
        termos.add(config["marca"])
    for a in config.get("apelidos", []):
        termos.add(a)
    for p in config.get("produtos_monitorados", []):
        termos.add(p["nome"])
    for c in config.get("concorrentes", []):
        termos.add(c["nome"])
    return sorted(termos)


def montar_input(termos, config):
    """Payload best-effort — NÃO confirmado. Ajuste conforme o schema real do actor."""
    return {
        "searchTerms": termos,
        "geo": config.get("trends_geo", "BR"),
        "timeframe": config.get("trends_timeframe", "today 1-m"),
    }


def extrair_serie(item):
    """Tenta achar a série de interesse-ao-longo-do-tempo em formatos plausíveis."""
    for chave in ("interestOverTime", "interest_over_time", "timelineData", "data"):
        v = item.get(chave)
        if isinstance(v, list) and v:
            return v
    return []


def media_valor(serie):
    valores = []
    for ponto in serie:
        for chave in ("value", "extractedValue", "interest"):
            v = ponto.get(chave) if isinstance(ponto, dict) else None
            if isinstance(v, list):
                v = v[0] if v else None
            if isinstance(v, (int, float)):
                valores.append(v)
                break
    return sum(valores) / len(valores) if valores else None


def coletar(config, tokens, actor, termos, debug_raw=False):
    payload = montar_input(termos, config)
    print(f"  [google trends] buscando {len(termos)} termo(s)...", file=sys.stderr)
    items, err, _ = apify_run_multi(actor, payload, tokens)
    if err:
        print(f"  [google trends] ERRO: {err}", file=sys.stderr)
        return {}, err
    if debug_raw and items:
        print("\n[DEBUG --debug-raw] primeiro item bruto:", file=sys.stderr)
        print(items[0], file=sys.stderr)
        print(file=sys.stderr)
    resultado = {}
    for it in items or []:
        termo = it.get("searchTerm") or it.get("keyword") or it.get("term")
        if not termo:
            continue
        serie = extrair_serie(it)
        resultado[termo] = {"media": media_valor(serie), "n_pontos": len(serie)}
    return resultado, None


def diff_picos(antigo, novo, limiar_pct):
    alertas = []
    for termo, dados in novo.items():
        media_nova = dados.get("media")
        media_antiga = (antigo.get(termo) or {}).get("media")
        if media_nova is None or media_antiga in (None, 0):
            continue
        pct = (media_nova - media_antiga) / media_antiga * 100
        if pct >= limiar_pct:
            alertas.append({"termo": termo, "media_antiga": media_antiga, "media_nova": media_nova, "pct": pct})
    return alertas


def main():
    ap = argparse.ArgumentParser(description="Monitor de Google Trends (beta, não testado).")
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="trends-alertas.json")
    ap.add_argument("--history-dir", required=True)
    ap.add_argument("--termos", default=None, help="lista separada por vírgula; default: marca+produtos+concorrentes")
    ap.add_argument("--actor", default=None)
    ap.add_argument("--token", default=None)
    ap.add_argument("--limiar-pct", type=float, default=40.0, help="salto %% mínimo para alertar")
    ap.add_argument("--debug-raw", action="store_true")
    args = ap.parse_args()

    config = load_json(args.config, {})
    tokens = get_tokens(config, args.token)
    if not tokens:
        print("ERRO: sem token Apify. Exporte APIFY_TOKEN (uma ou mais contas separadas por "
              "vírgula).", file=sys.stderr)
        sys.exit(1)

    actor = args.actor or config.get("apify_actors", {}).get("google_trends", DEFAULT_ACTOR)
    marca = config.get("marca", "marca")
    snap_path = os.path.join(args.history_dir, f"{marca}-trends-snapshot.json")
    termos = [t.strip() for t in args.termos.split(",")] if args.termos else termos_padrao(config)

    snapshot_antigo = load_json(snap_path, {})
    snapshot_novo, err = coletar(config, tokens, actor, termos, args.debug_raw)

    if err and is_billing_error(err):
        print("AVISO: erro de saldo/limite Apify — relatório pode sair vazio.", file=sys.stderr)

    alertas = diff_picos(snapshot_antigo, snapshot_novo, args.limiar_pct) if snapshot_antigo else []
    if not snapshot_antigo:
        print("[google trends] linha de base (1a execução) — sem diffs ainda.", file=sys.stderr)

    save_json(snap_path, snapshot_novo)
    save_json(args.out, {"picos": alertas, "termos": termos, "actor_usado": actor})

    print(f"[google trends] {len(alertas)} pico(s) de interesse detectado(s) -> {args.out}", file=sys.stderr)
    for a in alertas:
        print(f"  • {a['termo']}: {a['media_antiga']:.0f} → {a['media_nova']:.0f} ({a['pct']:+.0f}%)",
              file=sys.stderr)


if __name__ == "__main__":
    main()
