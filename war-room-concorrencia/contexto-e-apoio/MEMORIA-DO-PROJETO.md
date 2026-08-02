# Memória do Projeto — War Room de Concorrência (Joie Suplementos)

> Este documento existe para dar contexto completo a qualquer pessoa (ou sessão de
> IA) que continue este projeto sem ter acompanhado as conversas originais. Ele
> registra o que foi pedido, o que foi construído, as decisões tomadas, as
> descobertas técnicas e o que ainda está pendente. Para o "manual de uso" do
> sistema (como rodar cada script, o passo a passo dos 11 fluxos), ver
> `../SKILL.md`. Para as limitações e fontes de dado, ver
> `../references/fontes-e-limitacoes.md`. Este arquivo aqui é a **memória**, não
> o manual.

## COMECE AQUI — como retomar este projeto numa sessão nova

O container onde este projeto foi construído é **temporário**; o repositório
não. Tudo está no GitHub em `jrsanches1975/jrsanches`, branch
`claude/competitor-monitoring-war-room-pkhhlo`.

Para retomar, na prática:

1. Peça: *"continue o war room — leia
   `war-room-concorrencia/contexto-e-apoio/MEMORIA-DO-PROJETO.md`"*.
2. Leia **este arquivo até o fim** (sobretudo a última entrada da lista
   cronológica e a seção "PENDÊNCIA ATIVA") — a última entrada é sempre o ponto
   onde o trabalho parou.
3. Leia `../SKILL.md` para o passo a passo operacional de cada script.
4. Leia `../references/fontes-e-limitacoes.md` antes de prometer qualquer dado:
   ele diz, fonte por fonte, o que é medido, o que é proxy e o que não existe.
5. Os entregáveis prontos (HTML/XLSX) estão versionados em
   `arquivos-finais/` — não precisa regerar para consultar.
6. Para regerar tudo, os comandos completos estão no `SKILL.md`; as fixtures de
   `../scripts/examples/` permitem rodar sem token nem conector conectado.

**O que NÃO está no repositório (por design):** `scripts/config.json` (é
gitignored — cada ambiente tem o seu, copie de `config.example.json`), a pasta
`outputs/` (regenerável) e qualquer token/credencial.

## O que é isto

Um "war room" de inteligência competitiva para a Joie Suplementos (e-commerce
brasileiro de suplementos). Monitora preços, descontos, visibilidade e
atividade de anúncios de concorrentes (Black Skull, Growth Supplements, Max
Titanium etc.) no Mercado Livre e em canais de mídia paga, cruza isso com o
desempenho real da própria marca (Google Ads + GA4 via Windsor.ai), e quando os
KPIs próprios caem, aciona um protocolo de diagnóstico multi-lente (sazonalidade,
buzz de mercado, notícias, macro/microeconomia) antes de propor qualquer ação de
combate.

Domínio oficial confirmado: `joie-suplementos.com`. Seller oficial no Mercado
Livre: `JOIE`.

## Como o pedido evoluiu (ordem cronológica, resumida)

1. Pedido inicial: ferramenta de batalha para monitorar preço/desconto/ads de
   concorrentes, com análise de impacto, contra-estratégia imediata e KPIs de
   marketing.
2. Automação (Make.com ou alternativa) + conectar Google Ads/Analytics/Meta.
3. Mockup do dashboard → depois pedido explícito de redesenho: "tem que ter uns
   efeitos especiais tipo cockpit de nave espacial" → nasceu o visual HUD sci-fi
   (Orbitron + Share Tech Mono, cantos de mira, scanline, master caution).
4. Explicação da mecânica do alerta (sem código, só explicação).
5. Regra de apresentação: criativo novo → mostrar o criativo + análise; queda de
   keyword → mostrar ganhadores do leilão, CPC vencedor e estratégia de combate,
   sempre citando o(s) ponto(s) de interferência.
6. Conectar Meta e GA4 de verdade (Windsor.ai) e rodar com dado real.
7. Regra do protocolo de diagnóstico: queda de KPI próprio → investigar
   concorrência, cruzar com sazonalidade, buzz de marca/produto, notícias,
   macro/microeconomia — análise como especialista (econômico, administrador,
   estatístico, marketeiro, vendedor) → diagnóstico + ações corretivas + **pedir
   autorização** antes de executar qualquer ação de combate.
8. Simulação em tempo real de vários eventos consecutivos no próprio dashboard.
9. Explicação do método de seleção de concorrentes/anúncios (sem código).
10. Motor de descoberta e composição de concorrentes: lista manual de
    concorrentes E de produtos monitorados; para produto, buscar variantes
    similares; ranking por relevância (preço, autoridade de marca, presença de
    ads, vendas em marketplace, KPIs de redes sociais).
11. Taxonomia de agentes de IA de combate + monitor de ações em andamento
    (playbook); Radar de Posição no Mercado Livre (nós vs. concorrência: preço,
    ads, reviews); pedido explícito de "projeto sem precedentes", "guerra nas
    estrelas do combate à concorrência".
12. Simulador interativo (o usuário dispara qualquer evento manualmente, na
    ordem que quiser) — pedido duas vezes, a segunda vez para incluir o motor
    de descoberta recém-criado.
13. "Design imersivo com mais efeitos especiais" → boot sequence, starfield
    ambiente (canvas), glitch de título, hover-lift nos cards, materialização
    aprimorada — tudo fatorado em `scripts/_effects.py` para reuso nos 3
    geradores de HTML.
14. Verificação ao vivo do Windsor.ai depois que o usuário disse ter conectado
    Facebook e Google — **descoberta em andamento, ver seção própria abaixo**.
15. Painel de seleção de produtos monitorados (`gerar_painel_produtos.py`):
    tela self-contained com interruptor por produto (monitorando/candidato),
    edição inline, adicionar/remover produto, e exportação do `config.json`
    atualizado (via download ou copiar/colar) — o projeto não tem backend, então
    nada se grava sozinho.
16. Pedido do link de download do dashboard principal → arquivo enviado direto
    (`SendUserFile`) além do link do artifact já publicado.
17. Pedido para gerar/gravar contexto e memória junto dos arquivos finais numa
    pasta — este arquivo foi atualizado e `contexto-e-apoio/arquivos-finais/`
    passou a guardar cópias versionadas (commitadas, não gitignored) dos
    entregáveis HTML/XLSX mais recentes.
18. Pergunta sobre "a relação de players e a seleção e inclusão manual para
    pesquisa" — esclarecido que era sobre o relatório/planilha de descoberta já
    existente (`descoberta_concorrentes.py` → `descoberta.xlsx`), não um painel
    novo. Regerado com dado atual e entregue; adicionado também a
    `arquivos-finais/`.
19. Pergunta sobre onde salvar o `config.json` exportado do painel de produtos
    para o sistema ler — resposta: `scripts/config.json` (mesmo caminho que
    `--config config.json` já espera; é gitignored de propósito).
20. Pedido da "relação de palavras-chave usadas nas campanhas + valor dos
    leilões" — não existia (o `keyword_auction.py` só lista **quedas**, não o
    catálogo completo). Criado `gerar_relatorio_keywords.py` (reaproveita
    `agregar_keywords`/`agregar_dominios_por_campanha` de `keyword_auction.py`)
    que gera `relatorio-keywords.xlsx` com TODAS as keywords + métricas de
    leilão + domínios concorrentes por campanha. Como o Google Ads ainda não
    está conectado (pendência da seção acima), rodado com fixture simulada
    (`examples/keywords-simulado.json`) e sinalizado com `--simulado` (adiciona
    aba `⚠ AVISO` na frente do arquivo). Documentado no `SKILL.md` como passo
    "7b".
21. Pedido grande e consolidado (com referência visual anexada — mockup dark
    "fintech" com cards arredondados e gráficos coloridos): (a) o relatório de
    keywords tem que ser uma ABA do war room, não arquivo separado; (b) idem
    para o relatório de concorrentes e para o acompanhamento de produtos
    concorrentes no Google Shopping E no Mercado Livre; (c) a seleção/inclusão
    manual de produtos E concorrentes também tem que ser uma aba; (d) pedido de
    um gráfico NOVO — preço do concorrente × se está rodando ads no mesmo
    momento, marcando quando ele está "disputando direto" (posição à nossa
    frente) e a correlação com queda de KPI nosso; (e) "use python para
    economizar créditos"; (f) adotar aquele visual de referência.
    **Executado nesta mesma sessão** (ver seção "12" do SKILL.md):
    - Consolidação: `war_room.py` ganhou `--descoberta-json`,
      `--keywords-relatorio-json`, `--simulate-google-shopping(-proprio)` e
      passou a gerar um `war-room.html`/`war-room.xlsx` com TABS (Visão Geral,
      Marketplaces, Concorrentes, Keywords & Leilão, Histórico Preço×Ads,
      Seleção Manual) — nada mais fica só em arquivo avulso.
      `descoberta_concorrentes.py` e `gerar_relatorio_keywords.py` ganharam
      `--export-json` pra alimentar essas abas sem duplicar a lógica de
      agregação/score.
    - Google Shopping: sem conector/actor real ainda — estrutura pronta
      (`montar_radar_marketplaces`), alimentada por fixtures simuladas
      (`examples/gshopping-simulado*.json`); sem dado fornecido, a aba mostra
      "ainda não coletado", nunca inventa.
    - Gráfico novo: `atualizar_historico_preco_ads()` + `render_historico_chart()`
      — acumula sozinho a cada rodada real (deriva do Radar de Marketplaces +
      alertas já calculados, sem coleta nova) em
      `<history-dir>/<marca>-historico-preco-ads.json`; SVG com linha de preço,
      marcador cheio/vazio de ads, faixa sombreada de "disputa direta" e traço
      vermelho nos momentos de queda de KPI. Fixture rica de demonstração em
      `examples/historico-preco-ads-simulado.json` (`--simulate-historico-preco-ads`).
    - Seleção manual: embutida como aba (`render_selecao_manual_tab`), cobrindo
      produtos E concorrentes juntos (o painel avulso `gerar_painel_produtos.py`
      segue existindo, só com produtos).
    - Redesign visual completo: saiu o tema cockpit sci-fi (Orbitron/Share Tech
      Mono, scanline, boot sequence) SÓ do `war_room.py` — entrou tema "fintech
      escuro" (fonte Sora variável, embutida em `_fonts.py` como
      `FONT_SORA_B64`; paleta categórica validada pela skill `dataviz`: azul
      `#3987e5`, laranja `#d95926`, verde-água `#199e70` etc.; cards
      arredondados 16px, sombra suave). `gerar_demo_live.py` e
      `gerar_simulador.py` **não foram redesenhados** — continuam com o visual
      cockpit original (não foi pedido).
    - Testado ponta a ponta: sintaxe Python, JS (`node --check`), openpyxl
      (todas as abas), Playwright (as 6 abas navegando, toggle/adicionar/
      remover/exportar da Seleção Manual, fallback gracioso quando
      Descoberta/Keywords/Google Shopping não são fornecidos, acumulação REAL
      do histórico em 2 rodadas seguidas sem flag de simulação).
