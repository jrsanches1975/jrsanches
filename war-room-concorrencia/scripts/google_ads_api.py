#!/usr/bin/env python3
"""
Coletor do GOOGLE ADS direto na API oficial — sem Windsor.ai no meio.

Produz linhas com os MESMOS nomes de campo planos que `keyword_auction.py` e
`gerar_relatorio_keywords.py` já consomem (`keyword_text`, `campaign`,
`impressions`, `clicks`, `cpc`, `first_page_cpc`, `quality_score`,
`search_impression_share`, `search_rank_lost_impression_share`...), então entra no
war room sem adaptador.

O QUE ELE TRAZ: desempenho por campanha e por palavra-chave — impressões, cliques,
custo, CPC médio, conversões, receita, índice de qualidade, estimativas de CPC de
primeira página / topo, e parcela de impressões (perdida por orçamento e por
classificação).

O QUE ELE **NÃO** TRAZ, e por quê: o **Auction Insights por domínio** (aquela
tabela de vhita.com.br, mercadolivre.com.br etc. com participação e sobreposição)
**não existe na API pública** — é liberado só para contas em allowlist, via
representante do Google. O caminho público é exportar da interface
(Insights > Relatórios > Auction Insights) e importar com `sheets_import.py
--tipo leilao`. Não há como automatizar isso sem a allowlist; dizer o contrário
seria prometer o que a API não entrega.

CREDENCIAIS (nunca em arquivo do repositório):
    export GOOGLE_ADS_DEVELOPER_TOKEN='...'      # do Centro de API do Google Ads
    export GOOGLE_ADS_CLIENT_ID='....apps.googleusercontent.com'
    export GOOGLE_ADS_CLIENT_SECRET='...'
    export GOOGLE_ADS_REFRESH_TOKEN='1//...'
    export GOOGLE_ADS_CUSTOMER_ID='1234567890'          # sem hifens
    export GOOGLE_ADS_LOGIN_CUSTOMER_ID='0987654321'    # só se acessar via MCC

Como obter cada um está em `references/google-ads-api-setup.md`.

Uso:
    python google_ads_api.py --dias 30 \\
        --keywords-out ../outputs/gads-keywords.json \\
        --campanhas-out ../outputs/gads-campanhas.json

    python google_ads_api.py --dias 7 --debug-raw --keywords-out /tmp/k.json

    # testar a conversão sem credencial (usa resposta salva)
    python google_ads_api.py --resposta-keywords examples/gads-api-keywords-bruto.json \\
        --keywords-out /tmp/k.json

VERSÃO DA API: sondada neste ambiente em 2026-08-02 — v15 a v19 já retornam 404
(retiradas); v20 em diante respondem. O padrão abaixo reflete isso, e
`--versao-api` existe porque o Google retira versões a cada ~12 meses.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from apify_common import save_json

VERSAO_API_PADRAO = "v22"
BASE = "https://googleads.googleapis.com"
URL_TOKEN = "https://oauth2.googleapis.com/token"


class ErroGoogle(Exception):
    pass


# ------------------------------------------------------------------ utilidades
def _fundo(d, caminho):
    """Busca aninhada em resposta proto3-JSON. `caminho` usa ponto:
    'adGroupCriterion.keyword.text'. Devolve None se qualquer nível faltar."""
    atual = d
    for parte in caminho.split("."):
        if not isinstance(atual, dict):
            return None
        atual = atual.get(parte)
    return atual


def _num(v):
    """Proto3-JSON serializa int64 como STRING ("1234"). Sem esta conversão,
    custo e impressões viriam como texto e as somas concatenariam."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except ValueError:
        return None


def _micros(v):
    """Google reporta dinheiro em micros (1 real = 1.000.000)."""
    n = _num(v)
    return (n / 1_000_000.0) if n is not None else None


