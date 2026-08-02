# Token da Meta Marketing API — passo a passo

Para `scripts/meta_ads_api.py` funcionar você precisa de duas coisas: um **token
de usuário de sistema** e o **id da conta de anúncio**. Leva uns 15 minutos, é
gratuito, e **não exige Revisão de App** — revisão só é necessária para ler dados
de *terceiros*. Ler a sua própria conta usa Acesso Padrão, que já vem liberado.

## Por que usuário de sistema, e não o token fácil

O token que aparece no Explorador da API Graph expira em **1 a 2 horas**. Serve
para um teste, não para automação: no dia seguinte o coletor falharia com erro
190. O token de **usuário de sistema** não expira, e é o único caminho que faz
sentido aqui.

## 1. Ter um app Meta ligado ao seu Negócio

1. `developers.facebook.com/apps` → **Criar app** → tipo **Empresa/Business**.
2. Vincule-o ao seu Gerenciador de Negócios quando ele perguntar (precisa ser o
   mesmo Negócio que é dono da conta de anúncio — se forem diferentes, o token
   não enxerga a conta).
3. No painel do app → **Adicionar produto** → **Marketing API**.

Anote o **ID do app**; você vai escolhê-lo na hora de gerar o token.

## 2. Criar o usuário de sistema

1. `business.facebook.com/settings` → **Usuários** → **Usuários do sistema**.
2. **Adicionar** → nome (ex.: `war-room-coletor`) → função **Funcionário**
   (não precisa ser Admin, porque só vamos *ler*).
3. Com ele selecionado → **Adicionar ativos** → aba **Contas de anúncios** →
   marque a conta da Joie → permissão **Ver desempenho** (leitura basta).

Dar só leitura é deliberado: se esse token vazar, ninguém altera campanha nem
orçamento com ele.

## 3. Gerar o token

1. Ainda no usuário de sistema → **Gerar novo token**.
2. Escolha o **app** do passo 1.
3. Marque os escopos **`ads_read`** e **`read_insights`**.
4. Em validade, escolha **Nunca expira**.
5. **Copie o token na hora** — a Meta não mostra de novo. Se perder, gere outro.

## 4. Pegar o id da conta de anúncio

No Gerenciador de Anúncios, o id aparece no seletor de conta e na URL
(`act=1234567890`). O formato que o script espera é com o prefixo: `act_1234567890`.

## 5. Configurar na sua máquina

```powershell
# Windows (PowerShell) — vale só nesta janela
$env:META_ACCESS_TOKEN = "EAAG..."
$env:META_AD_ACCOUNT_ID = "act_1234567890"
```

```bash
# macOS / Linux
export META_ACCESS_TOKEN='EAAG...'
export META_AD_ACCOUNT_ID='act_1234567890'
```

**Nunca** coloque o token no `config.json` nem em qualquer arquivo do
repositório. Variável de ambiente existe para isso.

Para não redigitar a cada sessão, no Windows use
*Variáveis de Ambiente do Usuário* nas configurações do sistema; no macOS/Linux,
acrescente as duas linhas ao seu `~/.zshrc` ou `~/.bashrc`.

## 6. Primeira execução — confira antes de confiar

```bash
cd scripts
python meta_ads_api.py --dias 7 --debug-raw \
  --out ../outputs/meta-insights.json \
  --criativos-out ../outputs/meta-criativos.json
```

O `--debug-raw` imprime o primeiro item bruto de cada endpoint. **Olhe esse item**
antes de usar o resultado: a Meta muda nomes de campo entre versões da API, e é
aqui que se descobre. Depois compare o resumo que o script imprime (gasto,
impressões, cliques, compras, receita) com o Gerenciador de Anúncios no mesmo
período.

Se as **compras** divergirem, é quase sempre o `action_type`: o pixel de cada
conta reporta compra sob um nome diferente. O script tenta `omni_purchase`,
`purchase` e `offsite_conversion.fb_pixel_purchase`, nessa ordem, e **imprime qual
usou**. Se o seu for outro, ajuste `TIPOS_COMPRA` no topo de `meta_ads_api.py`.

## 7. Ligar no war room

```bash
python meta_ads_performance.py \
  --ga4-campanhas examples/ga4-real/ga4-campanhas.json \
  --plataforma ../outputs/meta-insights.json \
  --criativos ../outputs/meta-criativos.json \
  --out ../outputs/meta-ads.json

python war_room.py --config config.json \
  --meta-ads-performance-json ../outputs/meta-ads.json \
  --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
```

Repare que **não** passamos `--simulado` aqui: a partir do momento em que o dado
vem da API de verdade, o aviso de simulado sai do relatório. Enquanto você estiver
testando com as fixtures (`--resposta-insights`), o próprio arquivo de saída se
declara como teste e o `--simulado` deve continuar.

## Erros que você provavelmente vai ver

| Erro | O que é |
|---|---|
| código **190** | token expirado ou inválido. Se você usou o Explorador da API, é isso: gere um de usuário de sistema |
| código **200** / HTTP 403 | falta `ads_read`, ou o usuário de sistema não tem a conta de anúncio nos ativos |
| código **17** ou **613** | limite de uso da API. O script já espera e tenta de novo com recuo progressivo |
| "Unsupported get request" | conta sem o prefixo `act_`, ou app em Negócio diferente do dono da conta |
| erro de versão da API | suba `--versao-api` (as versões saem de suporte a cada ~2 anos) |
| respondeu, mas **zero linhas** | janela sem veiculação, ou anúncios pausados no período. O script avisa e **não grava zeros** |

## Estado de teste deste coletor

A camada de **parse e agregação foi testada** com resposta salva em arquivo
(`scripts/examples/meta-api-*-bruto.json`), cobrindo os casos que quebram parser:
número vindo como texto, conversão aninhada em `actions`, campo de gasto ausente,
zero real de cliques e anúncio sem criativo legível.

A camada **HTTP não pôde ser testada**: `graph.facebook.com` está bloqueado pela
política de rede do ambiente onde o script foi escrito (verificado, não suposto).
Por isso o `--debug-raw` existe e por isso o passo 6 pede conferência contra o
Gerenciador. Não é um script "provavelmente funciona" apresentado como pronto — é
um script cuja lógica está testada e cuja conexão precisa da sua primeira execução
para ser confirmada.
