#!/usr/bin/env python3
"""
Coletor da GA4 direto na Google Analytics Data API — sem Windsor.ai no meio.

POR QUE EXISTE: o Windsor.ai (plano Free) só libera 1 conector por vez, e a
vaga estava disputada entre GA4 e Meta Ads. Falando direto com a API oficial
do Google, os dois passam a rodar ao mesmo tempo, sem mensalidade — mesmo
motivo que já valeu para `meta_ads_api.py` (Meta) e `google_ads_api.py`
(Google Ads).

O QUE ELE TRAZ: os mesmos 7 blocos que `ga4_jornada.py` já consome via
`--overview/--funil/--canais/--devices/--landing/--serie/--campanhas` — dá
pra rodar os dois em sequência sem mudar nada em `ga4_jornada.py`.

CREDENCIAL — conta de serviço do Google Cloud (não é OAuth de usuário, não
expira, não pede tela de consentimento):
    export GA4_SERVICE_ACCOUNT_JSON='/caminho/para/service-account.json'
    export GA4_PROPERTY_ID='304174518'   # sem o prefixo "properties/"

Como criar a conta de serviço e dar acesso de leitura à propriedade está em
`references/ga4-api-setup.md`.

**Nunca** aponte `GA4_SERVICE_ACCOUNT_JSON` para um arquivo dentro deste
repositório nem cole o conteúdo da chave em nenhum lugar versionado — é uma
credencial como outra qualquer, variável de ambiente é o lugar certo.

Uso:
    python ga4_api.py --dias 30 --saida-dir ../outputs

    # primeira execução real: veja o item bruto de cada relatório antes de
    # confiar no parser (nomes de dimensão/métrica podem divergir por conta)
    python ga4_api.py --dias 7 --debug-raw --saida-dir /tmp

ESTADO DE TESTE — leia antes de confiar:
a camada de autenticação (JWT assinado RS256 + troca por access_token em
`oauth2.googleapis.com`) foi testada de ponta a ponta contra o Google de
verdade nesta sessão — com uma chave de teste (não uma conta real), o Google
respondeu "invalid_grant: account not found", confirmando que a assinatura e
o formato do pedido estão corretos (só a CONTA não existe, que é o esperado
com uma chave fake). A camada de PARSE dos relatórios (`runReport`) usa
os nomes de dimensão/métrica OFICIAIS e documentados da GA4 Data API — mas,
diferente da autenticação, **não pôde ser confirmada contra dado real de uma
propriedade de verdade** (exigiria uma credencial real, que este agente nunca
aceita colada no chat). Rode com `--debug-raw` na primeira execução real e
compare os números com a interface da GA4 antes de confiar no relatório —
mesmo cuidado já pedido em `meta_ads_api.py` e `google_ads_api.py`.

Duas métricas merecem atenção extra no primeiro uso: `itemViewEvents` (funil
de e-commerce) pode não existir/pode vir zerada dependendo de como a conta
mede `view_item`; e `sessionDefaultChannelGroup` (canal) é a dimensão
CORRETA e atual da GA4 — se a conta usa uma agregação de canal customizada,
o valor pode não bater com o que aparece na UI em "Canais padrão".
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from apify_common import save_json

TOKEN_URI_PADRAO = "https://oauth2.googleapis.com/token"
DATA_API_BASE = "https://analyticsdata.googleapis.com/v1beta"
ESCOPO = "https://www.googleapis.com/auth/analytics.readonly"

# nome oficial da API (camelCase) -> nome local que ga4_jornada.py já espera
# (o mesmo que o Windsor.ai usava — confirmado real em rodadas anteriores
# deste projeto). Não é um transform mecânico: cada um foi conferido contra
# a documentação da GA4 Data API.
CAMPO_API_PARA_LOCAL = {
    "sessions": "sessions",
    "totalUsers": "totalusers",
    "newUsers": "newusers",
    "engagementRate": "engagement_rate",
    "bounceRate": "bounce_rate",
    "averageSessionDuration": "average_session_duration",
    "screenPageViews": "screen_page_views",
    "itemViewEvents": "item_view_events",
    "addToCarts": "add_to_carts",
    "checkouts": "checkouts",
    "ecommercePurchases": "ecommerce_purchases",
    "purchaseRevenue": "purchase_revenue",
    "totalPurchasers": "total_purchasers",
    "firstTimePurchasers": "first_time_purchasers",
    "engagedSessions": "engaged_sessions",
    "sessionDefaultChannelGroup": "default_channel_group",
    "deviceCategory": "devicecategory",
    "landingPage": "landing_page",
    "date": "date",
    "sessionCampaignName": "campaign",
    "sessionSource": "source",
    "sessionMedium": "medium",
}

# um bloco por arquivo que ga4_jornada.py consome — (dimensões, métricas)
RELATORIOS = {
    "overview": ([], ["sessions", "totalUsers", "newUsers", "engagementRate",
                       "bounceRate", "averageSessionDuration", "screenPageViews"]),
    "funil": ([], ["itemViewEvents", "addToCarts", "checkouts", "ecommercePurchases",
                    "purchaseRevenue", "totalPurchasers", "firstTimePurchasers"]),
    "canais": (["sessionDefaultChannelGroup"],
               ["sessions", "engagedSessions", "engagementRate", "addToCarts",
                "checkouts", "ecommercePurchases", "purchaseRevenue"]),
    "devices": (["deviceCategory"],
                ["sessions", "engagementRate", "addToCarts", "checkouts",
                 "ecommercePurchases", "purchaseRevenue"]),
    "landing": (["landingPage"],
                ["sessions", "engagementRate", "bounceRate", "addToCarts",
                 "ecommercePurchases", "purchaseRevenue"]),
    "serie": (["date"],
              ["sessions", "addToCarts", "checkouts", "ecommercePurchases",
               "purchaseRevenue", "engagementRate"]),
    "campanhas": (["sessionCampaignName", "sessionSource", "sessionMedium"],
                  ["sessions", "engagementRate", "addToCarts", "checkouts",
                   "ecommercePurchases", "purchaseRevenue"]),
}


def _b64url(dados_bytes):
    return base64.urlsafe_b64encode(dados_bytes).rstrip(b"=").decode("ascii")


def gerar_jwt(client_email, private_key_pem, token_uri):
    """Monta e assina (RS256) o JWT de conta de serviço — é a troca padrão do
    Google pra OAuth2 servidor-a-servidor, sem tela de consentimento e sem
    token que expira em horas (diferente do token de usuário do Explorador
    da API)."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    agora = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": client_email, "scope": ESCOPO, "aud": token_uri,
        "iat": agora, "exp": agora + 3600,
    }
    entrada = (_b64url(json.dumps(header, separators=(",", ":")).encode()) + "." +
               _b64url(json.dumps(claims, separators=(",", ":")).encode()))
    chave = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
    assinatura = chave.sign(entrada.encode(), padding.PKCS1v15(), hashes.SHA256())
    return entrada + "." + _b64url(assinatura)


