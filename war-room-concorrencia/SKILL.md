---
name: war-room-concorrencia
description: >
  Sala de guerra (war room) de monitoramento competitivo: acompanha mudanças de preço e
  desconto dos concorrentes por canal (foco Mercado Livre, com preço próprio como
  referência), e sinais de aumento de investimento em ads (Google, Meta e Mercado Livre
  Ads). A cada mudança relevante, classifica severidade, estima o impacto na concorrência
  e no volume de vendas, recomenda a estratégia imediata de resposta e lista os KPIs de
  marketing digital afetados. Gera alerta em console, tracker histórico em .xlsx e um
  dashboard HTML tipo "war room". Use SEMPRE que o usuário pedir uma "war room" ou "sala
  de guerra" de concorrência, "monitorar preço do concorrente", "me avise quando o
  concorrente baixar o preço/lançar desconto", "concorrente aumentou o investimento em
  ads", "battle card" ou "ferramenta de batalha" de concorrência digital, ou pedir para
  saber o impacto/estratégia quando o concorrente mexe em preço ou mídia — mesmo sem citar
  o nome do skill. Diferente do radar-keywords-concorrentes (achar quem pega carona no
  nome da marca) e do brand-bidding-monitor (achar quem dá lance pago no nome da marca):
  este skill acompanha os PRÓPRIOS concorrentes já conhecidos e decide a reação tática.
---

# War Room de Concorrência

Esta skill é a "sala de guerra" tática: dado um conjunto de concorrentes já conhecidos
(não é para descobrir quem eles são — isso é `radar-keywords-concorrentes` e
`brand-bidding-monitor`), ela acompanha **preço, desconto e sinais de investimento em
mídia** desses concorrentes ao longo do tempo e, a cada mudança, entrega o pacote
completo: severidade, impacto competitivo, impacto estimado no volume, estratégia
imediata e os KPIs de marketing digital afetados.

## A verdade sobre "instantâneo" e sobre "investimento em ads" — diga isto antes de prometer

Duas expectativas do pedido original precisam de calibração honesta antes de rodar algo:

1. **"Instantâneo" não existe via scraping.** Não há webhook público de concorrente
   avisando quando ele muda preço ou liga uma campanha. O que existe é **polling**: rodar
   o monitor em intervalos (ex.: a cada 2–6h) e alertar assim que uma rodada encontra
   diferença em relação à anterior. Trate "instantâneo" como "no próximo ciclo de
   verificação" — agende com a skill `/loop` ou com `CronCreate` (ver seção
   "Agendamento" abaixo). Quanto menor o intervalo, mais perto de tempo real, mas mais
   chamadas de API/scraping consome.

2. **Gasto real de ads (R$ investido) do concorrente NÃO é dado público — em nenhuma
   plataforma.** Google Ads e Meta Ads não expõem o orçamento de terceiros. O que dá
   para capturar são **sinais substitutos (proxies) de variação de investimento**:
   - **Mercado Livre**: posição/frequência com que o anúncio do concorrente aparece na
     busca do termo, e se ele está entre os primeiros resultados (Mercado Ads
     patrocinado costuma ocupar o topo). Isso É automatizável (mesma infra do
     `radar-keywords-concorrentes`).
   - **Google Ads Transparency Center** e **Meta Ad Library**: são públicos e gratuitos,
     mas indexam por **anunciante**, não por keyword, e mostram os anúncios **ativos**,
     não o valor gasto (exceto ads políticos/de questão social no Meta). Contar quantos
     anúncios ativos um concorrente tem nesses painéis, e ver esse número crescer ao
     longo do tempo, é um proxy honesto de "aumento de investimento" — não é o gasto em
     si. Hoje isso é **captura manual/semi-automatizada** (ver
     `references/fontes-e-limitacoes.md`): o script tem um modo `--ads-manual` que
     recebe essa contagem (preenchida por quem olhou os painéis) e faz o diff ao longo
     do tempo, do mesmo jeito que faz com preço.

   **Nunca afirme "o concorrente X aumentou o investimento em Y%"** — isso não é
   mensurável sem acesso à conta dele. Diga sempre "sinal de aumento de atividade/
   visibilidade paga", com o número de anúncios ativos observados como evidência.

Leia `references/fontes-e-limitacoes.md` para o detalhe completo por canal antes de
prometer cobertura ao usuário.

## Pré-requisitos

- **Token Apify** (para a coleta de preço/desconto no Mercado Livive). Exporte
  `APIFY_TOKEN` no ambiente ou passe `--token`. **Nunca** grave um token real dentro de
  `config.json` neste repositório — ele vai para o Git. Use variável de ambiente.
- `openpyxl` para o tracker `.xlsx` (já disponível no ambiente).
- Concorrentes e produtos já mapeados (nome do seller no Mercado Livre, termo de busca).
  Se ainda não sabe quem monitorar, rode primeiro `radar-keywords-concorrentes` ou
  `brand-bidding-monitor` para identificar os concorrentes antes de configurar esta skill.
- **Opcional, para o passo 5 (desempenho próprio):** conector Windsor.ai conectado
  (Google Ads no mínimo; Meta/GA4 se quiser incluir também). Sem isso, a skill funciona
  normalmente — só fica sem a calibração por dado real.

## Fluxo de trabalho

### 1. Configure `scripts/config.json`

Copie `scripts/config.example.json`, preencha com o usuário:

- `marca`, `produtos_monitorados` (nome, `termo_busca_ml`, preço/ticket médio próprio —
  necessário para comparar o preço do concorrente contra o seu).
- `concorrentes`: nome, `sellers_ml` (nicknames que aparecem no Mercado Livre — pode
  ter mais de um), `dominio_site`, `meta_page` e `google_advertiser` (nomes usados para
  montar os links de checagem manual do Ad Library / Ads Transparency Center).
- `limiares`: os cortes de severidade (queda de preço leve/moderada/agressiva, salto de
  posição, crescimento de reviews, aumento mínimo de anúncios ativos). Vêm com defaults
  sensatos; calibre com o usuário na primeira rodada.
- `elasticidade_estimada`: premissa de elasticidade-preço cruzada usada **apenas** para
  o cálculo de impacto estimado no volume — é uma estimativa configurável, não um dado
  medido. Se o usuário tiver dado histórico melhor, ajuste aqui.