22. Usuário apontou que "o design não tem nada a ver com a imagem anexada" —
    correção de paleta. Tentei acessar o link de referência real
    (`desktopcommander.app/welcome`) via WebFetch e Playwright: **bloqueado
    (403)** pela política de rede deste ambiente (mesmo padrão de bloqueio já
    documentado para outros domínios — `fonts.googleapis.com`/`gstatic.com`
    seguem liberados, sites gerais não). Usuário reenviou um print (dark tech
    landing page com objeto 3D translúcido brilhante, halos/anéis neon,
    gradiente azul→violeta→magenta em botões/destaques). Corrigido:
    `:root` do `war_room.py` ganhou `--violet #8b6bf2`, `--magenta #e34fa8`,
    `--blue #4a7cf6` e `--gradient` (linear-gradient azul→violeta→magenta),
    aplicado no brand mark (glass/glow), tab ativa, botões primários, toggles
    e no acento geral (`--accent` agora é o violeta, não mais o azul sozinho).
    Fundo ficou quase-preto (`#07070f`) com glows radiais roxo/magenta/azul
    fixos no topo (imitando o halo do objeto 3D) + textura de pontos sutil.
    **Importante:** as cores CATEGÓRICAS dos gráficos (`--s1`..`--s8`,
    validadas pela skill `dataviz` para segurança de daltonismo) NÃO foram
    reordenadas nem trocadas — só a identidade visual/chrome (marca, botões,
    linha única do gráfico de histórico) passou a usar o gradiente novo. Web
    fetch de sites arbitrários continua bloqueado nesta sessão — se pedirem
    outra referência por URL, checar de novo antes de assumir que vai
    funcionar, e pedir print como alternativa direta.

23. Nova referência visual (print de capa de livro técnico "Spec-Driven
    Development"): navy quase-preto, **um único azul** de acento (sem gradiente
    multicolorido), bordas finas de 1px, micro-labels em CAIXA ALTA com
    letter-spacing largo, pill badge com separadores "·", título bicolor
    (branco + azul), régua fina sob o título, **pipeline horizontal de etapas
    com setas `»` e a etapa final acesa/glow**, **selo circular** com texto
    curvo, e **barra de credenciais** no rodapé (3 células com ícone + 2 linhas,
    separadas por régua fina). Pedido também: "procure skills de design
    avançado" — pesquisei (`SearchSkills`), só existem `canvas-design` (para
    PNG/PDF, não HTML) e `brand-guidelines` (identidade da Anthropic, não
    aplicável); as relevantes (`artifact-design`, `dataviz`) já estavam em uso.
    Implementado no `war_room.py`:
    - Paleta trocada: `--bg #040814`, `--accent #1187f0` (azul único; violeta e
      magenta REMOVIDOS), superfícies translúcidas navy, bordas
      `rgba(17,135,240,.2)`, raio 10px (era 14-16px). Fundo com grade
      blueprint 44px + glow radial azul no topo.
    - `render_seal(config)` — selo SVG com anel duplo, 24 ticks radiais
      (`math.radians`), texto curvo via `textPath` e a cadência real no centro.
      Cuidado tomado: o texto curvo estoura o arco se for longo — ficou
      "Polling · Diff" com font-size 7.6px/letter-spacing .16em num arco r=42.
    - `render_pipeline(alertas_rodada, primeira_rodada)` — COLETA » DIFF »
      ALERTA » AGENTE » AÇÃO. **Não é decoração**: a etapa acesa é a última que
      de fato aconteceu na rodada (primeira rodada acende DIFF/"linha de base";
      com alerta aguardando autorização acende AÇÃO). Os sublabels são contagens
      reais.
    - `render_credbar(config, own_perf, keywords_data)` — 3 células com fatos
      verificáveis (produtos monitorados + candidatos, concorrentes + candidatos,
      fontes ativas na rodada, marcando "(simulado)" quando for o caso).
    - `h2` virou micro-label azul tracked com régua degradê à direita;
      `h3.descoberta-produto` virou caixa alta tracked.
    - Cores CATEGÓRICAS dos gráficos (`--s1`..`--s8`) mantidas intactas de novo
      — só o chrome/identidade mudou.
    Testado: sintaxe, `node --check`, openpyxl (14 abas), Playwright (6 abas,
    selo legível, pipeline refletindo estado real em rodada-base E rodada com
    alertas, seleção manual, sem scroll horizontal no body, zero erros de JS).

24. Pedido de "layout surpreendente" com efeitos especiais: neon, movimento,
    lentes/transparências, popups e botões interativos. Criado
    **`scripts/_fx_neon.py`** (`FX_CSS`/`FX_BODY`/`FX_JS`) — separado do
    `_effects.py`, que segue sendo o tema cockpit do demo/simulador. Entregue:
    - **Ambiente:** campo de partículas em canvas com linhas de constelação e
      parallax de mouse; aurora/glow que deriva em 34s; scanline; spotlight
      radial que segue o cursor (`mix-blend-mode: soft-light`).
    - **Vidro/lente:** `backdrop-filter: blur+saturate` nos painéis; tilt 3D nos
      battlecards com reflexo radial que acompanha o cursor (`--gx/--gy`).
    - **Neon:** text-shadow no título/valores; breathe pulsante no pill de alerta
      crítico e no card crítico; **border-beam** girando na etapa ativa do
      pipeline; anel de ticks do selo girando + sweep de radar; pulso viajando
      pelas setas do pipeline.
    - **Movimento:** revelação em cascata via IntersectionObserver; contadores
      animados (só onde há número real — nunca anima um "—"); linha do gráfico
      se desenhando via `stroke-dashoffset`; pontos com pop escalonado.
    - **Popups:** modal de detalhe do battlecard alimentado por um payload JSON
      (`#fx-alertas-data`) com os MESMOS alertas já calculados, na mesma ordem
      dos cards; modal genérico de linha de tabela que lê os próprios `<th>`/
      `<td>` (serve para qualquer tabela sem payload extra); tooltip nos pontos
      do gráfico. Fecha com ESC, clique no backdrop e botão, com devolução de
      foco.
    - **Interativos:** ripple no clique de botões/abas/chips; **chips de filtro
      de severidade que filtram os battlecards de verdade** (com contagem real
      e estado vazio); navegação das abas por setas do teclado.
    Armadilhas encontradas e resolvidas: (a) o border-beam com `inset` +
    `rotate` vazava fora do card — resolvido com quadrado 200% girando dentro de
    `overflow:hidden` + `::after` mascarando o interior e `> * { z-index: 2 }`;
    (b) o texto curvo do selo estoura o arco se for longo.
    Tudo respeita `prefers-reduced-motion` (ambiente estático, animações
    desligadas, **interações preservadas**). Testado com Playwright: modal do
    card (10 campos reais), modal de tabela (9 colunas), filtro (6→1→5→6),
    tooltip, reduced-motion, regressão da seleção manual + export, build sem
    alertas (degrada sem chips/cards/erros), zero erro de JS, sem scroll
    horizontal.

25. Pedido: mais efeitos nas outras abas + uma aba inteira de GA4 (jornada de
    compra, funil, "tudo que a GA4 traz", compilado como um gestor de tráfego,
    com as melhores práticas). **A GA4 está conectada de verdade**, então TUDO
    nesta aba é dado MEDIDO, puxado ao vivo via Windsor.ai — não é simulação.
    Criado **`scripts/ga4_jornada.py`** (VERIFICADO) + aba "GA4 · Jornada".
    Números reais do período 02/07–31/07/2026 que ficaram nas fixtures
    (`examples/ga4-real/`): 20.310 sessões, 16.466 usuários (93% novos),
    engajamento 41,4%, funil 10.770 view_item → 2.974 add_to_cart → 528
    begin_checkout → 199 purchase, receita R$ 111.184, ticket médio R$ 558,71,
    conversão 0,98%, 188 compradores (82% na 1ª compra).
    Achados técnicos da coleta (documentados no SKILL.md passo 13 e no docstring):
    - **A GA4 aceita no máximo 10 métricas por `get_data`** (erro explícito
      "GA4 allows at most 10 metrics per request") → coleta em blocos.
    - O funil de e-commerce da conta é medido de verdade; existe até um funil
      nomeado `conversions_funil_jornada_de_compra___ecommerce`.
    - `engagement_rate`/`bounce_rate` voltam como fração (0-1), não %.
    Diagnóstico que o motor produziu sozinho sobre o dado real (bom exemplo do
    que o sistema deve fazer): maior vazamento = **Checkout** (só 17,8% do
    carrinho chega lá, 2.446 perdidos); **Paid Shopping com 943 sessões, 449
    add-to-cart e ZERO compra** (o script sugere checar rastreamento antes de
    culpar a audiência — volume alto com zero compra costuma ser tag/atribuição);
    Paid Social com engajamento 18,4% contra mediana 46,6%; 9 landing pages com
    tráfego e nenhuma compra (a maior: /garrafa-copa-joie/p com 493 sessões e 712
    adições ao carrinho).
    Decisões de honestidade tomadas aqui (manter em qualquer evolução):
    - Quadrantes de canal cortam pela **mediana do próprio período**, nunca por
      benchmark de mercado — e isso está escrito na legenda da aba.
    - Landing pages só entram acima de um limiar de sessões (default 100), porque
      abaixo disso a taxa oscila demais para embasar decisão.
    - A série diária tem 3 grandezas (sessões/compras/receita) e **NÃO usa dois
      eixos Y** — cada uma tem faixa normalizada própria e o absoluto vem no
      tooltip (dois eixos Y é o erro nº 1 de dataviz).
    - Nada de projeção de receita futura; métrica ausente vira `n/d`, nunca 0.
    Efeitos adicionados nas outras abas (em `_fx_neon.py`): linhas de tabela
    entrando em cascata com IntersectionObserver, régua neon na linha sob o
    cursor, linha "NÓS" do radar pulsando, shine percorrendo as barras/medidores,
    lift+glow em quadrantes/diagnósticos/devices/gauges/squadron, reflexo de
    lente nos KPIs da GA4 (sem tilt, movimento mais contido), barra da etapa de
    vazamento respirando. Corrigido: o contador animado quebrava o separador de
    milhar (mostrava "20310") — agora formata em pt-BR (`toLocaleString`) para
    inteiros e vírgula decimal para frações.
    Testado: 7 abas alternando, tooltip da série, popup de linha nas tabelas da
    GA4, reduced-motion (barras com largura final, linhas visíveis, contadores
    formatados), build sem `--ga4-json` mostrando como carregar em vez de
    quebrar, 18 abas no xlsx, zero erro de JS, sem scroll horizontal.

