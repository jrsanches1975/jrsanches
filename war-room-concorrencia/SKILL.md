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

### 14. Metas, evolução e planejamento (`metas.py`) — a bússola das ações

Todo o racional de ação do war room aponta para uma meta. Declare em
`config["metas"]` (ver `config.example.json`): `faturamento`, `unidades`,
`ticket_medio`, `sessoes`, `tx_conversao` (fração), `receita_por_sessao` e
`produtos` (por produto: `unidades` e/ou `faturamento`).

```bash
python metas.py --config config.json --ga4-json ../outputs/ga4-jornada.json \
  --vendas-produto-json vendas-por-produto.json --dias-do-periodo 31 \
  --out ../outputs/metas.json

python war_room.py --config config.json --metas-json ../outputs/metas.json ...
```

A aba **Metas & Evolução** traz:

- **Quadro de metas** — realizado × meta por indicador, com barra de progresso e o
  **traço de ritmo ideal até hoje** (meta distribuída linearmente no período).
  Estar atrás do traço = fora do ritmo, mesmo com a barra crescendo. Status:
  no ritmo / atenção / fora do ritmo.
- **Evolução × meta** — faturamento acumulado (medido) contra a linha de meta.
- **Alavancas** — quanto tráfego, conversão OU ticket precisaria mudar,
  isoladamente, para fechar a lacuna. É aritmética reversa sobre o realizado:
  serve para dimensionar esforço, não para prometer resultado (na prática as três
  se movem juntas).
- **Simulador de planejamento** — sliders de tráfego/conversão/ticket que
  recalculam a projeção × meta **ao vivo** no navegador. A tela deixa explícito
  o que é **realizado (medido)** e o que é **cenário sob premissa do usuário**.
- **Metas por produto** — unidades e faturamento por produto. O realizado por
  produto **não vem da GA4** no recorte usado: informe via
  `--vendas-produto-json` (export do ERP/loja). Sem isso, as metas aparecem e o
  realizado fica em branco — nunca preenchido por estimativa.

Honestidade embutida: `projecao_fim_periodo` mantém o ritmo médio observado e é
rotulada como **premissa**, não previsão (sem sazonalidade nem saturação). Meta
não declarada aparece como "sem meta definida". Ticket médio, conversão e
receita/sessão não são acumuláveis, então não têm linha de ritmo nem projeção.

### 15. Aba Meta Ads (`meta_ads_performance.py`) — duas fontes, nunca misturadas

Mesma lógica da aba GA4, mas para o Meta. O script mantém **separadas** duas
fontes com status de confiança diferente:

- **Lado GA4 (REAL, disponível hoje)** — as campanhas do Meta aparecem na GA4 via
  UTM (`source: Facebook`), com sessões, engajamento, carrinho, checkout, compras
  e receita. É medido, mas **sem gasto, impressão, clique, CTR, CPM ou criativo**
  — a GA4 não vê o lado da plataforma.
- **Lado plataforma** — gasto/impressões/cliques/CTR/CPM/frequência + imagem do
  criativo. Exige o conector `facebook` do Windsor.ai, que nesta integração está
  **desconectado**. Enquanto estiver, rode com `--simulado` para o relatório
  avisar em letra garrafal.

```bash
python meta_ads_performance.py --ga4-campanhas examples/ga4-real/ga4-campanhas.json \
  --plataforma meta-insights.json --criativos criativos.json --simulado \
  --out ../outputs/meta-ads.json

python war_room.py --config config.json \
  --meta-ads-performance-json ../outputs/meta-ads.json ...
```

Cuidado com o nome: `--meta-ads-json` (já existente) é o monitor de criativo
**novo de CONCORRENTE**; `--meta-ads-performance-json` é esta aba.

O script nunca soma métrica de uma fonte com a outra. O `roas_cruzado` (receita
GA4 ÷ gasto plataforma) é calculado mas vem sempre com o aviso de que são
**janelas de atribuição diferentes**. Produto/objetivo/formato saem do padrão de
nomenclatura das campanhas (`[[Conv]] - [Colágeno] - Carrossel`); onde o padrão
não existe, aparece "—" em vez de chute.

### 16. Medidas a serem tomadas (GA4 e Meta Ads)

Ambas as abas têm uma seção **Medidas a serem tomadas**: ação, **por quê** (com o
número medido que a sustenta), **como fazer** e **qual meta ela move**. Ordenadas
por impacto sobre a meta ÷ esforço.

Toda medida é **recomendação**. Nenhuma ação de escrita (verba, campanha, preço,
`execute_action`) é executada sem autorização explícita e específica do usuário —
princípio que vale para o sistema inteiro.

### 17. Criativos nas abas GA4 e Meta

A imagem do criativo **não vem da GA4**. Vem do Meta/Google (ou de um mapa
manual) e é anexada por nome de campanha via `--criativos`. Onde não houver, o
card diz "sem criativo anexado" — nunca mostra placeholder passando por criativo
real. As fixtures de exemplo usam mockups SVG gerados proceduralmente, com
"MOCKUP SIMULADO" impresso na própria arte.