### 1b. Alternativa visual: painel de seleção de produtos (`gerar_painel_produtos.py`)

Em vez de editar `produtos_monitorados`/`produtos_candidatos_manual` direto no JSON,
gere um painel HTML self-contained (sem backend, mesmo estilo cockpit/HUD do resto do
projeto) onde dá para ligar/desligar cada produto, editar nome/termo de busca/preço,
adicionar um produto novo ou remover um do catálogo:

```bash
python gerar_painel_produtos.py --config config.json --out ../outputs/painel-produtos.html
```

Cada produto aparece com um interruptor: ligado = vai para `produtos_monitorados`
(o monitor de preço/visibilidade do Mercado Livre roda pra ele); desligado = vira
`produtos_candidatos_manual` (o motor de descoberta ainda considera, mas o monitor de
preço não roda). Como não há servidor, o painel não grava nada sozinho — depois de
mexer nos toggles/campos, clique em **"Exportar config.json atualizado"** (baixa um
`config.json` novo, com o resto da configuração preservado e só
`produtos_monitorados`/`produtos_candidatos_manual` recalculados) ou em
**"Copiar JSON"** como alternativa. Salve o arquivo baixado por cima do seu
`scripts/config.json` e rode `war_room.py` normalmente na próxima rodada.

### 2. Rode o monitor

```bash
cd scripts
python war_room.py --config config.json --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
```

Primeira rodada = linha de base (sem diffs ainda, só o snapshot). Da segunda em diante,
o script compara com o snapshot salvo em `scripts/history/<marca>-snapshot.json` e
gera alertas para o que mudou.

Para incluir os sinais manuais de ads (Meta Ad Library / Google Ads Transparency /
Mercado Ads), preencha `scripts/ads-manual-example.json` (copie para `ads-manual.json`)
depois de checar os painéis pelos links que o script imprime, e rode com:

```bash
python war_room.py --config config.json --ads-manual ads-manual.json \
  --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
```

Flags úteis: `--produtos "Whey Silk Protein,HePro"` (limita a coleta), `--per-produto N`
(itens buscados por produto no ML, default 15).

### 3. Leia e aja sobre os alertas

O script imprime no console um **banner de alerta** para cada mudança de severidade
alta, e grava:

- `outputs/war-room.xlsx` — abas: **Alertas** (log histórico acumulado de toda mudança
  detectada, com severidade, impacto, estratégia e KPIs), **Battlecards** (o pacote
  completo de cada alerta da rodada atual, pronto para levar pra reunião), **Preços
  Atuais** (snapshot bruto desta rodada), **Ads (manual)** (se fornecido) e
  **Limitações**.
- `outputs/war-room.html` — dashboard visual tipo "war room", cartões coloridos por
  severidade, pensado para publicar como Artifact e deixar aberto monitorando.
- `scripts/history/alerts.json` — os mesmos alertas em JSON estruturado, para você (o
  agente) consumir programaticamente: por exemplo, para cada alerta de severidade alta,
  redigir um rascunho de e-mail de alerta via Gmail MCP, ou postar num canal.

Ao apresentar ao usuário: publique o HTML como Artifact (dashboard "war room" de
verdade, visual) e entregue o `.xlsx` como arquivo para a equipe usar/arquivar.

### 4. Agendamento — como chegar perto de "instantâneo"

Esta skill não roda sozinha em background; quem agenda é a sessão do Claude Code:

- Uso pontual/curto prazo: `/loop` rodando este comando a cada N minutos/horas.
- Recorrente de verdade: `CronCreate` com o comando do passo 2, em um intervalo definido
  com o usuário (sugestão default em `cadencia_sugerida_horas` no config — comece
  conservador, ex. a cada 6h, para não estourar o saldo Apify).
- Em cada execução agendada, leia `scripts/history/alerts.json`: se houver alerta de
  severidade **alta**, avise o usuário imediatamente (mensagem direta, ou rascunho de
  e-mail via Gmail MCP) em vez de esperar o usuário puxar o relatório.

### 5. Enriquecer com desempenho próprio real (Google Ads / Meta Ads / GA4, via Windsor.ai)

Isto é o que transforma o "impacto estimado no volume" de um chute em algo calibrado
com dado de verdade. O script não coleta Google Ads/Meta/GA4 sozinho — quem faz isso é
você (o agente), usando o MCP do **Windsor.ai** (já traz Google Ads/Meta/GA4/300+
conectores):

1. Confirme quais contas estão conectadas: `mcp__Windsor_ai__get_connectors`. Se faltar
   Meta ou GA4, gere o link de autorização com
   `mcp__Windsor_ai__get_connector_connect_info` (connector `facebook` / `googleanalytics4`)
   e peça para o usuário clicar — é OAuth, não dá para autorizar por ele.
   **Atenção com plano Free do Windsor.ai:** já aconteceu de conectar um conector novo
   "empurrar" outro pra fora (o Google Ads caiu quando GA4 foi autorizado). Depois de
   qualquer nova autorização, rode `get_connectors` de novo e confira se os conectores
   que já funcionavam continuam com `accounts` preenchido antes de seguir.
2. Descubra os campos certos com `get_fields` (não adivinhe IDs) e puxe os dados com
   `get_data`. Para Google Ads/Meta: `fields: ["date","campaign","impressions","clicks",
   "spend","conversions","conversions_value"]`. Para GA4 (não tem gasto/impressão —
   é sessão/engajamento): `fields: ["date","campaign","source","medium","sessions",
   "engaged_sessions","conversions","transactions"]`, `date_preset: "last_30d"`. Se o
   retorno estourar o limite de tokens, agregue com jq/python no arquivo salvo em vez de
   pedir tudo de novo.
3. Grave o retorno bruto num JSON `{"connector": "google_ads"|"facebook"|"googleanalytics4",
   "registros": [...]}` (um arquivo por conector) e rode:
   ```bash
   python own_performance.py --input google-ads-30d.json --input ga4-30d.json \
     --config config.json --out ../outputs/own-performance-por-produto.json
   ```
   Isso agrega por campanha e casa com `produtos_monitorados[].campanhas_google_ads` /
   `campanhas_meta_ads` do config — o GA4 tenta casar contra os dois (a sessão chega com
   o nome de campanha de qualquer canal pago que a originou, então dá pra enxergar
   conversão/engajamento do Meta via UTM mesmo sem o conector do Meta Ads conectado). O
   script avisa quais campanhas não casaram, para você ajustar o config.