# ------------------------------------------------------------------------ auth
def obter_access_token(client_id, client_secret, refresh_token):
    dados = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(URL_TOKEN, data=dados,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())["access_token"]
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")
        codigo, descricao = None, corpo[:200]
        try:
            j = json.loads(corpo)
            codigo = j.get("error")
            descricao = j.get("error_description") or descricao
        except ValueError:
            pass
        # a dica tem de casar com o erro que veio. Sugerir conserto de
        # 'invalid_grant' quando o erro foi 'invalid_client' manda a pessoa
        # procurar no lugar errado.
        dicas = {
            "invalid_client": "o CLIENT_ID ou o CLIENT_SECRET está errado (ou é de outro "
                              "projeto do Google Cloud). Confira os dois no Console de APIs.",
            "invalid_grant": "o REFRESH TOKEN não vale mais: foi revogado, foi gerado com "
                             "outro client_id, ou o app OAuth está em modo 'Teste' — nesse "
                             "modo o refresh token expira em 7 dias. Publique o app ou gere "
                             "outro token.",
            "invalid_request": "faltou parâmetro na troca de token; confira se as quatro "
                               "variáveis estão exportadas.",
            "unauthorized_client": "o app OAuth não tem permissão para este tipo de "
                                    "concessão. Recrie a credencial como 'App para desktop'.",
        }
        dica = dicas.get(codigo, "confira as quatro credenciais de OAuth.")
        raise ErroGoogle(
            f"não consegui trocar o refresh token por access token.\n"
            f"  Google respondeu: {codigo or 'erro'} — {descricao}\n"
            f"  O que isso significa: {dica}\n"
            "  Passo a passo: references/google-ads-api-setup.md")


# ------------------------------------------------------------------------ HTTP
def _consultar(versao, customer_id, login_customer_id, token, dev_token, gaql,
               debug_raw=False, rotulo=""):
    """POST em googleAds:search, seguindo nextPageToken. Erro do Google sai
    verbatim — a mensagem dele é específica e útil, esconder atrás de um texto
    genérico só atrasaria o diagnóstico."""
    url = f"{BASE}/{versao}/customers/{customer_id}/googleAds:search"
    cabecalhos = {
        "Authorization": f"Bearer {token}",
        "developer-token": dev_token,
        "Content-Type": "application/json",
    }
    if login_customer_id:
        cabecalhos["login-customer-id"] = login_customer_id

    resultados, pagina, page_token = [], 0, None
    while True:
        corpo = {"query": gaql, "pageSize": 10000}
        if page_token:
            corpo["pageToken"] = page_token
        req = urllib.request.Request(url, data=json.dumps(corpo).encode(),
                                     headers=cabecalhos, method="POST")
        espera = 2
        for tentativa in range(1, 5):
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.loads(r.read().decode())
                break
            except urllib.error.HTTPError as e:
                bruto = e.read().decode("utf-8", "replace")
                msg, campo = _explicar_erro(bruto, e.code)
                if e.code in (429, 500, 502, 503) and tentativa < 4:
                    print(f"  [gads] HTTP {e.code} — nova tentativa em {espera}s", file=sys.stderr)
                    time.sleep(espera); espera *= 2
                    continue
                raise ErroGoogle(msg) if not campo else ErroCampo(campo, msg)
            except urllib.error.URLError as e:
                if tentativa < 4:
                    print(f"  [gads] rede falhou ({e.reason}) — nova tentativa em {espera}s",
                          file=sys.stderr)
                    time.sleep(espera); espera *= 2
                    continue
                raise ErroGoogle(f"não alcancei {BASE}: {e.reason}")
        else:
            raise ErroGoogle("esgotei as tentativas")

        lote = d.get("results") or []
        if debug_raw and pagina == 0 and lote:
            print(f"\n[--debug-raw] primeiro resultado bruto de {rotulo}:", file=sys.stderr)
            print(json.dumps(lote[0], ensure_ascii=False, indent=2), file=sys.stderr)
            print("[--debug-raw] confira os nomes de campo antes de confiar no parser.\n",
                  file=sys.stderr)
        resultados.extend(lote)
        page_token = d.get("nextPageToken")
        pagina += 1
        if not page_token:
            break
        print(f"  [gads] {rotulo}: {len(resultados)} linhas, próxima página…", file=sys.stderr)
    return resultados


class ErroCampo(ErroGoogle):
    """Erro causado por um campo específico que a conta/versão não aceita.
    Existe para permitir tentar de novo sem ele, em vez de falhar a coleta toda."""
    def __init__(self, campo, msg):
        super().__init__(msg)
        self.campo = campo


