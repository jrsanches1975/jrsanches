# Credenciais da Google Ads API — passo a passo

São **cinco** valores. Mais burocrático que a Meta, e um dos passos é **assíncrono
(dias de espera)** — comece por ele.

| Variável | De onde vem |
|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Centro de API do Google Ads (**exige aprovação**) |
| `GOOGLE_ADS_CLIENT_ID` | Console de APIs do Google Cloud |
| `GOOGLE_ADS_CLIENT_SECRET` | idem |
| `GOOGLE_ADS_REFRESH_TOKEN` | gerado por `scripts/google_ads_oauth.py` |
| `GOOGLE_ADS_CUSTOMER_ID` | id da conta no Google Ads, só dígitos |

## 1. Developer token

**Se você já tem um token com nível atribuído no Centro de API, pule para o passo 2.**
O caso da Joie (verificado em 2026-08-02): MCC `595-971-6066`, nível
**"Acesso às Análises"**, dados de desenvolvedor já preenchidos — nada pendente.

Se o nível alcança contas de produção, só se descobre executando: a documentação
pública é inconsistente sobre esse nível. Rode o coletor; se vier
`403 — DEVELOPER_TOKEN_NOT_APPROVED`, aí sim peça elevação de nível e aguarde a
análise. O coletor traduz esse erro com o caminho exato.

### Se você ainda NÃO tem token (a espera é de dias)

1. Entre em `ads.google.com` com a **conta gerenciadora (MCC)**. O Centro de API
   **só aparece em conta MCC** — se você só tem conta comum, crie uma MCC em
   `ads.google.com/home/tools/manager-accounts` e vincule a conta da Joie a ela.
2. Ferramentas e Configurações → Configuração → **Centro de API**.
3. Preencha o formulário. Você recebe na hora um token com **Acesso de Teste**,
   que só funciona em contas de teste — **não serve** para ler a conta real.
4. Solicite o **Acesso Básico**. É aqui que entra a análise do Google, que leva
   **de alguns dias a algumas semanas**. Enquanto não sair, o coletor vai
   responder erro 403.

Descreva o uso com honestidade no formulário (relatório interno de desempenho das
próprias campanhas, sem revenda de dados) — pedido vago é o que mais leva a
indeferimento.

## 2. Projeto no Google Cloud e credencial OAuth

1. `console.cloud.google.com` → criar projeto (ou usar um existente).
2. APIs e Serviços → **Ativar APIs** → ative a **Google Ads API**.
3. **Tela de permissão OAuth**: tipo Externo, preencha o básico.
   **Publique o app.** Se ficar em modo "Teste", o refresh token **expira em 7
   dias** e a coleta quebra sozinha na semana seguinte. É o erro mais comum
   nesta etapa.
4. Credenciais → Criar credenciais → **ID do cliente OAuth** → tipo
   **App para computador**.
5. Em **URIs de redirecionamento autorizados**, adicione exatamente:
   `http://localhost:8899`
   (é a porta padrão do utilitário do passo 3; se usar outra, cadastre a mesma).
6. Copie o **ID do cliente** e a **Chave secreta**.

## 3. Refresh token

```bash
export GOOGLE_ADS_CLIENT_ID='....apps.googleusercontent.com'
export GOOGLE_ADS_CLIENT_SECRET='...'

cd scripts
python google_ads_oauth.py
```

Ele imprime um link; você autoriza no navegador logado na conta que tem acesso ao
Google Ads; ele imprime o refresh token e as linhas prontas para exportar.

Isso **precisa** rodar na sua máquina: o fluxo exige navegador logado na sua conta
e retorno em `localhost`. Não é limitação do script.

## 4. Customer ID

No Google Ads, canto superior direito: `123-456-7890`. Use **só os dígitos**:
`1234567890`. Se você acessa a conta através da MCC, exporte também o id da MCC:

```bash
export GOOGLE_ADS_LOGIN_CUSTOMER_ID='0987654321'
```

Sem isso, acesso via gerenciadora responde 403.

## 5. Coletar

```bash
cd scripts
python google_ads_api.py --dias 30 --debug-raw \
    --keywords-out ../outputs/gads-keywords.json \
    --campanhas-out ../outputs/gads-campanhas.json
```

Use `--debug-raw` na primeira vez e confira os totais contra a interface do Google
Ads no mesmo período. Depois, para o relatório de keywords do war room:

```bash
python gerar_relatorio_keywords.py --keywords-json ../outputs/gads-keywords.json \
    --config config.json --out ../outputs/relatorio-keywords.xlsx \
    --export-json ../outputs/keywords-relatorio.json
```

## O que a API NÃO entrega — e o que fazer

**Auction Insights por domínio** (aquela tabela com vhita.com.br,
mercadolivre.com.br, participação de impressões, sobreposição, taxa de posição
superior) **não existe na API pública.** É liberada apenas para contas em
allowlist, via representante do Google. Não há como automatizar sem isso.

O caminho que funciona:

1. No Google Ads: Insights e relatórios → **Auction Insights** → exportar.
2. Importe: `python sheets_import.py --entrada leilao.csv --tipo leilao --campanha "Brand." --out ../outputs/auction.json`
3. Use no relatório: `gerar_relatorio_keywords.py --auction-json ../outputs/auction.json`

**Ao exportar, cuidado com o separador decimal** — foi exatamente aí que a
planilha anterior se corrompeu (export em inglês colado em planilha pt-BR
transformou `0.1408` em `1408`). Exporte com a conta em Português, ou use
*Arquivo > Importar* no Sheets em vez de colar. O `sheets_import.py` recusa o
arquivo se detectar taxa acima de 100%.

**Parcela de impressões** (`search_impression_share` e as perdidas por orçamento e
por classificação) **está** disponível na API — essa parte é automática.

## Erros que você provavelmente vai ver

| Erro | O que é |
|---|---|
| `invalid_client` | CLIENT_ID ou CLIENT_SECRET errado, ou de outro projeto |
| `invalid_grant` | refresh token revogado, de outro client_id, ou app em modo Teste (expira em 7 dias) |
| **403** | developer token ainda sem Acesso Básico aprovado, ou falta `login-customer-id` ao acessar via MCC |
| **401** | access token expirou (o script renova sozinho a cada execução) |
| **404** | versão da API retirada — suba `--versao-api` |
| `redirect_uri_mismatch` | a porta do utilitário não está cadastrada na credencial OAuth |
| campo recusado | o script tenta de novo sem o campo e **avisa qual caiu**; ele sai como n/d, não como zero |

## Estado de teste deste coletor

Diferente do coletor da Meta, aqui a **camada HTTP pôde ser testada**:
`googleads.googleapis.com` e `accounts.google.com` respondem do ambiente onde o
script foi escrito. Verificado com credencial inválida contra a API real que o
erro do Google chega traduzido e específico.

Também sondado ao vivo quais versões existem: **v15 a v19 já retornam 404**
(retiradas); **v20 em diante respondem**. O padrão é `v22`.

A camada de conversão foi testada com resposta salva em
`scripts/examples/gads-api-keywords-bruto.json`, cobrindo o que quebra parser em
proto3-JSON: **camelCase** (`costMicros`, não `cost_micros`), int64 vindo como
**string**, dinheiro em **micros**, campo ausente virando `None` (não zero) e zero
real preservado.

O que falta é a sua primeira execução com credencial válida, para confirmar os
nomes de campo da sua conta.