26. **PEDIDO (concluído na entrada 27).** O usuário mandou uma referência
    visual nova (landing page "DOMAIN Premium Internet": cosmos/nebulosa com
    buraco negro, gradientes violeta→magenta→ciano, cards de plano em vidro com
    o do meio destacado em neon, faixa de ícones+label, footer com newsletter) e
    pediu, de uma vez:
    a) aperfeiçoar o layout com base nessa imagem e **inserir imagem futurista**
       desse tipo (nebulosa/cosmos) no dashboard;
    b) na aba GA4, **desempenho das campanhas com imagens dos criativos**;
    c) **nova aba Meta Ads** com a mesma função da GA4, mas com dados e
       mecanismos do Meta;
    d) em GA4 **e** Meta: uma seção de **medidas a serem tomadas** para melhorar
       performance;
    e) **quadro de metas** (faturamento, unidades vendidas por produto, ticket
       médio) para que todo o racional das ações aponte para bater as metas;
    f) **quadro evolutivo de planejamento e evolução** — gráfico que se
       **auto-atualiza conforme as variáveis mudam**, mostrando em tempo real
       evolução × metas.
    **O que já foi feito antes de parar:** coletei o desempenho de campanhas
    REAL da GA4 (`get_data` em `googleanalytics4`, last_30d, sessions>=50) e
    salvei em `scripts/examples/ga4-real/ga4-campanhas.json` (30 campanhas, com
    campaign/source/medium + sessões/engajamento/carrinho/checkout/compras/
    receita). Nada de código novo foi escrito para os itens a-f.
    **Observações importantes já levantadas para quem retomar:**
    - As campanhas do Meta APARECEM na GA4 via UTM (source "Facebook") e o dado
      é revelador: `🟩 - [[Tráfego]] - [Padrão] - Catálogo` com 616 sessões e
      engajamento de 10,6%; várias campanhas Meta com 0 compra. Isso permite
      montar o desempenho de campanha Meta pelo lado da GA4 mesmo **sem** o
      conector do Meta ligado — mas sem gasto/impressão/clique/criativo.
    - **Imagens de criativo NÃO vêm da GA4.** Vêm do Meta (Ad Library / API).
      O conector `facebook` do Windsor segue **desconectado** nesta integração
      (ver pendência da seção acima), então a aba Meta Ads precisa nascer como
      ESTRUTURA + fixture claramente marcada como simulada (mesmo padrão já
      usado em Keywords e Google Shopping), nunca com número inventado passando
      por real.
    - A "imagem futurista" deve ser **gerada proceduralmente** (SVG/Canvas, tipo
      nebulosa/starfield/disco de acreção), não baixada: a rede está bloqueada
      neste ambiente e imagem de terceiro traria problema de direito de uso.
    - O "gráfico que se auto-atualiza conforme as variáveis mudam" pede
      controles (sliders/inputs) de premissa — tráfego, taxa de conversão,
      ticket — recalculando projeção × meta ao vivo no navegador. Deixar
      explícito na tela o que é **realizado (medido)** e o que é **projeção
      sob premissa do usuário** — nunca desenhar projeção como se fosse dado.

27. **PEDIDO DA ENTRADA 26 — CONCLUÍDO.** Implementados todos os 6 itens:
    - **(a) Visual cósmico + imagem futurista:** criado `scripts/_cosmos.py` com arte
      **gerada proceduralmente em SVG** (nebulosa, disco de acreção, buraco negro,
      cometa, starfield com seed fixa determinística) — não é imagem baixada
      (rede bloqueada + direito de uso). Paleta violeta→magenta→ciano, título com
      gradiente, divisores com cantos recortados, `cosmos-frame` com halo. O
      cabeçalho virou coluna única à esquerda com a arte ocupando a direita
      (igual à referência) — antes o buraco negro cobria o selo e as stats.
    - **(b) Campanhas com criativos na GA4:** `ga4_jornada.py` ganhou
      `--campanhas` e `--criativos`. **A imagem do criativo NÃO vem da GA4** —
      vem do Meta/Google ou de mapa manual, anexada por nome de campanha; sem
      ela o card diz "sem criativo anexado" em vez de placeholder.
    - **(c) Aba Meta Ads:** criado `meta_ads_performance.py` que mantém DUAS
      fontes explicitamente separadas: **lado GA4 (REAL** — campanhas Meta via
      UTM, 10 campanhas / 2.372 sessões / 3 compras, sem gasto/CTR/criativo) e
      **lado plataforma** (gasto/CTR/CPM/criativo, exige conector `facebook`
      desconectado → fixture com `--simulado`). Nunca soma métrica de uma com a
      outra; `roas_cruzado` sai com aviso de janelas de atribuição diferentes.
      CLI: `--meta-ads-performance-json` (o `--meta-ads-json` que já existia é o
      monitor de criativo novo de CONCORRENTE — nomes parecidos, funções
      distintas).
    - **(d) Medidas a serem tomadas:** seção nas duas abas, com ação / por quê
      (com o número) / como fazer / qual meta move, ordenadas por impacto ÷
      esforço. Sempre recomendação, nunca execução.
    - **(e+f) Metas e evolução:** criado `metas.py` + aba "Metas & Evolução" com
      quadro de metas (realizado × meta, com **traço de ritmo ideal até hoje**),
      curva de evolução acumulada × linha de meta, **alavancas** (quanto tráfego/
      conversão/ticket precisa mudar isoladamente para fechar a lacuna) e
      **simulador de planejamento** com sliders que recalculam projeção × meta ao
      vivo. Metas declaradas em `config["metas"]`.
    Números reais do quadro de metas com as metas de exemplo: faturamento 74% da
    meta (fora do ritmo), unidades 71%, ticket médio 103% (no alvo), sessões 85%,
    conversão 78%. Alavancas: +34,9% em qualquer uma das três fecharia a lacuna.
    Decisões de honestidade (manter em qualquer evolução):
    - Projeção rotulada como **premissa** (mantém ritmo médio), nunca previsão;
      sem sazonalidade nem saturação de canal.
    - Ticket médio, conversão e receita/sessão **não são acumuláveis** → sem
      linha de ritmo nem projeção.
    - Realizado por produto **não vem da GA4** → exige `--vendas-produto-json`
      (ERP/loja); sem isso fica em branco, nunca estimado.
    - Meta não declarada = "sem meta definida", nunca alvo inventado.
    - No simulador, a tela diz explicitamente o que é medido e o que é cenário.
    Bug corrigido: a revelação em cascata não disparava para conteúdo de aba que
    estava `display:none` (IntersectionObserver não observa oculto) — ao trocar
    de aba agora revela todo o painel.
    Testado: 9 abas, modal de card e de linha, simulador recalculando ao vivo
    (R$ 111.184 → R$ 202.355 com +40% tráfego e +30% conversão), reduced-motion,
    build sem os JSONs novos degradando com instrução, 18 abas no xlsx, zero
    erro de JS, sem scroll horizontal.

28. Pergunta: "não consegue extrair as conexões igual do Looker e trazer para
    nosso projeto?" (com URL de um relatório Looker Studio). **Verificado, não
    assumido:**
    - A URL do relatório responde **403** via WebFetch (é privada, exige sessão
      Google).
    - **O Looker Studio não tem API para extrair fontes de dados nem dados de
      gráfico** — a API dele só gerencia permissões de asset. Isso é limitação
      da plataforma, não do ambiente. Não insistir nesse caminho.
    - Mas o **Google Drive MCP funciona** — e achei a planilha "Joie - Keyword
      War Room - Dados" (id `1dAdIja9QQKgb-PfGoe6ux-NpJTAEQWMvB3QAlV_uwoc`) com
      **Auction Insights real**: vhita.com.br, mercadolivre.com.br,
      gsuplementos.com.br, vitafor.com.br, shopee.com.br, puravida.com.br (com
      impression share, overlap, taxa de posição superior, topo de página, 1ª
      posição e parcela de vitórias). Confirma e amplia a lista de concorrentes.
    Recomendação dada ao usuário: a rota ideal a longo prazo é conectar direto
    nas fontes (traz gasto/CTR/criativo, que nem o Looker nem a GA4 dão), mas
    está travada no plano Free do Windsor; a rota que funciona hoje é importar
    planilha. Criado **`scripts/sheets_import.py`** com 4 tipos (`leilao`,
    `campanhas`, `vendas-produto`, `metas`, mais `bruto` para inspeção),
    detecção automática de markdown/TSV/CSV e escolha do bloco de tabela.
    **Dois bugs reais achados em teste e corrigidos** (registrar para não
    repetir):
    - CSV pt-BR delimitado por `;`: o split aceitava `,` como delimitador e
      quebrava `31.240,50` em duas células. Agora detecta o delimitador por
      linha e o padrão numérico pela planilha inteira.
    - `keyword_auction.py` lê a chave `registros`, não `result` — o import
      gerava só `result` e o cruzamento dava zero. Agora emite as duas.
    Cuidados de honestidade embutidos: a escala de percentual do Auction
    Insights é ambígua (`1.408` = 1,4% ou 14,08%?), então há `--escala-pct` e o
    script IMPRIME os valores convertidos para conferência em vez de decidir no
    escuro; a linha "Você" é excluída dos concorrentes; sem `--campanha` os
    domínios não cruzam com o relatório de keywords e o script avisa; em
    `vendas-produto` linhas repetidas do mesmo produto são somadas.
    **Pendente de confirmação com o usuário:** a escala real dos percentuais
    daquela planilha (se `1.408` é 1,4% ou 14,08%) — sem isso o dado não deve
    substituir o simulado na aba de Keywords.