**Uma campanha pode ter mais de um criativo rodando ao mesmo tempo** (variações
de imagem/vídeo/copy) — no `--criativos` de `ga4_jornada.py`, cada chave (nome
da campanha) aceita tanto um objeto único (`{imagem_url, titulo, ...}`) quanto
uma **lista** desses objetos. `montar_campanhas()` guarda a lista inteira em
`criativos` (usada pela galeria — um card por variação, com badge "variação X
de Y") e mantém os campos `criativo_*` no topo da linha como compatibilidade
(sempre o primeiro item da lista). O Meta Ads (`meta_ads_api.py`/
`meta_ads_performance.py`) já resolve isso nativamente porque coleta no nível
de ANÚNCIO (não de campanha) — cada anúncio é uma linha com seu próprio
criativo, então uma campanha com 3 anúncios já aparecia com 3 cards antes desta
mudança. O Google Ads ainda não tem um coletor automático de criativo
equivalente ao `meta_ads_api.py` (só o mapa manual acima) — se/quando isso for
construído, é só alimentar `--criativos` de `ga4_jornada.py` com uma lista por
campanha, no mesmo formato.

### 17b. "Modo story" no Diagnóstico (GA4 e Meta Ads) — `render_diagnostico_story()`

Usuário mandou um exemplo de anúncio (Instagram Stories da "aure.digital") com
KPIs revelados em sequência — barra de progresso no topo estilo Stories,
gráfico de barras "desenhando" e legenda narrando o achado — e pediu esse tipo
de animação/storytelling nos diagnósticos do war room.

`render_diagnostico_story(achados, id_prefix, serie=None, campo_serie="sessions",
rotulo_serie="sessões/dia")` transforma a mesma lista de achados que já
alimenta `render_ga4_diagnostico()` (nível/título/detalhe — **nenhum texto
novo, nenhum número inventado**) numa sequência de slides em tela cheia:

- Barra de progresso por achado (`.story-seg`), preenchendo em 5,2s por slide
  (autoplay), clicável pra pular direto pra qualquer um.
- Sparkline (`.story-spark`) desenhando as barras com `scaleY` + delay
  escalonado — usa a **série diária REAL** já coletada pela GA4 (`serie`,
  campo `sessions` por padrão); sem `serie` ou com menos de 3 pontos válidos,
  o sparkline simplesmente não aparece (nunca um gráfico decorativo no lugar
  de dado real).
- Clique na 1/3 esquerda do palco = slide anterior; nos outros 2/3 = próximo
  (mesma convenção do Instagram Stories). Botão de pausa (`❚❚`/`►`) some o
  timer; passar o mouse por cima também pausa.
- `prefers-reduced-motion: reduce` desliga o autoplay inteiro e o desenho do
  sparkline (mostra tudo já "pronto", sem animação) — never trava quem
  desabilitou movimento no SO.

**Não substitui a grade estática** — ela continua embaixo, dentro de um
`<details>` ("Ver todos os achados em lista", via o helper `_lista_completa()`),
pra quem quer ler tudo de uma vez sem esperar o autoplay.

Ligado nos dois lugares que já usavam `render_ga4_diagnostico()`: aba GA4 ·
Jornada (`render_ga4_tab`, com sparkline usando `ga4['serie']`) e aba Meta Ads
(`render_meta_tab`, sem sparkline — Meta não tem série diária própria neste
modelo de dado). Cada instância tem um `id_prefix` único (`ga4-diag-story`,
`meta-diag-story`) porque o JS de cada uma é um `<script>` próprio, autocontido,
sem estado global — pode haver várias na mesma página sem colidir.

**Bug pego e corrigido durante o teste:** o `<i>` de cada barra do sparkline é
um elemento vazio — sem altura intrínseca, `transform: scaleY()` escalona
*zero* e a barra simplesmente não aparece. Precisa de `height: 100%` explícito
no `<i>` (relativo à altura fixa do container `.story-spark`) pra escalonar
alguma coisa de verdade. Pego só depois de olhar o screenshot Playwright — o
código "parecia certo" sem isso.

### 17c. Efeito do vídeo de referência (esqueleto→sólido, tendência, contagem)

Usuário mandou um vídeo real (anúncio Instagram da "aure.digital": 3 cards
Investimento/Faturamento/ROAS revelando em sequência, cada um com barras
"esqueleto→sólidas", linha de tendência tracejada + seta, e número grande
colorido `-28% MENOR ↓` / `+10% MAIOR ↑` contando). Extraí os frames do `.mp4`
com `ffmpeg` (via `imageio-ffmpeg`, instalado on-the-fly — não tinha `ffmpeg`
nem `opencv` no ambiente) pra analisar o efeito quadro a quadro antes de
implementar — sem isso seria "chutar" a partir de descrição, o que o projeto
não faz.

**Decisão consciente do que NÃO replicar:** a ilustração 3D das caixas, a
narração em áudio e a moldura do Instagram ("Seguir" etc.) são material de
anúncio, não fazem sentido num painel interno — não foram construídos.

**O que foi trazido, com dado real por trás, em dois lugares:**

1. **Sparkline do Diagnóstico (`render_diagnostico_story`)** — trocado de 14
   barras finas pra 10 mais largas (formato do vídeo), com:
   - Linha de tendência tracejada (`<svg class="story-trend">`, `<line>` +
     `<circle>` no ponto final) calculada a partir da média da 1ª metade da
     janela vs a 2ª metade da série real (não é regressão bonita, é a mesma
     comparação simples que o vídeo mostra).
   - Delta grande animado (`.story-delta`, ícone ▲/▼ + `data-count`): mesma
     conta (média 2ª metade ÷ média 1ª metade - 1) × 100, nunca inventado.
     Sem pontos suficientes (`< 4` dias válidos), o delta simplesmente não
     aparece.
   - Cor do delta é NEUTRA (não vermelho/verde) de propósito: ao contrário do
     vídeo (onde "investimento caindo" É a notícia boa), num achado de
     diagnóstico "sessões subindo" não significa necessariamente algo bom
     (ex.: o achado "Paid Shopping traz volume e não converte" — sessão
     subindo ali não é vitória). Quem carrega o julgamento de gravidade
     continua sendo só o badge de nível (`.story-nivel`, alta/média/baixa).

2. **Motor de contagem animada (global, novo `<script>` logo antes do script
   principal de abas)** — os atributos `data-count`/`data-count-dec`/
   `data-count-suf` já existiam em 3 lugares do código (KPIs da GA4, KPIs do
   Meta Ads, ROAS do Desempenho Próprio) **sem nenhum JS consumindo** — uma
   funcionalidade preparada e nunca ligada. Agora um único motor
   (`querySelectorAll('[data-count]')`, ease-out cúbico, ~1,1s, respeitando
   `prefers-reduced-motion`) anima TODOS de uma vez, incluindo o novo delta do
   story. Nenhum HTML mudou — só a apresentação do número que já estava lá.

3. **Ícone-em-círculo no card de Desempenho Próprio** (`.gauge-icon`, glifo
   "⬈" ao lado do ROAS) — visual equivalente ao ícone circular do vídeo. Sem
   seta direcional aqui: não existe comparação período-a-período no dado de
   `own_performance.py` hoje (só o valor do período atual), então uma seta
   pra cima/baixo seria inventar uma tendência que não foi medida. Perguntei
   ao usuário antes de decidir isso (`AskUserQuestion`) e ele confirmou os
   dois lugares mesmo sabendo dessa limitação.

**Bug pego só no screenshot, de novo:** o card de Desempenho Próprio pareceu
"sumido" (opacity 0) no primeiro teste — não é bug novo, é o `.fx-reveal`
(scroll-reveal via `IntersectionObserver`, `_fx_neon.py`) que já existia:
só anima quando o elemento entra na viewport. `scroll_into_view_if_needed()`
antes do screenshot resolveu — lição: ao testar visualmente qualquer seção
abaixo da dobra, rolar até ela antes de tirar print, senão parece quebrado
sem estar.

### 18. Visual cósmico (`_cosmos.py`)

A arte do hero (nebulosa, disco de acreção, buraco negro, cometa, starfield) é
**gerada proceduralmente em SVG** com seed fixa — não é imagem baixada. Motivo:
a rede deste ambiente é bloqueada para hosts arbitrários e imagem de terceiro
traria problema de direito de uso. O mesmo módulo exporta a paleta cósmica
(violeta → magenta → ciano), o divisor de seção e orbes decorativos. As cores
**categóricas dos gráficos** seguem intactas (validadas para daltonismo pela
skill `dataviz`) — só a identidade visual usa o gradiente.

### 19. Importar planilha / Looker Studio (`sheets_import.py`)

**Sobre o Looker Studio, com clareza:** ele **não expõe API** para listar as
fontes de dados de um relatório nem para ler os dados dos gráficos — a API dele
só gerencia permissões de asset. Verificado também que a URL de um relatório
privado responde **403** sem sessão Google. Ou seja: "extrair as conexões do
Looker" não é possível nem com credencial. E não precisa ser: o Looker é só a
camada de visualização — as conexões dele apontam para as MESMAS fontes que o war
room já alcança (GA4, Google Ads, Sheets, BigQuery).

O caminho que funciona: **materializar o dado em planilha e importar**. O Looker
agenda entrega automática para Google Sheets (ou você exporta o gráfico), e o
Google Drive está acessível via MCP.

Fluxo em duas etapas (o script não tem credencial do Drive — quem lê é o agente):

```
1) o agente lê a planilha:  mcp__Google_Drive__search_files -> read_file_content
   e salva o texto num arquivo (ex.: planilha.txt)
2) o script converte:
```

```bash
# Auction Insights -> alimenta o monitor de leilão
python sheets_import.py --entrada planilha.txt --tipo leilao \
  --campanha "Brand." --out ../outputs/auction-do-sheets.json

# vendas por produto (ERP) -> destrava as metas por produto
python sheets_import.py --entrada erp.csv --tipo vendas-produto \
  --out vendas-por-produto.json

# campanhas, metas, ou só inspecionar
python sheets_import.py --entrada x.tsv --tipo campanhas --out camp.json
python sheets_import.py --entrada x.csv  --tipo metas --escala-pct pontos --out metas.json
python sheets_import.py --entrada x.txt  --tipo bruto  --out bruto.json   # mostra os cabeçalhos
```

Formatos de entrada detectados automaticamente: **tabela markdown** (o que o MCP
do Drive devolve), **TSV** e **CSV**. Uma planilha exportada costuma ter vários
blocos de tabela — o script escolhe o bloco cujo cabeçalho tem as colunas do tipo
pedido, e `--tabela N` força outro.

**Duas armadilhas que o script trata explicitamente** (ambas encontradas em teste
real com a planilha "Joie - Keyword War Room - Dados"):

1. **Separador decimal.** `31.240,50` em CSV pt-BR (delimitado por `;`) era
   quebrado em duas células quando o split aceitava `,` como delimitador. Agora o
   delimitador é detectado por linha (`;` quando presente) e o padrão numérico é
   detectado pela planilha inteira (vírgula decimal ⇒ pt-BR), nunca célula a
   célula.
2. **Escala de percentual.** `Impression Share = 1.408` pode ser 1,4% ou 14,08%
   dependendo de como o Google exportou. `--escala-pct auto|fracao|pontos`
   resolve, e o script **imprime os primeiros valores convertidos** para você
   conferir antes de confiar. Errar aqui distorce a leitura toda — por isso ele
   avisa em vez de escolher no escuro. O sinal `%` na própria célula tem
   precedência sobre `--escala-pct`: é a informação mais confiável que existe
   sobre a escala, e sem essa regra o modo `auto` leria `0,5%` como 50% (0,5 ≤ 1
   viraria fração), errando por 100× justamente nos concorrentes pequenos.
3. **Planilha corrompida por locale — recusada, não adivinhada.** Um export do
   Auction Insights em en-US (`0.1408`) colado numa planilha em **pt-BR**, onde
   `.` é separador de MILHAR, faz o Sheets engolir o ponto e o zero à esquerda:
   `0.1408` vira o inteiro **1408**. A impressão digital do problema é que as
   células com 2 casas (`0.26`) sobram como **texto**, porque o Sheets não
   consegue lê-las como milhar. `checar_taxas()` aborta com exit 2 quando
   qualquer taxa passa de 100% (impossível por definição) e explica como
   reexportar. **Não há flag para forçar**: `592` pode ter vindo de `0,592` ou de
   `0,0592`, as duas leituras são plausíveis e dão respostas diferentes —
   adivinhar aqui inventaria dado de concorrente, que é exatamente o que este
   projeto não faz.

Detalhes que evitam erro silencioso: a linha "Você" do Auction Insights (a
própria conta) é excluída dos concorrentes; o Auction Insights exportado **não
traz a campanha**, e sem `--campanha` os domínios não cruzam com o relatório de
keywords (o cruzamento é por nome de campanha) — o script avisa nesse caso; e o
JSON de saída emite as chaves `registros` **e** `result`, porque
`keyword_auction.py` lê uma e os scripts de retorno cru do Windsor leem a outra.

Para `vendas-produto`, várias linhas do mesmo produto são **somadas** (export por
pedido), não sobrescritas.

### 20. Backend: incluir item e rodar na hora (`servidor.py`)

A aba de Seleção Manual sozinha não executa nada — um HTML estático não grava
arquivo nem dispara processo. `servidor.py` é o backend local que fecha esse laço:
você inclui um produto ou concorrente, clica em **⚡ Salvar e rodar agora** e a
coleta sai na hora, **sem esperar a janela de cadência**.

```bash
cd scripts
python servidor.py --config config.json

# abra http://127.0.0.1:8787 — o painel tem de ser aberto PELO servidor,
# não por file://, senão o navegador bloqueia a conversa com a API

# passando argumentos extras para a rodada (tudo depois de --extra vai ao war_room.py):
python servidor.py --config config.json \
  --extra --ga4-json ../outputs/ga4-jornada.json --metas-json ../outputs/metas.json
```

Só de biblioteca padrão — nada de instalar dependência. Rotas: `GET /` serve o
painel, `GET /api/estado`, `POST /api/selecao` grava, `POST /api/rodar` dispara,
`GET /api/rodada?desde=N` devolve o log incremental (o painel mostra ao vivo, com
cronômetro, e oferece recarregar quando termina bem).

#### Primeira vez na sua máquina

**Decisão do projeto (2026-08-02):** o war room roda **local, na máquina do
usuário**, até a ferramenta estar fechada. Publicar em servidor está adiado por
escolha dele — o kit existe em `deploy/` e a comparação das opções está registrada
na memória do projeto, mas **não retome esse assunto sem ele pedir**.

Uma vez só, para preparar:

```bash
# Windows (PowerShell), dentro da pasta do projeto
py -m pip install openpyxl
cd scripts
copy config.example.json config.json
$env:APIFY_TOKEN = "apify_api_..."     # vale só nesta janela do PowerShell
py servidor.py --config config.json

# macOS / Linux
python3 -m pip install openpyxl
cd scripts
cp config.example.json config.json
export APIFY_TOKEN="apify_api_..."
python3 servidor.py --config config.json
```

Depois é só abrir **http://127.0.0.1:8787**. Enquanto a janela do terminal estiver
aberta, o backend está de pé; fechar a janela derruba o serviço (é local, não tem
systemd). Para deixar rodando sem token do Apify, acrescente
`--extra --simulate-ml examples/ml-simulado-rodada2.json` e o painel sobe com dado
de exemplo em vez de erro.

**Nunca** coloque o `APIFY_TOKEN` dentro do `config.json`: esse arquivo é
gitignored justamente para não vazar, mas variável de ambiente é o lugar certo.

**Sem terminal, com duplo-clique (2026-08-02):** o usuário pediu um "botão
start" no HTML — impossível de verdade (página web não tem permissão pra
ligar processo na máquina, é bloqueio de segurança do navegador, não
limitação de código). O mais perto que dá: `servidor.py` agora **abre o
navegador sozinho** ao subir (`webbrowser.open()`, com `threading.Timer` de
0.4s pro socket já estar de pé — só quando `--host` é local; `--sem-navegador`
desliga isso, pra rodar como serviço/tarefa agendada sem sessão gráfica). E
criado `scripts/iniciar-painel.bat`: duplo-clique nele entra na pasta certa
(`%~dp0`), confere se o Python existe, copia `config.example.json` pra
`config.json` se ainda não existir, e sobe o `servidor.py` — zero terminal
digitado. Pode ser arrastado pra Área de Trabalho (criar atalho) pra virar um
"ícone de app". Ainda precisa da janela preta aberta (é o processo do
servidor rodando) — fechar ela desliga, mesma limitação de sempre sem systemd.

