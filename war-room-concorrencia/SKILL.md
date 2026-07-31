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

### 5. Enriquecer com desempenho próprio real (Google Ads / Meta Ads, via Windsor.ai)

Isto é o que transforma o "impacto estimado no volume" de um chute em algo calibrado
com dado de verdade. O script não coleta Google Ads/Meta sozinho — quem faz isso é você
(o agente), usando o MCP do **Windsor.ai** (já traz Google Ads/Meta/GA4/300+ conectores):

1. Confirme quais contas estão conectadas: `mcp__Windsor_ai__get_connectors`. Se faltar
   Meta ou GA4, gere o link de autorização com
   `mcp__Windsor_ai__get_connector_connect_info` (connector `facebook` / `googleanalytics4`)
   e peça para o usuário clicar — é OAuth, não dá para autorizar por ele.
2. Descubra os campos certos com `get_fields` (não adivinhe IDs) e puxe os dados com
   `get_data` — ex.: `fields: ["date","campaign","impressions","clicks","spend",
   "conversions","conversions_value","roas","cpa"]`, `date_preset: "last_30d"`. Se o
   retorno estourar o limite de tokens, agregue com jq/python no arquivo salvo em vez de
   pedir tudo de novo.
3. Grave o retorno bruto num JSON `{"connector": "google_ads", "registros": [...]}` (um
   arquivo por conector: `google_ads`, `facebook`) e rode:
   ```bash
   python own_performance.py --input google-ads-30d.json --input meta-30d.json \
     --config config.json --out ../outputs/own-performance-por-produto.json
   ```
   Isso agrega por campanha e casa com `produtos_monitorados[].campanhas_google_ads` /
   `campanhas_meta_ads` do config (o script avisa quais campanhas não casaram, para
   você ajustar o config).
4. Rode o `war_room.py` passando `--own-performance ../outputs/own-performance-por-produto.json`
   junto dos outros argumentos. Isso faz três coisas: (a) enriquece o texto de impacto
   estimado nos alertas de preço com o CPA/ROAS/CTR reais do produto; (b) adiciona a aba
   **Desempenho Próprio** no xlsx; (c) adiciona uma faixa de KPIs reais no topo do
   dashboard HTML.

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

## O playbook de resposta (o que muda por tipo de mudança)

O mapeamento completo tipo-de-mudança → impacto na concorrência → impacto estimado no
volume → estratégia imediata → KPIs impactados está em
`references/playbook-resposta.md` (versão legível) e `scripts/playbook.json` (versão
que o script usa). **Leia o playbook antes de comentar qualquer alerta** — a resposta
certa muda bastante entre "concorrente baixou preço 3%" e "concorrente lançou cupom
agressivo de 25%".

Resumo dos tipos cobertos: queda de preço (leve/moderada/agressiva), novo desconto/cupom,
aumento de preço do concorrente (oportunidade), salto de posição/visibilidade no Mercado
Livre, aumento de anúncios ativos (Meta/Google/ML Ads — via captura manual), concorrente
saiu da busca (possível ruptura de estoque) e novo entrante (concorrente novo pescando o
mesmo termo).

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
