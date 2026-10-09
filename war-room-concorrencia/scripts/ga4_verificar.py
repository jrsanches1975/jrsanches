#!/usr/bin/env python3
"""
Verificador de credencial da GA4 — roda ANTES da primeira coleta.

Confere, em ordem, as três coisas que podem estar erradas depois dos passos
4 a 7 de `references/ga4-api-setup.md`, e diz exatamente qual delas falhou:

  1. o arquivo JSON da conta de serviço existe e tem os campos certos;
  2. a credencial autentica no Google (assinatura e projeto corretos);
  3. a conta de serviço TEM acesso de leitura à propriedade GA4 — o passo
     que mais gente esquece, e que só aparece como erro na primeira chamada
     de relatório, não na autenticação.

Uso:
    python ga4_verificar.py
    python ga4_verificar.py --service-account-json /caminho/chave.json --property-id 304174518

Sai com código 0 se está tudo pronto para `ga4_api.py`; diferente de 0 com a
causa impressa, caso contrário. Nenhum dado da credencial é impresso além do
e-mail da conta de serviço (que não é segredo — é o que você cola na GA4).
"""
import argparse
import json
import os
import sys

from ga4_api import obter_access_token, run_report


def falhar(mensagem, remedio, codigo):
    print(f"\n  FALHOU: {mensagem}", file=sys.stderr)
    print(f"  O que fazer: {remedio}", file=sys.stderr)
    sys.exit(codigo)


def main():
    ap = argparse.ArgumentParser(description="Confere se a credencial da GA4 está pronta para coletar.")
    ap.add_argument("--service-account-json", default=os.environ.get("GA4_SERVICE_ACCOUNT_JSON"))
    ap.add_argument("--property-id", default=os.environ.get("GA4_PROPERTY_ID"))
    args = ap.parse_args()

    print("Verificando a credencial da GA4...\n")

    # 1. variáveis e arquivo
    print("  [1/3] arquivo da conta de serviço", end=" ... ", flush=True)
    if not args.service_account_json:
        falhar("GA4_SERVICE_ACCOUNT_JSON não está definida.",
               "rode o script de configuração (deploy/configurar-ga4.ps1 no Windows, "
               "deploy/configurar-ga4.sh no macOS/Linux) ou passe --service-account-json.", 1)
    if not args.property_id:
        falhar("GA4_PROPERTY_ID não está definida.",
               "pegue o ID numérico em GA4 > Admin > Detalhes da propriedade (só o número).", 1)
    if not os.path.exists(args.service_account_json):
        falhar(f"arquivo não encontrado: {args.service_account_json}",
               "confira o caminho; o arquivo é o JSON baixado em Contas de serviço > Chaves.", 1)
    try:
        with open(args.service_account_json, encoding="utf-8") as f:
            service_account = json.load(f)
    except json.JSONDecodeError as exc:
        falhar(f"o arquivo não é um JSON válido ({exc}).",
               "baixe a chave de novo — o download pode ter vindo incompleto.", 1)
    faltando = [c for c in ("client_email", "private_key", "token_uri") if c not in service_account]
    if faltando:
        falhar(f"o JSON não tem o(s) campo(s): {', '.join(faltando)}.",
               "esse não é o arquivo de chave de conta de serviço. Baixe em "
               "Google Cloud > IAM e admin > Contas de serviço > sua conta > Chaves > JSON.", 1)
    email = service_account["client_email"]
    print("ok")
    print(f"        conta de serviço: {email}")

    # 2. autenticação
    print("  [2/3] autenticação no Google", end=" ... ", flush=True)
    access_token, err = obter_access_token(service_account)
    if err:
        texto = str(err)
        if "account not found" in texto:
            remedio = ("a conta de serviço não existe mais, ou a chave é de outro projeto. "
                       "Confira o projeto no Google Cloud e gere uma chave nova.")
        elif "Invalid JWT Signature" in texto:
            remedio = "o arquivo da chave está corrompido — baixe de novo."
        else:
            remedio = ("confira se a Google Analytics Data API está ATIVADA no projeto "
                       "(APIs e Serviços > Biblioteca > Google Analytics Data API > Ativar).")
        falhar(f"o Google recusou a credencial: {texto}", remedio, 2)
    print("ok")

    # 3. acesso à propriedade — o passo 5 do guia
    print(f"  [3/3] acesso de leitura à propriedade {args.property_id}", end=" ... ", flush=True)
    resposta, err = run_report(access_token, args.property_id, [], ["sessions"],
                               "7daysAgo", "yesterday", limit=1)
    if err:
        texto = str(err)
        if "403" in texto or "PERMISSION_DENIED" in texto:
            falhar("a conta de serviço autenticou, mas não tem acesso à propriedade (HTTP 403).",
                   f"na GA4 > Admin > Acesso à propriedade > Adicionar usuários, cole "
                   f"{email} com o papel Leitor. É o passo 5 do references/ga4-api-setup.md.", 3)
        if "404" in texto or "NOT_FOUND" in texto:
            falhar(f"a propriedade {args.property_id} não foi encontrada (HTTP 404).",
                   "confira o ID em GA4 > Admin > Detalhes da propriedade — é só o número, "
                   "sem 'properties/' e sem o 'G-' do fluxo de dados.", 3)
        falhar(f"a chamada de relatório falhou: {texto}",
               "me mande essa mensagem que eu ajusto o coletor.", 3)
    print("ok")

    linhas = resposta.get("rows") or []
    sessoes = linhas[0]["metricValues"][0]["value"] if linhas else "0"
    print(f"        últimos 7 dias: {sessoes} sessões")
    if not linhas or sessoes in ("0", "0.0"):
        print("\n  AVISO: a credencial funciona, mas a propriedade não retornou sessões nos "
              "últimos 7 dias.\n  Pode ser propriedade nova, sem tráfego, ou o ID de outra "
              "propriedade. Confira na interface da GA4 antes de seguir.")

    print("\nTudo pronto. Próximo passo (primeira coleta, para conferência):")
    print("    python ga4_api.py --dias 7 --debug-raw --saida-dir /tmp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
