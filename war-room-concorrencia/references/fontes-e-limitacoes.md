# Fontes, sinais e limitações por canal

Detalhe do que cada fonte realmente entrega, para calibrar promessa vs. entrega antes de
rodar a war room. Leia antes de configurar cadência ou prometer cobertura ao usuário.

## Bloqueio de rede desta sessão de trabalho (achado real, não hipotético)

Ao tentar automatizar Meta Ad Library, Google Ads Transparency Center e Google Trends,
uma chamada de teste direta (`curl`) para `api.apify.com`, `www.facebook.com`,
`adstransparency.google.com` e `trends.google.com` voltou **403 de política de
egress** da organização para esta sessão — não é erro de configuração, é bloqueio
deliberado (`gateway answered 403 to CONNECT (policy denial)`). Ferramentas de MCP
(Windsor.ai) e as ferramentas de busca (`WebSearch`) continuam funcionando porque usam
outro canal, não a rede direta desta sessão.

Isso significa que os scripts `meta_ads.py`, `google_ads_transparency.py` e
`google_trends.py` **não puderam ser testados ao vivo** nesta sessão — foram escritos
com actors reais (nomes conferidos no Apify Store via busca), mas o schema exato de
input/output não foi confirmado por uma chamada real. Rode a primeira execução real
num ambiente com acesso (máquina do usuário, outro ambiente do Claude Code) e calibre
a partir de `--debug-raw` — ver SKILL.md, passo 6.

## Mercado Livre — preço, desconto e visibilidade (automatizado, sinal forte)

Reusa o mesmo actor do `radar-keywords-concorrentes`
(`viralanalyzer/mercadolivre-scraper`, input `{"searchQuery": "<termo>"}`).

- **Preço e desconto:** os campos `price`, `original_price` e `discount_pct` vêm direto
  do anúncio — é dado observado, não estimado. Diff entre rodadas mostra queda/alta de
  preço e aparecimento/mudança de desconto com confiança alta.
- **Posição na busca (proxy de investimento/visibilidade):** a posição de um anúncio na
  lista de resultados de um termo reflete uma mistura de relevância orgânica **e**
  Mercado Ads (patrocinado) — o scraper usado não confirma, em cada item, se aquele
  resultado específico é patrocinado ou orgânico. Por isso: **subida sustentada de
  posição ao longo de várias rodadas** é tratada como sinal de "aumento de
  visibilidade/investimento", não como prova de Mercado Ads. Seja honesto sobre essa
  ambiguidade ao comentar o alerta.
- **Reviews/rating:** crescimento anormal do número de reviews entre rodadas é usado
  como proxy (fraco) de aumento de volume de vendas do concorrente — reviews são um
  atraso em relação à venda real e nem todo comprador avalia, então trate como sinal
  direcional, não como número de vendas.
- **Ruptura de estoque:** se um seller conhecido some da busca do termo, é hipótese de
  ruptura de estoque, pausa de campanha, ou apenas queda de relevância — não afirme
  "esgotado" sem checar a página do produto.

## Google Ads — leilão pago (gasto NÃO capturável; atividade parcialmente capturável)

- **Gasto/orçamento:** não existe fonte pública. Ponto final.
- **`paidResults`/`paidProducts` do scraper de SERP:** testado no `radar-keywords-concorrentes`
  e confirmado que vêm **vazios**, mesmo em termos com anúncio comprovado. Ou seja, esta
  war room **não** enxerga o leilão pago do Google via scraping automatizado.
- **Google Ads Transparency Center** (`adstransparency.google.com`): público, gratuito,
  indexa por **anunciante** (não por keyword). Mostra os anúncios **ativos** de um
  anunciante conhecido — não o gasto. Serve para contar quantos anúncios um concorrente
  tem no ar e ver esse número crescer/cair ao longo do tempo, e para capturar o
  **criativo** (headline/descrição/imagem/vídeo) de cada anúncio. Duas formas de captar:
  - **Manual** (sempre funciona): a war room gera o link pronto
    (`https://adstransparency.google.com/?region=BR&domain=<dominio>`) e recebe a
    contagem via `--ads-manual`.
  - **Automatizada, BETA** (`scripts/google_ads_transparency.py`, actor default
    `unseenuser/google-ads`, alternativas `lentic_clockss/google-ads-transparency-center-vn`
    e `automation-lab/google-ads-scraper`): detecta anúncio NOVO por diff de ID e traz o
    criativo. **Não testado ao vivo nesta sessão** (ver seção de bloqueio de rede acima)
    — calibre com `--debug-raw` no primeiro uso real.