4. Rode o `war_room.py` passando `--own-performance ../outputs/own-performance-por-produto.json`
   junto dos outros argumentos. Isso faz três coisas: (a) enriquece o texto de impacto
   estimado nos alertas de preço com o CPA/ROAS/CTR reais do produto; (b) adiciona a aba
   **Desempenho Próprio** no xlsx (agora com colunas GA4: sessões, engajamento,
   conversão); (c) adiciona uma faixa de gauges reais no topo do dashboard HTML, com uma
   seção GA4 separada quando disponível.

**Automação de verdade (rodando sem precisar de você acionar):** o Windsor.ai tem
destinos nativos (Google Sheets, BigQuery, Postgres etc. — ver `get_destinations`) com
agendamento próprio (`hourly`/`daily`/`15_min`/`30_min`), que rodam no lado do
Windsor.ai, independente da sessão do Claude Code. Isso é preferível a montar isso no
**Make.com**: não há conector de Make instalado nesta conta, então qualquer automação
lá exigiria montar o cenário manualmente no site do Make e colar as credenciais — o
Windsor.ai já está autenticado aqui e resolve o mesmo problema sem essa camada extra.
Se o usuário já tiver Make e preferir usá-lo mesmo assim, ofereça montar o blueprint
(JSON do cenário) para ele importar, deixando claro que a ativação final é manual, do
lado dele.

Para criar o destino: `get_destination_setup_info(destination_type="googlesheets")` dá
o `setup_url` (o usuário autoriza uma vez) e os `target_fields`/`schedule_types`; depois
disso, `create_destination_task` grava a tarefa recorrente. Uma vez com a planilha
alimentada automaticamente, o Google Drive (já conectado) permite ler o arquivo em
qualquer sessão futura e alimentar o `own_performance.py` sem precisar rechamar
`get_data` toda vez.

### 6. Automatizar Meta Ad Library, Google Ads Transparency Center e Google Trends (beta) + análise de criativo

Isto substitui a captura manual do `--ads-manual` (passo 4) por coleta automática via
Apify — com uma ressalva séria que precisa ser dita **antes** de rodar:

**Esta sessão de trabalho pode estar com o acesso à rede bloqueado para esses hosts**
(política de egress da organização — já aconteceu: `api.apify.com`,
`facebook.com`, `adstransparency.google.com` e `trends.google.com` retornaram 403 de
política ao testar). Antes de prometer que vai rodar, teste com uma chamada pequena;
se vier 403 de CONNECT, **não tente contornar** — avise o usuário que esta sessão não
alcança esses hosts e que a execução real precisa acontecer num ambiente com acesso
(a máquina do usuário, outro ambiente do Claude Code, um cron fora deste sandbox).

Os três scripts abaixo (`meta_ads.py`, `google_ads_transparency.py`,
`google_trends.py`) usam actors do Apify **escolhidos por pesquisa** (nome real,
existem no Apify Store), mas o **schema de input/output NÃO foi confirmado por uma
chamada real** — ao contrário do actor de Mercado Livre (testado e documentado no
`radar-keywords-concorrentes`). Isso é diferente de inventar dados: os actors existem
de verdade, só falta calibrar o parser no primeiro uso real. Fluxo:

1. Rode com `--debug-raw` na primeira execução real (fora deste sandbox, onde há
   rede): o script imprime o primeiro item bruto retornado por concorrente/termo.
2. Compare com `CAMPOS_ESPERADOS` no topo do script. Se os nomes não baterem, ajuste
   `extrair_campos()` (ou troque o actor em `config["apify_actors"]` por uma das
   alternativas abaixo — a chamada em si, via `apify_common.apify_run`, é genérica e
   não muda).
3. Depois de calibrado, roda normal:
   ```bash
   python meta_ads.py --config config.json --history-dir ../outputs/demo-history \
     --out ../outputs/meta-ads-novos.json
   python google_ads_transparency.py --config config.json --history-dir ../outputs/demo-history \
     --out ../outputs/google-ads-transparency-novos.json
   python google_trends.py --config config.json --history-dir ../outputs/demo-history \
     --out ../outputs/trends-alertas.json
   python war_room.py --config config.json --meta-ads-json ../outputs/meta-ads-novos.json \
     --google-ads-transparency-json ../outputs/google-ads-transparency-novos.json \
     --trends-json ../outputs/trends-alertas.json --own-performance ../outputs/own-performance-por-produto.json \
     --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
   ```
   Cada um detecta **anúncio novo** (não visto na rodada anterior) por diff de ID —
   isso é o pedido de "monitorar anúncios novos dos concorrentes", automatizado tanto
   para Meta quanto para Google. `google_trends.py` detecta picos de interesse de
   busca (marca, produtos e concorrentes) acima de `--limiar-pct` (default 40%).

Actor default de cada um (trocável em `config["apify_actors"]` sem mexer no código):

| Sinal | Actor default | Alternativas encontradas (se o default não servir) |
|---|---|---|
| Meta Ad Library | `apify/facebook-ads-scraper` (oficial) | `viralanalyzer/facebook-ads-library`, `curious_coder/facebook-ads-library-scraper`, `automation-lab/facebook-ads-library` |
| Google Ads Transparency Center | `unseenuser/google-ads` | `lentic_clockss/google-ads-transparency-center-vn`, `automation-lab/google-ads-scraper` |
| Google Trends | `apify/google-trends-scraper` (oficial) | `automation-lab/google-trends-scraper`, `scrapemint/google-trends-scraper` |

Por que Apify para Trends em vez de `pytrends`: a lib está com o repositório
arquivado desde abril/2025 (sem manutenção) e sofre rate-limit imprevisível; a API
oficial do Google Trends segue em alfa fechado (allowlist). Preferimos manter tudo
no mesmo provedor/token já usado no resto da skill.

