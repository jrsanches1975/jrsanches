# O que falta fazer — checklist do usuário

Atualizado em 2026-08-02, depois da decisão de seguir **só pelo Windsor multi-conta**.

Tudo aqui depende de acesso a contas que só você tem. Nada disso pode ser feito de
dentro de uma sessão do Claude: os hosts do Windsor, do Meta Business e do Google
Ads estão bloqueados na rede do ambiente (verificado), e token não deve trafegar por
chat.

---

## Decisão que encurtou a lista

Você criou duas contas Windsor a mais, uma por ferramenta, e escolheu seguir por
elas. Isso **cancelou** três itens que estavam pendentes:

- ~~Token de usuário de sistema da Meta~~
- ~~Developer token do Google Ads + credencial OAuth + refresh token~~
- ~~Reexportar a planilha de Auction Insights à mão~~

O último é o ganho mais interessante: o Windsor entrega `auction_insight_domain`
(a tabela de leilão por domínio concorrente), e a **API oficial do Google não
entrega** — lá é restrita a contas em allowlist. Sua escolha preservou uma
capacidade que o caminho dos coletores nativos perderia.

Os coletores nativos (`meta_ads_api.py`, `google_ads_api.py`) ficam no repositório,
testados na camada de conversão, caso você queira retomar depois. Não são
necessários agora.

---

## 1. Conectar uma fonte em cada conta Windsor

- [ ] Conta A → **GA4** (esta já está feita: é a que a integração do Claude usa)
- [ ] Conta B → **Google Ads**
- [ ] Conta C → **Meta Ads** (`facebook`)

Confirme em cada conta que o conector aparece **com a conta de anúncio associada**,
não só autorizado. Foi exatamente aí que as tentativas anteriores falharam: a
autorização parecia ter dado certo e o conector continuava sem conta.

---

## 2. Pegar a chave de API de cada conta

Cada conta Windsor tem a **sua própria** chave — é isso que faz o esquema
multi-conta funcionar. No painel do Windsor de cada conta, procure em
*Settings / API*.

- [ ] Chave da conta do Google Ads
- [ ] Chave da conta do Meta

Guarde como variável de ambiente, **nunca** em arquivo do repositório:

```powershell
# Windows (PowerShell) — vale nesta janela
$env:WINDSOR_KEY_GADS = "..."
$env:WINDSOR_KEY_META = "..."
```

```bash
# macOS / Linux
export WINDSOR_KEY_GADS='...'
export WINDSOR_KEY_META='...'
```

---

## 3. Descobrir os nomes de campo — antes de coletar

Os nomes de campo do **Google Ads** são confiáveis (vêm do `keyword_auction.py`,
que já rodou contra sua conta real). Os do **Meta** são um palpite informado meu e
**precisam ser confirmados**:

```bash
cd scripts
python windsor_api.py --listar-campos facebook --chave-env WINDSOR_KEY_META
```

- [ ] Rodar e me mandar a lista de campos que aparecer

Com ela eu ajusto o script para os nomes reais da sua conta. Se eu adivinhar
errado, a coleta traz colunas vazias — e coluna vazia num painel é pior que campo
ausente declarado.

---

## 4. Primeira coleta — CONCLUÍDA (2026-08-02)

Os quatro pedidos vieram reais e estão processados em `outputs/`:

- [x] `google_ads auction_insight_domain` (leilão por domínio) — 771 registros,
      03/07 a 31/07 → `outputs/auction-windsor.json`
- [x] `facebook` com todos os campos (impressões, CTR, CPM, gasto) — 241
      registros, 03/07 a 01/08 → `outputs/meta-insights.json`
- [x] Lado GA4 das mesmas campanhas Meta (via MCP, sem precisar de URL) →
      `outputs/ga4-campanhas-facebook.json`
