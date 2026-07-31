# Playbook de resposta — tipo de mudança → impacto → estratégia → KPIs

Esta é a versão legível do que `scripts/playbook.json` usa para montar cada alerta.
Leia antes de comentar um alerta com o usuário — a reação certa muda bastante entre os
níveis de severidade do mesmo tipo de mudança.

Convenção de impacto no volume: nunca é um número fabricado. É calculado como
`impacto_estimado_% = elasticidade_estimada × variação_percentual_do_preço_do_concorrente`
(a `elasticidade_estimada` vem do `config.json`, é uma premissa do usuário, não um dado
medido). Sempre apresente como estimativa e com a premissa explícita ao lado.

---

## 1. Queda de preço do concorrente

O concorrente reduziu o preço de um produto equivalente/substituto ao seu.

| Nível | Corte | Impacto na concorrência | Impacto estimado no volume | Estratégia imediata | KPIs impactados |
|---|---|---|---|---|---|
| **Leve** | < 5% | Ajuste normal de mercado, provável reação a sazonalidade/estoque. Baixo risco de migração de demanda relevante. | Marginal — geralmente dentro do ruído normal de conversão. | Monitorar 2–3 rodadas antes de reagir. Não gastar budget de defesa ainda. Preparar cupom de contingência caso vire tendência. | CTR e taxa de conversão do seu anúncio equivalente (para confirmar se já está sentindo o efeito). |
| **Moderada** | 5–15% | Diferencial de preço passa a aparecer nas primeiras posições de comparação (ML ordena por relevância+preço); risco real de perda de Buy Box/primeira posição em produtos-commodity. | Estimar com a fórmula acima; tipicamente perceptível na conversão do SKU equivalente em 3–7 dias. | Avaliar price-match parcial (não precisa igualar 100%, cobrir a diferença que tira o produto do "melhor preço"); reforçar frete grátis/parcelamento como diferencial não-preço; ativar cupom pontual no seu produto equivalente. | CAC, ROAS do SKU, taxa de conversão, posição média/Buy Box no Mercado Livre, ticket médio. |
| **Agressiva** | > 15% | Sinal de liquidação de estoque, entrada de novo produto substituto ou guerra de preço deliberada. Risco alto de canibalização de vendas no curto prazo. | Estimar com a fórmula acima e tratar o resultado como piso — quedas agressivas costumam converter desproporcionalmente mais do que a elasticidade "normal" sugere (efeito ancoragem). | Decisão executiva rápida: (a) price-match seletivo só no(s) SKU(s) mais expostos, não na linha toda; (b) reforçar prova social (reviews, garantia) para justificar não seguir a queda; (c) campanha de retenção/e-mail para base já convertida antes que migre; (d) checar se é liquidação (temporária) antes de comprometer margem de forma permanente. | Margem de contribuição, ROAS, CAC, share of search/Buy Box, taxa de conversão, ticket médio. |

## 2. Novo desconto/cupom do concorrente

Um `discount_pct` aparece onde não havia, ou sobe de forma relevante, mesmo sem mudar o
preço "de tabela".

- **Impacto na concorrência:** desconto por tempo limitado costuma converter mais rápido
  que uma baixa de preço permanente (urgência) — mesmo que o valor final seja parecido.
- **Impacto no volume:** tratar como a mesma fórmula da queda de preço, usando o
  percentual efetivo do desconto; adicionar um fator de urgência (o efeito tende a se
  concentrar na janela do cupom, não distribuído).
- **Estratégia imediata:** cupom-espelho de curta duração no produto equivalente;
  destacar no anúncio próprio "frete grátis"/"parcelamento sem juros" se não puder cobrir
  o desconto; monitorar se o cupom é sazonal (Black Friday, aniversário do marketplace) —
  nesse caso a resposta é sincronizar a própria campanha à mesma data, não reagir isolado.
- **KPIs impactados:** CTR, taxa de conversão, CAC no período do cupom, ROAS da campanha
  ativa no produto equivalente.

## 3. Aumento de preço do concorrente (oportunidade)

O espelho da queda — o concorrente subiu o preço.

- **Impacto na concorrência:** janela de oportunidade para ganhar posição/Buy Box e
  volume sem sacrificar margem.
- **Impacto no volume:** estimar ganho potencial com a mesma fórmula de elasticidade,
  em sentido positivo.
