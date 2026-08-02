#!/usr/bin/env python3
"""
Coletor do META ADS direto na Marketing API — sem Windsor.ai no meio.

POR QUE EXISTE: o conector `facebook` do Windsor está preso no limite de 1
conector do plano Free (a vaga é da GA4). Falando direto com a Graph API o dado
vem mais completo, sem mensalidade e sem depender de política de conector de
terceiro. Ler a SUA PRÓPRIA conta de anúncio não exige revisão de app na Meta —
revisão só é necessária para acessar dados de terceiros.

O QUE ELE TRAZ (o que a GA4 não vê): gasto, impressões, cliques, CTR, CPM, CPC,
frequência, compras e receita pelo pixel, e os criativos (imagem, título, corpo,
link de preview). Sai nos DOIS arquivos que `meta_ads_performance.py` já consome:
`--out` (insights) e `--criativos-out`.

CREDENCIAIS (nunca no config.json — ele vai para o Git):
    export META_ACCESS_TOKEN='EAAG...'     # token de usuário de sistema, longa duração
    export META_AD_ACCOUNT_ID='act_1234567890'

Como gerar o token está em `references/meta-api-setup.md`.

Uso:
    python meta_ads_api.py --dias 30 \\
        --out ../outputs/meta-insights.json \\
        --criativos-out ../outputs/meta-criativos.json

    # primeira execução real: veja o item bruto antes de confiar no parser
    python meta_ads_api.py --dias 7 --debug-raw --out /tmp/i.json

    # testar o parser sem rede (usa resposta salva em arquivo)
    python meta_ads_api.py --resposta-insights examples/meta-api-insights-bruto.json \\
        --resposta-ads examples/meta-api-ads-bruto.json --out /tmp/i.json

ESTADO DE TESTE — leia antes de confiar:
a camada de PARSE e agregação foi testada com resposta real salva em arquivo
(`examples/meta-api-*-bruto.json`, formato copiado da documentação da Graph API).
A camada HTTP **não pôde ser testada neste ambiente**: `graph.facebook.com` está
bloqueado pela política de egress (verificado). Na primeira execução com rede,
rode com `--debug-raw` e confira os nomes de campo antes de usar o resultado.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta

from apify_common import save_json

VERSAO_API_PADRAO = "v21.0"
BASE = "https://graph.facebook.com"

# métricas pedidas no nível do anúncio: dá para agregar por campanha depois, mas
# não dá para desagregar se pedirmos já somado por campanha
CAMPOS_INSIGHTS = [
    "campaign_id", "campaign_name", "adset_name", "ad_id", "ad_name",
    "spend", "impressions", "clicks", "ctr", "cpm", "cpc", "frequency", "reach",
    "actions", "action_values",
]
CAMPOS_ADS = [
    "id", "name", "effective_status", "preview_shareable_link",
    "creative{id,title,body,thumbnail_url,image_url,object_type}",
]

# a Meta expõe compra sob nomes diferentes conforme a configuração do pixel e a
# idade da conta. Preferimos o mais abrangente e caímos para os antigos; o script
# IMPRIME qual foi usado, porque escolher em silêncio esconderia divergência
# contra o painel da Meta.
TIPOS_COMPRA = ("omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase")


def _num(v):
    """A Graph API devolve número como STRING ("123.45"). Sem esta conversão as
    somas concatenariam texto e o CTR sairia como None em tudo."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _brl(v):
    """1234.5 -> 'R$ 1.234,50'. O swap direto de ',' por '.' (que eu tinha feito
    antes) transforma 2.336,63 em 2.336.63 — o mesmo erro de separador que
    corrompeu a planilha de Auction Insights. Aqui a troca é em três passos, com
    um marcador temporário."""
    return "R$ " + f"{v:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _int(v):
    return f"{v:,.0f}".replace(",", ".")


def _acao(lista, tipos):
    """Extrai o valor de uma ação do array `actions`/`action_values`.
    Devolve (valor, tipo_usado) — o tipo volta para poder ser reportado."""
    if not isinstance(lista, list):
        return None, None
    por_tipo = {}
    for item in lista:
        if isinstance(item, dict) and item.get("action_type"):
            v = _num(item.get("value"))
            if v is not None:
                por_tipo[item["action_type"]] = v
    for t in tipos:
        if t in por_tipo:
            return por_tipo[t], t
    return None, None


# --------------------------------------------------------------------- HTTP
class ErroMeta(Exception):
    pass


