# O que falta fazer — checklist do usuário

Atualizado em 2026-08-02, depois da decisão de seguir **só pelo Windsor multi-conta**.

Tudo aqui depende de acesso a contas que só você tem. Nada disso pode ser feito de
dentro de uma sessão do Claude: os hosts do Windsor, do Meta Business e do Google
Ads estão bloqueados na rede do ambiente (verificado), e token não deve trafegar por
chat.

---

## Decisão que encurtou a lista

Você criou duas contas Windsor a mais, uma por ferramenta, e escolheu seguir por
elas. Isso **cancelou** três itens que estavam pendentes:

- ~~Token de usuário de sistema da Meta~~
- ~~Developer token do Google Ads + credencial OAuth + refresh token~~
- ~~Reexportar a planilha de Auction Insights à mão~~

O último é o ganho mais interessante: o Windsor entrega `auction_insight_domain`
(a tabela de leilão por domínio concorrente), e a **API oficial do Google não
entrega** — lá é restrita a contas em allowlist. Sua escolha preservou uma
capacidade que o caminho dos coletores nativos perderia.

Os coletores nativos (`meta_ads_api.py`, `google_ads_api.py`) ficam no repositório,
testados na camada de conversão, caso você queira retomar depois. Não são
necessários agora.

---

## 1. Conectar uma fonte em cada conta Windsor

- [ ] Conta A → **GA4** (esta já está feita: é a que a integração do Claude usa)
- [ ] Conta B → **Google Ads**
- [ ] Conta C → **Meta Ads** (`facebook`)

Confirme em cada conta que o conector aparece **com a conta de anúncio associada**,
não só autorizado. Foi exatamente aí que as tentativas anteriores falharam: a
autorização parecia ter dado certo e o conector continuava sem conta.

---

## 2. Pegar a chave de API de cada conta

Cada conta Windsor tem a **sua própria** chave — é isso que faz o esquema
multi-conta funcionar. No painel do Windsor de cada conta, procure em
*Settings / API*.

- [ ] Chave da conta do Google Ads
- [ ] Chave da conta do Meta

Guarde como variável de ambiente, **nunca** em arquivo do repositório:

```powershell
# Windows (PowerShell) — vale nesta janela
$env:WINDSOR_KEY_GADS = "..."
$env:WINDSOR_KEY_META = "..."
```

```bash
# macOS / Linux
export WINDSOR_KEY_GADS='...'
export WINDSOR_KEY_META='...'
```

---

## 3. Descobrir os nomes de campo — antes de coletar

Os nomes de campo do **Google Ads** são confiáveis (vêm do `keyword_auction.py`,
que já rodou contra sua conta real). Os do **Meta** são um palpite informado meu e
**precisam ser confirmados**:

```bash
cd scripts
python windsor_api.py --listar-campos facebook --chave-env WINDSOR_KEY_META
```

- [ ] Rodar e me mandar a lista de campos que aparecer

Com ela eu ajusto o script para os nomes reais da sua conta. Se eu adivinhar
errado, a coleta traz colunas vazias — e coluna vazia num painel é pior que campo
ausente declarado.

---

## 4. Primeira coleta

```bash
cd scripts

python windsor_api.py --dias 30 --debug-raw \
    --fonte google_ads:WINDSOR_KEY_GADS:../outputs/gads-keywords.json \
    --leilao-out ../outputs/auction-windsor.json

python windsor_api.py --dias 30 --debug-raw \
    --fonte facebook:WINDSOR_KEY_META:../outputs/meta-insights.json
```

- [ ] Rodar as duas
- [ ] Conferir os totais contra os painéis do Google Ads e do Gerenciador da Meta
- [ ] Me mandar **o resumo que os scripts imprimem** (não as chaves)

O `--debug-raw` mostra o primeiro registro bruto de cada fonte. É nele que se
descobre divergência de nome de campo antes de o dado errado entrar no painel.

---

## 5. Rodar o war room na sua máquina

Se ainda não fez o primeiro uso local:

```powershell
py -m pip install openpyxl
cd scripts
copy config.example.json config.json
py servidor.py --config config.json
```

- [ ] Abrir `http://127.0.0.1:8787`
- [ ] Confirmar que a aba Seleção Manual mostra "backend conectado" (barra verde)

---

## O que saber sobre a escolha do Windsor

Não são defeitos do script — são consequências do caminho, e é melhor você saber
antes de apresentar o painel a alguém:

- **Teto do plano Free:** limite de volume e de janela de dados. Se a coleta vier
  cortada, o script avisa em vez de gravar zeros.
- **Imagem do criativo provavelmente não vem.** Os cards da aba Meta Ads ficariam
  com texto e métricas, sem arte. Se isso importar, o único caminho é a API nativa
  da Meta (`meta_ads_api.py`, já pronto no repositório).
- **Várias contas gratuitas para contornar o limite de um plano normalmente
  contraria os termos do Windsor.** Se as contas forem fechadas, a coleta para sem
  aviso. É risco seu a assumir, mas registrado aqui para não ser surpresa.

---

## O que NÃO fazer

- **Não repointe o conector Windsor do Claude.** A conta
  `mktjoiesuplementos@gmail.com` tem a GA4, que é o que a integração MCP precisa.
  Trocar faria perder a GA4.
- **Não mande chaves nem tokens pelo chat.** Elas vivem em variável de ambiente na
  sua máquina.
- **Não coloque chave no `config.json`.**

---

## Pendência de segurança

- [ ] **Redefinir o token de desenvolvedor do Google Ads** — ele apareceu num print
      compartilhado em conversa em 2026-08-02. Com o caminho Windsor você não vai
      usá-lo, mas ele continua válido na sua conta: `ads.google.com` (MCC
      595-971-6066) → Ferramentas → Configuração → Central de API → **Redefinir
      token**.

---

## Oportunidade paralela (opcional)

O conector **Semrush** está disponível na sua organização, ainda não autenticado.
Traria palavra-chave paga e tráfego **dos concorrentes**, hoje simulados nas abas
de Keywords e Descoberta. Autentique e me avise que eu integro.

---

## Estado atual do dado no painel

| Aba | Fonte |
|---|---|
| GA4 · Jornada | **real medido** (GA4 via Windsor MCP) |
| Metas & Evolução | **real** (cruza GA4 com as metas do config) |
| Mercado Livre / Radar | **real** (Apify, precisa do `APIFY_TOKEN`) |
| Keywords & Leilão | simulado — destrava com os itens 1 a 4 |
| Meta Ads (lado plataforma) | simulado — destrava com os itens 1 a 4 |
| Marketplaces (Google Shopping) | simulado |
