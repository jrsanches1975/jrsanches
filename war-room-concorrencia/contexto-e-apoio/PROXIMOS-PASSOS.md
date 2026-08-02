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

## 4. Primeira coleta

**Atualizado em 2026-08-02 à noite — já processei o que você colou.** Três dos
quatro pedidos já vieram reais e estão gravados em `outputs/`:

- [x] `google_ads auction_insight_domain` (leilão por domínio) — 771 registros,
      03/07 a 31/07 → `outputs/auction-windsor.json`
- [x] `facebook` com todos os campos (impressões, CTR, CPM, gasto) — 241
      registros, 03/07 a 01/08 → `outputs/meta-insights.json`
- [x] Lado GA4 das mesmas campanhas Meta (via MCP, sem precisar de URL) →
      `outputs/ga4-campanhas-facebook.json`
- [ ] **Ainda falta:** `google_ads` por **palavra-chave** (não por campanha).
      O que você mandou foi clique/gasto agregado por campanha — a aba
      Keywords & Leilão precisa do nível de keyword para ficar 100% real:

```
fields=date,campaign,keyword_text,impressions,clicks,ctr,cpc,
       search_impression_share,search_rank_lost_impression_share,
       quality_score
```

- [ ] Rodar essa URL no painel do Windsor (conta do Google Ads) e me mandar o
      JSON, do mesmo jeito que mandou os outros três

Não precisa mais rodar `windsor_api.py` você mesmo pelas contas — continue
colando o JSON do painel do Windsor aqui que eu normalizo e gravo. O script
`windsor_api.py` só entraria em jogo se você preferir automatizar via linha de
comando mais pra frente.

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

**Sobre o ator do Apify que você estava olhando** (`karamelo/mercadolivre-scraper-brasil-portugues`,
$5/1.000 resultados): corrigi um bug que fazia `war_room.py` ignorar o ator
configurado em `config.json` — agora é de verdade trocável, sem editar código
(`apify_actors.mercado_livre` + `apify_actors_campos.mercado_livre` para os
nomes de campo, que são diferentes de ator para ator). Você pediu para testar
os dois e ficar com o que trouxer resultado mais apurado — isso eu não consigo
rodar por aqui (sem `APIFY_TOKEN` neste ambiente e sem o campo de busca real do
`karamelo` confirmado ainda).

- [ ] Rodar uma busca de teste nos dois atores (o atual e o karamelo) para o
      mesmo produto e comparar quantos concorrentes de verdade aparecem
- [ ] Se decidir pelo `karamelo`: no Input dele, clicar em **"JSON"** (ao lado
      de "Form") e me mandar o print — preciso do nome real do campo "Nome do
      produto" antes de trocar `apify_actors_campos` (nome errado não dá erro,
      só traz coleta vazia)

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
| Mercado Livre / Radar | **real** (Apify, precisa do `APIFY_TOKEN`) |
| Meta Ads (lado GA4 + lado plataforma) | **real** desde 2026-08-02 (as duas pontas — falta só rodar o comando do item 5 pra entrar no HTML/XLSX) |
| Keywords & Leilão — leilão por domínio | **real coletado** (`outputs/auction-windsor.json`), ainda não plugado na aba — falta o item 4 (keyword) pra trocar a fixture pela versão real de uma vez |
| Keywords & Leilão — por palavra-chave | simulado — falta o item 4 |
| Marketplaces (Google Shopping) | simulado |