- **Auction Insights:** a fonte definitiva de quem disputa o leilão da sua própria marca
  — mas exige acesso à conta Google Ads da marca e só enxerga os termos em que ELA
  mesma anuncia. Fora do escopo de scraping; se o usuário tiver acesso, oriente a puxar
  esse relatório manualmente e alimentar como mais um dado no `--ads-manual` ou na
  conversa.

## Meta Ads (Facebook/Instagram) — gasto NÃO capturável; atividade parcialmente capturável

- **Gasto/orçamento:** não é público, **exceto** para anúncios classificados como
  políticos/de questão social — que não é o caso de concorrência comercial de produto.
  Não afirme valor investido.
- **Meta Ad Library** (`facebook.com/ads/library/?active_status=active&country=BR&q=<nome>`):
  público, gratuito, mostra os criativos **ativos** de uma página. Duas formas de captar:
  - **Manual** (sempre funciona): contar quantos anúncios ativos aparecem para a página
    de um concorrente, e ver esse número crescer entre rodadas, via `--ads-manual`.
  - **Automatizada, BETA** (`scripts/meta_ads.py`, actor default
    `apify/facebook-ads-scraper` — oficial da Apify, alternativas
    `viralanalyzer/facebook-ads-library`, `curious_coder/facebook-ads-library-scraper`,
    `automation-lab/facebook-ads-library`): detecta anúncio NOVO por diff de ID (ou hash
    do conteúdo, se o actor não trouxer ID estável) e traz texto/imagem/vídeo do
    criativo. **Não testado ao vivo nesta sessão** (bloqueio de rede — ver acima);
    calibre com `--debug-raw` no primeiro uso real, e troque o actor em
    `config["apify_actors"]["meta_ads"]` se o default não servir.

## Mercado Livre Ads (Mercado Ads / patrocinado)

- Não há painel de transparência público equivalente ao do Google/Meta para o Mercado
  Ads de terceiros. O único proxy disponível é a posição/frequência do anúncio na busca
  (ver seção Mercado Livre acima). Se o usuário tiver acesso ao painel de Mercado Ads da
  própria conta, ele pode comparar o próprio CPC/impression share como leitura indireta
  da pressão competitiva, mas isso não vem de scraping de terceiro.

## Google Trends — interesse de busca (BETA, automatizado, não testado ao vivo)

`scripts/google_trends.py` acompanha o interesse de busca (0-100, escala relativa do
próprio Google Trends) da marca, dos produtos e dos concorrentes, e alerta quando a
média de uma rodada sobe além de `--limiar-pct` (default 40%) em relação à rodada
anterior. Actor default `apify/google-trends-scraper` (oficial), alternativas
`automation-lab/google-trends-scraper` e `scrapemint/google-trends-scraper`.

Por que via Apify e não a lib `pytrends`: o repositório está arquivado desde
abril/2025 (sem manutenção) e sofre rate-limit imprevisível (erros 429 mesmo em
volume baixo); a API oficial do Google Trends segue em alfa fechado (allowlist), não
disponível de forma geral em 2026. Manter tudo no mesmo provedor/token (Apify) evita
somar mais uma dependência não confiável.

**O que o alerta NÃO diz:** a causa do pico. Um salto de interesse pode ser
lançamento, viralização orgânica, mídia fora de ads (influenciador, PR), sazonalidade,
ou até um evento não relacionado ao negócio (mesmo nome usado por outra coisa). Isso é
investigação do agente/usuário, não algo que a ferramenta infere sozinha.

## Análise de criativo do concorrente que está impactando

Quando `meta_ads.py` ou `google_ads_transparency.py` (ou um achado de severidade alta
de preço/desconto) trouxer `imagem_url`/`video_url`/texto do anúncio, a leitura do
criativo (gancho, oferta, formato, CTA, se cita a marca própria) é feita pelo agente
no momento do alerta — usando a evidência capturada, nunca inventada. Se a captura
automatizada não trouxer a mídia (schema não confirmado, ou rede bloqueada), peça
print/link ao usuário, do mesmo jeito que `brand-bidding-monitor` já faz para achados
manuais. Um anúncio que cita a marca/produto próprio no texto vira caso de brand
bidding — encaminhe para aquela skill, não trate só como "criativo interessante".