**Atualizado (2026-08-02, mesmo dia): `.bat` agora junta as fontes reais já
coletadas antes.** O usuário notou que seções que apareciam nos entregáveis
gerados por CLI (Trends, Leilão/Keyword, KPI Próprio, Descoberta de
Concorrentes) tinham sumido na rodada ao vivo do botão. Causa: `servidor.py`
monta o comando só com `--config`/`--out`/`--html` + `self.args.extra`, e o
`.bat` nunca passava nenhum `--extra` — então nenhuma outra fonte (GA4, Meta
Ads, Keywords, Metas, Descoberta, Google Shopping) chegava no `war_room.py`
da rodada ao vivo, só o Radar ML/Shopping interno. `iniciar-painel.bat` agora
monta `--extra` sozinho, checando com `if exist` se cada arquivo convencional
existe em `..\outputs` (`own-performance-por-produto.json`, `ga4-jornada.json`,
`keywords-relatorio.json`, `meta-ads.json`, `metas.json`, `descoberta.json`,
`descoberta-shopping.json`, `descoberta-termos.json`, `google-shopping.json`,
`google-shopping-proprio.json`) — só entra o que existir de verdade, nada
inventado. Testado rodando `servidor.py` manualmente com os 10 `--extra`
apontando pra fixtures mínimas + `POST /api/rodar`, confirmando `estado: ok`.
**Não incluído de propósito:** `--trends-json`, `--keyword-auction-json`,
`--meta-ads-json` (novo criativo concorrente), `--google-ads-transparency-json`,
`--ads-manual` — são capturas pontuais/manuais que ficariam enganosas se
replicadas silenciosamente rodada após rodada sem o usuário revisitar a
fonte; continuam exigindo passar manualmente quando houver dado novo.

**Esquadrão de Combate (`render_esquadrao()`) já existe e é REAL, não é
exclusivo da demonstração.** O usuário viu a demo animada (`gerar_demo_live.py`,
com relógio de simulação e "reiniciar simulação" — 100% fake, feita pra
apresentação) agrupando alertas por agente responsável (Precificação e
Margem, Mídia Paga e Leilão, Marketplace Ops, Marca e Enforcement) e
perguntou se isso "seria abordado". Resposta: já É o comportamento do
dashboard real — `agentes.json` define esses 4 papéis, `make_alert()` já
atribui `agente_chave`/`agente_nome`/`status_acao` a cada alerta real, e
`render_esquadrao(alertas_rodada)` já roda na aba Visão Geral (antes do
Desempenho Próprio) — só ainda não apareceu no dashboard do usuário porque
as rodadas reais até agora tiveram 0 alertas. Assim que uma rodada real
detectar mudança de preço/desconto/visibilidade etc., o card do agente
responsável aparece sozinho, sem nenhum código novo.

**O painel detecta em qual modo está, não presume.** Aberto pelo servidor: barra
verde "backend conectado", botões de rodar/salvar ativos. Aberto como arquivo:
barra âmbar "modo arquivo", os botões de servidor ficam **desabilitados** (não
existe botão que parece funcionar e não faz nada) e sobram exportar/copiar o
`config.json`. A detecção é por protocolo antes do `fetch`, porque em `file://` o
navegador bloqueia a chamada antes de o JS poder tratar, e isso sujaria o console.

