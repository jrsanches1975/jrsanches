#!/usr/bin/env python3
"""
Coletor do Windsor.ai pela API REST, com SUPORTE A VÁRIAS CONTAS.

POR QUE EXISTE: o plano Free do Windsor permite um conector por conta, e a
integração MCP autentica numa conta só — então, por MCP, ter três contas não soma
nada. Pela API REST cada conta tem a SUA chave, e um script pode chamar as três.
É isso que este arquivo faz: uma chave por fonte, tudo numa rodada.

    conta A (chave 1) -> googleanalytics4
    conta B (chave 2) -> google_ads
    conta C (chave 3) -> facebook

VANTAGEM SOBRE OS COLETORES NATIVOS: o Windsor entrega `auction_insight_domain`
— a tabela de leilão por domínio concorrente — que a API oficial do Google Ads
**não** expõe (lá é restrita a contas em allowlist). Essa parte só existe por aqui.

LIMITAÇÕES QUE VÊM COM A ESCOLHA (não são defeito do script):
  - o plano Free tem teto de volume e de janela de dados;
  - o conjunto de campos é mais estreito que o das APIs nativas — em particular,
    a imagem do criativo pode não vir, e sem ela os cards da aba Meta Ads ficam
    sem arte (o texto e as métricas continuam);
  - várias contas gratuitas para contornar o limite de um plano normalmente
    contraria os termos do Windsor: se as contas forem fechadas, a coleta para.

CREDENCIAIS — uma variável de ambiente por conta, nunca em arquivo do repositório:
    export WINDSOR_KEY_GA4='...'
    export WINDSOR_KEY_GADS='...'
    export WINDSOR_KEY_META='...'

A chave fica no painel do Windsor, em cada conta (Settings / API).

Uso:
    python windsor_api.py --dias 30 \\
        --fonte google_ads:WINDSOR_KEY_GADS:../outputs/gads-keywords.json \\
        --fonte facebook:WINDSOR_KEY_META:../outputs/meta-insights.json

    # PRIMEIRA VEZ: descubra os campos que a SUA conta aceita
    python windsor_api.py --listar-campos facebook --chave-env WINDSOR_KEY_META

    # primeira coleta: veja o registro bruto antes de confiar
    python windsor_api.py --dias 7 --debug-raw \\
        --fonte facebook:WINDSOR_KEY_META:/tmp/m.json

    # testar a conversão sem rede
    python windsor_api.py --resposta examples/windsor-facebook-bruto.json \\
        --conector facebook --out /tmp/m.json

ESTADO DE TESTE — leia antes de confiar:
os hosts do Windsor (`connectors.windsor.ai`, `api.windsor.ai`) estão
**BLOQUEADOS** no ambiente onde este script foi escrito (verificado, não suposto).
A camada HTTP, portanto, **não pôde ser testada** — só a de conversão, com resposta
salva em arquivo. Rode `--listar-campos` e `--debug-raw` na primeira vez.

Os nomes de campo de `google_ads` **são confiáveis**: vêm de `keyword_auction.py`,
que já rodou contra a conta real via Windsor. Os de `facebook` **são um palpite
informado** e precisam ser confirmados com `--listar-campos`.
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
from datetime import date, timedelta

from apify_common import save_json

BASE_PADRAO = "https://connectors.windsor.ai"

# ---------------------------------------------------------------------- campos
# google_ads: nomes CONFIRMADOS (keyword_auction.py rodou com dado real daqui).
# O comentário do keyword_auction.py registra uma restrição importante:
# auction_insight_domain NÃO combina com métricas de performance no mesmo pedido —
# por isso são duas chamadas separadas.
CAMPOS = {
    "google_ads": {
        "performance": [
            "date", "datasource", "account_name", "source",
            "campaign", "keyword_text", "impressions", "clicks", "cpc",
            "first_page_cpc", "quality_score", "search_impression_share",
            "search_rank_lost_impression_share",
            "position_estimates_top_of_page_cpc_micros",
        ],
        "leilao": ["date", "datasource", "campaign", "auction_insight_domain"],
    },
    # facebook: PALPITE INFORMADO — confirme com --listar-campos antes de confiar.
    # Os nomes seguem a convenção que o Windsor usa nos outros conectores.
    "facebook": {
        "performance": [
            "date", "datasource", "account_name", "source",
            "campaign", "adset", "ad_name", "spend", "impressions",
            "clicks", "ctr", "cpm", "cpc", "frequency", "reach",
            "purchases", "purchase_value",
        ],
    },
    "googleanalytics4": {
        "performance": [
            "date", "sessionCampaignName", "sessionSource", "sessionMedium",
            "sessions", "engagedSessions", "addToCarts", "checkouts",
            "ecommercePurchases", "purchaseRevenue",
        ],
    },
}


class ErroWindsor(Exception):
    pass


def _pedir(url, tentativas=4, debug_raw=False, rotulo=""):
    espera = 2
    for tentativa in range(1, tentativas + 1):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                bruto = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            corpo = e.read().decode("utf-8", "replace")
            if e.code in (401, 403):
                raise ErroWindsor(
                    f"HTTP {e.code} — chave rejeitada.\n"
                    "  A chave é POR CONTA do Windsor: confira se a variável de ambiente\n"
                    "  aponta para a conta que tem ESTE conector conectado.\n"
                    f"  Resposta: {corpo[:200]}")
            if e.code in (402, 429):
                raise ErroWindsor(
                    f"HTTP {e.code} — limite do plano.\n"
                    "  O plano Free tem teto de volume e de janela. Reduza --dias ou o número\n"
                    f"  de campos.\n  Resposta: {corpo[:200]}")
            if e.code in (500, 502, 503) and tentativa < tentativas:
                print(f"  [windsor] HTTP {e.code} — nova tentativa em {espera}s", file=sys.stderr)
                time.sleep(espera); espera *= 2
                continue
            raise ErroWindsor(f"HTTP {e.code}: {corpo[:300]}")
        except urllib.error.URLError as e:
            if tentativa < tentativas:
                print(f"  [windsor] rede falhou ({e.reason}) — nova tentativa em {espera}s",
                      file=sys.stderr)
                time.sleep(espera); espera *= 2
                continue
            raise ErroWindsor(
                f"não alcancei o Windsor: {e.reason}\n"
                "  Se for bloqueio de rede/proxy, rode na sua máquina — os hosts do Windsor\n"
                "  estão bloqueados no ambiente onde este script foi escrito.")

        try:
            d = json.loads(bruto)
        except ValueError:
            raise ErroWindsor(f"resposta não é JSON: {bruto[:300]}")
        linhas = d.get("data") if isinstance(d, dict) else d
        if linhas is None:
            # o Windsor devolve erro dentro de 200 em alguns casos
            raise ErroWindsor(f"resposta sem 'data': {json.dumps(d, ensure_ascii=False)[:300]}")
        if debug_raw and linhas:
            print(f"\n[--debug-raw] primeiro registro bruto de {rotulo}:", file=sys.stderr)
            print(json.dumps(linhas[0], ensure_ascii=False, indent=2), file=sys.stderr)
            print("[--debug-raw] confira os nomes de campo antes de confiar no parser.\n",
                  file=sys.stderr)
        return linhas
    raise ErroWindsor("esgotei as tentativas")


def montar_url(base, conector, chave, campos, desde, ate, caminho="all"):
    """O caminho é `/all`, CONFIRMADO pela URL que o próprio painel do Windsor
    gera (`connectors.windsor.ai/all?api_key=...`). Com um conector por conta,
    `/all` devolve exatamente aquela fonte, e o campo `datasource` identifica de
    qual veio. Antes eu montava `/{conector}`, que era palpite meu."""
    p = {
        "api_key": chave,
        "fields": ",".join(campos),
        "date_from": desde,
        "date_to": ate,
    }
    return f"{base}/{caminho}?" + urllib.parse.urlencode(p)


def filtrar_fonte(linhas, conector):
    """Se vier mais de uma fonte na resposta (conta com vários conectores),
    mantém só a pedida. Sem isso, métricas de fontes diferentes se somariam."""
    if not linhas:
        return linhas
    chave = next((k for k in ("datasource", "data_source", "source_type")
                  if k in linhas[0]), None)
    if not chave:
        return linhas
    fontes = {str(l.get(chave)) for l in linhas}
    if len(fontes) <= 1:
        return linhas
    print(f"  [windsor] a resposta trouxe {len(fontes)} fontes ({', '.join(sorted(fontes))}); "
          f"mantendo só '{conector}'", file=sys.stderr)
    return [l for l in linhas if str(l.get(chave)) == conector]


def coletar(base, conector, chave, campos, desde, ate, debug_raw, rotulo, caminho="all"):
    url = montar_url(base, conector, chave, campos, desde, ate, caminho)
    # a chave NUNCA vai para o log
    print(f"  [windsor] {rotulo}: {conector}, {len(campos)} campos, {desde} a {ate}",
          file=sys.stderr)
    return filtrar_fonte(_pedir(url, debug_raw=debug_raw, rotulo=rotulo), conector)


def listar_campos(base, conector, chave):
    """Tenta descobrir os campos aceitos. Como não pude verificar o endpoint de
    metadados, faz duas tentativas e, se as duas falharem, cai para um pedido
    mínimo e mostra as CHAVES que voltaram — que é a informação que interessa."""
    tentativas = [
        f"{base}/{conector}/fields?api_key={urllib.parse.quote(chave)}",
        f"{base}/fields?api_key={urllib.parse.quote(chave)}&connector={conector}",
    ]
    for url in tentativas:
        try:
            d = _pedir(url)
            print(json.dumps(d, ensure_ascii=False, indent=2)[:4000])
            return
        except ErroWindsor as e:
            print(f"  (tentativa falhou: {str(e).splitlines()[0]})", file=sys.stderr)
    print("\n  Endpoint de metadados não respondeu. Fazendo um pedido mínimo para ver "
          "quais chaves vêm no registro:", file=sys.stderr)
    ate = (date.today() - timedelta(days=1)).isoformat()
    desde = (date.today() - timedelta(days=7)).isoformat()
    minimos = {"google_ads": ["date", "campaign", "clicks"],
               "facebook": ["date", "campaign", "spend"],
               "googleanalytics4": ["date", "sessions"]}.get(conector, ["date", "campaign"])
    linhas = _pedir(montar_url(base, conector, chave, minimos, desde, ate))
    if linhas:
        print("\n  CHAVES presentes no registro:", file=sys.stderr)
        for k in sorted(linhas[0]):
            print(f"    {k}", file=sys.stderr)
    else:
        print("  o pedido mínimo voltou vazio (sem veiculação no período?).", file=sys.stderr)


def _num(v):
    """Converte para número. O sinal '%' na célula significa PONTOS percentuais e
    tem de virar fração 0-1, que é a convenção do resto do projeto: o war room
    multiplica por 100 para exibir, então deixar "2.18%" como 2.18 mostraria 218%.
    É a mesma armadilha de escala que corrompeu a planilha de Auction Insights."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    percentual = "%" in s
    s = s.replace("%", "").strip()
    try:
        n = float(s)
    except ValueError:
        return None
    return n / 100.0 if percentual else n