- [x] `google_ads` por palavra-chave (42 keywords) → `outputs/gads-keywords.json`,
      já processado por `gerar_relatorio_keywords.py` **sem** `--simulado` em
      `outputs/keywords-relatorio.json` — a aba Keywords & Leilão já pode
      ficar 100% real na próxima vez que rodar o comando do item 5

**Dois achados na coleta de keyword, pra você saber:**

1. **Sem quebra por dia.** Toda linha veio com uma chave `"fields=date": null`
   em vez de `"date"` — sinal de que o `fields=` foi colado duas vezes na URL
   (`...&fields=fields=date,...`). Não quebra nada agora (o relatório atual
   não usa data), mas se um dia eu precisar comparar "antes x depois" por
   keyword, essa URL vai precisar ser refeita sem o `fields=` duplicado.
2. **`quality_score` fora da escala esperada** — valores reais chegaram até
   **290** (ex.: "Joie" = 290), mas a Quality Score do Google Ads é sempre
   1-10. Não consigo confirmar o que esse campo do Windsor representa de
   verdade (a conta do Google Ads não está acessível por aqui). **Não apliquei
   nenhuma correção** — gravei o valor bruto como veio.
   - [ ] Confira a coluna "Nível de qualidade" no Google Ads pra keyword
         "Joie" ou "magnésio quelato" e me diga o número real — só assim eu
         sei se o campo do Windsor é outra coisa ou se precisa de ajuste antes
         de mostrar no painel

---

### Achado no leilão que precisa da sua decisão

Comparando quantos dias cada domínio apareceu no leilão **durante** a janela de
alta de CPC (18–26/07) contra o resto do período, estes aumentaram presença
justamente nessa janela: `renovabe.com.br`, `soldiersnutrition.com.br`,
`darklabsuplementos.com.br`, `coompare.com.br`, `vivatrue.com.br` (e
`maxtitanium.com.br`, que você já rastreia). Já adicionei os cinco novos como
**candidatos** em `config.example.json` (`candidatos_concorrentes_manual`) —
não como concorrentes confirmados, porque presença no leilão é correlação, não
prova.

- [ ] Revisar os cinco e decidir se promove algum para `concorrentes[]`

**Mais importante:** `gsuplementos.com.br` aparece 51 dos 62 dias — é o
domínio mais presente depois dos marketplaces — e você já tem "Growth
Supplements" cadastrado, mas com o domínio `growthsupplements.com.br` (sem o
"row"). Pode ser a mesma empresa anunciando por um domínio diferente do que
está no cadastro.

- [ ] Confirmar se `gsuplementos.com.br` é a Growth Supplements e, se for,
      corrigir `dominio_site` em `config.example.json`/`config.json`

---

## 5. Rodar o war room na sua máquina

Se ainda não fez o primeiro uso local:

```powershell
py -m pip install openpyxl
cd scripts
copy config.example.json config.json
py servidor.py --config config.json
```

- [ ] Abrir `http://127.0.0.1:8787`
- [ ] Confirmar que a aba Seleção Manual mostra "backend conectado" (barra verde)

**Por que não gerei o HTML/XLSX final eu mesmo desta vez:** a aba de Radar do
Mercado Livre exige uma coleta ao vivo via Apify (`APIFY_TOKEN`), e esse token
não existe neste ambiente (nem deveria — é seu). Rodar sem ele com
`--simulate-ml` teria voltado essa aba de "real" para "simulado" no painel
novo, uma regressão que preferi não fazer silenciosamente. Rode este comando na
sua máquina, com seu `APIFY_TOKEN` exportado, pra juntar tudo que já está real
(inclusive o que processei agora) num painel só:

```bash
cd scripts
python war_room.py --config config.json \
  --out ../outputs/war-room.xlsx --html ../outputs/war-room.html \
  --token SEU_APIFY_TOKEN \
  --own-performance ../outputs/own-performance-por-produto.json \
  --descoberta-json ../outputs/descoberta.json \
  --keywords-relatorio-json ../outputs/keywords-relatorio.json \
  --ga4-json ../outputs/ga4-jornada.json \
  --metas-json ../outputs/metas.json \
  --meta-ads-performance-json ../outputs/meta-ads-performance.json
```