**Segurança — um endpoint que executa comando merece justificativa explícita:**

- Escuta em **127.0.0.1** por padrão. `--host 0.0.0.0` **exige** `--token`
  (ou `WAR_ROOM_TOKEN`), senão o script se recusa a subir: sem isso, qualquer um
  na mesma rede dispararia rodadas e queimaria seu saldo de API.
- **O comando da rodada nunca vem do navegador** — é montado no servidor a partir
  da linha de comando. `POST /api/selecao` aceita **só as quatro listas** de
  seleção e valida campo por campo contra uma lista de permissão; qualquer chave
  fora dela é descartada. Sem isso, uma aba maliciosa aberta ao lado poderia
  gravar um campo que virasse comando e ter execução remota na sua máquina.
  *Testado:* um POST com `comando_rodada: ["rm","-rf","/"]` grava o item e
  **descarta a chave**.
- Nunca `shell=True`; o subprocesso recebe lista de argumentos.
- Exige `Content-Type: application/json` e recusa `Origin` de outra origem — junto,
  é o que obriga o navegador a um preflight que falha em pedido cross-site.
- **Backup antes de sobrescrever** (`config.json.bak-<hora>`, no `.gitignore`) e
  troca atômica via `os.replace`, para nunca deixar meio arquivo.
- Uma rodada por vez (segundo clique recebe 409) e trava de intervalo mínimo
  (`--intervalo-minimo-minutos`, padrão 5) contra clique duplo; o botão pergunta
  antes de forçar, porque forçar consome saldo de verdade.
- `--timeout-minutos` (padrão 30) mata rodada travada.

**Honestidade de estado:** se o `war_room.py` sai com código ≠ 0, a rodada é
marcada **`erro`** mesmo tendo impresso coisa útil antes, e o botão de recarregar
**não** aparece — o painel na tela continua sendo o da rodada anterior, em vez de
sugerir que atualizou. Nome repetido é barrado no navegador na hora da inclusão
(o nome é a chave do diff entre rodadas; repetido, a comparação quebra) e também
no backend, como segunda barreira.

Verificado com navegador real nos dois modos: inclusão → gravação no
`config.json` → rodada disparada → item aparecendo no painel regerado, e o ciclo
"salvar sem mexer em nada" é **idempotente** (nenhum item ou campo perdido, as 25
outras chaves do config intactas).

### 21. Coletor próprio do Meta Ads (`meta_ads_api.py`) — sem Windsor

Fala direto com a Marketing API da Meta, contornando o limite de 1 conector do
plano Free do Windsor (a vaga é da GA4). Traz o que a GA4 não vê: gasto,
impressões, cliques, CTR, CPM, CPC, frequência, alcance, compras e receita pelo
pixel, e os criativos (imagem, título, corpo, link de preview).

Ler a **própria** conta de anúncio **não exige Revisão de App** — revisão só é
necessária para dados de terceiros. O passo a passo do token está em
`references/meta-api-setup.md`; resumo: usuário de sistema no Gerenciador de
Negócios, escopos `ads_read` + `read_insights`, validade "nunca expira",
permissão só de leitura na conta. Token do Explorador da API **não serve**: expira
em 1-2h.

```bash
export META_ACCESS_TOKEN='EAAG...'
export META_AD_ACCOUNT_ID='act_1234567890'

cd scripts
python meta_ads_api.py --dias 30 \
    --out ../outputs/meta-insights.json \
    --criativos-out ../outputs/meta-criativos.json

# depois, direto para as abas do war room:
python meta_ads_performance.py --ga4-campanhas examples/ga4-real/ga4-campanhas.json \
    --plataforma ../outputs/meta-insights.json --criativos ../outputs/meta-criativos.json \
    --out ../outputs/meta-ads.json
```

Só biblioteca padrão (`urllib`) — nada de SDK. Pede insight no nível de **anúncio**
por padrão, porque dá para agregar por campanha depois, mas não dá para desagregar
o que já vier somado. Segue `paging.next` até o fim (a Graph API pagina em ~25 e
ignorar isso truncaria a conta em silêncio).

**Cuidados que o script trata explicitamente:**

1. **Todo número vem como string** na Graph API (`"spend": "1284.53"`). Sem
   conversão, as somas concatenariam texto.
2. **Conversão vive dentro de `actions`/`action_values`**, e o nome muda por conta.
   Tenta `omni_purchase`, `purchase`, `offsite_conversion.fb_pixel_purchase` e
   **imprime qual usou** — escolher em silêncio esconderia divergência contra o
   Gerenciador.
3. **Ausente é `None`, nunca 0.** Uma linha sem campo `spend` não vira gasto zero
   (que faria o ROAS explodir); e um zero real de cliques é preservado como zero.
4. **Erro da Meta sai verbatim**, com código e subcódigo, e com a tradução do que
   fazer (190 = token expirado, 200/403 = falta escopo ou ativo). Recuo progressivo
   em 17/613/429/5xx.
5. **`--debug-raw`** imprime o primeiro item bruto de cada endpoint. Use na
   primeira execução real: a Meta muda nome de campo entre versões.
6. **`--versao-api`** é flag porque versões da Graph API saem de suporte a cada
   ~2 anos.

**Estado de teste (importante):** o parse e a agregação foram **testados** com
resposta salva em `examples/meta-api-insights-bruto.json` e
`examples/meta-api-ads-bruto.json`, cobrindo número como texto, conversão
aninhada, gasto ausente, zero real e anúncio sem criativo. A camada **HTTP não
pôde ser testada**: `graph.facebook.com` está bloqueado pela rede do ambiente
(verificado). Daí o `--debug-raw` e o pedido de conferir os totais contra o
Gerenciador antes de apresentar a alguém.

**Modo arquivo é honesto sobre si:** rodando com `--resposta-insights`, a saída se
declara `"origem": "ARQUIVO DE TESTE..."` e `"simulado": true`, para uma fixture
não passar por coleta real mais adiante no pipeline.

### 22. Coletor próprio do Google Ads (`google_ads_api.py` + `google_ads_oauth.py`)

Fala direto com a API oficial e produz os MESMOS nomes de campo planos que
`keyword_auction.py` e `gerar_relatorio_keywords.py` já consomem (`keyword_text`,
`campaign`, `impressions`, `clicks`, `cpc`, `first_page_cpc`, `quality_score`,
`search_impression_share`, `search_rank_lost_impression_share`) — entra sem
adaptador. Passo a passo das credenciais em `references/google-ads-api-setup.md`.

```bash
python google_ads_oauth.py                 # gera o refresh token (roda na máquina do usuário)
python google_ads_api.py --dias 30 --debug-raw \
    --keywords-out ../outputs/gads-keywords.json \
    --campanhas-out ../outputs/gads-campanhas.json
```

**O gargalo é assíncrono: peça o developer token PRIMEIRO.** O Centro de API só
existe em conta **MCC**, e o Acesso Básico passa por análise do Google que leva
dias ou semanas. Até sair, a API responde 403. Diga isso ao usuário na primeira
menção ao Google Ads, para não virar surpresa.

**O que a API NÃO entrega:** o **Auction Insights por domínio** é restrito a contas
em allowlist (liberação por representante do Google). Não prometa automatizar
aquela tabela de concorrentes — o caminho é exportar da interface e importar com
`sheets_import.py --tipo leilao`. Já a **parcela de impressões**
(`search_impression_share`, perdida por orçamento e por classificação) **vem** pela
API normalmente.

**Cuidados embutidos:**

1. **proto3-JSON usa camelCase** (`costMicros`, não `cost_micros`) e serializa
   int64 como **string**. Dinheiro vem em **micros** (÷ 1.000.000).
2. **Consulta tolerante a campo:** os campos opcionais (índice de qualidade,
   estimativas de CPC, parcela de impressões) podem ser recusados dependendo da
   conta e da versão. Em vez de perder a coleta toda, o script remove o campo
   culpado, repete e **reporta quais caíram** — que saem como n/d, nunca zero.
3. **Erro traduzido e casado com o código real:** `invalid_client` recebe a dica do
   client_id/secret, `invalid_grant` a do refresh token e do modo Teste. Dica que
   não casa com o erro manda a pessoa procurar no lugar errado.