def obter_access_token(service_account):
    token_uri = service_account.get("token_uri", TOKEN_URI_PADRAO)
    jwt = gerar_jwt(service_account["client_email"], service_account["private_key"], token_uri)
    corpo = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }).encode()
    req = urllib.request.Request(token_uri, data=corpo,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())["access_token"], None
    except urllib.error.HTTPError as e:
        corpo_erro = e.read().decode("utf-8", "replace")[:400]
        return None, f"HTTP {e.code} ao trocar o JWT por access_token: {corpo_erro}"
    except Exception as e:
        return None, repr(e)


def run_report(access_token, property_id, dimensoes, metricas, desde, ate, limit=100000):
    url = f"{DATA_API_BASE}/properties/{property_id}:runReport"
    payload = {
        "dateRanges": [{"startDate": desde, "endDate": ate}],
        "dimensions": [{"name": d} for d in dimensoes],
        "metrics": [{"name": m} for m in metricas],
        "limit": limit,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:400]}"
    except Exception as e:
        return None, repr(e)


def converter_linhas(resposta):
    """runReport -> lista de dicts flat, com os nomes locais que ga4_jornada.py
    já espera. Métrica vem sempre como STRING no JSON da API — convertida pra
    número aqui; dimensão 'date' vem como AAAAMMDD sem traço, reformatada pra
    AAAA-MM-DD (é o formato que o resto do pipeline usa)."""
    dim_nomes = [h["name"] for h in resposta.get("dimensionHeaders", [])]
    met_nomes = [h["name"] for h in resposta.get("metricHeaders", [])]
    linhas = []
    for row in resposta.get("rows", []):
        reg = {}
        for i, nome in enumerate(dim_nomes):
            valor = row["dimensionValues"][i]["value"]
            if nome == "date" and len(valor) == 8 and valor.isdigit():
                valor = f"{valor[:4]}-{valor[4:6]}-{valor[6:]}"
            reg[CAMPO_API_PARA_LOCAL.get(nome, nome)] = valor
        for j, nome in enumerate(met_nomes):
            bruto = row["metricValues"][j]["value"]
            try:
                valor = float(bruto)
                if valor.is_integer():
                    valor = int(valor)
            except (TypeError, ValueError):
                valor = None
            reg[CAMPO_API_PARA_LOCAL.get(nome, nome)] = valor
        linhas.append(reg)
    return linhas