- [ ] Rodar e abrir `../outputs/war-room.html` — a aba **Meta Ads** já deve vir
      com o funil e as campanhas 100% reais (as duas pontas, GA4 e plataforma)
- [ ] `Keywords & Leilão` continua parcialmente simulada até o item 4 (keyword
      do Google Ads) chegar — o leilão por domínio dentro dela ainda é o da
      fixture de exemplo, não o real; me avise quando rodar que eu troco pela
      versão real (`outputs/auction-windsor.json`) via
      `gerar_relatorio_keywords.py`

---

## 6. Rotina automática, sem clicar em nada (2026-08-02)

Você pediu para o Radar do Mercado Livre rodar sozinho, sem esperar você abrir
o painel e clicar. Criei uma Tarefa Agendada do Windows pra isso — roda
`war_room.py` de tempos em tempos, recoletando o Mercado Livre de verdade a
cada vez.

```powershell
setx APIFY_TOKEN "apify_api_..."          # uma vez só; abra um terminal NOVO depois
cd war-room-concorrencia\deploy
.\agendar-tarefa-windows.ps1              # padrão a cada 6h
```

- [ ] Rodar os dois comandos (o `setx` só se ainda não tiver feito)
- [ ] Conferir depois de ~10 min: `outputs\rotina.log` deve mostrar uma rodada OK
- [ ] Saber a limitação: sem senha guardada na tarefa, ela só dispara com sua
      sessão do Windows aberta (computador desligado/deslogado, não roda)

**Ator do Apify trocado — `karamelo` já é o padrão (2026-08-02).** Você testou
os dois lados de verdade (saída com a busca "magnesio quelato 60 capsulas",
entrada com o print do Input em JSON) e o `karamelo/mercadolivre-scraper-brasil-portugues`
está ativado em `config.example.json`:

- [x] Bug corrigido: `war_room.py` respeita de verdade o ator configurado
- [x] Saída mapeada e testada: preço, desconto, vendedor, frete, reviews,
      link — tudo conferido contra o dado real. Ganha dois campos que o ator
      anterior não tinha: quantidade vendida estimada e selo de destaque
      ("MAIS VENDIDO" etc.)
- [x] Entrada confirmada pelo seu print: o campo é `keyword` (não
      "nomeProduto" como o rótulo sugeria). `maxPages: 2`, `maxPagesOfertas: 1`,
      `promoted: true`, `scrapeOfertas: false` foram copiados do payload que
      você testou de verdade — não um palpite
- [x] `apify_actors.mercado_livre` e `apify_actors_formato.mercado_livre` já
      trocados para `karamelo` em `config.example.json`

Falta só você copiar isso pro seu `config.json` local (se ele já existia antes
de hoje, essas chaves não vão aparecer sozinhas — precisa mesclar à mão ou
recriar a partir do `config.example.json` atualizado):

- [ ] Se seu `config.json` já existe: copie as quatro chaves novas/alteradas
      (`apify_actors.mercado_livre`, `apify_actors_campos`,
      `apify_actors_extra`, `apify_actors_formato`) do `config.example.json`
      pro seu `config.json`
- [ ] Rodar uma coleta de verdade e conferir se os concorrentes aparecem
      certinhos no Radar (mesma lógica de sempre, agora com o ator novo)
- [ ] **Em aberto, sem urgência:** `promoted: true` não trouxe nenhum item
      patrocinado no teste — se algum dia aparecer um anúncio patrocinado de
      verdade no resultado, me avise para eu confirmar se o campo funciona
      como esperado
- [ ] **Se quiser reverter:** troque `apify_actors.mercado_livre` de volta pra
      `"viralanalyzer~mercadolivre-scraper"` e `apify_actors_formato.mercado_livre`
      pra `"viralanalyzer"` — os dois juntos, o código dos dois continua pronto