4. **`--versao-api`** porque o Google retira versões a cada ~12 meses. Sondado ao
   vivo em 2026-08-02: v15–v19 dão 404, v20+ respondem; padrão `v22`.
5. **Modo 'Teste' do app OAuth expira o refresh token em 7 dias** — o utilitário
   avisa isso ao imprimir o token.

**Estado de teste:** aqui a camada **HTTP pôde ser testada** (ao contrário da
Meta): `googleads.googleapis.com` e `accounts.google.com` respondem, e foi
verificado com credencial inválida contra a API real que o erro chega traduzido. A
conversão foi testada com `examples/gads-api-keywords-bruto.json`. Falta a
primeira execução com credencial válida.

### 23. Windsor.ai por REST, MULTI-CONTA (`windsor_api.py`)

Contorna o limite de 1 conector do plano Free usando **uma conta Windsor por
fonte**, cada uma com a sua chave de API. A integração MCP não serve para isso —
ela autentica numa conta só, e `get_data` não aceita parâmetro de conta Windsor
(o `accounts` dele é para contas de anúncio dentro do conector). Pela REST, sim.

```bash
export WINDSOR_KEY_GADS='...'   # conta com google_ads
export WINDSOR_KEY_META='...'   # conta com facebook

python windsor_api.py --listar-campos facebook --chave-env WINDSOR_KEY_META
python windsor_api.py --dias 30 --debug-raw \
    --fonte google_ads:WINDSOR_KEY_GADS:../outputs/gads-keywords.json \
    --leilao-out ../outputs/auction-windsor.json
python windsor_api.py --dias 30 \
    --fonte facebook:WINDSOR_KEY_META:../outputs/meta-insights.json
```

**A vantagem que só existe por aqui:** o Windsor entrega `auction_insight_domain`
— a tabela de leilão por domínio concorrente — e a **API oficial do Google Ads
não entrega** (lá é restrita a contas em allowlist). Por isso o caminho Windsor
não é só "mais fácil": ele preserva uma capacidade que os coletores nativos
perdem. O leilão é **pedido separado**, porque `auction_insight_domain` não
combina com métricas de performance no mesmo request (restrição registrada no
`keyword_auction.py`) — daí o `--leilao-out`.

**Endpoint confirmado por print real do painel: é `/all` (fixo), não
`/{conector}`.** `--caminho` existe como escape se alguma conta gerar outro.
Uma resposta real de `/all` veio com **duas fontes misturadas**
(`google_ads` + `googleanalytics4`) — sem filtrar, `clicks` de um somaria com
`sessions` do outro; `filtrar_fonte()` cuida disso antes de normalizar.

**Confiança dos nomes de campo:** os de `google_ads` e `facebook` **já foram
confirmados contra dado real** colado pelo usuário (não mais palpite) —
`--listar-campos` continua disponível para quando uma conta nova divergir.

**Nome de campanha, dois problemas só visíveis com dado real:**

1. O nome que chega via UTM na GA4 vem **codificado de URL** (`+` no lugar de
   espaço, `%XX`) — `_texto_campanha()` decodifica.
2. O mesmo nome carrega decoração diferente nos dois lados (emoji de status
   colorido, espaço duplo, ponto final, acentuação inconsistente) —
   `chave_campanha()` gera uma chave de junção normalizada (sem acento,
   minúscula, sem pontuação/emoji) em `campanha_chave`, ao lado do nome de
   exibição intacto. Sem isso a mesma campanha aparece duplicada por fonte.

**Cuidados embutidos:**

1. **`%` na célula vira fração.** Windsor devolve `"ctr": "2.18%"`. Deixar como
   2.18 faria o painel exibir **218%**, porque `_f_pct` multiplica por 100. É a
   mesma armadilha de escala da planilha de Auction Insights.
2. **Ausente é `None`, nunca 0**; zero real é preservado.
3. **A chave nunca vai para o log** — o script imprime conector e período, não a URL.
4. **Erros traduzidos:** 401/403 = a chave é de uma conta que não tem esse
   conector; 402/429 = teto do plano.
5. **Vazio não vira zero:** se a resposta não trouxer linha, o script avisa e
   grava vazio de propósito.
6. **`--resposta` (modo de teste sem rede) valida a chave `data`** — uma fixture
   do formato errado (`results` do `google_ads_api.py`, por exemplo) nomeia as
   chaves encontradas no erro em vez de estourar um `TypeError` cru.

**Estado de teste:** a camada HTTP em si (`_pedir()`, dentro do próprio script)
**não pôde ser exercitada** — todos os hosts do Windsor
(`connectors.windsor.ai`, `api.windsor.ai`, `onboard.windsor.ai`, `windsor.ai`)
seguem **bloqueados** neste ambiente (verificado). Mas a **normalização já foi
validada contra dado real**: o usuário colou exports reais do painel do Windsor
(`google_ads` clique/gasto, `auction_insight_domain`, `facebook` completo) e
esse dado real passou por `normalizar()` sem erro — só não passou pela função
`_pedir()`/`coletar()` porque não veio de uma chamada HTTP feita por este
script. `--base-url` continua existindo como escape.

**Limitações do caminho, para dizer ao usuário:** teto de volume/janela do plano
Free; **imagem de criativo provavelmente não vem** (os cards da aba Meta Ads
ficariam sem arte — para isso só a API nativa serve); e várias contas gratuitas
para contornar limite de plano normalmente contraria os termos do Windsor, então
as contas podem ser fechadas e a coleta parar sem aviso.

### 24. Ator de Mercado Livre configurável (`apify_actors` / `apify_actors_campos`)

`collect_snapshot()` (dentro de `war_room.py`) lia o ator de Mercado Livre de
uma constante fixa (`ML_ACTOR`) e **ignorava** `config["apify_actors"]["mercado_livre"]`,
apesar do comentário no `config.example.json` dizer que dava para trocar por lá —
bug latente, corrigido em 2026-08-02. Agora:

```jsonc
"apify_actors": { "mercado_livre": "viralanalyzer~mercadolivre-scraper" },
"apify_actors_campos": { "mercado_livre": {"termo": "searchQuery", "limite": "maxItems"} },
"apify_actors_extra":  { "mercado_livre": {} }
```

`apify_actors_campos.mercado_livre` mapeia os NOMES DE CAMPO que o payload
manda pro ator — porque atores diferentes esperam campos diferentes, e campo
com nome errado **não dá erro, só traz coleta vazia** (mesma classe de risco
que já apareceu com os campos do Windsor). Ao trocar de ator: abra o Input dele
no painel do Apify, clique em **"JSON"** ao lado de "Form" para ver os nomes
reais, e só então preencha `termo`/`limite` (e qualquer campo fixo extra em
`apify_actors_extra`, ex.: toggles) — nunca adivinhar.

**Ativado em produção (2026-08-02):** `karamelo/mercadolivre-scraper-brasil-portugues`
(vira `karamelo~mercadolivre-scraper-brasil-portugues` na chamada da API —
Apify usa `~`, a URL da loja usa `/`) é agora o ator padrão em
`config.example.json`, no lugar do antigo `viralanalyzer~mercadolivre-scraper`
(que continua suportado — ver "Como reverter" abaixo). Decidido depois de duas
rodadas de dado real colado pelo usuário:

1. **Saída** (busca "magnesio quelato 60 capsulas", 2.105 resultados, 48 itens):
   `_campos_listagem(item, position, formato="karamelo")` lê os nomes reais
   (`eTituloProduto`, `novoPreco`/`precoAnterior` em formato BR — vírgula
   decimal, convertidos por `_num_br()` —, `Vendedor`, `freteGratis`,
   `numeroAvaliacoes`, `produtoReviews`, `zProdutoLink`), recalcula
   `discount_pct` a partir dos dois preços (mais robusto que parsear o texto
   "16% OFF"), e usa `tipoResultado` ("ORGANIC" em todos os itens testados)
   como sinal de patrocinado mais confiável que o best-effort genérico de
   `extrair_patrocinado()`. Captura também dois campos que o `viralanalyzer`
   não tem — `venda_estimada` (de `quantidadeVendida`) e `destaque` (de
   `highlight`, ex. "MAIS VENDIDO") —, aditivos, ainda sem coluna própria no
   XLSX/HTML (próximo passo natural, não feito ainda).