def main():
    ap = argparse.ArgumentParser(description="Coleta os 7 blocos da GA4 direto na Data API oficial.")
    ap.add_argument("--service-account-json", default=os.environ.get("GA4_SERVICE_ACCOUNT_JSON"),
                     help="caminho do arquivo JSON da conta de serviço (ou variável GA4_SERVICE_ACCOUNT_JSON)")
    ap.add_argument("--property-id", default=os.environ.get("GA4_PROPERTY_ID"),
                     help="id numérico da propriedade GA4, sem 'properties/' (ou variável GA4_PROPERTY_ID)")
    ap.add_argument("--dias", type=int, default=30, help="janela em dias contando de ontem para trás")
    ap.add_argument("--desde", help="AAAA-MM-DD (sobrepõe --dias)")
    ap.add_argument("--ate", help="AAAA-MM-DD (sobrepõe --dias)")
    ap.add_argument("--saida-dir", default="../outputs",
                     help="pasta onde gravar os 7 arquivos (ga4-overview.json, ga4-funil.json, ...)")
    ap.add_argument("--debug-raw", action="store_true",
                     help="imprime a resposta crua do primeiro relatório de cada bloco. USE na "
                          "primeira execução real, antes de confiar no parser.")
    args = ap.parse_args()

    if not args.service_account_json:
        print("ERRO: sem credencial. Exporte GA4_SERVICE_ACCOUNT_JSON com o caminho do arquivo "
              "JSON da conta de serviço, ou passe --service-account-json.\n"
              "  Como criar: references/ga4-api-setup.md", file=sys.stderr)
        sys.exit(1)
    if not args.property_id:
        print("ERRO: sem propriedade. Exporte GA4_PROPERTY_ID (só o número, sem 'properties/'), "
              "ou passe --property-id.", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.service_account_json):
        print(f"ERRO: arquivo não encontrado: {args.service_account_json}", file=sys.stderr)
        sys.exit(1)

    with open(args.service_account_json, encoding="utf-8") as f:
        service_account = json.load(f)
    for chave in ("client_email", "private_key"):
        if chave not in service_account:
            print(f"ERRO: o JSON da conta de serviço não tem o campo '{chave}' — é o arquivo "
                  "certo (baixado em IAM e admin > Contas de serviço > Chaves)?", file=sys.stderr)
            sys.exit(1)

    from datetime import date, timedelta
    ate = args.ate or (date.today() - timedelta(days=1)).isoformat()
    desde = args.desde or (date.fromisoformat(ate) - timedelta(days=args.dias - 1)).isoformat()
    print(f"[ga4_api] propriedade {args.property_id} | {desde} a {ate}", file=sys.stderr)

    print("[ga4_api] autenticando (JWT de conta de serviço)...", file=sys.stderr)
    access_token, err = obter_access_token(service_account)
    if err:
        print(f"\nERRO ao autenticar: {err}", file=sys.stderr)
        print("  Confira: a conta de serviço tem acesso de leitura à propriedade GA4? "
              "(Admin > Acesso à propriedade > Adicionar usuários > e-mail da conta de "
              "serviço, papel Leitor). Ver references/ga4-api-setup.md.", file=sys.stderr)
        sys.exit(2)
    print("[ga4_api] autenticado com sucesso.", file=sys.stderr)

    os.makedirs(args.saida_dir, exist_ok=True)
    algum_erro = False
    for nome_bloco, (dimensoes, metricas) in RELATORIOS.items():
        print(f"  buscando bloco '{nome_bloco}' ({len(dimensoes)} dimensão(ões), "
              f"{len(metricas)} métrica(s))...", file=sys.stderr)
        resposta, err = run_report(access_token, args.property_id, dimensoes, metricas, desde, ate)
        if err:
            print(f"  ERRO no bloco '{nome_bloco}': {err}", file=sys.stderr)
            algum_erro = True
            continue
        if args.debug_raw and resposta.get("rows"):
            print(f"\n[--debug-raw] primeira linha crua de '{nome_bloco}':", file=sys.stderr)
            print(json.dumps(resposta["rows"][0], ensure_ascii=False, indent=2), file=sys.stderr)
            print(f"  cabeçalhos: dimensões={[h['name'] for h in resposta.get('dimensionHeaders', [])]} "
                  f"métricas={[h['name'] for h in resposta.get('metricHeaders', [])]}\n", file=sys.stderr)
        linhas = converter_linhas(resposta)
        caminho = os.path.join(args.saida_dir, f"ga4-{nome_bloco}.json")
        save_json(caminho, {"result": linhas, "origem": "GA4 Data API via ga4_api.py",
                             "propriedade": args.property_id, "periodo": {"desde": desde, "ate": ate}})
        print(f"  OK -> {caminho} ({len(linhas)} linha(s))", file=sys.stderr)

    if algum_erro:
        print("\nAVISO: pelo menos um bloco falhou — os arquivos que já existiam de rodadas "
              "anteriores continuam onde estavam (nada foi sobrescrito com erro).", file=sys.stderr)
        sys.exit(2)

    print(f"\nOK — rode agora:\n  python ga4_jornada.py --overview {args.saida_dir}/ga4-overview.json "
          f"--funil {args.saida_dir}/ga4-funil.json --canais {args.saida_dir}/ga4-canais.json "
          f"--devices {args.saida_dir}/ga4-devices.json --landing {args.saida_dir}/ga4-landing.json "
          f"--serie {args.saida_dir}/ga4-serie.json --campanhas {args.saida_dir}/ga4-campanhas.json "
          f"--out {args.saida_dir}/ga4-jornada.json", file=sys.stderr)


if __name__ == "__main__":
    main()