29. **RESOLVIDO (2026-08-02) — a escala não era ambígua, a planilha está
    corrompida.** Em vez de perguntar a escala ao usuário, baixei a planilha via
    `download_file_content` como **.xlsx** e li os valores CRUS com openpyxl (o
    `read_file_content` devolve markdown já renderizado, que era a origem da
    dúvida). O que a aba `auction_raw` guarda de fato:
    - `B2 = 1408.0` (float, formato `#,##0`), `G2 = 708.0`, `E3 = 655.0`,
      `F3 = 3534.0` — **inteiros**, não decimais.
    - `C4 = '0.26'`, `F5 = '0.43'`, `E8 = '0.61'` — **strings**.
    Diagnóstico: um export do Auction Insights em **en-US** (`0.1408`) foi colado
    numa planilha em **pt-BR**, onde `.` é separador de MILHAR. O Sheets engoliu
    o ponto e o zero à esquerda e `0.1408` virou `1408`. As células com 2 casas
    (`0.26`) sobraram como TEXTO porque o Sheets não conseguiu lê-las como
    milhar — essa mistura de inteiro grande com string decimal é a **impressão
    digital** do problema.
    **O estrago é irreversível por cálculo:** `592` pode ter vindo de `0,592`
    (59,2%) ou de `0,0592` (5,9%) e as duas leituras são plausíveis pela coluna.
    Escolher uma seria inventar dado de concorrente. Então, em vez de importar,
    `sheets_import.py` ganhou `checar_taxas()`: aborta com **exit 2** quando
    qualquer taxa passa de 100% (impossível por definição) e imprime como
    reexportar (trocar idioma da conta no Google Ads, ou usar
    *Arquivo > Importar* em vez de colar, ou formatar a coluna como Texto
    simples antes de colar). **Não há flag para forçar** — nenhuma `--escala-pct`
    conserta, porque o separador foi *perdido*, não deslocado.
    **Mais dois bugs reais achados pelo teste de regressão** (o teste com dado
    correto falhou, o que expôs os dois):
    - `_tem_virgula_decimal()` usava `re.fullmatch` na célula crua, então o `%`
      de `14,08%` impedia o casamento e a planilha era classificada como en-US —
      transformando `14,08%` em `1408`. Agora limpa `%`, `R$` e espaços antes de
      casar.
    - O modo `--escala-pct auto` leria `0,5%` como fração (0,5 ≤ 1) e reportaria
      **50%** em vez de 0,5% — erro de 100× exatamente nos concorrentes de
      participação pequena. `_pct(v, escala)` foi substituído por
      `fazer_pct(num, escala)`, que recebe a célula CRUA e dá precedência ao
      sinal `%` sobre qualquer escala escolhida.
    Testado ponta a ponta: planilha real → recusada com exit 2; os mesmos dados
    em pt-BR correto → `0.1408 / 0.708`; borda `0,5%` → `0.005`; e os tipos
    `campanhas`, `vendas-produto` e `metas` seguem convertendo certo.
    **Estado do dado:** a aba de Keywords & Leilão continua com dado simulado e
    marcado como tal. Os 6 domínios da planilha são achado real e válido (a
    LISTA de concorrentes serve); só os PERCENTUAIS estão inutilizáveis até o
    reexport.

30. **Backend local (`scripts/servidor.py`) — pedido de 2026-08-02.** O usuário
    pediu: "na inclusão manual deve ter um botão pra assim que incluir algum
    produto ou concorrente ele poder ser acionado e o sistema começar a rodar com
    as novas informações sem esperar a janela de 6hs. precisamos de um backend".
    Correto — HTML estático não grava arquivo nem executa processo. Criado
    `servidor.py`, só biblioteca padrão (`http.server` + `subprocess`), com
    `GET /`, `GET /api/estado`, `POST /api/selecao`, `POST /api/rodar`,
    `GET /api/rodada?desde=N`. A aba de Seleção Manual ganhou barra de estado do
    backend, **⚡ Salvar e rodar agora**, **⌸ Só salvar** e painel de log ao vivo
    com cronômetro.
    **Decisões de segurança (não afrouxar sem pensar):** escuta em 127.0.0.1 e
    `--host` aberto EXIGE `--token`; o comando da rodada é montado no servidor a
    partir da linha de comando e **nunca** vem do POST; `POST /api/selecao` aceita
    só as 4 listas e valida contra lista de permissão de campos (testado: uma
    chave `comando_rodada` injetada é descartada); sem `shell=True`; exige
    `Content-Type: application/json` e recusa `Origin` estranha; backup +
    `os.replace` atômico.
    **Honestidade de estado:** código de saída ≠ 0 ⇒ rodada marcada `erro` e o
    botão de recarregar NÃO aparece (o painel na tela segue sendo o da rodada
    anterior, em vez de sugerir que atualizou).
    **Bugs achados pelos testes** (todos com navegador real via Playwright):
    - o front deixava adicionar nome duplicado e só descobria no salvamento, com
      `alert` cru. Agora barra na inclusão, comparando sem diferenciar caixa — o
      nome é a chave do diff entre rodadas, repetido a comparação quebra.
    - o `fetch` em `file://` era bloqueado pela política de origem antes do JS
      poder tratar, sujando o console com erro de CORS. Agora a detecção é por
      `location.protocol`, sem tentar.
    - `/favicon.ico` gerava 404 no log a cada carregamento → responde 204.
    **Verificado ponta a ponta:** inclusão no navegador → gravação no
    `config.json` → rodada disparada → item no painel regerado; ciclo "salvar sem
    mexer em nada" idempotente (nenhum campo perdido, 25/25 das outras chaves
    intactas); trava de rodada simultânea (409) e de intervalo mínimo, com
    confirmação antes de forçar.
    **Armadilha do ambiente, para não perder tempo de novo:** `pkill -f`/`pgrep -f`
    casam com a própria linha de comando do shell quando ela contém o texto
    `servidor.py` (ex.: um `nohup python3 servidor.py` na mesma chamada) e **matam
    o próprio shell** (exit 144). Mate os processos numa chamada separada, sem o
    nome literal no resto do comando.