2. **Entrada** (print do Input em modo "JSON"): o campo de busca é `keyword`
   — **não** `nomeProduto`/`productName` como o rótulo "Nome do produto"
   sugeriria, confirmando por que nunca se deve adivinhar nome de campo. O
   payload também não tem um campo de "máximo de itens" (`limite`); ele
   pagina por `maxPages`/`maxPagesOfertas` (nº de páginas), por isso
   `apify_actors_campos.mercado_livre` só declara `termo`, e `maxPages: 2`,
   `maxPagesOfertas: 1`, `promoted: true`, `scrapeOfertas: false` foram
   copiados EXATAMENTE do payload que o usuário testou de verdade, não
   escolhidos a dedo — ver `apify_actors_extra` em `config.example.json`.
   **Em aberto:** `promoted: true` não trouxe nenhum item com
   `tipoResultado != ORGANIC` no teste — não está confirmado se esse campo
   de fato mistura anúncio patrocinado no resultado ou se é outra coisa (ex.:
   priorizar loja oficial); reavaliar se aparecer um patrocinado de verdade.

**Como reverter para o `viralanalyzer`,** se o `karamelo` decepcionar num teste
maior: troque `apify_actors.mercado_livre` para `"viralanalyzer~mercadolivre-scraper"`
e `apify_actors_formato.mercado_livre` para `"viralanalyzer"` — os dois juntos,
o código dos dois formatos continua presente e testado.

### 25. Rotina automática sem clicar em nada (Windows Task Scheduler)

O botão "Salvar e rodar agora" (passo 20) dispara uma rodada na hora, mas exige
o `servidor.py` aberto e alguém clicando. Para rodar sozinho, em intervalo fixo
(a doc já recomendava "conservador, ex. a cada 6h" — ver passo 25.1), sem
depender do backend nem de estar na frente do computador:

```powershell
setx APIFY_TOKEN "apify_api_..."      # uma vez só; abra um terminal NOVO depois
cd war-room-concorrencia\deploy
.\agendar-tarefa-windows.ps1          # padrão 6h; -IntervaloHoras N pra outro valor
```

Isso registra a Tarefa Agendada `WarRoomRodada`, que chama
`scripts\rodar_rotina.ps1` no intervalo escolhido. Esse script roda
`war_room.py` com os flags reais que já existirem em `outputs/` (Radar do
Mercado Livre é **recoletado de verdade** a cada execução — é o único lado
100% automatizável sem outra sessão; GA4/Meta/Keywords só atualizam quando os
JSONs em `outputs/` forem atualizados por fora, via Windsor). Log de cada
rodada em `outputs/rotina.log`.

**Por que `setx` e não `$env:`:** a Tarefa Agendada roda numa sessão nova do
Windows, que não herda variáveis do seu PowerShell interativo. `$env:APIFY_TOKEN = ...`
só vale na janela aberta (é o que o botão manual usa hoje); `setx` grava
permanente no seu usuário, e qualquer processo novo (inclusive a tarefa
agendada) já nasce com ela.

**Limitação a saber:** sem senha guardada na tarefa, ela só dispara com sua
sessão do Windows aberta (tela bloqueada tudo bem, desligado/deslogado não).
Rodar mesmo sem ninguém logado exigiria um servidor sempre ligado — ver
`deploy/instalar.sh`, o caminho de VPS, decisão à parte.

**Também existe (mas não substitui isto):** o próprio painel do Apify tem uma
aba **Schedules** por ator, que roda só o ator sozinho, na nuvem, sem depender
do seu computador. Mas ela só reabastece o dataset do Apify — **não** chama
`war_room.py` nem atualiza o painel sozinha, porque quem lê o resultado, monta
os alertas e regera o HTML/XLSX é este script. Útil como complemento (dado
sempre fresco esperando), não como substituto da tarefa acima.

### 26. Agente: quais produtos monitorar no Google Shopping (`descoberta_produtos_shopping.py`)

Decide QUAIS produtos merecem monitoramento no Google Shopping — por evidência
real, não por achismo, de dois canais:

1. **Anúncios do site (Google Ads):** campanha com o padrão de nome
   `"Shopping - <produto>"` é confirmação direta de Shopping Ads ativo. Achado
   real que motivou este script: a campanha `"Shopping - Colageno"` (R$ 422,78
   de gasto, 1.230 cliques) já rodava, mas "Colágeno" **não estava cadastrado
   como produto nenhum** em `produtos_monitorados`/`produtos_candidatos_manual`
   — o agente achou isso sozinho na primeira rodada de teste. Já adicionado
   como candidato em `config.example.json`.
2. **Anúncios nos marketplaces:** o NOSSO anúncio no Mercado Livre
   (`snapshot_proprio`, o mesmo que alimenta o Radar de Posição) aparecendo de
   fato na busca é sinal de catálogo ativo — candidato a ganhar Shopping mesmo
   sem campanha dedicada ainda.

```bash
cd scripts
python descoberta_produtos_shopping.py --config config.json \
    --own-performance-json ../outputs/own-performance-por-produto.json \
    --out ../outputs/descoberta-shopping.xlsx --export-json ../outputs/descoberta-shopping.json
```

Cada produto sai classificado: **já monitorado no Shopping** (campanha real
achada), **candidato** (vende no ML, sem Shopping — oportunidade), **ACHADO
fora do config** (tem Shopping real mas nenhum produto cadastrado bate com
ele — como aconteceu com Colágeno), ou **sem evidência** (não promove
sozinho, só sinaliza pra revisão).

**O que este agente NÃO faz (ainda):** não coleta CONCORRENTES no Google
Shopping — isso exige um ator do Apify pra Shopping, que ninguém testou ao
vivo (mesmo status BETA de `meta_ads.py`/`google_ads_transparency.py`). Este
agente resolve só a metade "quais produtos NOSSOS vigiar"; a coleta de quem
mais aparece lá pra esses produtos é o próximo passo natural, uma vez que já
se sabe quais produtos importam.

**Por que não virou aba nova ainda:** o usuário perguntou sobre uma aba de
orquestração de agentes — a posição tomada foi: construir agentes um de cada
vez, cada um provado contra dado real primeiro (como este foi, contra a
campanha Shopping real), e só desenhar a aba de orquestração depois de ter
pelo menos um rodando de verdade, pra saber o que ela realmente precisa
mostrar. Este é o primeiro.

### 27. Coletor de concorrentes no Google Shopping (`google_shopping.py`) — entrada e saída confirmadas

Metade que faltava do passo 26: agora que se sabe QUAIS produtos vigiar no
Shopping, este script coleta os CONCORRENTES lá — mesmo formato de saída do
Radar de ML (`{produto: {concorrente: {...}}}` + `{produto: {...}}` do
próprio), com um casador de loja mais amplo que o do ML
(`match_competitor_shopping()`, que olha `nome`/`google_advertiser`/
`sellers_ml` do concorrente, porque o nome da loja no Shopping tende a se
parecer mais com a marca do que com um nickname de ML).

**Diferença deliberada dos outros BETA deste projeto:** `meta_ads.py` e
`google_ads_transparency.py` chutaram um ator específico (de descrição
pública no Apify Store), mesmo sem testar ao vivo. Para Google Shopping eu
não tive essa confiança de início — nenhum ator foi sugerido, de propósito —
até o usuário testar um de verdade.

**Ator escolhido e 100% confirmado com dado real (2026-08-02):**
`damilo~google-shopping-apify` ("Google Shopping Scraper" na Apify Store,
$3,50/1.000 resultados).

- **Saída:** `source` (vendedor) e `link` (URL) são os campos reais — na
  frente dos palpites em `CAMPOS_ESPERADOS`. Preço chega como texto, às
  vezes com sufixo `"agora"` (`"R$ 99,40 agora"`), tratado por regex em
  `_num()`. Não há campo de preço original/desconto nesta saída —
  `discount_pct` fica sempre `None` aqui (correto: o ator não traz essa
  informação, não é bug de mapeamento).
- **Entrada:** confirmada pelo JSON real do Input —
  `{"country": "br", "date_range": "anytime", "language": "pt-br",
  "max_pages": 2, "num": "50", "query": "..."}`. `"query"` era só indício
  antes (a saída ecoava esse nome); confirmado de verdade agora.
  `"country"` é minúsculo. Não existe `maxItems` — o volume é `max_pages` ×
  `num` (este como texto, `"50"`, preservado assim em `montar_input()`).