**Criativo novo que está impactando o rendimento — apresente a peça, não só o texto:**
os três scripts trazem `imagem_url`/`video_url`/texto do anúncio quando o actor
retorna isso, e o dashboard HTML já embute a imagem direto no card (`<img>`, ver
`render_creative()`) sempre que ela vier na evidência. O que fica por sua conta (o
agente) é a **análise** — o script não tem visão para isso:

1. Quando um `novo_criativo_concorrente` estiver associado a queda de rendimento
   (seu próprio CTR/ROAS caindo no produto equivalente, ou o alerta vier junto de um
   preço/desconto de severidade alta), busque a imagem/página (Read ou WebFetch, se o
   host não estiver bloqueado) e escreva um JSON `{ad_id: {"gancho":..., "oferta":...,
   "formato":..., "cta":..., "observacao":...}}` — o `ad_id` é o mesmo campo que sai
   em `novos_anuncios` no JSON do `meta_ads.py`/`google_ads_transparency.py`.
2. Rode `war_room.py` de novo passando `--creative-analysis-json
   essa-analise.json`: o card daquele criativo específico ganha um bloco "// análise
   do criativo" logo abaixo da imagem, com gancho/oferta/formato/CTA lado a lado.
3. **Nunca invente a leitura sem a evidência em mãos** — se a imagem não veio (actor
   não trouxe, ou host bloqueado), diga isso e peça print/link ao usuário, do mesmo
   jeito que `brand-bidding-monitor` já faz. Se o criativo citar a marca/produto
   próprio no texto, é caso de `brand-bidding-monitor`, não só "criativo
   interessante".

### 7. Monitor de leilão por palavra-chave (Google Ads, via Windsor.ai) — VERIFICADO

Diferente do passo 6 (beta), este pedaço **foi testado com dado real** da conta
Google Ads da Joie via Windsor.ai — não é suposição. Quando o rendimento de uma
palavra-chave cai, `keyword_auction.py` traz os **pontos de interferência** (quem
está no leilão), o **CPC envolvido**, e a **estratégia de combate** — exatamente o
que foi pedido.

1. Puxe os dois conjuntos de dados via MCP do Windsor.ai (são chamadas SEPARADAS —
   testei e confirmei que o Google Ads recusa misturar `auction_insight_domain` com
   métricas de performance na mesma query, erro "unsupported metrics"):
   ```
   get_data(connector="google_ads", fields=["date","campaign","keyword_text",
     "impressions","clicks","ctr","cpc","quality_score","search_impression_share",
     "search_rank_lost_impression_share","first_page_cpc",
     "position_estimates_top_of_page_cpc_micros"], date_preset="last_7d")

   get_data(connector="google_ads", fields=["date","campaign",
     "auction_insight_domain"], date_preset="last_7d")
   ```
   Grave cada retorno num JSON `{"connector": "google_ads", "registros": [...]}`.
2. Rode:
   ```bash
   python keyword_auction.py --config config.json --keywords-json keywords-7d.json \
     --auction-json auction-7d.json --history-dir ../outputs/demo-history \
     --out ../outputs/quedas-keyword.json
   python war_room.py --config config.json --keyword-auction-json ../outputs/quedas-keyword.json \
     --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
   ```
3. Cada queda vem com: impression share antes/depois, rank lost antes/depois,
   Quality Score antes/depois, CPC médio pago, CPC de topo de página estimado pelo
   Google **quando disponível** (na conta testada veio `null` para termos de baixo
   volume — o script reporta isso honestamente, nunca inventa um valor), e os
   domínios do Auction Insight da mesma campanha ordenados por frequência no
   período — são os "pontos de interferência" pedidos.
4. Achado real ao testar (conta Joie, últimos 7 dias): palavras-chave genéricas
   (`whey protein`, `omega 3`, `suplementos alimentares`) com Quality Score 1-3 e
   impression share no piso (~10%, com 33-50% perdido por rank), contra
   `Joie`/`Joie suplementos` (marca) com Quality Score 9-10 e impression share
   quase 100%. Os domínios que mais aparecem disputando essas campanhas:
   `mercadolivre.com.br`, `shopee.com.br`, `vitafor.com.br`, `gsuplementos.com.br`,
   `puravida.com.br`, `sanavita.com.br`, `maxtitanium.com.br`, `oficialfarma.com.br`.
   Isso não é genérico — é o padrão real desta conta: termos de marca são fortes,
   termos genéricos perdem o leilão para marketplaces e concorrentes diretos.

### 7b. Relatório completo de keywords + leilão (`gerar_relatorio_keywords.py`)

O passo 7 só aponta **quedas** de performance (o que virou alerta). Para ver a
relação **completa** de todas as palavras-chave das campanhas — CTR, CPC médio,
Quality Score, impression share, rank lost e os domínios concorrentes disputando
cada campanha, mesmo quem não caiu — use este gerador em vez de (ou além de)
`keyword_auction.py`. Reaproveita as mesmas funções de agregação (`agregar_keywords`,
`agregar_dominios_por_campanha`), só troca "detectar queda e alertar" por "listar
tudo":

```bash
python gerar_relatorio_keywords.py --config config.json \
  --keywords-json keywords-7d.json --auction-json auction-7d.json \
  --out ../outputs/relatorio-keywords.xlsx
```

Os dois JSONs de entrada são os mesmos do passo 7 (coletados via MCP do
Windsor.ai, `get_data` no connector `google_ads` — ver passo 7 para os campos
exatos e por que `auction_insight_domain` exige uma chamada separada). Gera 3
abas: **Keywords** (todas, com métricas + os domínios do leilão da campanha),
**Leilão por Campanha** (todos os domínios concorrentes, não só o top 5) e
**Metodologia**. Sempre que os dois JSONs de entrada não vierem de uma coleta
real (por exemplo, para mostrar o formato do relatório num ambiente sem acesso
ao Windsor.ai), passe `--simulado` — isso adiciona uma aba `⚠ AVISO` como
primeira aba, deixando explícito que os números são só ilustrativos e não dado
medido da conta.

### 8. Diagnóstico completo quando um KPI próprio cai — nunca reagir sem investigar

Rode `own_performance.py` com `--history-dir` (mesmo diretório do resto da war room)
para detectar automaticamente queda de ROAS/CTR/taxa de conversão(GA4)/aumento de CPA
entre rodadas:

```bash
python own_performance.py --input google-ads-30d.json --input ga4-30d.json \
  --config config.json --out ../outputs/own-performance-por-produto.json \
  --history-dir ../outputs/demo-history
python war_room.py --config config.json --queda-kpi-json ../outputs/demo-history/queda-kpi-proprio.json \
  --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
```

Isso gera um alerta `queda_kpi_proprio` — e este é **diferente de todos os outros**:
o playbook dele não traz uma estratégia tática pronta, porque a causa não é
conhecida ainda. Ele manda rodar o **protocolo de diagnóstico completo**
(`references/protocolo-diagnostico.md`) antes de propor qualquer ação:

1. Reunir o que a própria war room já capturou (concorrência, leilão, criativo).
2. Cruzar com sazonalidade do varejo/consumo brasileiro (calendário no protocolo).
3. Pesquisar buzz da marca/produto/segmento (`WebSearch` real — Reclame Aqui,
   redes, questão regulatória da categoria).
4. Pesquisar notícias/imprensa sobre a marca, os produtos e o segmento.
5. Pesquisar contexto micro/macroeconômico (Selic, inflação, câmbio, confiança do
   consumidor, desempenho do varejo) relevante ao poder de compra do público.
6. Sintetizar com 5 lentes: economista, administrador, estatístico, marketeiro,
   vendedor — cada uma contribuindo a leitura da própria área.
7. Fechar com o diagnóstico principal (causa mais provável + grau de confiança) e
   as ações corretivas propostas, em ordem de prioridade.
8. **Pedir autorização explícita antes de executar qualquer ação** — nunca chamar
   uma ação de escrita (`mcp__Windsor_ai__execute_action`, que pausa/ativa campanha,
   muda orçamento/lance de verdade) sem o usuário ter confirmado aquela ação
   específica na conversa. Isso não é burocracia: a ferramenta tem acesso de escrita
   real às contas de mídia da marca.

Leia `references/protocolo-diagnostico.md` inteiro antes de conduzir esse
diagnóstico — ele detalha as fontes e o formato de cada passo.

### 9. Esquadrão de agentes de combate + monitor de ações em andamento

`scripts/agentes.json` define os **mandatos** que respondem a cada tipo de alerta —
na prática, o mesmo agente Claude conduz tudo, adotando a lente certa conforme o
gatilho (para paralelizar de verdade em incidentes com muitos alertas simultâneos,
dá para instanciar um subagente por alerta via `Agent` tool, cada um assumindo um
destes papéis):

| Agente | Mandato | Gatilhos | Executa ação real? |
|---|---|---|---|
| ◈ Precificação e Margem | Price-match, cupom-espelho, cálculo de margem | queda/alta de preço, novo desconto | Não integrado (depende do ERP/e-commerce da marca) |
| ▲ Mídia Paga e Leilão | Lance, orçamento, Quality Score, negativação | aumento de ads, queda de keyword, queda de KPI | **Sim** — Windsor.ai (`execute_action`, Google Ads/Meta), com autorização |
| ◆ Criativo | Analisa e propõe/gera o contra-criativo | novo criativo de concorrente | Geração via Canva MCP; publicação via Windsor.ai, com autorização |
| ● Marketplace (ML Ops) | Ficha, frete, prova social, monitora posição | novo entrante, sumiço, salto de visibilidade | Não — ação manual da equipe de conteúdo |
| ◈ Marca e Enforcement | Aciona radar de marca, denúncia ou defesa | pico de interesse de busca | Skills irmãs + campanha de defesa via Windsor.ai |
| ◎ Inteligência e Diagnóstico | Roda o protocolo completo (passo 8) | queda de KPI próprio | Só investiga — nunca executa |
| ★ Comandante (orquestrador) | Prioriza, consolida, pede autorização | — | Nunca executa diretamente |

`war_room.py` atribui automaticamente o agente e um **status de ação** a cada
alerta (`aguardando_autorizacao` para severidade alta de agente que executa ação
real; `investigando` para severidade alta sem ação de escrita; `monitorando` para
o resto) — isso alimenta o painel **"Esquadrão de Combate"** no dashboard HTML e a
aba de mesmo nome no xlsx, mostrando quantas ações cada agente tem em andamento e
qual o status mais urgente. Nenhum status muda sozinho: "aguardando_autorizacao"
só vira "autorizado"/execução quando você (o agente, na conversa) recebe a
confirmação explícita do usuário — ver o princípio de autorização no passo 8.

### 10. Radar de posição no Mercado Livre (nós vs. concorrência)

Antes, `collect_snapshot()` só via os concorrentes. Agora, configurando
`official_sellers` (nickname do seu seller oficial no ML — mesmo padrão do
`radar-keywords-concorrentes`), ele também casa o **nosso próprio anúncio** na
mesma busca e monta o painel **"Radar de Posição"** (xlsx: aba "Radar ML"; HTML:
tabela dedicada) com nós e cada concorrente lado a lado, por produto: posição,
preço, desconto, reviews, rating, frete grátis, e uma tentativa de flag de
"anúncio patrocinado" (`extrair_patrocinado()` — best-effort, o actor usado não
confirma isso de forma confiável; vem "n/d" quando a informação não está na
captura, nunca inventado). Isso é o que permite ver de relance, por exemplo, "nosso
Faciderm está na posição 3, custando R$149,90, enquanto o concorrente que acabou de
baixar preço está na posição 1 a R$71,90" — o cruzamento que faltava entre "o que o
concorrente fez" e "onde isso nos deixa".

Para testar sem coleta real: `--simulate-ml-proprio scripts/examples/ml-simulado-proprio.json`
(mesmo mecanismo do `--simulate-ml`).

### 11. Motor de descoberta e composição de concorrentes (`descoberta_concorrentes.py`)

Responde à pergunta "quem deveria estar em `concorrentes[]` e ainda não está".
**Método de seleção, por completo:**

1. **Introdução manual** — `config["candidatos_concorrentes_manual"]` (nome,
   domínio, sellers_ml conhecidos) e `config["produtos_candidatos_manual"]`
   (produtos/variantes que você quer passar a observar antes de configurar por
   completo em `produtos_monitorados`).