def _pedir(url, tentativas=4):
    """GET com backoff. Erro da Graph API é reportado VERBATIM: código, subcódigo
    e mensagem. Nunca devolve dado parcial fingindo sucesso."""
    espera = 2
    for tentativa in range(1, tentativas + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", "replace")
            try:
                err = json.loads(corpo).get("error", {})
            except ValueError:
                err = {}
            codigo = err.get("code")
            msg = err.get("message") or corpo[:300]
            sub = err.get("error_subcode")

            if codigo == 190:
                raise ErroMeta(
                    f"token inválido ou expirado (código 190): {msg}\n"
                    "  Gere um token novo — veja references/meta-api-setup.md. "
                    "Token de usuário comum expira em ~2h; use usuário de sistema.")
            if codigo == 200 or e.code == 403:
                raise ErroMeta(
                    f"sem permissão (código {codigo}): {msg}\n"
                    "  O token precisa do escopo 'ads_read' e o usuário precisa ter "
                    "acesso a esta conta de anúncio no Gerenciador de Negócios.")
            # 17/613 = limite de uso da API; 1/2 = erro transitório do lado deles
            if codigo in (17, 613, 1, 2, 80004) or e.code in (429, 500, 502, 503):
                if tentativa < tentativas:
                    print(f"  [meta_api] {e.code}/{codigo}: {msg[:90]} — "
                          f"nova tentativa em {espera}s ({tentativa}/{tentativas})", file=sys.stderr)
                    time.sleep(espera)
                    espera *= 2
                    continue
            raise ErroMeta(f"HTTP {e.code} (código {codigo}, subcódigo {sub}): {msg}")
        except urllib.error.URLError as e:
            if tentativa < tentativas:
                print(f"  [meta_api] rede falhou ({e.reason}) — nova tentativa em {espera}s",
                      file=sys.stderr)
                time.sleep(espera)
                espera *= 2
                continue
            raise ErroMeta(f"não alcancei {BASE}: {e.reason}\n"
                           "  Se for bloqueio de rede/proxy, rode num ambiente com saída liberada.")
    raise ErroMeta("esgotei as tentativas")


def _paginar(url, debug_raw=False, rotulo=""):
    """Segue paging.next até o fim. A Graph API pagina em ~25 itens por padrão e
    ignorar isso truncaria a conta inteira silenciosamente."""
    itens, pagina = [], 0
    while url:
        d = _pedir(url)
        lote = d.get("data") or []
        if debug_raw and pagina == 0 and lote:
            print(f"\n[--debug-raw] primeiro item bruto de {rotulo}:", file=sys.stderr)
            print(json.dumps(lote[0], ensure_ascii=False, indent=2), file=sys.stderr)
            print("[--debug-raw] confira os nomes de campo antes de confiar no parser.\n",
                  file=sys.stderr)
        itens.extend(lote)
        pagina += 1
        url = (d.get("paging") or {}).get("next")
        if url:
            print(f"  [meta_api] {rotulo}: {len(itens)} itens, buscando página {pagina + 1}…",
                  file=sys.stderr)
    return itens


def montar_url(caminho, params, versao, token):
    p = dict(params)
    p["access_token"] = token
    return f"{BASE}/{versao}/{caminho}?" + urllib.parse.urlencode(p)


# ------------------------------------------------------------------ conversão
def converter_insights(brutos):
    """Resposta da Graph API -> formato que meta_ads_performance.py consome.
    Métrica ausente vira None, nunca 0: 'não medido' e 'zero' são coisas
    diferentes e confundi-las inventaria desempenho."""
    linhas, tipos_vistos = [], set()
    for r in brutos:
        compras, tipo_c = _acao(r.get("actions"), TIPOS_COMPRA)
        receita, tipo_r = _acao(r.get("action_values"), TIPOS_COMPRA)
        if tipo_c:
            tipos_vistos.add(tipo_c)
        if tipo_r:
            tipos_vistos.add(tipo_r)
        crea = r.get("creative") or {}
        linhas.append({
            "campaign_name": r.get("campaign_name"),
            "campaign_id": r.get("campaign_id"),
            "adset_name": r.get("adset_name"),
            "ad_id": r.get("ad_id"),
            "ad_name": r.get("ad_name"),
            "spend": _num(r.get("spend")),
            "impressions": _num(r.get("impressions")),
            "clicks": _num(r.get("clicks")),
            "reach": _num(r.get("reach")),
            "frequency": _num(r.get("frequency")),
            # ctr/cpm da própria Meta entram como referência; o war room recalcula
            # a partir de clicks/impressions para não misturar definições
            "ctr_meta": _num(r.get("ctr")),
            "cpm_meta": _num(r.get("cpm")),
            "cpc_meta": _num(r.get("cpc")),
            "purchases": compras,
            "purchase_value": receita,
            "creative_thumbnail_url": crea.get("thumbnail_url") or crea.get("image_url"),
            "creative_title": crea.get("title"),
            "creative_body": crea.get("body"),
            "ad_permalink": r.get("preview_shareable_link"),
            "effective_status": r.get("effective_status"),
        })
    return linhas, tipos_vistos


def converter_criativos(ads):
    """Resposta de /ads -> dicionário indexado por ad_id, no formato de
    `--criativos` (imagem_url/titulo/corpo/formato/url_anuncio)."""
    saida = {}
    for a in ads:
        crea = a.get("creative") or {}
        imagem = crea.get("thumbnail_url") or crea.get("image_url")
        if not any((imagem, crea.get("title"), crea.get("body"))):
            continue          # anúncio sem nenhum ativo legível não vira card
        saida[a.get("id")] = {
            "nome": a.get("name"),
            "imagem_url": imagem,
            "titulo": crea.get("title"),
            "corpo": crea.get("body"),
            "formato": crea.get("object_type"),
            "url_anuncio": a.get("preview_shareable_link"),
            "status": a.get("effective_status"),
        }
    return saida


def juntar_criativo(linhas, criativos):
    """Preenche o criativo nas linhas de insight que vierem sem ele (o insight de
    nível de anúncio não devolve o creative; ele vem do endpoint /ads)."""
    for l in linhas:
        c = criativos.get(l.get("ad_id"))
        if not c:
            continue
        l["creative_thumbnail_url"] = l.get("creative_thumbnail_url") or c.get("imagem_url")
        l["creative_title"] = l.get("creative_title") or c.get("titulo")
        l["creative_body"] = l.get("creative_body") or c.get("corpo")
        l["ad_permalink"] = l.get("ad_permalink") or c.get("url_anuncio")
        l["effective_status"] = l.get("effective_status") or c.get("status")
    return linhas


# ----------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description="Coleta desempenho e criativos do Meta Ads direto na Marketing API.")
    ap.add_argument("--token", default=os.environ.get("META_ACCESS_TOKEN"),
                     help="token de acesso. Prefira a variável META_ACCESS_TOKEN — "
                          "token em linha de comando fica no histórico do shell.")
    ap.add_argument("--conta", default=os.environ.get("META_AD_ACCOUNT_ID"),
                     help="id da conta de anúncio, com o prefixo act_ (ou META_AD_ACCOUNT_ID)")
    ap.add_argument("--versao-api", default=VERSAO_API_PADRAO,
                     help=f"versão da Graph API (padrão {VERSAO_API_PADRAO}). Versões expiram "
                          "a cada ~2 anos; se der erro de versão, suba este valor.")
    ap.add_argument("--dias", type=int, default=30,
                     help="janela em dias contando de ontem para trás (padrão 30)")
    ap.add_argument("--desde", help="AAAA-MM-DD (sobrepõe --dias)")
    ap.add_argument("--ate", help="AAAA-MM-DD (sobrepõe --dias)")
    ap.add_argument("--nivel", default="ad", choices=("ad", "adset", "campaign"),
                     help="granularidade do insight (padrão 'ad': dá para agregar depois, "
                          "mas não dá para desagregar se pedir já somado)")
    ap.add_argument("--out", required=True, help="JSON de insights (vai para --plataforma)")
    ap.add_argument("--criativos-out", help="JSON de criativos (vai para --criativos)")
    ap.add_argument("--debug-raw", action="store_true",
                     help="imprime o primeiro item bruto de cada endpoint. USE na primeira "
                          "execução real, antes de confiar no parser.")
    ap.add_argument("--resposta-insights", help="[teste] lê resposta salva em vez de chamar a API")
    ap.add_argument("--resposta-ads", help="[teste] idem para o endpoint /ads")
    args = ap.parse_args()

    modo_arquivo = bool(args.resposta_insights or args.resposta_ads)

    if not modo_arquivo:
        if not args.token:
            print("ERRO: sem token. Exporte META_ACCESS_TOKEN ou passe --token.\n"
                  "  Como gerar: references/meta-api-setup.md", file=sys.stderr)
            sys.exit(1)
        if not args.conta:
            print("ERRO: sem conta de anúncio. Exporte META_AD_ACCOUNT_ID (formato act_123...) "
                  "ou passe --conta.", file=sys.stderr)
            sys.exit(1)
        conta = args.conta if args.conta.startswith("act_") else f"act_{args.conta}"

        ate = args.ate or (date.today() - timedelta(days=1)).isoformat()
        desde = args.desde or (date.fromisoformat(ate) - timedelta(days=args.dias - 1)).isoformat()
        print(f"[meta_api] conta {conta} | {desde} a {ate} | nível {args.nivel} | "
              f"API {args.versao_api}", file=sys.stderr)

        url_ins = montar_url(f"{conta}/insights", {
            "level": args.nivel,
            "fields": ",".join(CAMPOS_INSIGHTS),
            "time_range": json.dumps({"since": desde, "until": ate}),
            "limit": 200,
        }, args.versao_api, args.token)
        url_ads = montar_url(f"{conta}/ads", {
            "fields": ",".join(CAMPOS_ADS),
            "limit": 200,
        }, args.versao_api, args.token)

        try:
            brutos = _paginar(url_ins, args.debug_raw, "insights")
            ads = _paginar(url_ads, args.debug_raw, "ads/criativos") if args.criativos_out else []
        except ErroMeta as e:
            print(f"\nERRO da Meta: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        print("[meta_api] MODO ARQUIVO: lendo resposta salva, sem chamar a API", file=sys.stderr)
        def _ler(p):
            if not p:
                return []
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            return d.get("data") if isinstance(d, dict) else d
        brutos = _ler(args.resposta_insights)
        ads = _ler(args.resposta_ads)

    linhas, tipos = converter_insights(brutos)
    criativos = converter_criativos(ads)
    if criativos:
        linhas = juntar_criativo(linhas, criativos)

    if not linhas:
        print("AVISO: a API respondeu sem nenhuma linha de insight. Causas comuns: janela "
              "sem veiculação, conta errada, ou anúncios pausados no período. NÃO estou "
              "gravando zeros — arquivo sai vazio de propósito.", file=sys.stderr)

    # a origem tem de dizer a VERDADE sobre de onde o número veio. No modo arquivo
    # o dado não saiu da API, e deixar "Meta Marketing API" aqui faria uma fixture
    # de teste passar por coleta real mais adiante no pipeline.
    if modo_arquivo:
        procedencia = {
            "origem": f"ARQUIVO DE TESTE ({args.resposta_insights or args.resposta_ads})"
                      " — NÃO é coleta real da Meta",
            "simulado": True,
        }
    else:
        procedencia = {
            "origem": "Meta Marketing API via meta_ads_api.py",
            "conta": conta, "periodo": {"desde": desde, "ate": ate},
            "coletado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
    save_json(args.out, {"result": linhas, "registros": linhas, **procedencia})
    print(f"OK -> {args.out} ({len(linhas)} linha(s))", file=sys.stderr)
    if args.criativos_out:
        save_json(args.criativos_out, criativos)
        print(f"OK -> {args.criativos_out} ({len(criativos)} criativo(s))", file=sys.stderr)

    # resumo para conferir contra o painel da Meta ANTES de apresentar a alguém
    gasto = sum(l["spend"] for l in linhas if l["spend"] is not None)
    impr = sum(l["impressions"] for l in linhas if l["impressions"] is not None)
    cliq = sum(l["clicks"] for l in linhas if l["clicks"] is not None)
    comp = sum(l["purchases"] for l in linhas if l["purchases"] is not None)
    rec = sum(l["purchase_value"] for l in linhas if l["purchase_value"] is not None)
    print(f"  gasto {_brl(gasto)} | {_int(impr)} impressões | {_int(cliq)} cliques",
          file=sys.stderr)
    print(f"  {_int(comp)} compras | receita {_brl(rec)}", file=sys.stderr)
    if tipos:
        print(f"  tipo de conversão usado: {', '.join(sorted(tipos))}", file=sys.stderr)
        print("  ^ confira esse total contra o Gerenciador de Anúncios. Se divergir, o pixel "
              "pode reportar sob outro action_type (ajuste TIPOS_COMPRA).", file=sys.stderr)
    elif linhas:
        print("  nenhuma conversão encontrada em actions/action_values — se a conta TEM "
              "compras, o pixel usa outro action_type e TIPOS_COMPRA precisa ser ajustado.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