---

## 7. Agentes de produto (2026-08-02)

Três agentes, pedidos por você:

**`descoberta_produtos_shopping.py`** (pronto, já rodou contra seu dado real):
decide quais produtos vigiar no Google Shopping. Já achou que a campanha real
`"Shopping - Colageno"` estava rodando sem "Colágeno" estar cadastrado como
produto — já adicionei como candidato em `config.example.json`.
- [ ] Revisar `preco_proprio`/`ticket_medio` de "Colágeno" (deixei em branco)
- [ ] Rodar você mesmo, quando quiser: `python descoberta_produtos_shopping.py
      --config config.json --own-performance-json ../outputs/own-performance-por-produto.json
      --out ../outputs/descoberta-shopping.xlsx`

**`google_shopping.py`** — **pronto, ENTRADA e SAÍDA confirmadas contra dado
real** (`damilo~google-shopping-apify`, "Google Shopping Scraper"). Você
testou os dois lados: a busca real ("magnesio quelato") confirmou
`source`/`link`/preço com sufixo "agora"; o print do JSON do Input confirmou
`query`/`country` (minúsculo)/`max_pages`/`num`. Já ativado em
`config.example.json`.
- [ ] Se seu `config.json` local já existe, copie
      `apify_actors.google_shopping` do `config.example.json` atualizado
- [ ] Rode de verdade: `python google_shopping.py --config config.json
      --token $APIFY_TOKEN --out ../outputs/google-shopping.json
      --out-proprio ../outputs/google-shopping-proprio.json --debug-raw`
- [x] Rodado — deu **0 concorrentes** nos 3 produtos (dado real: Black Skull/
      Growth Supplements não aparecem no Shopping pra esses termos). Próximo
      passo depois disso é eu ligar essa saída em `war_room.py` com flags
      dedicados (ainda não existem)

**`descoberta_termos_busca.py`** (novo, pronto, já rodou contra seu dado
real): você apontou que o termo configurado às vezes não é o "ativo" certo
("Colágeno" genérico vs "colágeno verisol" específico) — isso explica em
parte o "0 concorrentes" acima. Este agente minera as keywords REAIS do
Google Ads e recomenda o termo de mais clique/impressão por produto:
```bash
python descoberta_termos_busca.py --config config.json \
    --gads-keywords-json ../outputs/gads-keywords.json \
    --out ../outputs/descoberta-termos.xlsx
```
- [x] Já ajustei `termo_busca_ml` de "Colágeno" pra `"colágeno verisol"`
      (92 impressões/11 cliques reais) — escolhi o específico, não o de mais
      clique (`"Colageno"`, genérico, 38 cliques), pela sua indicação
- [ ] Revisar se essa escolha (específico vs volume) faz sentido pros outros
      produtos também, se algum dia o Shopping continuar sem achar
      concorrente com os termos atuais
- [ ] Rodar com o Google Shopping de novo pra "Colágeno" (o produto novo, sem
      snapshot ainda) e ver se aparece algum concorrente configurado agora

---

## 8. Aba "Agentes" no painel (2026-08-02)

Criada a aba que você pediu — mostra os 4 agentes/coletores com efeitos
especiais (a borda acende e gira quando tem achado de verdade na rodada).
Testei com Playwright, renderiza certinho nos 3 estados (aguardando dado /
sem achado / achado). De caminho, também liguei o `google_shopping.py` na
aba **Marketplaces** (antes só tinha o card na aba Agentes).