def _explicar_erro(bruto, http):
    """Traduz o erro do Google para algo acionável, preservando o texto original.
    Devolve (mensagem, campo_problematico_ou_None)."""
    try:
        j = json.loads(bruto)
    except ValueError:
        return f"HTTP {http}: {bruto[:300]}", None
    err = j.get("error", {})
    detalhe = err.get("message", "")
    campo = None
    # o Google indica o campo ruim no nome do erro ou no trigger
    for d in (err.get("details") or []):
        for e in (d.get("errors") or []):
            loc = ((e.get("location") or {}).get("fieldPathElements") or [])
            nomes = [x.get("fieldName") for x in loc if x.get("fieldName")]
            cod = e.get("errorCode") or {}
            if any(k in cod for k in ("queryError", "fieldError")):
                m = re.search(r"'([a-z_]+\.[a-z_.]+)'", e.get("message", "") or "")
                if m:
                    campo = m.group(1)
            detalhe = e.get("message") or detalhe
            if nomes:
                detalhe += f" [campo: {'.'.join(nomes)}]"
    if http == 401:
        return (f"401 não autenticado: {detalhe}\n"
                "  O access token expirou (dura 1h) ou o refresh token é de outro client_id.", None)
    if http == 403:
        return (f"403 sem permissão: {detalhe}\n"
                "  Causas comuns: developer token ainda sem acesso aprovado, developer token\n"
                "  de outra conta MCC, ou falta o cabeçalho login-customer-id ao acessar via MCC.", None)
    if http == 404:
        return (f"404: {detalhe}\n"
                "  Versão da API retirada? Sonde com --versao-api (v15-v19 já saíram).", None)
    return f"HTTP {http}: {detalhe or bruto[:300]}", campo


# ----------------------------------------------------------------------- GAQL
# campos separados em obrigatórios e opcionais: se a conta ou a versão recusar um
# opcional, o script tenta de novo sem ele e AVISA qual caiu, em vez de perder a
# coleta inteira por um campo.
KW_BASE = [
    "campaign.name", "ad_group.name",
    "ad_group_criterion.keyword.text", "ad_group_criterion.keyword.match_type",
    "metrics.impressions", "metrics.clicks", "metrics.cost_micros",
    "metrics.average_cpc", "metrics.conversions", "metrics.conversions_value",
]
KW_OPCIONAIS = [
    "ad_group_criterion.quality_info.quality_score",
    "ad_group_criterion.position_estimates.first_page_cpc_micros",
    "ad_group_criterion.position_estimates.top_of_page_cpc_micros",
    "metrics.search_impression_share",
    "metrics.search_rank_lost_impression_share",
    "metrics.search_top_impression_share",
    "metrics.search_absolute_top_impression_share",
]
CAMP_BASE = [
    "campaign.id", "campaign.name", "campaign.status",
    "campaign.advertising_channel_type", "campaign_budget.amount_micros",
    "metrics.impressions", "metrics.clicks", "metrics.cost_micros",
    "metrics.average_cpc", "metrics.conversions", "metrics.conversions_value",
]
CAMP_OPCIONAIS = [
    "metrics.search_impression_share",
    "metrics.search_budget_lost_impression_share",
    "metrics.search_rank_lost_impression_share",
]


def montar_gaql(recurso, campos, desde, ate):
    return (f"SELECT {', '.join(campos)} FROM {recurso} "
            f"WHERE segments.date BETWEEN '{desde}' AND '{ate}' "
            f"AND campaign.status != 'REMOVED'")


def consultar_tolerante(recurso, base, opcionais, desde, ate, ctx, rotulo):
    """Tenta com todos os campos; a cada recusa de campo, remove o culpado e tenta
    de novo. Os campos que caírem são REPORTADOS — um relatório sem parcela de
    impressões precisa dizer que ela não veio, não sumir em silêncio."""
    opc = list(opcionais)
    caidos = []
    while True:
        gaql = montar_gaql(recurso, base + opc, desde, ate)
        try:
            return _consultar(gaql=gaql, rotulo=rotulo, **ctx), caidos
        except ErroCampo as e:
            alvo = e.campo if e.campo in opc else None
            if alvo is None:
                # não deu para identificar: derruba o último opcional e segue
                if not opc:
                    raise
                alvo = opc[-1]
            opc.remove(alvo)
            caidos.append(alvo)
            print(f"  [gads] a conta recusou '{alvo}' — repetindo sem esse campo", file=sys.stderr)


