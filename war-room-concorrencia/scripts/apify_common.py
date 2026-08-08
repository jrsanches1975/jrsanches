"""Infra compartilhada entre os scripts que chamam Apify (war_room.py, meta_ads.py,
google_ads_transparency.py, google_trends.py) — evita duplicar o mesmo boilerplate de
chamada de API em cada um.
"""
import json
import os
import sys
import urllib.error
import urllib.request

APIFY_BASE = "https://api.apify.com/v2/acts"


def get_token(config, cli_token):
    return get_tokens(config, cli_token)[0] if get_tokens(config, cli_token) else ""


def get_tokens(config, cli_token):
    """Lista de tokens Apify, na ordem em que devem ser tentados. Suporta mais
    de uma CONTA Apify para contornar esgotamento de crédito de uma delas: separe
    os tokens por vírgula na mesma variável (`APIFY_TOKEN='apify_api_AAA,apify_api_BBB'`)
    ou no `--token` da linha de comando. Nunca no config.json — mesma regra do
    token único de sempre (variável de ambiente é o lugar certo pra credencial)."""
    bruto = cli_token or os.environ.get("APIFY_TOKEN") or config.get("apify_token") or ""
    return [t.strip() for t in bruto.split(",") if t.strip()]


def apify_run(actor, payload, token, timeout=240):
    """Chama run-sync-get-dataset-items. Retorna (lista, erro_str_ou_None)."""
    url = f"{APIFY_BASE}/{actor}/run-sync-get-dataset-items?token={token}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:200]
        except Exception:
            pass
        return [], f"HTTP {e.code}: {body}"
    except Exception as e:
        return [], repr(e)


def apify_run_multi(actor, payload, tokens, timeout=240):
    """Como `apify_run`, mas tenta cada token da lista em ordem — só passa pro
    próximo quando o erro é de SALDO/LIMITE DA CONTA (`is_billing_error`); erro de
    rede/timeout não pula de conta, porque trocar de token não resolve isso (é o
    retry de rede que já existe em cada script que continua valendo). Devolve
    (itens, erro_ou_None, indice_do_token_usado)."""
    if not tokens:
        return [], "sem token Apify configurado", -1
    ultimo_erro = None
    for i, token in enumerate(tokens):
        items, err = apify_run(actor, payload, token, timeout=timeout)
        if not err:
            return items, None, i
        ultimo_erro = err
        if is_billing_error(err) and i < len(tokens) - 1:
            print(f"  [apify] conta {i + 1}/{len(tokens)} sem saldo/limite ({err[:90]}) — "
                  f"tentando a conta {i + 2}...", file=sys.stderr)
            continue
        return items, err, i
    return [], ultimo_erro, len(tokens) - 1


def is_billing_error(err):
    """Erro terminal de saldo/memória da conta Apify (não adianta repetir)."""
    if not err:
        return False
    e = err.lower()
    return ("402" in e or "403" in e or "usage" in e or "memory-limit" in e
            or "hard limit" in e or "paid-actor" in e or "actor-disabled" in e)


def norm(s):
    return " ".join((s or "").lower().split())


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