```bash
python google_shopping.py --config config.json \
    --token $APIFY_TOKEN --out ../outputs/google-shopping.json \
    --out-proprio ../outputs/google-shopping-proprio.json --debug-raw
```

(o ator já vem de `config["apify_actors"]["google_shopping"]`, não precisa de
`--actor` a menos que queira sobrescrever)

**Ainda não ligado a `war_room.py`:** os flags existentes
`--simulate-google-shopping`/`--simulate-google-shopping-proprio` são para
teste/demo (a aba Marketplaces não os distingue de dado real com um selo,
diferente de Meta Ads/Keywords). Próximo passo certo: criar flags dedicados
`--google-shopping-json`/`--google-shopping-proprio-json` em vez de
reaproveitar os de simulação — mesmo cuidado já tomado com o Windsor (nunca
usar o caminho de teste pra dado de verdade).

### 28. Agente: termo de busca certo por produto (`descoberta_termos_busca.py`)

Achado na primeira coleta real de Google Shopping (passo 27): Faciderm/Amaze/
Linha Joie Fit não acharam Black Skull nem Growth Supplements — quem aparece
pra esses termos são farmácias/marketplaces (Amazon, Drogasil). O usuário
apontou a causa provável: o termo configurado nem sempre é o "ativo" certo —
"Colágeno" como categoria genérica é diferente de "colágeno verisol" (o ativo
específico), e um termo genérico demais atrai concorrente genérico demais.

Este agente NÃO adivinha o termo certo — ele MINERA as keywords REAIS do
Google Ads já coletadas (`outputs/gads-keywords.json`) e recomenda, por
produto, a keyword com mais clique/impressão real dentro das campanhas
daquele produto, comparando contra o `termo_busca_ml` configurado:

```bash
python descoberta_termos_busca.py --config config.json \
    --gads-keywords-json ../outputs/gads-keywords.json \
    --out ../outputs/descoberta-termos.xlsx --export-json ../outputs/descoberta-termos.json
```

**Achado real na primeira rodada, e um bug corrigido antes de confiar nele:**
a campanha `"Search - Linha Joie Fit"` mistura keywords de **dois produtos
diferentes** (whey — `"whey protein"`, 4.436 impressões — E colágeno —
`"Colageno"`, 823 impressões, 38 cliques) na mesma campanha. Casar
keyword→produto só por NOME da campanha (como `own_performance.py::match_produto`
faz, correto pro caso dele) atribuiria a keyword `"Colageno"` ao produto
"Linha Joie Fit" por engano — a primeira versão deste script fez exatamente
isso. Corrigido com `match_produto_por_keyword()`: casa a keyword direto
contra o NOME de cada produto primeiro (mais específico), só cai pra
casamento por campanha se a keyword não citar nenhum produto — com remoção
de acento dos dois lados (`_sem_acento()`), porque o dado real tem
`"Colageno"` e `"colágeno"` juntos e `norm()` do resto do projeto não tira
acento de propósito (mataria outros casamentos que dependem de acento
existir).

Resultado depois da correção: "Colágeno" ficou com a recomendação certa
(`"Colageno"`, 38 cliques reais) e "Linha Joie Fit" manteve `"whey protein
isolado"` (já bate com a keyword real de mais volume, `"whey protein"`).
`termo_busca_ml` de "Colágeno" em `config.example.json` foi ajustado pra
`"colágeno verisol"` — não o de mais clique (`"Colageno"`, genérico), mas o
mais específico que o usuário confirmou ser o ativo certo, também com
evidência real (92 impressões, 11 cliques).

### 29. Aba "Agentes" — central de status dos agentes de descoberta/recomendação

Depois de três agentes prontos (passos 11/26/28) e um coletor (passo 27), o
usuário pediu uma aba mostrando os agentes "trabalhando", com efeitos
especiais, pra fechar uma versão de uso. `render_agentes_tab()` em
`war_room.py` monta um card por agente — **painel de status, não motor**: não
recalcula nada, só reflete o que foi carregado nesta rodada via os
`--*-json` correspondentes.

**Sete cards, em duas famílias.** O usuário perguntou pela aba que mostrasse o
motor que detecta o concorrente, cruza a mudança contra a rodada anterior
(efeito) e monta a estratégia de combate — isso já existia (é o que gera os
battlecards da Visão Geral), só não tinha card na aba Agentes. Adicionados os
3 primeiros:

- **Vigilância do Radar (ML + Shopping)** — `radar_ml` (o mesmo dict que
  alimenta a aba Marketplaces). Achado = pelo menos 1 concorrente rastreado em
  algum produto nesta rodada.
- **Cruzamento de Efeito** — `alertas_rodada` filtrado pelos tipos que vêm de
  `diff_precos()` (`novo_entrante`, `queda_preco`, `aumento_preco_concorrente`,
  `novo_desconto`, `salto_visibilidade_ml`, `concorrente_sumiu`). Se
  `primeira_rodada` for `True`, o card mostra "vazio" com o motivo explícito
  (linha de base, comparação só vale a partir da próxima coleta) — nunca
  confundir "sem comparação ainda" com "sem mudança".