## Leilão por palavra-chave (Google Ads Auction Insight, via Windsor.ai) — VERIFICADO

Diferente de tudo que é marcado "beta" acima, isto foi **testado com dado real** da
conta Google Ads da Joie (connector `google_ads` no Windsor.ai). Dois achados técnicos
confirmados ao vivo:

1. `auction_insight_domain` (o campo que lista quem está no leilão) **não pode ser
   combinado** com métricas de performance (`impressions`, `search_impression_share`
   etc.) na mesma chamada `get_data` — o Google Ads recusa com
   `"unsupported metrics: impressions, search_impression_share, ..."`. Por isso
   `keyword_auction.py` exige dois arquivos de entrada separados
   (`--keywords-json` e `--auction-json`) e cruza os dois pela campanha.
2. `first_page_cpc` e `position_estimates_top_of_page_cpc_micros` (as estimativas de
   CPC do próprio Google para aparecer na 1a página/topo) **vieram `null` para todas
   as palavras-chave testadas** — comum em termos de baixo volume. O script nunca
   inventa um valor aqui: relata "não disponível para este termo/período" e usa o
   CPC médio que a própria conta pagou como referência.

O que SAI real e confiável desse monitor: impression share, rank lost impression
share e Quality Score por palavra-chave (todos medidos, não estimados), e a lista de
domínios que aparecem competindo na mesma campanha (Auction Insight), ordenada por
frequência no período. Achado real ao testar (conta Joie, últimos 7 dias): termos
genéricos (`whey protein`, `omega 3`, `suplementos alimentares`, `polivitamínico`)
com Quality Score 1-3 e impression share no piso (~10%, 33-50% perdido por rank);
termos de marca (`Joie`, `Joie suplementos`) com Quality Score 9-10 e impression
share quase 100%. Domínios mais frequentes disputando essas campanhas:
`mercadolivre.com.br`, `shopee.com.br`, `vitafor.com.br`, `gsuplementos.com.br`,
`puravida.com.br`, `sanavita.com.br`, `maxtitanium.com.br`, `oficialfarma.com.br`.

## Desempenho PRÓPRIO (Google Ads / Meta Ads / GA4) — isto sim é dado real

Tudo que foi dito acima sobre "gasto não é público" vale para o **concorrente**. Para a
própria marca é diferente: se a conta estiver conectada no **Windsor.ai** (MCP já
disponível neste ambiente), `get_data` traz spend, impressões, cliques, conversões,
ROAS, CPA etc. **reais**, por campanha e por dia — não é proxy, é o dado da própria
conta. É isso que `scripts/own_performance.py` agrega por produto e o `war_room.py`
usa (via `--own-performance`) para trocar a estimativa genérica de elasticidade por uma
leitura calibrada com o desempenho real da marca naquele produto. GA4 entra do mesmo
jeito quando conectado (conector `googleanalytics4` no Windsor.ai).

## "Instantâneo"

Toda automação aqui é **por polling** (rodar o monitor e comparar com a rodada
anterior). Não existe webhook de concorrente. A cadência é o que determina a
"instantaneidade" percebida — declare sempre qual intervalo está configurado
(`cadencia_sugerida_horas` no config) e ajuste-o conforme o saldo de API disponível.

## Ideias de evolução (não implementado)

- **Validar ao vivo** `meta_ads.py`, `google_ads_transparency.py` e `google_trends.py`
  num ambiente com rede liberada, e atualizar `CAMPOS_ESPERADOS`/`montar_input()` com o
  schema real confirmado (hoje é best-effort a partir de descrição pública do actor).
- Flag explícita de "patrocinado" por item do Mercado Livre, se algum actor futuro
  expuser esse campo — eliminaria a ambiguidade do proxy de posição.
- Integração de preço do concorrente em outros canais (site próprio, Shopee, Amazon) —
  hoje o monitor cobre só Mercado Livre por ser a fonte mais confiável e barata.
- Automatizar a leitura/classificação do criativo (hoje depende do agente olhar a
  evidência manualmente a cada alerta).
