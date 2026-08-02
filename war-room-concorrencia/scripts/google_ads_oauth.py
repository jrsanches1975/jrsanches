#!/usr/bin/env python3
"""
Gera o REFRESH TOKEN do Google Ads. É o passo mais chato da configuração, e este
utilitário existe para você não ter que fazer curl à mão nem instalar o SDK.

Rode na SUA máquina (precisa abrir o navegador e receber o retorno em localhost):

    export GOOGLE_ADS_CLIENT_ID='....apps.googleusercontent.com'
    export GOOGLE_ADS_CLIENT_SECRET='...'
    python google_ads_oauth.py

Ele imprime um link, você autoriza no navegador, e ele imprime o refresh token.

POR QUE NÃO DÁ PARA FAZER ISSO POR AQUI: o fluxo exige um navegador logado na SUA
conta Google e um retorno em `http://localhost`. Nenhuma das duas coisas existe
num ambiente remoto — e o token não deve trafegar por chat de todo modo.

NOTA SOBRE O MODO 'TESTE': se a tela de consentimento do seu app OAuth estiver
como "Teste", o refresh token **expira em 7 dias** e a coleta quebra sozinha
depois disso. Publique o app (Console de APIs > Tela de permissão OAuth >
Publicar) para o token virar permanente. É o erro mais comum nessa etapa.
"""
import argparse
import http.server
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request

ESCOPO = "https://www.googleapis.com/auth/adwords"
URL_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
URL_TOKEN = "https://oauth2.googleapis.com/token"

recebido = {}


class Retorno(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        recebido["code"] = (q.get("code") or [None])[0]
        recebido["state"] = (q.get("state") or [None])[0]
        recebido["error"] = (q.get("error") or [None])[0]
        corpo = ("<h2>Pronto.</h2><p>Pode fechar esta aba e voltar ao terminal.</p>"
                 if recebido["code"] else
                 f"<h2>Falhou</h2><p>{recebido.get('error') or 'sem código'}</p>").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *a):
        pass          # não poluir o terminal com log de request


def main():
    ap = argparse.ArgumentParser(description="Obtém o refresh token do Google Ads.")
    ap.add_argument("--client-id", default=os.environ.get("GOOGLE_ADS_CLIENT_ID"))
    ap.add_argument("--client-secret", default=os.environ.get("GOOGLE_ADS_CLIENT_SECRET"))
    ap.add_argument("--porta", type=int, default=8899,
                     help="porta local que recebe o retorno do Google (padrão 8899). "
                          "Ela precisa estar cadastrada como URI de redirecionamento "
                          "autorizado na sua credencial OAuth.")
    args = ap.parse_args()

    if not (args.client_id and args.client_secret):
        print("ERRO: exporte GOOGLE_ADS_CLIENT_ID e GOOGLE_ADS_CLIENT_SECRET "
              "(ou passe --client-id/--client-secret).\n"
              "  Como criar: references/google-ads-api-setup.md", file=sys.stderr)
        sys.exit(1)

    redirect = f"http://localhost:{args.porta}"
    estado = secrets.token_urlsafe(16)
    params = {
        "client_id": args.client_id,
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": ESCOPO,
        "access_type": "offline",       # sem isto NÃO vem refresh token
        "prompt": "consent",            # força vir refresh token mesmo se já autorizou antes
        "state": estado,
    }
    url = f"{URL_AUTH}?" + urllib.parse.urlencode(params)

    # o socket já fica escutando a partir do construtor, então o retorno do Google
    # espera na fila até handle_request() atendê-lo. Uma thread aqui seria pior que
    # inútil: ela atenderia o primeiro retorno e o handle_request() de baixo
    # ficaria esperando um segundo que nunca chega.
    servidor = http.server.HTTPServer(("127.0.0.1", args.porta), Retorno)

    print("\n1) Abra este link no navegador (logado na conta que tem acesso ao Google Ads):\n")
    print(f"   {url}\n")
    print(f"2) Autorize. O Google vai redirecionar para {redirect} e este script continua.")
    print("   Se der erro de 'redirect_uri_mismatch', cadastre exatamente "
          f"{redirect} como URI de redirecionamento autorizado na credencial OAuth.\n")
    print("Aguardando o retorno do Google…", file=sys.stderr)

    try:
        servidor.handle_request()
    except KeyboardInterrupt:
        print("\ncancelado", file=sys.stderr)
        sys.exit(1)

    if recebido.get("error"):
        print(f"\nERRO: o Google recusou a autorização: {recebido['error']}", file=sys.stderr)
        sys.exit(2)
    if not recebido.get("code"):
        print("\nERRO: não recebi o código de autorização.", file=sys.stderr)
        sys.exit(2)
    # state protege contra alguém induzir o seu navegador a completar um fluxo alheio
    if recebido.get("state") != estado:
        print("\nERRO: o 'state' devolvido não corresponde ao enviado — fluxo abortado "
              "por segurança. Rode de novo.", file=sys.stderr)
        sys.exit(2)

    dados = urllib.parse.urlencode({
        "code": recebido["code"],
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
    }).encode()
    req = urllib.request.Request(URL_TOKEN, data=dados,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            tok = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"\nERRO ao trocar o código pelo token: {e.read().decode()[:300]}", file=sys.stderr)
        sys.exit(2)

    refresh = tok.get("refresh_token")
    if not refresh:
        print("\nERRO: o Google não devolveu refresh_token. Isso acontece quando a conta já "
              "autorizou este app antes. Revogue o acesso em "
              "myaccount.google.com/permissions e rode de novo.", file=sys.stderr)
        sys.exit(2)

    print("\n" + "─" * 70)
    print("REFRESH TOKEN (guarde como variável de ambiente, nunca em arquivo do repo):\n")
    print(f"   {refresh}\n")
    print("Windows (PowerShell):")
    print(f'   $env:GOOGLE_ADS_REFRESH_TOKEN = "{refresh}"')
    print("\nmacOS / Linux:")
    print(f"   export GOOGLE_ADS_REFRESH_TOKEN='{refresh}'")
    print("─" * 70)
    print("\nSe a tela de consentimento do seu app estiver em modo 'Teste', este token "
          "expira em 7 DIAS. Publique o app para ele virar permanente.")


if __name__ == "__main__":
    main()