# ------------------------------------------------------------------ conversão
def converter_keywords(brutos):
    """Resposta GAQL -> nomes planos que keyword_auction.py já consome."""
    linhas = []
    for r in brutos:
        linhas.append({
            "keyword_text": _fundo(r, "adGroupCriterion.keyword.text"),
            "match_type": _fundo(r, "adGroupCriterion.keyword.matchType"),
            "campaign": _fundo(r, "campaign.name"),
            "ad_group": _fundo(r, "adGroup.name"),
            "impressions": _num(_fundo(r, "metrics.impressions")),
            "clicks": _num(_fundo(r, "metrics.clicks")),
            "cost": _micros(_fundo(r, "metrics.costMicros")),
            "cpc": _micros(_fundo(r, "metrics.averageCpc")),
            "conversions": _num(_fundo(r, "metrics.conversions")),
            "conversions_value": _num(_fundo(r, "metrics.conversionsValue")),
            "quality_score": _num(_fundo(r, "adGroupCriterion.qualityInfo.qualityScore")),
            "first_page_cpc": _micros(
                _fundo(r, "adGroupCriterion.positionEstimates.firstPageCpcMicros")),
            "position_estimates_top_of_page_cpc_micros": _num(
                _fundo(r, "adGroupCriterion.positionEstimates.topOfPageCpcMicros")),
            "top_of_page_cpc": _micros(
                _fundo(r, "adGroupCriterion.positionEstimates.topOfPageCpcMicros")),
            "search_impression_share": _num(_fundo(r, "metrics.searchImpressionShare")),
            "search_rank_lost_impression_share": _num(
                _fundo(r, "metrics.searchRankLostImpressionShare")),
            "search_top_impression_share": _num(_fundo(r, "metrics.searchTopImpressionShare")),
            "search_absolute_top_impression_share": _num(
                _fundo(r, "metrics.searchAbsoluteTopImpressionShare")),
        })
    return linhas


def converter_campanhas(brutos):
    linhas = []
    for r in brutos:
        linhas.append({
            "campaign": _fundo(r, "campaign.name"),
            "campaign_id": _fundo(r, "campaign.id"),
            "status": _fundo(r, "campaign.status"),
            "canal": _fundo(r, "campaign.advertisingChannelType"),
            "orcamento_diario": _micros(_fundo(r, "campaignBudget.amountMicros")),
            "impressions": _num(_fundo(r, "metrics.impressions")),
            "clicks": _num(_fundo(r, "metrics.clicks")),
            "cost": _micros(_fundo(r, "metrics.costMicros")),
            "cpc": _micros(_fundo(r, "metrics.averageCpc")),
            "conversions": _num(_fundo(r, "metrics.conversions")),
            "conversions_value": _num(_fundo(r, "metrics.conversionsValue")),
            "search_impression_share": _num(_fundo(r, "metrics.searchImpressionShare")),
            "search_budget_lost_impression_share": _num(
                _fundo(r, "metrics.searchBudgetLostImpressionShare")),
            "search_rank_lost_impression_share": _num(
                _fundo(r, "metrics.searchRankLostImpressionShare")),
        })
    return linhas


