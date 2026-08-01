# Memória do Projeto — War Room de Concorrência (Joie Suplementos)

> Este documento existe para dar contexto completo a qualquer pessoa (ou sessão de
> IA) que continue este projeto sem ter acompanhado as conversas originais. Ele
> registra o que foi pedido, o que foi construído, as decisões tomadas, as
> descobertas técnicas e o que ainda está pendente. Para o "manual de uso" do
> sistema (como rodar cada script, o passo a passo dos 11 fluxos), ver
> `../SKILL.md`. Para as limitações e fontes de dado, ver
> `../references/fontes-e-limitacoes.md`. Este arquivo aqui é a **memória**, não
> o manual.

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

**Próximo passo ao retomar:** pedir o print do resultado da autorização (ou
rodar `get_connectors`/`get_fields` de novo ao vivo), e se o padrão de "só 1
conector no Free" se confirmar, apresentar ao usuário as opções reais: (a)
upgrade de plano (link de `get_subscription_url` já disponível), (b) manter
só GA4 real e não fabricar dado de Ads enquanto isso, ou (c) reconfigurar qual
conta Windsor esta integração usa (fora do escopo de ferramentas deste chat —
é ajuste de conector no Claude/Cowork).

## Onde estão os detalhes completos

Se precisar de mais profundidade sobre qualquer ponto acima (trechos de
código exatos, mensagens de erro completas, decisões de design pixel a
pixel), o histórico integral da conversa está no transcript da sessão — mas
este arquivo deve ser suficiente para retomar o trabalho sem precisar
reler tudo.
