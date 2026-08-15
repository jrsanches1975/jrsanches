# Credencial da GA4 Data API — passo a passo

Para `scripts/ga4_api.py` funcionar você precisa de uma **conta de serviço** do
Google Cloud com acesso de leitura à propriedade GA4. Leva uns 10 minutos, é
gratuito, e **não expira** (diferente de um token de usuário comum).

## Por que conta de serviço, e não login do Google

Conta de serviço é feita pra automação: nenhuma tela de consentimento, nenhum
"faça login de novo daqui a 1 hora". Você cria uma vez, dá acesso de Leitor à
propriedade GA4 pro e-mail dela, e pronto — funciona pra sempre (até você
revogar).

## 1. Criar um projeto no Google Cloud (se ainda não tiver um)

1. `console.cloud.google.com` → seletor de projeto no topo → **Novo Projeto**.
2. Dê um nome (ex.: `war-room-joie`) → **Criar**.

## 2. Ativar a Google Analytics Data API

1. Com o projeto selecionado, vá em **APIs e Serviços** → **Biblioteca**.
2. Busque por **"Google Analytics Data API"** → clique nela → **Ativar**.

## 3. Criar a conta de serviço

1. **APIs e Serviços** → **Credenciais** → **Criar credenciais** → **Conta de
   serviço**.
2. Nome: algo como `war-room-ga4-leitor` → **Criar e continuar**.
3. Nas telas de papel/acesso, pode pular (não precisa de papel no projeto
   Google Cloud — o acesso de verdade é dado na PRÓPRIA GA4, no passo 5) →
   **Concluído**.
4. Anote o **e-mail da conta de serviço** — algo como
   `war-room-ga4-leitor@SEU-PROJETO.iam.gserviceaccount.com`. Ele que você
   vai usar no passo 5.

## 4. Gerar a chave (o arquivo JSON)

1. Na lista de contas de serviço, clique na que você acabou de criar.
2. Aba **Chaves** → **Adicionar chave** → **Criar nova chave** → tipo
   **JSON** → **Criar**.
3. O navegador baixa um arquivo `.json` sozinho — **guarde esse arquivo fora
   do repositório do projeto** (ex.: `C:\Users\SeuUsuario\credenciais\ga4-service-account.json`).
   Ele não pode ir pro Git de jeito nenhum: é a credencial inteira.

## 5. Dar acesso de leitura à propriedade GA4

1. Entre na **GA4** (`analytics.google.com`) da conta que administra a
   propriedade da Joie.
2. **Admin** (ícone de engrenagem) → na coluna da **Propriedade** →
   **Acesso à propriedade** (Property Access Management).
3. **Adicionar usuários** (botão azul) → cole o **e-mail da conta de
   serviço** (do passo 3) → papel **Leitor** (Viewer) → **Adicionar**.

Sem esse passo, a autenticação até funciona, mas toda chamada de relatório
volta com erro de permissão — é o passo que mais gente esquece.

## 6. Pegar o ID da propriedade

No mesmo **Admin**, coluna **Propriedade** → **Detalhes da propriedade** — o
ID aparece no topo, algo como `ID da propriedade: 304174518`. É só o número,
sem o prefixo `properties/`.

## 7. Configurar na sua máquina

```powershell
# Windows (PowerShell) — vale só nesta janela
$env:GA4_SERVICE_ACCOUNT_JSON = "C:\Users\SeuUsuario\credenciais\ga4-service-account.json"
$env:GA4_PROPERTY_ID = "304174518"
```

```bash
# macOS / Linux
export GA4_SERVICE_ACCOUNT_JSON="/caminho/para/ga4-service-account.json"
export GA4_PROPERTY_ID="304174518"
```

Pra não redigitar toda vez, use `setx` no Windows (mesmo mecanismo já usado
pro `APIFY_TOKEN`):

```powershell
setx GA4_SERVICE_ACCOUNT_JSON "C:\Users\SeuUsuario\credenciais\ga4-service-account.json"
setx GA4_PROPERTY_ID "304174518"
```

Feche e abra o terminal de novo depois do `setx` — só pega em janela nova.

**Nunca** coloque o caminho (nem o conteúdo) desse arquivo dentro do
`config.json` nem de qualquer arquivo do repositório.

## 8. Primeira execução — confira antes de confiar

```bash
cd scripts
python ga4_api.py --dias 7 --debug-raw --saida-dir /tmp
```

O `--debug-raw` imprime a primeira linha crua de cada um dos 7 relatórios.
**Olhe esses números** e compare com o que a interface da GA4 mostra pro
mesmo período (Relatórios > Aquisição, Engajamento, Monetização) antes de
confiar no resultado — duas métricas merecem atenção especial:

- `itemViewEvents` (bloco funil): é o evento `view_item` — se a loja não
  dispara esse evento (ou dispara com nome diferente), vem zerado.
- `sessionDefaultChannelGroup` (bloco canais): se a conta usa uma
  agrupamento de canal CUSTOMIZADO (em vez do padrão do Google), os nomes de
  canal aqui podem não bater 1:1 com o que aparece na UI.

## 9. Ligar no war room

```bash
python ga4_api.py --dias 30 --saida-dir ../outputs

python war_room.py --config config.json \
  --ga4-json ../outputs/ga4-jornada.json \
  --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
```

(o `ga4_api.py` já roda o `ga4_jornada.py` sozinho por baixo — ele grava os 7
arquivos crus E chama a compilação final; a última linha do `ga4_api.py`
sempre imprime o comando exato do `ga4_jornada.py` caso você queira rodar de
novo só a etapa de compilação, sem chamar a API de novo.)

## Erros que você provavelmente vai ver

| Erro | O que é |
|---|---|
| `invalid_grant: account not found` | e-mail da conta de serviço errado, ou a chave é de outro projeto |
| `invalid_grant: Invalid JWT Signature` | o arquivo `.json` da chave está corrompido/incompleto — baixe de novo |
| HTTP 403 no `runReport` | a conta de serviço não tem acesso à propriedade — repita o passo 5 |
| HTTP 400 "Field ... is not a valid dimension/metric" | nome de campo mudou de versão da API — avise pra eu ajustar `CAMPO_API_PARA_LOCAL` em `ga4_api.py` |
| Todo bloco retorna `0` linhas | janela de datas sem dado (propriedade nova, ou período sem tráfego) |

## Estado de teste deste coletor

A camada de **autenticação** (JWT assinado RS256 + troca por access_token)
foi testada de ponta a ponta contra os servidores reais do Google nesta
sessão — com uma chave de teste (não uma conta real), o Google respondeu
`invalid_grant: account not found`, confirmando que a assinatura e o formato
do pedido HTTP estão corretos (só a conta não existe, que é o esperado com
uma chave fake).

A camada de **parse dos relatórios** foi testada de ponta a ponta contra um
servidor HTTP local que imita a resposta da GA4 Data API (mesmo formato
documentado: `dimensionHeaders`/`metricHeaders`/`rows`), confirmando que a
conversão pros nomes de campo que `ga4_jornada.py` espera funciona
corretamente nos 7 blocos, incluindo a reformatação de data (`20260801` →
`2026-08-01`). **Não pôde ser testada contra uma propriedade GA4 real** —
exigiria uma credencial de verdade, que este agente nunca aceita colada no
chat. Por isso o `--debug-raw` existe e por isso o passo 8 pede conferência
contra a interface da GA4 antes de confiar no resultado.
