"""Infra compartilhada entre os scripts que chamam Apify (war_room.py, meta_ads.py,
google_ads_transparency.py, google_trends.py) — evita duplicar o mesmo boilerplate de
chamada de API em cada um.
"""
import json
import os
import urllib.error
import urllib.request

APIFY_BASE = "https://api.apify.com/v2/acts"


def get_token(config, cli_token):
    return os.environ.get("APIFY_TOKEN") or cli_token or config.get("apify_token") or ""


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
