# Protocolo de diagnóstico completo (quando um KPI próprio cai)

Isto é acionado pelo alerta `queda_kpi_proprio` (gerado por `own_performance.py
--history-dir`, quando ROAS/CTR/taxa de conversão do GA4 caem ou o CPA sobe além do
limiar) — mas o princípio vale para qualquer queda relevante de KPI que apareça na
war room. **A causa não é conhecida até este protocolo ser rodado.** Nunca pule direto
para "é a concorrência" ou para uma ação tática isolada — a queda pode ser
sazonalidade, câmbio, uma matéria negativa, uma ruptura de estoque, ou realmente o
concorrente. O trabalho é descobrir qual, com evidência, antes de propor ação.

Rode os 6 passos abaixo, nesta ordem, e feche com o diagnóstico + proposta +
autorização (passos 7 e 8). Não pule etapas para "economizar tempo" — é exatamente
a comparação entre elas que dá o diagnóstico certo.

## 1. O que a própria war room já sabe (dado interno, sem pesquisa nova)

Antes de sair pesquisando fora, reúna o que já está capturado nesta mesma rodada ou
nas últimas:
- `scripts/history/alerts.json` — alertas de concorrência (preço, desconto,
  visibilidade, criativo novo) no mesmo produto/período.
- `scripts/history/queda-keyword.json` / saída de `keyword_auction.py` — perda de
  leilão na mesma campanha.
- O próprio `own-performance-por-produto.json` — o produto caiu em TODOS os canais
  (Google Ads, Meta via GA4, GA4 orgânico) ou só num? Se é só um canal, a causa
  tende a ser interna àquele canal (ex.: criativo, lance), não de mercado.

## 2. Concorrência

Cruze com os alertas de concorrência do mesmo produto/janela (passo 1). Se não há
nenhum alerta de concorrência capturado no período, **diga isso explicitamente** —
"sem sinal de concorrência capturado nesta janela" é uma conclusão válida, não uma
lacuna a esconder. Nunca afirme "foi o concorrente X" sem um alerta/evidência
correspondente.

## 3. Sazonalidade

Confira a data do achado contra o calendário de sazonalidade do varejo/consumo
brasileiro (datas típicas que deslocam demanda de suplementos/beleza/saúde):

| Época | Efeito esperado |
|---|---|
| Janeiro ("ano novo, vida nova") | Alta de busca/demanda em suplementos, dieta, treino |
| Carnaval (fev/mar) | Queda geral de atenção/conversão em e-commerce na semana |
| Volta às aulas (jan/fev) | Desloca budget de mídia do consumidor para outras categorias |
| Dia das Mães (maio) | Alta em presente/beleza, pode canibalizar budget de suplemento |
| Dia dos Namorados (jun) | Idem, efeito menor |
| Dia dos Pais (ago) | Alta leve em suplementos "fitness" |
| Black Friday (novembro) | Alta forte de conversão, mas CPC/CPM sobem para todo o mercado — ROAS pode cair mesmo com volume subindo |
| Natal/Ano Novo (dez) | Orçamento do consumidor migra para presentes; categoria de suplemento tende a esfriar |
| Feriados prolongados | Queda pontual de sessões/conversão, recupera na semana seguinte |

Se a data do alerta cair perto de uma dessas janelas, isso pesa no diagnóstico —
mas não é conclusivo sozinho; sempre cruze com os outros passos.

## 4. Buzz da marca/produto/segmento

Use `WebSearch` (real, não invente) para checar reputação/conversa recente:
- `"<marca>" reclame aqui` — para sinais de crise de atendimento/produto.
- `"<marca>" OR "<nome do produto>"` + termos como "opinião", "resenha", "funciona",
  "fake", "polêmica" — para picos de conversa negativa.
- Nome do(s) ingrediente(s)/categoria (ex. "creatina", "colágeno verisol") + "anvisa"
  ou "alerta" — para checar se há questão regulatória/sanitária afetando a categoria
  inteira (não só a marca).
- Se o `google_trends.py` (skill irmã, passo 6 do war-room) tiver captado um pico/
  queda de interesse no mesmo período, cite isso aqui também.

## 5. Notícias/imprensa sobre o segmento, marca ou produtos

`WebSearch` focado em imprensa: `"<segmento, ex. suplementos alimentares>" notícias
<mês/ano>`, `"<marca>"` em portais de notícia, e notícias de varejo/e-commerce em
geral no período (ex. greve de transporte, mudança de imposto/tributação de
e-commerce, alteração de frete/Correios, mudança de política de marketplace).
Sempre cite a fonte (URL) — nunca resuma uma notícia que não foi de fato lida.

## 6. Contexto micro e macroeconômico

`WebSearch` os indicadores mais recentes e avalie a relevância para o poder de compra
do público-alvo (consumo de suplementos é discricionário, sensível a renda/confiança):
- Taxa Selic e tendência (juro alto trava crédito/parcelamento, reduz ticket médio)
- IPCA / inflação recente (aperta orçamento do consumidor)
- Câmbio (USD/BRL) — relevante se algum insumo/matéria-prima for importado, e porque
  CPM de mídia (Google/Meta) é parcialmente dolarizado
- Confiança do consumidor (índice Fecomércio/CNC ou equivalente mais recente)
- Desempenho do varejo/e-commerce no período (PMC do IBGE, ou notícia setorial)

O objetivo não é virar um relatório de macroeconomia — é checar se a queda bate com
um movimento de mercado mais amplo (o que muda a resposta: não dá para "vencer" uma
retração de consumo com uma tática de anúncio) ou se é isolada da marca (o que aponta
para causa interna ou de concorrência direta).

## 7. Síntese — diagnóstico com 5 lentes

Apresente a conclusão estruturada pelas 5 perspectivas, cada uma com 1–3 frases
objetivas (não é para inflar o texto, é para não deixar nenhum ângulo de fora):

- **📊 Economista** — o que os indicadores micro/macro dizem sobre a capacidade de
  compra do público nesse momento.
- **🏢 Administrador** — o que isso significa em termos de operação/recursos (vale
  realocar orçamento? pausar? é hora de negociar custo com fornecedor de mídia?).
- **📈 Estatístico** — a queda é estatisticamente relevante (magnitude, consistência
  entre canais) ou pode ser ruído/amostra pequena? Diga isso com honestidade — nem
  toda variação de uma rodada é sinal.
- **📣 Marketeiro** — o que a sazonalidade/buzz/concorrência sugerem sobre
  mensagem, criativo e canal.
- **🤝 Vendedor** — o que isso significa pro fechamento: preço, oferta, urgência,
  objeção do cliente nesse momento específico.

Termine com uma frase de diagnóstico principal (a causa mais provável, ou o combo de
causas) e o grau de confiança (alto/médio/baixo, conforme quanta evidência real
sustentou cada lente).

## 8. Ações corretivas propostas + pedido de autorização (obrigatório)

Liste as ações corretivas em ordem de prioridade, cada uma com o resultado esperado.
Depois, **pare e peça autorização explícita antes de executar qualquer uma** — isto
não é formalidade: o Windsor.ai tem ações de escrita reais (`execute_action`) que
pausam/ativam campanhas, mudam orçamento, lance, ou lançam criativo de verdade nas
contas de Google Ads/Meta da marca. Nunca chame `execute_action` sem o usuário ter
confirmado a ação específica na conversa — uma autorização não vale para todas as
ações futuras, só para a que foi descrita. Se a ação proposta não envolver escrita em
nenhuma plataforma (ex.: "monitorar mais uma rodada antes de agir"), diga isso — nem
toda queda pede uma ação executável imediatamente.