- **Estratégia de Combate** — conta quantos alertas da rodada têm
  `estrategia` não vazia (todo alerta tem, via `playbook_entry()` em
  `make_alert()` — este card é, na prática, "quantos battlecards saíram
  nesta rodada").

E os 4 que já existiam:
- **Descoberta de Concorrentes** — `--descoberta-json` (já existia, passo 11)
- **Produtos p/ Google Shopping** — `--descoberta-shopping-json` (novo, passo 26)
- **Termo de Busca Certo** — `--descoberta-termos-json` (novo, passo 28)
- **Radar Google Shopping** — `--google-shopping-json` (novo, passo 27)

O pulso (`.agent-pulse`, um ponto pulsante ao lado do rótulo de status) é o
efeito "em operação" — acende em qualquer card que não seja `status-off`
(ou seja, que rodou de verdade nesta rodada), diferente do border-beam
(`status-achado`), que só acende quando há achado real. Os dois efeitos juntos
respondem a "mostra os agentes trabalhando E o status": pulso = ativo agora,
beam = achou algo.

**Widget DEFCON (`render_defcon_widget()`).** Pedido depois de ver a aba
funcionando pela primeira vez com dado real: "não pode ficar sem graça" e tem
que "mudar conforme a execução". Fica no topo da aba Agentes, antes dos 7
cards. Nível calculado da severidade REAL desta rodada (`_defcon_nivel()`,
convenção militar: 1 = pior, 5 = melhor):
- `n_alta >= 2` → DEFCON 1 · `n_alta == 1` → DEFCON 2 · `n_media > 0` → DEFCON 3
- `n_baixa > 0` (sem alta/média) → DEFCON 4 · nada → DEFCON 5 (nominal)

O radar (`.defcon-radar`) gira **sem parar** (`@keyframes defcon-spin`,
velocidade por nível via `--defcon-vel` — quanto pior o nível, mais rápido) —
é o "full time"/"não ficar sem graça" pedido, sempre em movimento
independente de qualquer interação. Os pontos (`.defcon-blip`, um por
alerta, até 12) pulsam ao redor do núcleo central, que também pulsa
constantemente (`.defcon-core`). Cor e brilho (`--defcon-cor`) mudam por
nível (verde → ciano → âmbar → vermelho).

**Reage ao vivo à execução:** o mesmo polling de `/api/rodada` que já
alimenta o log de "Salvar e rodar agora" (função `vigiar()`) agora também
liga a classe `.defcon-scanning` no widget (acelera o giro do radar, troca o
rótulo pra "ESCANEANDO — coleta em andamento…") assim que uma rodada começa,
e desliga quando termina — nenhum polling novo, só um efeito colateral do
que já existia. Como o **nível** DEFCON em si é calculado no HTML gerado
(server-side), ele só atualiza de verdade depois de "recarregar painel" —
por isso o rótulo, ao concluir, avisa "recarregue o painel pra atualizar o
nível" em vez de fingir que já atualizou sozinho.

Testado com `examples/ml-simulado-rodada1.json` (linha de base → DEFCON 5) e
`examples/ml-simulado-rodada2.json` (alertas reais → DEFCON 2), com
screenshot Playwright dos dois estados, mais uma injeção manual da classe
`.defcon-scanning` via `page.evaluate` pra confirmar visualmente o estado
"escaneando".

Cada card tem 3 estados reais, nunca decorativos:
- `status-off` (borda tracejada, esmaecido) — agente existe, mas o JSON não
  foi passado nesta execução. **Não é erro.**
- `status-vazio` (borda verde) — o agente rodou (JSON carregado) e não achou
  nada de acionável nesta rodada.
- `status-achado` (borda azul + **border-beam girando**, mesma técnica visual
  de `.pipe-step.on` em `_fx_neon.py`) — o agente achou algo de verdade
  nesta rodada. É o "efeito especial" pedido: só acende em cima de achado
  real, não em todo card.

**De caminho, completado um pendente antigo:** `--google-shopping-json`/
`--google-shopping-proprio-json` agora alimentam de verdade
`montar_radar_marketplaces()` (com prioridade sobre
`--simulate-google-shopping*`, mesmo cuidado do Windsor — real nunca é
sobrescrito por caminho de teste), então o Radar Google Shopping também
aparece na aba Marketplaces quando os dois `--google-shopping-*-json` forem
passados, além do card na aba Agentes.

```bash
python war_room.py --config config.json ... \
    --descoberta-json ../outputs/descoberta.json \
    --descoberta-shopping-json ../outputs/descoberta-shopping.json \
    --descoberta-termos-json ../outputs/descoberta-termos.json \
    --google-shopping-json ../outputs/google-shopping.json \
    --google-shopping-proprio-json ../outputs/google-shopping-proprio.json
```

Testado com Playwright (screenshot da aba renderizada) contra dado real das
rodadas de teste dos três agentes — os 3 estados (off/vazio/achado) conferidos
visualmente, incluindo o card sem dado carregado (esmaecido/tracejado) e o
card com achado (borda acesa). **Só a aba HTML recebeu isso, não o XLSX** —
escopo mantido enxuto de propósito.

### 30. Múltiplas contas Apify com troca automática quando uma esgota o saldo

Usuário bateu o limite mensal de uma conta Apify em rodada real (erro real
visto: `HTTP 403 platform-feature-disabled — "Monthly usage hard limit
exceeded"`) e perguntou se dava pra cadastrar mais de uma conta pra trocar
sozinho quando uma esgotasse.

`apify_common.py` ganhou:

- **`get_tokens(config, cli_token)`** — em vez de um token só, devolve uma
  LISTA. Aceita mais de uma conta separando os tokens por vírgula na mesma
  variável: `APIFY_TOKEN='apify_api_AAA,apify_api_BBB'` (ou no `--token` da
  linha de comando). Continua vindo só de variável de ambiente/CLI — nunca do
  `config.json`, mesma regra de sempre. `get_token()` (singular) continua
  existindo, devolvendo só o primeiro, para quem ainda não foi migrado.
- **`apify_run_multi(actor, payload, tokens)`** — tenta cada token em ordem;
  só pula pro próximo quando `is_billing_error(err)` é verdadeiro (saldo/limite
  da CONTA — 402/403/usage/memory-limit/hard-limit/paid-actor/actor-disabled).
  Erro de rede/timeout **não** troca de conta (trocar de token não resolve
  timeout; é o retry de cada script que já existia que continua cuidando
  disso). Devolve `(itens, erro, indice_do_token_usado)`.

Ligado nos 6 scripts que chamam Apify: `war_room.py` (Radar ML — o principal),
`descoberta_concorrentes.py`, `google_shopping.py`,
`google_ads_transparency.py`, `google_trends.py`, `meta_ads.py`. Todos agora
recebem `tokens` (lista) em vez de `token` (string) internamente; a mensagem
de "sem token" em cada um foi atualizada pra mencionar que aceita mais de uma
conta.

Testado com token fake via monkeypatch de `apify_run` em 4 cenários: (1) 1ª
conta esgotada (erro com "hard limit") → troca sozinho pra 2ª e usa o
resultado dela; (2) só 1 conta configurada e esgotada → erro final propagado
normalmente, sem loop; (3) erro de rede ("timed out") → NÃO troca de conta,
só usa a primeira mesmo (correto: character do erro é diferente);
(4) `get_tokens` faz o parse correto de `"tokenA , tokenB"` (com espaços em
volta da vírgula). Rodado também `war_room.py --simulate-ml` ponta a ponta
depois da mudança pra confirmar que não quebrou o caminho sem token real.

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

### 31. GSAP + ScrollTrigger + Three.js no hero (`scripts/vendor/`)

Usuário pediu literalmente "gsap three scrolltrigger". Perguntei antes de
construir porque Three.js é um motor 3D pesado (~700KB minificado) e o
projeto já tinha decidido antes NÃO trazer elemento 3D pro painel (era da
propaganda de referência) — ele confirmou que queria os três mesmo assim.

**Nada vem de CDN** — mesmo princípio do `_cosmos.py` (arte gerada
proceduralmente porque a rede é bloqueada pra hosts arbitrários neste
ambiente E porque o `war-room.html` tem que continuar abrindo sozinho, sem
internet, movido de pasta). As 3 libs foram baixadas uma vez via `npm install
gsap three` (`registry.npmjs.org` é liberado, CDNs genéricos não) e ficam em
`scripts/vendor/` (`gsap.min.js`, `ScrollTrigger.min.js`, `three.min.js`) —
**arquivos versionados no repo**, não baixados a cada rodada. Three.js
moderno (r185) não publica mais build UMD/global — só ES module —, então
`three.min.js` é gerado com `esbuild` (`export * from 'three'` em modo
`iife --global-name=THREE`), não é o arquivo puro do pacote.

`render_cosmos_gl_assets()` em `war_room.py` lê os 3 arquivos
(`_ler_vendor()`) e embute INLINE em `<script>` — se a pasta `vendor/` não
existir (usuário esqueceu de copiar, ou zip antigo), a função devolve `""` e
a página funciona exatamente como antes, sem nenhum erro (testado apagando a
pasta e conferindo console limpo).

**O que foi construído, tudo com fallback gracioso:**
- Cena Three.js (`#cosmos-gl`, um `<canvas>` posto por cima da arte SVG do
  hero dentro de `.cosmos-hero-art`): starfield de ~900 partículas, disco de
  acreção (3 anéis `TorusGeometry` concêntricos com blend aditivo na mesma
  paleta violeta→magenta→ciano do `_cosmos.py`), e uma esfera preta no centro
  (horizonte de eventos) — rotação contínua + paralaxe sutil pelo mouse. A
  arte SVG **continua sendo renderizada primeiro** (nunca troca antes); o
  canvas só assume (`opacity:1`, esconde o SVG) depois que o
  `WebGLRenderer` é criado com sucesso e a 1ª cena já renderizou — GPU
  indisponível ou erro de WebGL = a SVG estática fica exatamente como sempre
  esteve, sem tela em branco.
- Efeito de scroll com GSAP + ScrollTrigger: o hero (arte + título) esmaece e
  encolhe sutilmente conforme rola a página, com `scrub` (acompanha a
  posição do scroll, não é uma animação disparada uma vez).
- `prefers-reduced-motion: reduce` desliga os DOIS efeitos por completo (nem
  inicia o Three.js, nem registra o ScrollTrigger) — a SVG estática cobre
  esse caso sozinha.

Testado com Playwright real (`--use-gl=swiftshader` pra WebGL funcionar
headless): canvas ativo e SVG escondido depois do carregamento, zero erro no
console; opacidade do hero caindo de 0,9 pra ~0,43 depois de rolar a página
(efeito do ScrollTrigger confirmado); com `prefers-reduced-motion: reduce`
emulado, canvas fica em opacity 0 e a SVG em opacity 1 (nem tentou rodar);
sem a pasta `vendor/`, página renderiza normal e sem erro. Ajuste feito no
raio dos anéis depois do primeiro screenshot mostrar o disco vazando pra fora
do container.

**Impacto no tamanho do arquivo:** `war-room.html` cresce de ~300KB pra
~1,1MB com as 3 libs embutidas (Three.js sozinho é ~700KB minificado — não
tem build menor disponível na versão atual). Isso é o preço de ser
self-contained; avisar o usuário se o arquivo ficar pesado demais pra
compartilhar por e-mail/WhatsApp em algum momento.

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