def _texto_campanha(v):
    """Nome de campanha da GA4 chega CODIFICADO DE URL, porque vem do UTM:
    '+-+[[Conv]]+-+[Whey+Silk+Protein]+-+Carrossel'. Os '+' são espaços e pode
    haver %XX. Sem decodificar, o cruzamento por nome de campanha entre GA4 e a
    plataforma de anúncio simplesmente não casa — foi visto na resposta real."""
    if not isinstance(v, str) or not v:
        return v
    if "+" not in v and "%" not in v:
        return v
    try:
        d = urllib.parse.unquote_plus(v)
    except Exception:
        return v
    d = re.sub(r"\s{2,}", " ", d).strip()
    # o UTM costuma começar pelo separador ("+-+[[Conv]]..."), o que deixa um
    # "- " sobrando na frente. Do lado da plataforma o nome é "[[Conv]] - ...",
    # e sem tirar isso o cruzamento GA4 x Meta por nome de campanha nunca casa.
    return re.sub(r"^[-–—\s]+|[-–—\s]+$", "", d)


def normalizar(linhas, conector):
    """O Windsor já devolve nomes planos, então a normalização é leve: converter
    número que vier como texto e preservar ausente como None (nunca zero — 'não
    medido' e 'zero' são coisas diferentes e confundi-las inventa desempenho)."""
    numericos = {
        "impressions", "clicks", "spend", "cpc", "ctr", "cpm", "frequency", "reach",
        "purchases", "purchase_value", "first_page_cpc", "quality_score",
        "search_impression_share", "search_rank_lost_impression_share",
        "position_estimates_top_of_page_cpc_micros", "sessions", "engagedSessions",
        "addToCarts", "checkouts", "ecommercePurchases", "purchaseRevenue", "cost",
    }
    saida = []
    for r in linhas:
        if not isinstance(r, dict):
            continue
        limpo = {}
        for k, v in r.items():
            if k in numericos:
                limpo[k] = _num(v)
            elif k in ("campaign", "campaign_name", "adset", "ad_name"):
                limpo[k] = _texto_campanha(v)
            else:
                limpo[k] = v
        saida.append(limpo)
    return saida