- **Estratégia imediata:** reforçar investimento em mídia paga (Google/Meta/Mercado Ads)
  no SKU equivalente enquanto a vantagem de preço dura; considerar reduzir desconto
  próprio parcialmente para capturar margem, mantendo-se ainda mais barato que o
  concorrente; atualizar comparativos de preço em conteúdo/anúncio.
- **KPIs impactados:** share of search/impressões, ROAS, margem de contribuição, CAC.

## 4. Salto de visibilidade/posição no Mercado Livre

O anúncio do concorrente sobe de forma sustentada na busca do termo (ver limitação de
ambiguidade orgânico-vs-patrocinado em `fontes-e-limitacoes.md`).

- **Impacto na concorrência:** mais impressões para o concorrente no mesmo termo de
  busca — nas primeiras posições do ML, o CTR cai muito rápido por posição, então cada
  posição perdida custa desproporcionalmente em cliques.
- **Impacto no volume:** correlacionado com perda de share of search, mas não
  quantificável com precisão sem dados de leilão; tratar como alerta de atenção, não
  como número fechado.
- **Estratégia imediata:** revisar ficha do produto próprio (título, imagens, reviews,
  perguntas respondidas) — fatores que pesam no ranqueamento orgânico do ML; considerar
  aumentar lance de Mercado Ads no termo se a marca já roda campanha ali; checar se o
  concorrente lançou promoção/frete que também ajuda o ranqueamento.
- **KPIs impactados:** posição média na busca, CTR, taxa de conversão, impression share
  (se a marca rodar Mercado Ads no termo).

## 5. Aumento de atividade em ads (Meta / Google / Mercado Ads) — sinal manual

Contagem de anúncios ativos do concorrente (Meta Ad Library / Google Ads Transparency
Center / posição no ML) sobe entre duas capturas.

| Nível | Corte | Impacto na concorrência | Estratégia imediata | KPIs impactados |
|---|---|---|---|---|
| **Moderado** | aumento ≥ `aumento_ads_min_unidades` anúncios ativos | Concorrente testando novos criativos/públicos ou expandindo campanha. | Auditar os criativos novos (mensagem, oferta, gancho) via os links do Ad Library/Transparency Center; ajustar mensagem própria se o concorrente estiver batendo em um ângulo que funciona. | CTR, frequência/fadiga de criativo próprio, CPM (se disponível na própria conta). |
| **Forte** | dobrou o nº de anúncios ativos em relação à última captura | Expansão relevante de investimento — pode ser lançamento de produto, nova safra de budget, ou campanha sazonal. | Reforçar defesa de marca (campanha de marca própria com CPC baixo, ver `brand-bidding-monitor`); revisar orçamento próprio nos mesmos públicos/termos; considerar acelerar lançamento próprio que estava represado. | CPC, CPA, ROAS, share of voice, taxa de conversão. |

Lembrete: o número de anúncios ativos é proxy de atividade, não de valor gasto — nunca
apresente como "concorrente investiu R$X" ou "aumentou investimento em Y%" sem essa
ressalva.

## 6. Concorrente sumiu da busca (possível ruptura/pausa)

- **Impacto na concorrência:** janela de oportunidade temporária — menos competição
  direta pelo termo/posição.
- **Impacto no volume:** oportunidade de ganho de share enquanto durar; não é permanente
  até confirmar (pode ser reposição de estoque em dias).
- **Estratégia imediata:** aumentar temporariamente investimento em mídia no termo/SKU
  equivalente para capturar a demanda órfã; não reduzir preço proativamente (a demanda
  já não tem para onde ir).
- **KPIs impactados:** share of search, volume/conversão do SKU equivalente, ROAS.

## 7. Novo entrante (concorrente novo aparece no termo)

- **Impacto na concorrência:** aumento da concorrência direta no mesmo termo de busca;
  dilui share entre mais players.
- **Impacto no volume:** risco difuso, maior quanto mais barato/melhor avaliado for o
  novo entrante.
- **Estratégia imediata:** cadastrar o novo concorrente no `config.json` para passar a
  monitorá-lo nas próximas rodadas; avaliar se ele compete por preço, por marca ou por
  diferencial de produto para calibrar a resposta.
- **KPIs impactados:** share of search, posição média, taxa de conversão.
