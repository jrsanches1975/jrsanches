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
├── SKILL.md                     # manual operacional completo (11 fluxos + 1b + 7b)
├── contexto-e-apoio/
│   ├── MEMORIA-DO-PROJETO.md    # ESTE arquivo — memória/histórico do projeto
│   └── arquivos-finais/         # cópias VERSIONADAS (não gitignored) dos entregáveis
│       ├── war-room.html            # dashboard de produção
│       ├── war-room.xlsx            # mesmo conteúdo em planilha
│       ├── war-room-live-demo.html  # demo de replay fixo
│       ├── war-room-simulador.html  # simulador interativo
│       ├── painel-produtos.html     # painel de seleção de produtos
│       ├── descoberta.xlsx          # relatório de descoberta/composição de concorrentes
│       └── relatorio-keywords.xlsx  # SIMULADO — relação completa de keywords + leilão
├── references/
│   ├── fontes-e-limitacoes.md   # honestidade por fonte de dado
│   ├── protocolo-diagnostico.md # protocolo de 8 passos p/ queda de KPI
│   └── playbook-resposta.md     # playbook legível por humano
├── scripts/
│   ├── war_room.py              # motor central (diff, alertas, xlsx, html)
│   ├── _effects.py              # efeitos visuais compartilhados (starfield, boot, glitch)
│   ├── _fonts.py                # fontes embutidas em base64 (Orbitron, Share Tech Mono)
│   ├── apify_common.py          # helpers compartilhados de scraping
│   ├── own_performance.py       # Google Ads + GA4 via Windsor.ai (dado real)
│   ├── meta_ads.py              # BETA — Meta Ad Library (Apify, nunca testado ao vivo)
│   ├── google_ads_transparency.py # BETA — idem, Google Ads Transparency Center
│   ├── google_trends.py         # BETA — idem, Google Trends
│   ├── keyword_auction.py       # VERIFICADO — leilão de keyword via Windsor.ai
│   ├── descoberta_concorrentes.py # motor de descoberta/composição + score de relevância
│   ├── gerar_painel_produtos.py  # painel de seleção de produtos monitorados
│   ├── agentes.json             # taxonomia de agentes de combate
│   ├── playbook.json            # definição de todos os tipos de alerta
│   ├── config.example.json      # config de exemplo (produtos, concorrentes, pesos etc.)
│   ├── gerar_demo_live.py        # demo de replay fixo (10 eventos)
│   ├── gerar_simulador.py        # simulador interativo (dispara evento a evento)
│   └── examples/                 # fixtures para rodar tudo em modo --simulate-*
└── outputs/                      # gerado localmente (gitignored) — a cada rodada nova;
                                   # a versão de referência fica em contexto-e-apoio/arquivos-finais/
```

Os 4 artifacts publicados (URLs — republicar com o mesmo `file_path`/`url` para
atualizar, nunca criar um novo):

- **War Room — Joie** (dashboard "de produção", `outputs/war-room.html`):
  `https://claude.ai/code/artifact/ef0d6339-6093-4a74-9e32-0b65f5357a69`
- **War Room — Joie · DEMO AO VIVO** (`outputs/war-room-live-demo.html`):
  `https://claude.ai/code/artifact/b45e96ac-b503-4463-a390-aa1e8a8eb778`
- **War Room — Joie · SIMULADOR** (`outputs/war-room-simulador.html`):
  `https://claude.ai/code/artifact/ce0e31b4-0f11-4bb8-9f79-59c5a71074e2`
- **War Room — Joie · Painel de Produtos** (`outputs/painel-produtos.html`):
  `https://claude.ai/code/artifact/cbab392a-cf2e-42bf-8f2f-bef7bcdeb495`

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