def main():
    ap = argparse.ArgumentParser(
        description="Coleta do Windsor.ai por API REST, com uma chave por conta.")
    ap.add_argument("--fonte", action="append", default=[], metavar="CONECTOR:ENV:SAIDA",
                     help="repetível. Ex.: google_ads:WINDSOR_KEY_GADS:../outputs/gads.json")
    ap.add_argument("--base-url", default=os.environ.get("WINDSOR_BASE_URL", BASE_PADRAO),
                     help=f"padrão {BASE_PADRAO}. Existe porque não pude verificar o endpoint "
                          "deste ambiente (host bloqueado).")
    ap.add_argument("--caminho", default="all",
                     help="caminho do endpoint. Padrao 'all', confirmado pela URL que o "
                          "painel do Windsor gera. Troque so se a sua conta usar outro.")
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--desde"); ap.add_argument("--ate")
    ap.add_argument("--campos", help="sobrepõe a lista padrão (separada por vírgula). "
                                      "Use depois de conferir com --listar-campos.")
    ap.add_argument("--leilao-out", help="[google_ads] arquivo separado para o "
                                          "auction_insight_domain, que não combina com "
                                          "métricas de performance no mesmo pedido")
    ap.add_argument("--listar-campos", metavar="CONECTOR",
                     help="descobre os campos aceitos. Requer --chave-env.")
    ap.add_argument("--chave-env", help="variável de ambiente com a chave (para --listar-campos)")
    ap.add_argument("--debug-raw", action="store_true")
    ap.add_argument("--resposta", help="[teste] lê resposta salva em vez de chamar a API")
    ap.add_argument("--conector", help="[teste] conector correspondente ao --resposta")
    ap.add_argument("--out", help="[teste] saída para o modo --resposta")
    args = ap.parse_args()

    if args.listar_campos:
        chave = os.environ.get(args.chave_env or "")
        if not chave:
            print(f"ERRO: exporte a chave e passe --chave-env NOME_DA_VARIAVEL.", file=sys.stderr)
            sys.exit(1)
        try:
            listar_campos(args.base_url, args.listar_campos, chave)
        except ErroWindsor as e:
            print(f"\nERRO do Windsor: {e}", file=sys.stderr)
            sys.exit(2)
        return

    if args.resposta:
        if not (args.conector and args.out):
            print("ERRO: --resposta exige --conector e --out.", file=sys.stderr)
            sys.exit(1)
        with open(args.resposta, encoding="utf-8") as f:
            d = json.load(f)
        linhas = normalizar(d.get("data") if isinstance(d, dict) else d, args.conector)
        save_json(args.out, {
            "result": linhas, "registros": linhas,
            "origem": f"ARQUIVO DE TESTE ({args.resposta}) — NÃO é coleta real do Windsor",
            "simulado": True,
        })
        print(f"[windsor] MODO ARQUIVO. OK -> {args.out} ({len(linhas)} linha(s))",
              file=sys.stderr)
        return

    if not args.fonte:
        print("ERRO: informe pelo menos um --fonte CONECTOR:ENV:SAIDA\n"
              "  Ex.: --fonte google_ads:WINDSOR_KEY_GADS:../outputs/gads-keywords.json",
              file=sys.stderr)
        sys.exit(1)

    ate = args.ate or (date.today() - timedelta(days=1)).isoformat()
    desde = args.desde or (date.fromisoformat(ate) - timedelta(days=args.dias - 1)).isoformat()

    falhas = []
    for spec in args.fonte:
        partes = spec.split(":")
        if len(partes) < 3:
            print(f"ERRO: --fonte mal formado: {spec}\n"
                  "  Formato: CONECTOR:VARIAVEL_DE_AMBIENTE:ARQUIVO_DE_SAIDA", file=sys.stderr)
            sys.exit(1)
        conector, env = partes[0], partes[1]
        saida = ":".join(partes[2:])          # caminho do Windows pode ter 'C:'
        chave = os.environ.get(env)
        if not chave:
            print(f"ERRO: a variável {env} não está definida (fonte {conector}).",
                  file=sys.stderr)
            falhas.append(conector)
            continue

        preset = CAMPOS.get(conector, {})
        campos = (args.campos.split(",") if args.campos
                  else preset.get("performance") or ["date", "campaign"])
        try:
            linhas = normalizar(coletar(args.base_url, conector, chave, campos, desde, ate,
                                         args.debug_raw, conector, args.caminho), conector)
        except ErroWindsor as e:
            print(f"\nERRO em {conector}: {e}\n", file=sys.stderr)
            falhas.append(conector)
            continue

        save_json(saida, {
            "result": linhas, "registros": linhas,
            "origem": f"Windsor.ai REST ({conector}) via windsor_api.py",
            "conta_env": env, "periodo": {"desde": desde, "ate": ate},
            "coletado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        print(f"OK -> {saida} ({len(linhas)} linha(s))", file=sys.stderr)
        if not linhas:
            print("  AVISO: veio vazio. Causas comuns: janela sem veiculação, conector "
                  "conectado em OUTRA conta, ou teto do plano. NÃO estou gravando zeros.",
                  file=sys.stderr)

        # o leilão por domínio é um pedido à parte (não combina com performance)
        if conector == "google_ads" and args.leilao_out:
            try:
                leilao = normalizar(coletar(args.base_url, conector, chave,
                                             preset["leilao"], desde, ate,
                                             args.debug_raw, "google_ads/leilão",
                                             args.caminho), conector)
                save_json(args.leilao_out, {
                    "result": leilao, "registros": leilao,
                    "origem": "Windsor.ai REST (google_ads auction_insight_domain)",
                    "periodo": {"desde": desde, "ate": ate},
                })
                print(f"OK -> {args.leilao_out} ({len(leilao)} linha(s) de leilão)",
                      file=sys.stderr)
                print("  ^ esta é a tabela de domínios concorrentes que a API oficial do "
                      "Google NÃO entrega.", file=sys.stderr)
            except ErroWindsor as e:
                print(f"\nERRO no leilão: {e}\n", file=sys.stderr)
                falhas.append("google_ads/leilão")

    if falhas:
        print(f"\nTerminou com falha em: {', '.join(falhas)}", file=sys.stderr)
        sys.exit(2)
    print("\n  Confira os totais contra os painéis das plataformas antes de apresentar "
          "a alguém.", file=sys.stderr)


if __name__ == "__main__":
    main()