2. **Descoberta por produto** — para cada produto (monitorado ou candidato), busca
   o `termo_busca_ml` no Mercado Livre e captura **todos os sellers distintos** do
   resultado (não só os já cadastrados) — isso é "procurar variantes similares e
   trazer os concorrentes daquele produto". O `título` de cada achado mostra qual
   variante específica compete (ex.: "Whey Protein Concentrado" vs. o seu
   "Isolado").
3. **Auction Insight** (Google Ads, real) — os domínios que disputam o leilão da
   própria conta, via o mesmo mecanismo do `keyword_auction.py`.

As três fontes são fundidas por candidato (substring contra nome/domínio/sellers_ml
— assim "Max Titanium" digitado à mão e "MAX TITANIUM OFICIAL" achado na busca viram
UM candidato só, com as origens registradas em `origem: []`).

**Ranking de relevância** — cada candidato recebe um score combinando (pesos em
`config["pesos_relevancia"]`, documentados em `references/fontes-e-limitacoes.md`):
preço (proximidade ao `preco_proprio`), autoridade de marca (proxy: rating médio no
ML), presença em ads (nº de anúncios ativos, se você alimentar `--ativos-ads-json`
com o resultado de `meta_ads.py`/`google_ads_transparency.py`), vendas em
marketplace (proxy: reviews + nº de listagens) e KPIs de redes sociais — **este
último não tem fonte de dado real integrada; é sempre "N/D", nunca inventado**. Um
componente sem dado sai do somatório (os pesos dos outros são renormalizados), não
vira zero por "falta de dado".

```bash
python descoberta_concorrentes.py --config config.json \
  --auction-json auction-domains.json --ativos-ads-json ativos-ads.json \
  --out ../outputs/descoberta.xlsx
```

Saída: `outputs/descoberta.xlsx` com **Candidatos por Produto** (ranqueados),
**Candidatos Globais (Leilão)** e uma aba **Metodologia** explicando cada
componente do score. Depois de revisar, é você quem decide promover um candidato
para `concorrentes[]` — o motor nunca promove sozinho.

### 12. War room consolidado — abas + redesign fintech

`war_room.py` deixou de ser só o monitor de preço/desconto: `war-room.html`
(e `war-room.xlsx`) agora reúnem **tudo num único artefato, por abas** — nada
mais fica espalhado em arquivos separados. Visual também mudou: saiu o cockpit
sci-fi (Orbitron/Share Tech Mono, scanline, boot sequence), entrou um tema
"fintech escuro" (tipografia Sora, cards arredondados, paleta categórica
validada para gráficos) — ver `scripts/_fonts.py` (fonte `FONT_SORA_B64`). Os
outros dois artefatos (`gerar_demo_live.py`, `gerar_simulador.py`) continuam
com o visual cockpit original — não foram redesenhados.

As abas do `war-room.html`, e de onde vem cada uma:

- **Visão Geral** — o que já existia: Esquadrão de Combate, Desempenho Próprio,
  Battlecards.
- **Marketplaces** — Radar de Posição do passo 10, agora com um segundo canal:
  **Google Shopping**, quando fornecido. `montar_radar_marketplaces(radar_ml,
  snapshot_gs_concorrentes, snapshot_gs_proprio)` reaproveita `montar_radar_ml()`
  para o Shopping (mesmo formato de item) — sem coleta real de Google Shopping
  ainda (nenhum actor/conector configurado), use
  `--simulate-google-shopping`/`--simulate-google-shopping-proprio` (mesmo
  formato de `--simulate-ml`/`--simulate-ml-proprio`, ver
  `scripts/examples/gshopping-simulado*.json`) para já deixar a estrutura
  demonstrável. Sem dado fornecido, a aba mostra "ainda não coletado" — nunca
  inventa posição/preço.
- **Concorrentes** — saída de `descoberta_concorrentes.py` (passo 11), agora
  embutida via `--descoberta-json` (aponte para o `--export-json` que o script
  gera) em vez de só existir na xlsx separada.
- **Keywords & Leilão** — a relação **completa** de keywords (não só as que
  caíram), via `gerar_relatorio_keywords.py` (passo 7b) + `--keywords-relatorio-json`
  (idem, `--export-json`). Mostra o aviso "⚠ SIMULADO" quando o arquivo de
  origem foi gerado com `--simulado`.
- **Histórico Preço × Ads** — gráfico novo: preço do concorrente ao longo do
  tempo, com marcador cheio/vazio conforme ele está ou não rodando ads
  (best-effort, campo `patrocinado` do próprio Radar de Marketplaces) e uma
  faixa sombreada nos períodos em que ele está **disputando direto** — posição
  dele à nossa frente no mesmo produto, no mesmo momento — mais um traço
  vermelho quando nosso KPI caiu naquela mesma janela (correlação que embasa o
  protocolo de diagnóstico do passo 8). Acumula **sozinho**, a cada rodada real
  — `atualizar_historico_preco_ads()` deriva tudo do Radar de Marketplaces +
  dos alertas já calculados, sem pedir nenhuma coleta nova; persiste em
  `<history-dir>/<marca>-historico-preco-ads.json`. Para demonstrar sem esperar
  várias rodadas reais, use `--simulate-historico-preco-ads
  examples/historico-preco-ads-simulado.json` (sobrescreve o acumulador só
  naquela execução).
- **Seleção Manual** — o mesmo mecanismo do painel do passo 1b (toggle
  monitorando/candidato, adicionar, remover, exportar `config.json`), só que
  embutido como aba do próprio `war-room.html`, e cobrindo **produtos E
  concorrentes** juntos (o painel avulso de `gerar_painel_produtos.py` continua
  existindo, só com produtos).

Comando completo (todas as fontes ligadas):

```bash
python descoberta_concorrentes.py --config config.json --auction-json auction.json \
  --ativos-ads-json ativos-ads.json --out ../outputs/descoberta.xlsx \
  --export-json ../outputs/descoberta.json

python gerar_relatorio_keywords.py --config config.json --keywords-json keywords.json \
  --auction-json auction.json --out ../outputs/relatorio-keywords.xlsx \
  --export-json ../outputs/keywords-relatorio.json   # + --simulado se não for dado real

python war_room.py --config config.json \
  --descoberta-json ../outputs/descoberta.json \
  --keywords-relatorio-json ../outputs/keywords-relatorio.json \
  --simulate-google-shopping gshopping.json --simulate-google-shopping-proprio gshopping-proprio.json \
  --own-performance ../outputs/own-performance-por-produto.json \
  --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
```