Pra ver com tudo junto, o comando agora é (adicionei 4 flags novos no final):
```powershell
py war_room.py --config config.json --out ..\outputs\war-room.xlsx --html ..\outputs\war-room.html --own-performance ..\outputs\own-performance-por-produto.json --descoberta-json ..\outputs\descoberta.json --keywords-relatorio-json ..\outputs\keywords-relatorio.json --ga4-json ..\outputs\ga4-jornada.json --metas-json ..\outputs\metas.json --meta-ads-performance-json ..\outputs\meta-ads-performance.json --descoberta-shopping-json ..\outputs\descoberta-shopping.json --descoberta-termos-json ..\outputs\descoberta-termos.json --google-shopping-json ..\outputs\google-shopping.json --google-shopping-proprio-json ..\outputs\google-shopping-proprio.json
```
- [ ] Rodar `descoberta_produtos_shopping.py` e `descoberta_termos_busca.py`
      com `--export-json` (se ainda não tiver os arquivos `descoberta-shopping.json`/
      `descoberta-termos.json` em `outputs/`)
- [ ] Rodar o comando acima e abrir `outputs\war-room.html` — clicar na aba
      **Agentes**
- [ ] Me avisar se algum card aparecer "aguardando dado" que você achava que
      já tinha rodado — pode ser só o caminho do arquivo errado no comando

---

## O que saber sobre a escolha do Windsor

Não são defeitos do script — são consequências do caminho, e é melhor você saber
antes de apresentar o painel a alguém:

- **Teto do plano Free:** limite de volume e de janela de dados. Se a coleta vier
  cortada, o script avisa em vez de gravar zeros.
- **Imagem do criativo provavelmente não vem.** Os cards da aba Meta Ads ficariam
  com texto e métricas, sem arte. Se isso importar, o único caminho é a API nativa
  da Meta (`meta_ads_api.py`, já pronto no repositório).
- **Várias contas gratuitas para contornar o limite de um plano normalmente
  contraria os termos do Windsor.** Se as contas forem fechadas, a coleta para sem
  aviso. É risco seu a assumir, mas registrado aqui para não ser surpresa.

---

## O que NÃO fazer

- **Não repointe o conector Windsor do Claude.** A conta
  `mktjoiesuplementos@gmail.com` tem a GA4, que é o que a integração MCP precisa.
  Trocar faria perder a GA4.
- **Não mande chaves nem tokens pelo chat.** Elas vivem em variável de ambiente na
  sua máquina.
- **Não coloque chave no `config.json`.**

---

## Pendência de segurança

- [ ] **Redefinir o token de desenvolvedor do Google Ads** — ele apareceu num print
      compartilhado em conversa em 2026-08-02. Com o caminho Windsor você não vai
      usá-lo, mas ele continua válido na sua conta: `ads.google.com` (MCC
      595-971-6066) → Ferramentas → Configuração → Central de API → **Redefinir
      token**.

---

## Oportunidade paralela (opcional)

O conector **Semrush** está disponível na sua organização, ainda não autenticado.
Traria palavra-chave paga e tráfego **dos concorrentes**, hoje simulados nas abas
de Keywords e Descoberta. Autentique e me avise que eu integro.

---

## Estado atual do dado no painel

| Aba | Fonte |
|---|---|
| GA4 · Jornada | **real medido** (GA4 via Windsor MCP) |
| Metas & Evolução | **real** (cruza GA4 com as metas do config) |
| Mercado Livre / Radar | **real, primeira coleta feita na sua máquina em 2026-08-02** (ator karamelo, achou a queda de preço da Black Skull) |
| Meta Ads (lado GA4 + lado plataforma) | **real** desde 2026-08-02 (as duas pontas — rode o comando do item 5 de novo pra entrar junto com o Radar no mesmo HTML/XLSX) |
| Keywords & Leilão | **real** desde 2026-08-02 (`outputs/keywords-relatorio.json`, `"simulado": false`) — `quality_score` com ressalva, ver item 4 |
| Marketplaces (Google Shopping) | simulado |

**Todas as abas de dado automatizável já são reais** — só falta Google Shopping
(sem fonte conectada ainda) e a ressalva do `quality_score` (item 4).
