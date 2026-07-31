# Fontes, sinais e limitações por canal

Detalhe do que cada fonte realmente entrega, para calibrar promessa vs. entrega antes de
rodar a war room. Leia antes de configurar cadência ou prometer cobertura ao usuário.

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
  tem no ar e ver esse número crescer/cair ao longo do tempo. Hoje é **captura manual**:
  a war room gera o link pronto (`https://adstransparency.google.com/?region=BR&domain=<dominio>`)
  e recebe a contagem via `--ads-manual`.
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
  público, gratuito, mostra os criativos **ativos** de uma página. Contar quantos
  anúncios ativos aparecem para a página de um concorrente, e ver esse número crescer
  entre rodadas, é o proxy usado aqui. Hoje é **captura manual** via `--ads-manual`
  (mesmo mecanismo do Google Ads Transparency Center).
- Sem actor de scraping validado neste ambiente para o Ad Library — se o usuário tiver
  acesso a um Apify actor confiável para isso, pode-se automatizar no futuro (ver seção
  "Evolução"); até lá, não simule esse dado.

## Mercado Livre Ads (Mercado Ads / patrocinado)

- Não há painel de transparência público equivalente ao do Google/Meta para o Mercado
  Ads de terceiros. O único proxy disponível é a posição/frequência do anúncio na busca
  (ver seção Mercado Livre acima). Se o usuário tiver acesso ao painel de Mercado Ads da
  própria conta, ele pode comparar o próprio CPC/impression share como leitura indireta
  da pressão competitiva, mas isso não vem de scraping de terceiro.

## "Instantâneo"

Toda automação aqui é **por polling** (rodar o monitor e comparar com a rodada
anterior). Não existe webhook de concorrente. A cadência é o que determina a
"instantaneidade" percebida — declare sempre qual intervalo está configurado
(`cadencia_sugerida_horas` no config) e ajuste-o conforme o saldo de API disponível.

## Ideias de evolução (não implementado)

- Actor dedicado de Meta Ad Library / Google Ads Transparency Center via Apify, para
  automatizar a contagem de anúncios ativos hoje feita em `--ads-manual`.
- Flag explícita de "patrocinado" por item do Mercado Livre, se algum actor futuro
  expuser esse campo — eliminaria a ambiguidade do proxy de posição.
- Integração de preço do concorrente em outros canais (site próprio, Shopee, Amazon) —
  hoje o monitor cobre só Mercado Livre por ser a fonte mais confiável e barata.