Todas as três flags (`--descoberta-json`, `--keywords-relatorio-json`,
`--simulate-google-shopping*`) são opcionais e independentes — rode
`war_room.py` sozinho (como no passo 2) que as abas correspondentes mostram a
mensagem de "nada carregado ainda" em vez de quebrar.

### 13. Aba "GA4 · Jornada" — leitura de gestor de tráfego (`ga4_jornada.py`) — VERIFICADO

Diferente do passo 5 (que casa GA4 *por produto* com o desempenho de mídia), esta
aba é a **visão de tráfego inteira**: funil de compra, jornada por canal,
dispositivo e landing page, com diagnóstico de onde agir primeiro. **Todos os
campos foram testados ao vivo** na propriedade GA4 da Joie via Windsor.ai.

Achados técnicos confirmados na coleta real:

- A GA4 aceita **no máximo 10 métricas por chamada** `get_data` (erro explícito
  "GA4 allows at most 10 metrics per request"). Por isso a coleta é feita em
  **blocos** — um `get_data` por recorte.
- O funil de e-commerce da conta é medido de verdade:
  `item_view_events` → `add_to_carts` → `checkouts` → `ecommerce_purchases`.
  A conta tem até um funil nomeado (`conversions_funil_jornada_de_compra___ecommerce`).
- `engagement_rate` e `bounce_rate` voltam como **fração (0-1)**, não porcentagem.

Coleta (o agente roda os `get_data` e grava cada retorno cru num JSON):

```
get_data(connector="googleanalytics4", fields=["sessions","totalusers","newusers",
  "engaged_sessions","engagement_rate","bounce_rate","average_session_duration",
  "screen_page_views"], date_preset="last_30d")                        → ga4-overview.json

get_data(... fields=["item_view_events","add_to_carts","checkouts",
  "ecommerce_purchases","purchase_revenue","transactions","total_purchasers",
  "first_time_purchasers"])                                            → ga4-funil.json

get_data(... fields=["default_channel_group","sessions","engaged_sessions",
  "engagement_rate","add_to_carts","checkouts","ecommerce_purchases",
  "purchase_revenue"])                                                 → ga4-canais.json

get_data(... fields=["devicecategory", ...mesmas métricas...])          → ga4-devices.json
get_data(... fields=["landing_page","sessions","engagement_rate","bounce_rate",
  "add_to_carts","ecommerce_purchases","purchase_revenue"],
  filters=[["sessions","gte",100]])                                    → ga4-landing.json
get_data(... fields=["date","sessions","add_to_carts","checkouts",
  "ecommerce_purchases","purchase_revenue","engagement_rate"])         → ga4-serie.json
```

Depois compile e injete:

```bash
python ga4_jornada.py --overview ga4-overview.json --funil ga4-funil.json \
  --canais ga4-canais.json --devices ga4-devices.json --landing ga4-landing.json \
  --serie ga4-serie.json --periodo "02/07 a 31/07/2026 (30 dias)" \
  --out ../outputs/ga4-jornada.json

python war_room.py --config config.json --ga4-json ../outputs/ga4-jornada.json \
  --out ../outputs/war-room.xlsx --html ../outputs/war-room.html
```

O que a aba entrega (e o que o script **não** faz):

- **KPIs de topo** — sessões, taxa de conversão, receita, receita/sessão, ticket
  médio, engajamento, duração, compradores e % de 1ª compra.
- **Funil de compra** em barras proporcionais, com taxa de passagem entre etapas,
  perdidos em número absoluto, e a etapa de **maior vazamento destacada** (é o
  ponto onde a correção tem maior efeito absoluto em vendas).
- **Matriz de decisão por canal** (escalar / corrigir primeiro / testar aumento /
  revisar ou cortar) — o corte é a **mediana do próprio período**, nunca um
  benchmark de mercado inventado; isso está escrito na legenda da aba.
- **Funil por canal** — sessão→carrinho, carrinho→checkout, checkout→compra, para
  ver *em que etapa* cada origem perde a venda.
- **Dispositivos** e **landing pages** (só acima de um limiar de sessões,
  configurável em `--limiar-landing-sessions`, default 100 — abaixo disso a taxa
  oscila demais para embasar decisão). Marca páginas com tráfego e **zero compra**.
- **Diagnóstico priorizado** com o número que sustenta cada achado.
- **Série diária** de sessões + compras + receita. Cada grandeza tem a própria
  faixa normalizada e o valor absoluto vem no tooltip — **nunca dois eixos Y no
  mesmo desenho**, que distorce a leitura.
- O script **não projeta receita futura** e **não inventa benchmark**. Métrica que
  não veio na coleta aparece como `n/d`, nunca como zero.

Também gera 4 abas na planilha: `GA4 Funil`, `GA4 Canais`, `GA4 Landing Pages` e
`GA4 Diagnóstico`.

## Mais insights, ferramentas e pontos a observar (roadmap honesto)

O que seria natural somar depois, na ordem que mais amplia a guerra competitiva —
nada abaixo está implementado ainda; peça explicitamente quando quiser que uma
dessas vire código:

- **Share of Search / Share of Shelf**: % dos top-N resultados do ML que são
  nossos vs. de cada concorrente, por termo — generalização do Radar de Posição
  (passo 10) para um índice único, rastreável ao longo do tempo.
- **Preço por unidade/grama**: comparação justa entre embalagens de tamanhos
  diferentes (hoje o preço bruto pode enganar se um concorrente vende embalagem
  menor por menos).
- **Velocidade de reviews e sentimento**: não só o total de reviews (já captado),
  mas o ritmo de crescimento e uma leitura de sentimento das mais recentes —
  aprofunda o proxy de volume/momentum do concorrente.