def _brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _int(v):
    return f"{v:,.0f}".replace(",", ".")


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="Coleta campanhas e palavras-chave do Google Ads direto na API oficial.")
    ap.add_argument("--dev-token", default=os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN"))
    ap.add_argument("--client-id", default=os.environ.get("GOOGLE_ADS_CLIENT_ID"))
    ap.add_argument("--client-secret", default=os.environ.get("GOOGLE_ADS_CLIENT_SECRET"))
    ap.add_argument("--refresh-token", default=os.environ.get("GOOGLE_ADS_REFRESH_TOKEN"))
    ap.add_argument("--customer-id", default=os.environ.get("GOOGLE_ADS_CUSTOMER_ID"),
                     help="id da conta, só dígitos (sem hifens)")
    ap.add_argument("--login-customer-id", default=os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
                     help="id da MCC, quando o acesso é por conta gerenciadora")
    ap.add_argument("--versao-api", default=VERSAO_API_PADRAO,
                     help=f"padrão {VERSAO_API_PADRAO}. O Google retira versões a cada ~12 meses.")
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--desde"); ap.add_argument("--ate")
    ap.add_argument("--keywords-out")
    ap.add_argument("--campanhas-out")
    ap.add_argument("--debug-raw", action="store_true",
                     help="imprime o primeiro resultado bruto. USE na primeira execução real.")
    ap.add_argument("--resposta-keywords", help="[teste] lê resposta salva em vez de chamar a API")
    ap.add_argument("--resposta-campanhas", help="[teste] idem para campanhas")
    args = ap.parse_args()

    if not (args.keywords_out or args.campanhas_out):
        print("ERRO: informe --keywords-out e/ou --campanhas-out.", file=sys.stderr)
        sys.exit(1)

    modo_arquivo = bool(args.resposta_keywords or args.resposta_campanhas)

    if modo_arquivo:
        print("[gads] MODO ARQUIVO: lendo resposta salva, sem chamar a API", file=sys.stderr)
        def _ler(p):
            if not p:
                return []
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            return d.get("results") if isinstance(d, dict) else d
        kw_brutos, camp_brutos, caidos_kw, caidos_camp = (
            _ler(args.resposta_keywords), _ler(args.resposta_campanhas), [], [])
        procedencia = {
            "origem": f"ARQUIVO DE TESTE ({args.resposta_keywords or args.resposta_campanhas})"
                      " — NÃO é coleta real do Google Ads",
            "simulado": True,
        }
    else:
        faltando = [n for n, v in (
            ("GOOGLE_ADS_DEVELOPER_TOKEN", args.dev_token),
            ("GOOGLE_ADS_CLIENT_ID", args.client_id),
            ("GOOGLE_ADS_CLIENT_SECRET", args.client_secret),
            ("GOOGLE_ADS_REFRESH_TOKEN", args.refresh_token),
            ("GOOGLE_ADS_CUSTOMER_ID", args.customer_id),
        ) if not v]
        if faltando:
            print("ERRO: faltam credenciais: " + ", ".join(faltando)
                  + "\n  Como obter cada uma: references/google-ads-api-setup.md", file=sys.stderr)
            sys.exit(1)

        from datetime import date, timedelta
        ate = args.ate or (date.today() - timedelta(days=1)).isoformat()
        desde = args.desde or (date.fromisoformat(ate) - timedelta(days=args.dias - 1)).isoformat()
        cid = re.sub(r"\D", "", args.customer_id)
        lcid = re.sub(r"\D", "", args.login_customer_id) if args.login_customer_id else None
        print(f"[gads] conta {cid} | {desde} a {ate} | API {args.versao_api}", file=sys.stderr)

        try:
            token = obter_access_token(args.client_id, args.client_secret, args.refresh_token)
            ctx = {"versao": args.versao_api, "customer_id": cid, "login_customer_id": lcid,
                   "token": token, "dev_token": args.dev_token, "debug_raw": args.debug_raw}
            kw_brutos, caidos_kw = ([], [])
            camp_brutos, caidos_camp = ([], [])
            if args.keywords_out:
                kw_brutos, caidos_kw = consultar_tolerante(
                    "keyword_view", KW_BASE, KW_OPCIONAIS, desde, ate, ctx, "keywords")
            if args.campanhas_out:
                camp_brutos, caidos_camp = consultar_tolerante(
                    "campaign", CAMP_BASE, CAMP_OPCIONAIS, desde, ate, ctx, "campanhas")
        except ErroGoogle as e:
            print(f"\nERRO do Google Ads: {e}", file=sys.stderr)
            sys.exit(2)
        procedencia = {
            "origem": "Google Ads API via google_ads_api.py",
            "conta": cid, "periodo": {"desde": desde, "ate": ate},
            "coletado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }

    if args.keywords_out:
        linhas = converter_keywords(kw_brutos)
        extra = {"campos_indisponiveis": caidos_kw} if caidos_kw else {}
        save_json(args.keywords_out,
                  {"result": linhas, "registros": linhas, **procedencia, **extra})
        print(f"OK -> {args.keywords_out} ({len(linhas)} keyword(s))", file=sys.stderr)
        custo = sum(l["cost"] for l in linhas if l["cost"] is not None)
        impr = sum(l["impressions"] for l in linhas if l["impressions"] is not None)
        cliq = sum(l["clicks"] for l in linhas if l["clicks"] is not None)
        conv = sum(l["conversions"] for l in linhas if l["conversions"] is not None)
        print(f"  custo {_brl(custo)} | {_int(impr)} impressões | {_int(cliq)} cliques "
              f"| {conv:.1f} conversões", file=sys.stderr)
        if caidos_kw:
            print(f"  ATENÇÃO: a conta não devolveu {', '.join(caidos_kw)} — esses campos "
                  "saem como n/d no relatório, não como zero.", file=sys.stderr)

    if args.campanhas_out:
        linhas = converter_campanhas(camp_brutos)
        extra = {"campos_indisponiveis": caidos_camp} if caidos_camp else {}
        save_json(args.campanhas_out,
                  {"result": linhas, "registros": linhas, **procedencia, **extra})
        print(f"OK -> {args.campanhas_out} ({len(linhas)} campanha(s))", file=sys.stderr)
        if caidos_camp:
            print(f"  ATENÇÃO: campos indisponíveis: {', '.join(caidos_camp)}", file=sys.stderr)

    if not modo_arquivo:
        print("\n  Confira os totais contra a interface do Google Ads no mesmo período antes "
              "de apresentar a alguém.", file=sys.stderr)
        print("  Lembrete: o Auction Insights por domínio NÃO vem por aqui (exige allowlist). "
              "Exporte da interface e use sheets_import.py --tipo leilao.", file=sys.stderr)


if __name__ == "__main__":
    main()