31. **DECISÃO: fica local até a ferramenta estar fechada (2026-08-02).** Depois de
    avaliarmos as opções de hospedagem, o usuário decidiu: *"vamos manter tudo como
    está agora na minha máquina até a ferramenta estar finalizada sem alterações aí
    a gente decide"*. Então o modo de uso é `servidor.py` rodando na máquina dele,
    e o `SKILL.md` (passo 20) tem o passo a passo de Windows e macOS/Linux.
    **Não retome o assunto de hospedagem sem ele pedir.** O material de decisão já
    está levantado, para não refazer a pesquisa:
    - **Hospedagem compartilhada de cPanel (HostGator e afins): NÃO serve.** Feita
      para PHP; não mantém processo Python vivo nem escuta em porta própria.
    - **VPS: serve, e é o encaixe do que ele pediu** (botão instantâneo com log ao
      vivo, histórico como arquivo, máquina reaproveitável em outros projetos).
      HostGator VPS tem root/SSH, ~R$86/mês; o *always free* ARM da Oracle roda
      isso sem mensalidade. Kit pronto e testado em `deploy/`.
    - **GitHub Actions sozinho: encaixe ruim** — sem processo vivo o botão perde a
      graça (20-60s só para subir, sem log ao vivo), o `scripts/history/` teria de
      ser commitado a cada rodada (perder o history faz toda rodada virar "primeira
      rodada", sem diff e sem alerta), e Pages em repositório privado publica o
      painel **aberto** (controle de acesso é recurso de Enterprise) — inaceitável
      para um painel com metas de faturamento e inteligência de concorrente.
    - **Netlify sozinho: não roda o pipeline.** Confirmado na documentação oficial
      (via `get-netlify-coding-context`): as funções serverless dele são
      **Node.js**, não há runtime Python — e o projeto é ~4 mil linhas de Python
      com `openpyxl`. Serve muito bem para *servir* o painel (estático, CDN, HTTPS,
      domínio próprio); a senha nativa é de plano pago, mas daria para fazer numa
      edge function.
    - **Netlify + GitHub Actions: combinação coerente e sem mensalidade**, e
      corrige as duas objeções ao Actions puro: o botão chama uma função Node no
      Netlify que dispara o `workflow_dispatch`, então o token do GitHub fica nas
      variáveis de ambiente do Netlify e **nunca no HTML**; e o painel fica no
      Netlify em vez do Pages, então não precisa ser público. Preço: latência de
      ~1min no botão, log por consulta à API em vez de linha a linha, e histórico
      via commit. Estimativa de trabalho: meio dia.

32. **Opção 3 escolhida e iniciada (2026-08-02): coletores próprios, sem Windsor.**
    O usuário disse "faz o passo 3". Criado `scripts/meta_ads_api.py`, que fala
    direto com a Marketing API da Meta (só `urllib`, sem SDK) e produz os dois
    arquivos que `meta_ads_performance.py` já consome (`--plataforma` e
    `--criativos`). Guia de token em `references/meta-api-setup.md`; documentado
    como passo 21 do `SKILL.md`.
    **Verificações de rede feitas neste ambiente (não repetir):**
    `graph.facebook.com` → **bloqueado** (curl não completa);
    `googleads.googleapis.com` → **responde** (404 na raiz, que é o normal para
    raiz de API). Ou seja: a camada HTTP da Meta não pôde ser testada aqui, mas a
    do Google Ads provavelmente poderá.
    **Testado com fixture** (`examples/meta-api-insights-bruto.json` e
    `meta-api-ads-bruto.json`, formato copiado da Graph API, valores inventados):
    número vindo como string, conversão aninhada em `actions`, gasto ausente
    virando `None` (e não zero, que faria o ROAS explodir), zero real de cliques
    preservado, anúncio sem criativo descartado, e a cadeia completa até
    `meta_ads_performance.py` gerando CTR/CPM/CPC/ROAS e os cards de criativo.
    **Bugs meus achados nos testes:** (a) o resumo imprimia `R$ 2.336.63` porque
    eu trocava `,` por `.` de forma ingênua — o MESMO erro de separador que
    corrompeu a planilha de Auction Insights; corrigido com troca em três passos
    (`_brl`). (b) no modo arquivo a saída se declarava `"origem": "Meta Marketing
    API"`, o que faria uma fixture de teste passar por coleta real adiante no
    pipeline; agora declara `"ARQUIVO DE TESTE"` e `"simulado": true`.
    **Confirmado que NÃO é bug:** os formatadores do `war_room.py` usam
    `isinstance`, então zero medido sai como `0,0%` e não `n/d` — a distinção
    entre "medido zero" e "não medido" está correta nas duas direções.
    **Próximo passo (não feito ainda):** o coletor do **Google Ads**. Ele exige um
    **developer token** aprovado pelo Google, e essa aprovação é assíncrona (dias)
    — o usuário precisa iniciar o pedido em `ads.google.com` → Ferramentas → Centro
    de API para não virar gargalo. A API é bem mais complexa que a da Meta (OAuth2
    com refresh token + consultas GAQL), e existe a opção de usar `urllib` contra a
    REST da Google Ads API em vez do SDK pesado.

33. **Coletor do Google Ads pronto (2026-08-02).** `scripts/google_ads_api.py`
    (campanhas + keywords) e `scripts/google_ads_oauth.py` (gera o refresh token na
    máquina do usuário). Guia em `references/google-ads-api-setup.md`, passo 22 do
    `SKILL.md`. Saem com os nomes de campo planos que `keyword_auction.py` já
    consome, então plugam sem adaptador.
    **Descobertas verificadas ao vivo (não repetir a sondagem):**
    - Versões da Google Ads API: **v15 a v19 devolvem 404** (retiradas), **v20, v21,
      v22, v23 e v24 respondem 401** (existem, exigem auth). Padrão adotado: `v22`.
    - **`business.facebook.com`, `developers.facebook.com` e `ads.google.com` estão
      BLOQUEADOS** neste ambiente; **`accounts.google.com` (302) e
      `googleads.googleapis.com` (404 na raiz) RESPONDEM.** Ou seja: as telas de
      criar credencial não abrem daqui, mas as APIs do Google sim — e por isso a
      camada HTTP do coletor do Google pôde ser testada, ao contrário da Meta.
    - **Auction Insights NÃO está na API pública do Google Ads** — só contas em
      allowlist, liberadas por representante do Google
      (groups.google.com/g/adwords-api/c/30s21wGZkOU). **Não prometer automatizar
      aquela tabela de domínios.** O caminho é exportar da interface e importar com
      `sheets_import.py --tipo leilao`. Parcela de impressões, por outro lado, vem
      pela API normalmente.
    **Bugs meus achados nos testes:**
    - A dica de erro do OAuth falava de `invalid_grant` quando o Google respondia
      `invalid_client` — orientação que manda procurar no lugar errado. Agora a
      dica é escolhida pelo código real do erro.
    - No `google_ads_oauth.py` eu chamava `handle_request()` **duas vezes** (uma em
      thread, uma no fluxo principal): a thread engolia o retorno do Google e o
      principal esperava para sempre um segundo retorno. A thread era desnecessária
      — o socket já escuta desde o construtor do `HTTPServer`.
    - A fixture do Google Ads estava internamente inconsistente (`costMicros` com
      três zeros a menos que `clicks × averageCpc`), o que confundiria quem
      calibrasse por ela. Corrigida.
    **Posição registrada sobre credenciais:** o usuário ofereceu autorizar acesso
    pelo navegador ("acesse tudo que precisa... que vou autorizando"). Foi
    respondido que isso não destrava, por três motivos: as telas de credencial
    estão bloqueadas na rede, não há acesso ao navegador logado dele, e **token não
    deve trafegar por chat** (fica em log; um token de sistema da Meta que "nunca
    expira" viraria credencial permanente exposta). **Não pedir nem aceitar
    credencial pelo chat em nenhuma sessão futura** — as credenciais vivem em
    variável de ambiente na máquina dele.
    **Pendente do lado do usuário:** (a) token de usuário de sistema da Meta;
    (b) developer token do Google Ads, que passa por análise de dias/semanas e
    exige conta MCC — foi pedido que ele inicie isso o quanto antes, porque é o
    único item com prazo externo.

34. **DECISÃO (2026-08-02): seguir SÓ pelo Windsor multi-conta.** O usuário criou
    duas contas Windsor a mais, uma por ferramenta, e ao ser apresentado às opções
    escolheu explicitamente "Só Windsor multi-conta" — abandonando o caminho dos
    coletores nativos. Foi informado dos custos dessa escolha (teto do plano Free,
    provável ausência da imagem de criativo, e que múltiplas contas gratuitas
    normalmente contrariam os termos do Windsor) e manteve a decisão. **Respeitar
    isso**; `meta_ads_api.py` e `google_ads_api.py` ficam no repositório, prontos,
    para retomada eventual — não são o caminho ativo.
    **Verificado antes de construir:** `get_data` do MCP **não aceita** parâmetro de
    conta Windsor (o `accounts` dele é para contas de anúncio dentro do conector),
    então por MCP três contas não somam nada. E **todos os hosts do Windsor
    (`connectors.windsor.ai`, `api.windsor.ai`, `onboard.windsor.ai`, `windsor.ai`)
    estão BLOQUEADOS neste ambiente** — a camada HTTP do novo script não pôde ser
    testada, só a normalização.
    **Achado que melhora a decisão dele:** o Windsor entrega
    `auction_insight_domain`, e `keyword_auction.py` já rodou com esse dado REAL —
    ou seja, o Windsor dá a tabela de leilão por domínio que a **API oficial do
    Google não dá** (allowlist). Isso cancelou o item da checklist de reexportar a
    planilha à mão, e é um ponto objetivo a favor do caminho escolhido.
    Criado `scripts/windsor_api.py`: `--fonte CONECTOR:VARIAVEL:SAIDA` repetível,
    `--listar-campos` para descobrir campos, `--leilao-out` (pedido separado, porque
    `auction_insight_domain` não combina com performance), `--debug-raw`, `--resposta`
    para teste sem rede.
    **Bug meu achado no teste:** o `%` do Windsor (`"ctr": "2.18%"`) era removido e
    o valor ficava em pontos, o que faria o painel exibir **218%** (o `_f_pct`
    multiplica por 100). Agora `%` vira fração. Terceira vez que a mesma classe de
    erro de escala aparece neste projeto — vale desconfiar dela sempre.
    **Confiança dos nomes de campo:** `google_ads` confiável (vem do
    `keyword_auction.py` verificado); **`facebook` é palpite** e precisa de
    `--listar-campos` antes de uso. **Pedido ao usuário:** rodar `--listar-campos
    facebook` e mandar a lista.
    Checklist reescrita em `contexto-e-apoio/PROXIMOS-PASSOS.md`: caiu o token da
    Meta, caiu todo o bloco de credenciais do Google Ads e caiu o reexport manual da
    planilha. Sobrou conectar uma fonte por conta, pegar as três chaves, conferir
    campos e coletar.

35. **`windsor_api.py` corrigido contra o endpoint real e a decoração de nome de
    campanha (2026-08-02).** O usuário mandou print do painel do Windsor com a URL
    real gerada: o endpoint é `/all` (fixo), não `/{conector}` como eu tinha
    assumido — `montar_url()` corrigido, com `--caminho` como escape se alguma
    conta usar outro. O `/all` real veio com **duas fontes misturadas** na mesma
    resposta (`google_ads` + `googleanalytics4`); sem filtrar, `clicks` de Ads
    somaria com `sessions` de GA4 — criado `filtrar_fonte()`.
    Nome de campanha real trouxe dois problemas que só apareceram com dado de
    verdade: (a) o nome que chega via UTM da GA4 vem **codificado de URL**
    (`+` no lugar de espaço, `%XX`) — `_texto_campanha()` decodifica; (b) o mesmo
    nome carrega decoração diferente dos dois lados (emoji de status colorido,
    espaço duplo, ponto final, acentuação inconsistente) — criada `chave_campanha()`,
    uma chave de junção normalizada (sem acento, minúscula, sem pontuação/emoji),
    guardada em `campanha_chave` ao lado do nome de exibição intacto. Sem isso a
    mesma campanha apareceria duplicada por fonte no painel.
    `--resposta` (modo de teste sem rede) ganhou validação: antes, uma fixture do
    formato errado (`results` do `google_ads_api.py` em vez de `data` do REST do
    Windsor) estourava um `TypeError` cru — agora a mensagem nomeia as chaves
    encontradas e aponta a causa provável.

36. **Primeiro dado REAL do Windsor processado, três fontes ao mesmo tempo
    (2026-08-02).** O usuário colou três exports reais do painel do Windsor
    (`/all`, JSON completo, não recortado): `google_ads` clique/gasto por
    campanha, `google_ads auction_insight_domain` (leilão por domínio, 771
    registros, 03/07 a 31/07) e `facebook` com todos os campos (impressões, CTR,
    CPM, gasto, 241 registros, 03/07 a 01/08). Complementado com uma chamada real
    via MCP (`get_data` na conta `mktjoiesuplementos@gmail.com`, que já está
    conectada) filtrando GA4 por `source=Facebook`, trazendo o lado GA4 das
    mesmas campanhas Meta (55 registros).
    Os três foram normalizados por `windsor_api.py` e gravados em
    `outputs/auction-windsor.json`, `outputs/meta-insights.json` e
    `outputs/ga4-campanhas-facebook.json` — **dado real, não fixture** (por isso
    NÃO usei o modo `--resposta`, que sempre marca `simulado: true`; processei
    com um script avulso chamando `normalizar()` direto, para poder gravar
    `simulado` como ausente/false e a origem real correta).
    Rodado `meta_ads_performance.py --ga4-campanhas ... --plataforma ...` **sem**
    `--simulado` — as duas pontas (GA4 e plataforma) agora são reais ao mesmo
    tempo pela primeira vez. Saída em `outputs/meta-ads-performance.json`.
    **Achado no leilão:** comparando a taxa de presença de cada domínio na janela
    de alta de CPC já identificada (18-26/07) contra o resto do período,
    `renovabe.com.br`, `soldiersnutrition.com.br`, `darklabsuplementos.com.br`,
    `coompare.com.br` e `vivatrue.com.br` aumentaram presença especificamente
    nessa janela (a `maxtitanium.com.br`, já rastreado, também) — adicionados a
    `candidatos_concorrentes_manual` em `config.example.json` com a origem
    anotada. É correlação, não confirmação: falta impression_share real para
    fechar a causalidade, e falta ainda **decidir se `gsuplementos.com.br`
    (51 de 62 dias, o domínio mais presente depois dos marketplaces) é o mesmo
    Growth Supplements já cadastrado sob `growthsupplements.com.br`** — sinalizado
    ao usuário, não presumido nem corrigido sozinho.
    **Ainda faltando para fechar a aba Keywords & Leilão com dado real:** dado
    de keyword_text (impressions, search_impression_share) do Google Ads — só
    veio clique/gasto por campanha e o leilão por domínio, não por palavra-chave.
    **Achado um bug de mojibake, não corrigido:** uma campanha (6 sessões, peso
    desprezível) veio com o emoji já corrompido antes da URL-codificação
    (`ðŸŸ©` em vez de `🟩`) — sintoma de um encoding errado na origem (provavelmente
    no próprio parâmetro UTM configurado na plataforma), não algo que
    `_texto_campanha()` deveria tentar adivinhar/consertar.
    **Não rodei `war_room.py` para regenerar o HTML/XLSX final** porque a aba de
    Radar do Mercado Livre exige coleta ao vivo via Apify (`APIFY_TOKEN`), que não
    existe neste ambiente — usar `--simulate-ml` teria regredido essa aba de
    "real" para "simulado" no export novo, então preferi deixar o HTML como está
    e documentar o comando completo para o usuário rodar na máquina dele (ver
    `PROXIMOS-PASSOS.md`).

37. **Rotina automática do Radar (Windows Task Scheduler) + bug do ator fixo
    (2026-08-02).** Usuário pediu uma rotina para rodar o ator do Apify sozinho,
    sem esperar clique no botão manual. Print da conversa mostrou que ele estava
    olhando o ator `karamelo/mercadolivre-scraper-brasil-portugues` no painel do
    Apify (conta pessoal "Joie Suplement...", $5/1.000 resultados) — **diferente**
    do que o código usa hoje (`viralanalyzer~mercadolivre-scraper`, campo
    `searchQuery`/`maxItems`). Ao investigar, achado um bug latente:
    `collect_snapshot()` em `war_room.py` tinha uma constante fixa `ML_ACTOR` e
    **ignorava** `config["apify_actors"]["mercado_livre"]`, apesar do comentário
    no `config.example.json` prometer que era trocável por config, sem editar
    código. Corrigido: o ator agora vem de config de verdade, e os NOMES DE CAMPO
    do payload também viraram configuráveis (`apify_actors_campos.mercado_livre`,
    `apify_actors_extra.mercado_livre`) — porque atores diferentes esperam campos
    diferentes, e campo com nome errado não dá erro, só traz coleta vazia (mesma
    classe de risco já vista com os campos do Windsor).
    Perguntado ao usuário se ele queria trocar de ator ou só automatizar o atual;
    respondeu "testa e usa o que trouxer as informações mais apuradas" — **não
    pude testar os dois** (sem `APIFY_TOKEN` neste ambiente, e sem MCP do Apify
    conectado nesta sessão) nem confirmar o nome real do campo de busca do
    `karamelo` (visto só no formulário como "Nome do produto", não no JSON) —
    ambos ficaram como pendência do usuário em `PROXIMOS-PASSOS.md`, item 6.
    Criados `deploy/agendar-tarefa-windows.ps1` (registra a Tarefa Agendada
    `WarRoomRodada` via `Register-ScheduledTask`, idempotente, parâmetro
    `-IntervaloHoras`, default 6h) e `scripts/rodar_rotina.ps1` (roda
    `war_room.py` com os `--*-json` reais que existirem em `outputs/`, loga em
    `outputs/rotina.log`, propaga o código de saída). **Achado de plataforma
    importante:** a Tarefa Agendada roda numa sessão nova do Windows, que NÃO
    herda `$env:APIFY_TOKEN` de uma janela de PowerShell interativa — só `setx`
    (gravação permanente por usuário) resolve; documentado nos dois scripts e no
    checklist, para não virar "token sumiu" sem explicação depois.
    **Registrado, não implementado:** o painel do Apify tem sua própria aba
    "Schedules" por ator — reabastece o dataset do Apify sozinha, na nuvem, mas
    NÃO chama `war_room.py` nem atualiza o painel, porque é o nosso script quem
    lê o resultado e monta os alertas/HTML. Não é substituto da tarefa do
    Windows, só um complemento possível.

38. **Saída do `karamelo~mercadolivre-scraper-brasil-portugues` mapeada e testada
    contra dado real (2026-08-02, mesmo dia da entrada 37).** O usuário colou uma
    coleta real do ator (busca "magnesio quelato 60 capsulas", 2.105 resultados,
    campos completos por item). Isso resolveu a metade que faltava da entrada 37:
    o lado de SAÍDA agora está implementado e testado — `_campos_listagem(item,
    position, formato="karamelo")` em `war_room.py` lê os nomes reais do
    `karamelo` (`eTituloProduto`, `novoPreco`/`precoAnterior`, `Vendedor`,
    `freteGratis`, `numeroAvaliacoes`, `produtoReviews`, `zProdutoLink`).
    **Achados de conversão:** preço e nota chegam em formato BR (vírgula
    decimal, ex. `"49,9"`) — criada `_num_br()` (não confundir com o `_num()` do
    Windsor, que trata `%`; aqui o problema é vírgula/ponto, formato diferente).
    `discount_pct` é RECALCULADO a partir de `novoPreco`/`precoAnterior` em vez
    de parsear o texto `"16% OFF"` — mais robusto, e evita mais uma classe de
    parsing de texto arriscado. `tipoResultado` (`"ORGANIC"` em todos os itens
    testados) virou o sinal de patrocinado, mais confiável que o best-effort
    genérico de `extrair_patrocinado()` (que segue como fallback se o campo vier
    vazio). Capturados dois campos que o `viralanalyzer` não tem —
    `venda_estimada` (de `quantidadeVendida`) e `destaque` (de `highlight`,
    ex. "MAIS VENDIDO") — aditivos, ainda sem coluna própria no XLSX/HTML.
    Testado com um recorte real de 4 itens (`AlwaysFit`/oficial, `Vhita`,
    `Quantum Nutrition`, `OCEAN DROP` — os dois últimos concorrentes fictícios
    de teste, não estão no `config.example.json` real): preço, desconto e
    match de vendedor conferidos um a um contra o esperado.
    **Ainda NÃO ativado por padrão** — falta confirmar o nome do campo de
    ENTRADA (o formulário mostra "Nome do produto", mas o JSON pode divergir);
    pedido ao usuário o print da aba "JSON" do Input antes de trocar
    `apify_actors.mercado_livre`/`apify_actors_formato.mercado_livre` de
    verdade. Ver `config.example.json` (`apify_actors_formato`) e
    `PROXIMOS-PASSOS.md` item 6.

39. **Entrada confirmada, `karamelo` ativado como padrão (2026-08-02, mesmo
    dia das entradas 37-38).** Usuário mandou o JSON real do Input do ator:
    `{"keyword": "...", "maxPages": 2, "maxPagesOfertas": 1, "promoted": true,
    "scrapeOfertas": false}`. Achado confirmando por que nunca se deve
    adivinhar nome de campo: o rótulo do formulário era "Nome do produto", mas
    a chave real é `keyword` — nenhuma relação óbvia entre os dois. Outro
    achado: o ator não tem um campo de "máximo de itens" equivalente a
    `maxItems` (do `viralanalyzer`) — pagina por NÚMERO DE PÁGINAS
    (`maxPages`/`maxPagesOfertas`), que não é derivável de `per_produto` de
    forma confiável, então ficou fora de `apify_actors_campos` e virou valor
    FIXO em `apify_actors_extra`, copiado exatamente do payload testado (não
    escolhido a dedo).
    Ativado em `config.example.json`: `apify_actors.mercado_livre` =
    `"karamelo~mercadolivre-scraper-brasil-portugues"`,
    `apify_actors_campos.mercado_livre` = `{"termo": "keyword"}`,
    `apify_actors_extra.mercado_livre` = `{"maxPages": 2, "maxPagesOfertas": 1,
    "promoted": true, "scrapeOfertas": false}`, `apify_actors_formato.mercado_livre`
    = `"karamelo"`. `viralanalyzer~mercadolivre-scraper` continua com código
    funcionando (fallback documentado em `config.example.json` e no SKILL.md).
    **Pendência registrada, não resolvida:** `promoted: true` não trouxe nenhum
    item com `tipoResultado != "ORGANIC"` no teste real — não dá pra confirmar
    se o campo de fato mistura patrocinado no resultado ou se controla outra
    coisa (ex.: priorizar loja oficial). Reavaliar se aparecer um patrocinado
    de verdade numa coleta futura, não assumir nem numa direção nem noutra.
    **Ação do usuário ainda pendente:** o `config.json` real dele (se já
    existia antes de hoje) não herda essas chaves automaticamente — precisa
    mesclar à mão a partir do `config.example.json` atualizado. Registrado em
    `PROXIMOS-PASSOS.md`.

40. **Google Ads por keyword processado, 100% real — mas com dois achados de
    qualidade de dado (2026-08-02, mesmo dia).** Usuário colou a resposta real
    da URL de keyword que eu tinha passado (42 linhas, campos: `campaign`,
    `keyword_text`, `impressions`, `clicks`, `ctr`, `cpc`,
    `search_impression_share`, `search_rank_lost_impression_share`,
    `quality_score`). Rodado `gerar_relatorio_keywords.py` **sem** `--simulado`
    contra ela + `outputs/auction-windsor.json` (real, da entrada 36) — export
    em `outputs/keywords-relatorio.json` com `"simulado": false`, primeira vez
    que a aba Keywords & Leilão tem as duas partes (keyword E leilão) reais ao
    mesmo tempo.
    **Achado 1 — bug de URL, não meu:** toda linha veio com uma chave
    `"fields=date": null` em vez de um campo `"date"` de verdade. Causa
    provável: o usuário colou o bloco `fields=date,campaign,...` inteiro como
    valor de um parâmetro `fields=` já existente na URL do painel do Windsor,
    resultando em `...&fields=fields=date,campaign,...` — o Windsor split por
    vírgula e o primeiro token ficou com o prefixo `fields=` grudado. Efeito
    prático: **não há quebra por dia nesta coleta**, é uma agregação do
    período inteiro. Não quebra o relatório atual (`agregar_keywords()` em
    `keyword_auction.py` nunca usou o campo `date`, só agrega por
    campanha+keyword), mas vai importar se algum dia for preciso comparar
    "antes x depois" por keyword (`detectar_quedas`) — nesse caso a URL
    precisa ser refeita SEM o `fields=` duplicado.
    **Achado 2 — quality_score fora da escala esperada, sinalizado ao usuário,
    NÃO corrigido.** Valores reais chegaram até **290** (ex.: "Joie" = 290,
    "Joie suplementos" = 261, "magnésio quelato" = 145) — a Quality Score
    pública do Google Ads é sempre 1-10. `get_fields` não pôde confirmar o que
    esse campo representa de verdade (a conta `google_ads` não está conectada
    nesta sessão MCP, só a `googleanalytics4` — mesma limitação de sempre).
    Duas hipóteses possíveis, nenhuma confirmada: (a) o campo do Windsor não é
    a Quality Score 1-10 e sim outra métrica com nome parecido; (b) é a QS
    correta mas nalgum agregado/multiplicador. **Não assumi nenhuma das duas
    nem apliquei fator de correção** (seria fabricar) — o valor bruto foi
    gravado como veio, e o usuário foi avisado para conferir contra o valor
    que aparece na coluna "Nível de qualidade" do Google Ads Editor/UI para
    uma dessas keywords antes de confiar no número exibido no painel.

41. **Primeira coleta REAL do Radar de Mercado Livre, na máquina do usuário
    (2026-08-02).** Como o `APIFY_TOKEN` não pode passar por chat e o host do
    Apify está bloqueado neste ambiente (confirmado com `curl` — 403 do proxy
    de política da organização, mesmo bloqueio já visto no Windsor), a
    solução foi empacotar a pasta inteira do projeto (`zip`, ~1MB, sem nenhum
    token dentro — conferido com grep antes de enviar) e mandar por
    `SendUserFile`, com passo a passo de `setx APIFY_TOKEN` e execução local.
    O usuário rodou com sucesso: `war_room.py` coletou de verdade os 3
    produtos configurados via o ator `karamelo`, achou **1 alerta ALTA real**
    (Black Skull baixou o preço de "Linha Joie Fit" de R$ 129,90 para R$ 106,72,
    -17,8%) e 5 alertas médios (concorrentes sumindo de buscas, novo desconto,
    salto de reviews). **Todas as abas de dado automatizável do painel agora
    são reais** — só falta Google Shopping (sem fonte conectada).
    **Bug cosmético achado e corrigido:** o texto do alerta de salto de
    reviews mostrava "910 para 4869.0" — `_num_br()` sempre devolve float, e o
    valor antigo (do snapshot anterior, coletado com o ator antigo) era int,
    gerando a mistura visual. Corrigido formatando a exibição como inteiro
    (`:.0f`) em `war_room.py`, tanto no texto do alerta quanto nas duas tabelas
    HTML do Radar — sem alterar o dado armazenado.
    **Nota de segurança à parte:** o usuário colou um print com o token da
    conta Apify em texto claro durante esta sessão, oferecendo "apagar o print
    depois". Respondido que não existe capacidade de apagar mensagem já
    enviada em uma conversa — o token já estava exposto no histórico
    independente do que acontecesse depois. Orientado a regenerar o token
    (botão 🔄 na tela de Settings → API & Integrations do Apify) antes de usar
    de verdade. Mesmo com autorização explícita do usuário para usar o token
    exposto, a chamada foi tecnicamente impossível (host bloqueado), então a
    questão de "usar ou não" nem chegou a se colocar de fato.

42. **Bug de import quebrado corrigido + primeiro "agente" de descoberta de
    produtos, provado contra dado real (2026-08-02, mesmo dia).** Ao revisar o
    pedido do usuário sobre trazer o título do produto concorrente na aba
    Descoberta, achado que `descoberta_concorrentes.py` estava com **import
    quebrado** (`from war_room import ML_ACTOR` — eu tinha renomeado a
    constante para `ML_ACTOR_PADRAO` na entrada 39 e não atualizei quem
    importava). Corrigido, e aproveitado pra unificar: `buscar_raw()`/
    `descobrir_por_produto()` agora usam o mesmo ator/payload/formato
    configurado (via `montar_payload_ml`/`_campos_listagem`, reaproveitados de
    `war_room.py`) em vez de ficarem presos no `viralanalyzer` com nomes de
    campo fixos — sem isso a coluna "titulo/variante" ficaria vazia contra
    qualquer ator diferente do original (bug que só apareceria na próxima vez
    que alguém rodasse `descoberta_concorrentes.py` de verdade, sem eu ter
    percebido no calor da troca de ator).
    Usuário pediu, na sequência: um "agente" que determina quais produtos
    monitorar no Google Shopping, com base nos anúncios do site e nos
    anúncios nos marketplaces. Criado `descoberta_produtos_shopping.py`:
    detecta campanhas Google Ads reais com o padrão `"Shopping - X"` (achado
    real e imediato: a campanha `"Shopping - Colageno"`, R$ 422,78 de gasto,
    1.230 cliques, já rodava sem "Colágeno" estar cadastrado como produto em
    lugar nenhum do config), cruza com `produtos_monitorados`/
    `produtos_candidatos_manual` e (opcionalmente) com o `snapshot_proprio` do
    Radar de ML, e classifica cada produto: já monitorado no Shopping /
    candidato (vende no ML, sem Shopping) / achado fora do config / sem
    evidência. Testado de ponta a ponta contra `outputs/own-performance-por-
    produto.json` (real) — achou exatamente o caso do Colágeno na primeira
    rodada. Adicionado "Colágeno" a `produtos_candidatos_manual` em
    `config.example.json` (sem `preco_proprio`/`ticket_medio`, que não tenho —
    fica para o usuário revisar antes de promover).
    **Escopo deliberadamente limitado:** este agente só determina QUAIS
    produtos vigiar — não coleta concorrentes no Google Shopping (precisa de
    um ator do Apify pra isso, nenhum testado ao vivo ainda, mesmo status
    BETA de `meta_ads.py`/`google_ads_transparency.py`). Decisão registrada:
    construir agentes um de cada vez, cada um provado contra dado real antes
    do próximo, e só desenhar a aba de orquestração (perguntada pelo usuário)
    depois de ter mais de um agente rodando de verdade.

43. **Coletor de concorrentes no Google Shopping (`google_shopping.py`), BETA
    SEM ATOR ESCOLHIDO — decisão deliberada (2026-08-02, mesmo dia).** Usuário
    pediu explicitamente ("sim") pra eu procurar e montar o coletor de
    concorrentes no Google Shopping, completando a metade que
    `descoberta_produtos_shopping.py` (entrada 42) deixou em aberto. Construído
    seguindo o MESMO padrão de `collect_snapshot()` em `war_room.py` (preço,
    posição, reviews, rating, por concorrente + o próprio), com extração de
    campo multi-candidato (`CAMPOS_ESPERADOS`, várias chaves plausíveis por
    campo lógico) no mesmo estilo de `meta_ads.py`.
    **Decisão que diferencia este de `meta_ads.py`/`google_ads_transparency.py`:**
    aqueles dois chutaram um ator específico (de descrição pública no Apify
    Store) mesmo sem testar ao vivo, porque havia alguma informação concreta
    sobre a existência deles. Para Google Shopping, não havia essa mesma
    confiança — inventar um nome de ator que talvez nem exista seria pior que
    não ter coletor nenhum (rodaria, pareceria funcionar, e devolveria erro ou
    vazio sem dizer o motivo real). Por isso `config["apify_actors"]["google_shopping"]`
    ficou **vazio de propósito** em `config.example.json`, e o script recusa
    rodar sem `--actor`/config preenchido, com mensagem de erro explicando por
    quê — em vez de seguir o precedente de "sempre chutar um default".
    Criado também `match_competitor_shopping()` — diferente do `match_competitor()`
    do Radar de ML (que só olha `sellers_ml`, nicknames de Mercado Livre), este
    olha `nome`/`google_advertiser`/`sellers_ml` do concorrente, porque o nome
    da loja que aparece no Google Shopping tende a se parecer mais com a marca
    do que com um nickname específico de ML.
    Testado com item sintético (claramente rotulado como teste, não dado real)
    — parsing multi-candidato e casamento de loja confirmados funcionando.
    **Pendência do usuário:** achar um ator real de Google Shopping na Apify
    Store (mesmo caminho que funcionou para o `karamelo` — testar e colar o
    resultado real aqui antes de confiar). **Ainda não ligado a `war_room.py`:**
    os flags `--simulate-google-shopping*` existentes são de teste/demo, sem
    selo de "real" na aba Marketplaces — quando o coletor for confirmado,
    criar flags dedicados (`--google-shopping-json`/`--google-shopping-proprio-json`)
    em vez de reaproveitar os de simulação, mesmo cuidado já tomado com o
    Windsor.

44. **Ator de Google Shopping testado e confirmado — saída sim, entrada ainda
    não (2026-08-02, mesmo dia da entrada 43).** Usuário achou e testou
    `damilo~google-shopping-apify` na Apify Store, colou uma busca real
    ("magnesio quelato", ~44 itens) junto com prints do Input (aba "Form") e
    de outro ator alternativo de Google Ads Transparency
    (`solidcode/ads-transparency-scraper`, só explorado, sem resultado real
    colado ainda — não trocado no config). Corrigido `google_shopping.py`
    contra o dado real: `source` (vendedor) e `link` (URL) são os campos REAIS
    — nenhum dos dois estava nos meus palpites originais (eu tinha
    `seller`/`merchant`/`store`/`storeName`/`sellerName` e
    `url`/`productUrl`/`offerUrl`, nenhum bateria sem esse teste). Preço vem
    como texto e às vezes com sufixo `"agora"` colado (`"R$ 99,40 agora"`) —
    a limpeza ingênua anterior (`.replace("R$", "")`) deixaria essa palavra
    grudada e o `float()` falharia silenciosamente, tratando um preço real
    como "não medido". Substituído por regex (`_PRECO_RE`) que extrai só o
    padrão numérico, testado contra as 4 variações reais vistas (com/sem
    "agora", com/sem milhar). Confirmado também que este ator **não tem** um
    campo de preço original/desconto — `discount_pct` fica `None` sempre para
    esta fonte, e isso é o correto, não uma falha de mapeamento.
    Ativado `config["apify_actors"]["google_shopping"] = "damilo~google-shopping-apify"`
    em `config.example.json`.
    **Ainda em aberto:** o campo de ENTRADA (nome da busca) nunca foi
    confirmado pela aba "JSON" do Input — só a "Form", com "Search query"
    (singular) e "Search queries" (plural, com "+ Add", sugerindo que o ator
    aceita várias buscas por chamada). `montar_input()` usa `"query"` porque a
    SAÍDA ecoa esse nome de campo — indício forte, não confirmação. Antes de
    confiar na coleta de produção, rodar com `--debug-raw` numa busca real e
    conferir se o resultado bate com o termo pedido.

## Princípios que NUNCA devem ser quebrados

- **Nunca fabricar dado.** Se uma fonte não existe ou não responde, dizer
  explicitamente "não disponível" / "não medido" — nunca inventar um número
  plausível. Isso já rendeu documentação extensa em
  `references/fontes-e-limitacoes.md` (ex.: investimento em ads de concorrente
  NÃO é público em nenhuma plataforma; KPIs de redes sociais não têm fonte real
  hoje; `first_page_cpc`/`top_of_page_cpc` do Google Ads às vezes vêm `null` de
  verdade).
- **Diagnóstico antes de ação.** Queda de KPI aciona investigação, não reação
  automática.
- **Nunca executar ação de escrita (execute_action, mudança de lance, campanha,
  etc.) sem autorização explícita e específica do usuário para aquela ação.**
  Quando perguntado quais ações de combate podiam ser executadas de verdade, a
  resposta registrada foi "Nenhuma ainda" — isso vale até o usuário autorizar
  algo pontualmente.
- **Verificar ao vivo antes de declarar algo conectado/funcionando.** Rodar
  `get_connectors`/testes reais em vez de assumir que uma conexão relatada pelo
  usuário está de fato ativa do lado que o sistema usa.

## Arquitetura (visão rápida)

```
war-room-concorrencia/
├── SKILL.md                     # manual operacional completo (11 fluxos + 1b + 7b + 12)
├── contexto-e-apoio/
│   ├── MEMORIA-DO-PROJETO.md    # ESTE arquivo — memória/histórico do projeto
│   └── arquivos-finais/         # cópias VERSIONADAS (não gitignored) dos entregáveis
│       ├── war-room.html            # dashboard CONSOLIDADO por abas (visual fintech)
│       ├── war-room.xlsx            # mesmo conteúdo em planilha (mais abas)
│       ├── war-room-live-demo.html  # demo de replay fixo (visual cockpit, não redesenhado)
│       ├── war-room-simulador.html  # simulador interativo (visual cockpit, não redesenhado)
│       ├── painel-produtos.html     # painel avulso de seleção de produtos (só produtos)
│       ├── descoberta.xlsx          # relatório avulso de descoberta (dado igual à aba Concorrentes)
│       └── relatorio-keywords.xlsx  # SIMULADO — relatório avulso (dado igual à aba Keywords & Leilão)
├── references/
│   ├── fontes-e-limitacoes.md   # honestidade por fonte de dado
│   ├── protocolo-diagnostico.md # protocolo de 8 passos p/ queda de KPI
│   └── playbook-resposta.md     # playbook legível por humano
├── scripts/
│   ├── war_room.py              # motor central — agora com tabs (Marketplaces, Concorrentes,
│   │                             # Keywords & Leilão, Histórico Preço×Ads, Seleção Manual)
│   ├── _effects.py              # efeitos visuais do tema cockpit (usado só por demo/simulador agora)
│   ├── _fonts.py                # fontes base64: Orbitron/Share Tech Mono (cockpit) + Sora (fintech)
│   ├── apify_common.py          # helpers compartilhados de scraping
│   ├── own_performance.py       # Google Ads + GA4 via Windsor.ai (dado real)
│   ├── meta_ads.py              # BETA — Meta Ad Library (Apify, nunca testado ao vivo)
│   ├── google_ads_transparency.py # BETA — idem, Google Ads Transparency Center
│   ├── google_trends.py         # BETA — idem, Google Trends
│   ├── keyword_auction.py       # VERIFICADO — leilão de keyword via Windsor.ai (só quedas)
│   ├── gerar_relatorio_keywords.py # TODAS as keywords + leilão; --export-json alimenta a aba
│   ├── descoberta_concorrentes.py # motor de descoberta/composição + score; --export-json alimenta a aba
│   ├── gerar_painel_produtos.py  # painel AVULSO de seleção de produtos (a aba embutida cobre + concorrentes)
│   ├── agentes.json             # taxonomia de agentes de combate
│   ├── playbook.json            # definição de todos os tipos de alerta
│   ├── config.example.json      # config de exemplo (produtos, concorrentes, pesos etc.)
│   ├── gerar_demo_live.py        # demo de replay fixo (10 eventos) — visual cockpit original
│   ├── gerar_simulador.py        # simulador interativo — visual cockpit original
│   └── examples/                 # fixtures para rodar tudo em modo --simulate-*/--simulado
└── outputs/                      # gerado localmente (gitignored) — a cada rodada nova;
                                   # a versão de referência fica em contexto-e-apoio/arquivos-finais/
```

Os 4 artifacts publicados (URLs — republicar com o mesmo `file_path`/`url` para
atualizar, nunca criar um novo):

- **War Room — Joie** (dashboard consolidado por abas, visual fintech,
  `outputs/war-room.html`): `https://claude.ai/code/artifact/ef0d6339-6093-4a74-9e32-0b65f5357a69`
- **War Room — Joie · DEMO AO VIVO** (`outputs/war-room-live-demo.html`,
  visual cockpit original): `https://claude.ai/code/artifact/b45e96ac-b503-4463-a390-aa1e8a8eb778`
- **War Room — Joie · SIMULADOR** (`outputs/war-room-simulador.html`,
  visual cockpit original): `https://claude.ai/code/artifact/ce0e31b4-0f11-4bb8-9f79-59c5a71074e2`
- **War Room — Joie · Painel de Produtos** (avulso, só produtos,
  `outputs/painel-produtos.html`): `https://claude.ai/code/artifact/cbab392a-cf2e-42bf-8f2f-bef7bcdeb495`

Kit de publicação em VPS: `deploy/` (instalar.sh + war-room.service + Caddyfile +
atualizar.sh + README). Hospedagem compartilhada de cPanel NÃO serve — precisa
root/SSH. GitHub Actions foi comparado e descartado para este uso: sem processo
vivo o botão de rodar na hora perde a graça, o `history/` precisaria ser
commitado a cada rodada, e Pages em repo privado publica o painel aberto.

Branch de trabalho: `claude/competitor-monitoring-war-room-pkhhlo`.

Importante: `contexto-e-apoio/arquivos-finais/` é uma **fotografia versionada**
(commitada no git) do último estado gerado — útil pra consulta/download sem
precisar rodar nada. Não é regenerada automaticamente; ao fechar uma rodada de
mudanças relevante, regere os 5 arquivos (comandos na seção "Fluxo de trabalho"
do `SKILL.md`) e copie por cima deste diretório antes de commitar.

## Descobertas técnicas importantes (não repetir o mesmo teste sem necessidade)

- **Rede bloqueada neste ambiente** para `api.apify.com`, `facebook.com`,
  `adstransparency.google.com`, `trends.google.com` (403 da política do proxy).
  Por isso `meta_ads.py`, `google_ads_transparency.py` e `google_trends.py`
  nunca foram testados ao vivo — são BETA com modo `--debug-raw` para calibrar
  quando rodarem num ambiente com rede liberada.
- **GA4 ≠ Ads.** GA4 dá `sessions`/`engaged_sessions`/`conversions`/
  `transactions`, nunca `impressions`/`clicks`/`spend`. `own_performance.py`
  trata isso como componente separado (`ga4_*`), nunca mistura com CTR/CPA/ROAS.
- **Auction Insight não combina com métricas de performance** na mesma consulta
  Windsor.ai/Google Ads (`auction_insight_domain` é uma leitura à parte).
- **Looker Studio não tem API de leitura.** A API dele só gerencia permissões de
  asset — não lista as fontes de dados de um relatório nem devolve os dados dos
  gráficos. A URL de relatório privado responde **403** sem sessão Google
  (testado com WebFetch). "Extrair as conexões do Looker" é impossível mesmo com
  credencial; e é desnecessário, porque o Looker é só camada de visualização —
  as conexões dele apontam para as MESMAS fontes (GA4, Google Ads, Sheets) que o
  war room já alcança. O caminho que funciona: materializar em planilha (o Looker
  agenda entrega para Sheets) e importar com `sheets_import.py`.
- **Para ler valores de planilha com precisão, baixe .xlsx, não markdown.**
  `read_file_content` do MCP do Drive devolve markdown já formatado, onde um
  inteiro `1408` e um decimal `1,408` podem aparecer iguais. `download_file_content`
  com `exportMimeType` de xlsx + openpyxl mostra o tipo, o valor e o
  `number_format` de cada célula — foi assim que a corrupção de locale da
  planilha de Auction Insights foi diagnosticada em vez de virar pergunta.
- **`keyword_auction.py` é o único dos "beta" que foi VERIFICADO com dado real**
  (rodou de fato contra a conta Google Ads da Joie via Windsor.ai).
- **Windsor.ai plano Free — limitação de conector único, achado 2x:**
  1. Primeira vez: ao autorizar GA4, o Google Ads (que estava funcionando)
     caiu.
  2. Segunda vez (2026-08-01): usuário relatou ter conectado Facebook e Google
     Ads; `get_connectors`/`get_fields` mostraram que **nada mudou** — só GA4
     segue com conta associada, e `get_fields` para `google_ads`/`facebook`
     retorna erro "No account... was found" para o usuário
     `mktjoiesuplementos@gmail.com`.
- **Causa raiz identificada nesta mesma sessão: são DUAS contas Windsor.ai
  diferentes.** O usuário estava logado no navegador como
  `jrsanches1975@gmail.com` (onde Google Ads e GA4 aparecem com dado real,
  inclusive tráfego do Facebook via UTM dentro do GA4). Mas a integração MCP
  que este Claude usa está autenticada como `mktjoiesuplementos@gmail.com`
  (confirmado por `get_current_user`), que só tem a GA4 conectada e está no
  plano `FREE`.

## PENDÊNCIA ATIVA — não está resolvida

Passos já tentados nesta sessão para resolver o descompasso de contas:

1. Gerado `get_connector_connect_info` para `google_ads` e `facebook` (links
   de autorização OAuth com auto-login na conta `mktjoiesuplementos@gmail.com`)
   e entregues ao usuário duas vezes (tokens são de uso único, então cada
   tentativa exige gerar links novos).
2. Usuário confirmou ter clicado e autorizado nos dois links da segunda
   rodada — mas `get_connectors`/`get_current_user` continuaram mostrando só
   GA4 depois disso.
3. Hipótese em aberto: o plano Free pode estar **rejeitando silenciosamente**
   a nova conexão porque a GA4 já ocupa a única vaga de conector permitida
   (diferente do primeiro achado, em que a nova conexão derrubava a antiga —
   desta vez parece que nem chegou a substituir).
4. Usuário pediu para eu olhar "a janela do navegador" — **não tenho essa
   capacidade** (sem acesso a screenshot/tela do usuário nesta sessão); pedi
   para ele mandar print, ainda sem resposta quando este documento foi escrito.

**Verificado de novo em 2026-08-02** (não repetir): `get_current_user` →
`mktjoiesuplementos@gmail.com`, plano `FREE`; `get_connectors` → só
`googleanalytics4` (conta `304174518` "GA4 - Joie Suplementos"). Nada mudou.

**Também verificado em 2026-08-02: não existe alternativa de MCP.** `ListConnectors`
e `SearchMcpRegistry` (chaves "Meta Ads", "Facebook Ads", "Google Ads",
"advertising campaigns", "marketing analytics") devolvem o **Windsor.ai como único**
conector de mídia paga. Não há "MCP da Meta" para instalar no lugar. Logo, a
solução é dentro do Windsor ou direto na API da fonte. Registrado porque o usuário
perguntou se não daria para "conectar via MCP" — a resposta é que o Windsor **já é**
o MCP; o gargalo é a conta e o plano, não o protocolo.

**Nota lateral:** `Semrush` aparece na lista de conectores da org com
`installState: unknown` (não autenticado). Não substitui o dado próprio de mídia
(não traz nosso gasto nem nosso CTR), mas traria keyword paga e tráfego **dos
concorrentes** — hoje simulados nas abas de Keywords e Descoberta. Oportunidade
paralela, não caminho crítico.

**EM ANDAMENTO (2026-08-02):** o usuário escolheu testar a opção de **repontar o
conector Windsor do claude.ai para a outra conta** (`jrsanches1975@gmail.com`),
que é grátis. **A armadilha que derrubou as duas tentativas anteriores:** é preciso
**fazer logout do windsor.ai no navegador antes** de reconectar — senão o OAuth
reaproveita a sessão existente e reconecta a MESMA conta, parecendo que não
funcionou. Ao retomar: rodar `get_current_user` + `get_connectors` e comparar com
os valores verificados acima. Se ainda vier o e-mail antigo, o conector deste chat
está com a sessão velha (desligar/religar o Windsor.ai nas configurações do chat,
ou abrir conversa nova).

**Ressalva a dizer ao usuário se a opção der certo pela metade:** se a outra conta
também for Free, o limite de 1 conector continua valendo — ele troca GA4 por Google
Ads em vez de ter os dois. Ter GA4 + Google Ads + Meta ao mesmo tempo exige plano
pago do Windsor **ou** coletores próprios contra a Marketing API da Meta e a API do
Google Ads (sem mensalidade, ~2 dias de trabalho, e o dado vem mais completo).

## Onde estão os detalhes completos

Se precisar de mais profundidade sobre qualquer ponto acima (trechos de
código exatos, mensagens de erro completas, decisões de design pixel a
pixel), o histórico integral da conversa está no transcript da sessão — mas
este arquivo deve ser suficiente para retomar o trabalho sem precisar
reler tudo.