- **Multi-marketplace**: hoje só Mercado Livre. Shopee, Amazon e Magalu exigiriam
  novos actors Apify (mesmo esforço/honestidade dos passos 6-7 — pesquisar,
  marcar como beta, calibrar no 1º uso real).
- **Auction Insights para os outros produtos/campanhas**: o achado do passo 7 foi
  numa amostra; rodar em todas as campanhas ativas dá o mapa completo de onde a
  conta está ganhando ou perdendo o leilão.
- **GA4 por landing page/dispositivo**: hoje agregado por campanha; abrir por
  página de destino e mobile-vs-desktop pode revelar fricção que o agregado
  esconde.
- **Preço-teto observado do mercado**: menor preço visto entre todos os
  concorrentes rastreados, para calibrar até onde um price-match faz sentido sem
  virar corrida ao fundo do poço.
- **Integração com o Reclame Aqui como fonte contínua** (hoje só entra via
  WebSearch pontual no protocolo de diagnóstico — dá para transformar num monitor
  recorrente de nota/volume de reclamação, com o mesmo mecanismo de diff das
  outras fontes).
- **KPIs de redes sociais no score de relevância** (passo 11): hoje sempre "N/D" —
  precisaria de uma integração nova (API do Instagram/TikTok/YouTube, ou um actor
  Apify de seguidores/engajamento, no mesmo padrão beta dos passos 6-7) antes de
  entrar de verdade no cálculo.

## O playbook de resposta (o que muda por tipo de mudança)

O mapeamento completo tipo-de-mudança → impacto na concorrência → impacto estimado no
volume → estratégia imediata → KPIs impactados está em
`references/playbook-resposta.md` (versão legível) e `scripts/playbook.json` (versão
que o script usa). **Leia o playbook antes de comentar qualquer alerta** — a resposta
certa muda bastante entre "concorrente baixou preço 3%" e "concorrente lançou cupom
agressivo de 25%".

Resumo dos tipos cobertos: queda de preço (leve/moderada/agressiva), novo desconto/cupom,
aumento de preço do concorrente (oportunidade), salto de posição/visibilidade no Mercado
Livre, aumento de anúncios ativos (Meta/Google/ML Ads — via captura manual ou via os
scripts beta do passo 6), concorrente saiu da busca (possível ruptura de estoque), novo
entrante (concorrente novo pescando o mesmo termo), novo criativo de concorrente detectado
no Meta Ad Library/Google Ads Transparency Center (com a peça embutida e análise, quando
fornecida), pico de interesse de busca (Google Trends) na marca, num produto ou num
concorrente, queda de performance de palavra-chave no leilão do Google Ads (moderada/
crítica — com pontos de interferência, CPC e estratégia de combate, passo 7, verificado),
e queda de KPI próprio (ROAS/CTR/conversão GA4/CPA — moderada/crítica, passo 8), que não
traz estratégia pronta e sim o gatilho para o protocolo de diagnóstico completo.

## Demo ao vivo e simulador (pitch/apresentação/treinamento)

Duas ferramentas de demonstração, ambas 100% simuladas/autocontidas (não dependem de
nenhum export real) e reaproveitando o motor real (`make_alert`, playbook, agentes,
`render_card`/`render_own_kpi`/`render_esquadrao`/`render_ml_radar`) via import de
`war_room.py` — a operação real continua sendo `war_room.py` normalmente, um
relatório por rodada:

- **Replay fixo** (`python gerar_demo_live.py --config config.example.json --out ../outputs/war-room-live-demo.html`):
  10 tipos de alerta chegando em sequência automática, com relógio, feed e "master
  caution" reagindo. Bom para um pitch de "deixa rodando".
- **Simulador interativo** (`python gerar_simulador.py --config config.example.json --out ../outputs/war-room-simulador.html`):
  painel de controle com ~19 eventos em 6 categorias (Preço, Mercado Livre, Criativo,
  Trends, Leilão, KPI Próprio) — você dispara **qualquer um, na ordem que quiser**,
  e o dashboard inteiro reage: card novo, feed, Esquadrão de Combate recalculado por
  agente, e o **Radar ML atualizando ao vivo** (a linha do concorrente afetado muda
  e pisca quando o evento é de preço/desconto/visibilidade/entrada/saída). Também
  tem "disparar tudo em sequência" e "reiniciar". É a ferramenta certa para treinar
  a equipe em como o sistema reage a cada tipo de evento, sem esperar um evento real
  acontecer. Inclui um grupo extra de botões **"Descoberta de Concorrentes"** que
  roda `descoberta_concorrentes.py` sobre as fixtures de exemplo e revela, numa
  tabela dedicada, os candidatos ranqueados por produto (e um para o leilão global) —
  mesma composição de fontes e score de relevância do passo 11.

## Princípios

- **Honestidade sobre o que é medido vs. estimado:** preço e desconto no Mercado Livre
  são dados observados; investimento em ads é sempre um *sinal proxy* (contagem de
  anúncios ativos), nunca o valor gasto; impacto em volume de vendas é uma *estimativa*
  com premissa explícita (elasticidade configurável), nunca um número fabricado
  apresentado como fato.
- **Sem token em texto versionado:** nunca grave `APIFY_TOKEN` real dentro de
  `config.json` neste repositório — leia de variável de ambiente.
- **Evidência sempre:** todo alerta carrega URL/seller/data de captura para conferência.
- **Reutilizável:** troque `config.json` para outra marca/rodada de concorrentes.
- **"Instantâneo" = cadência declarada:** sempre diga ao usuário qual o intervalo de
  verificação configurado, para não prometer tempo real que a fonte não entrega.
- **Diagnóstico antes de ação, sempre que a causa não é óbvia:** um alerta de queda
  de KPI próprio não vem com estratégia pronta de propósito — a causa pode ser
  sazonalidade, economia, buzz, ou concorrência, e só o protocolo completo
  (`references/protocolo-diagnostico.md`) distingue qual.
- **Nunca executar ação de escrita sem autorização explícita e específica:** o
  Windsor.ai pode de fato pausar campanha, mudar orçamento/lance ou publicar
  criativo. Apresentar o diagnóstico e a proposta, esperar a confirmação do usuário
  para aquela ação exata, e só então chamar `execute_action` — nunca antes, e uma
  autorização não cobre ações futuras diferentes.
