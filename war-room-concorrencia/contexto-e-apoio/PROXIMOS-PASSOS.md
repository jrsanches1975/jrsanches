# O que falta fazer — checklist do usuário

Atualizado em 2026-08-02. Tudo aqui depende de acesso a contas que só você tem;
nada disso pode ser feito de dentro de uma sessão do Claude (as telas de criar
credencial estão bloqueadas na rede do ambiente, e token não deve trafegar por
chat).

Ordem pensada para o item de espera externa sair da frente primeiro.

---

## 1. Developer token do Google Ads — COMECE POR AQUI

**Por que primeiro:** é o único item com prazo que não depende de você. A análise
do Google leva de dias a semanas. Todo o resto é questão de minutos.

- [ ] Confirmar que você tem uma **conta gerenciadora (MCC)**. O Centro de API
      **só aparece em MCC**. Se não tiver, crie em
      `ads.google.com/home/tools/manager-accounts` e vincule a conta da Joie.
- [ ] `ads.google.com` (logado na MCC) → Ferramentas e Configurações →
      Configuração → **Centro de API**
- [ ] Preencher o formulário e **solicitar Acesso Básico**
      (o Acesso de Teste que vem na hora **não** lê a conta real)
- [ ] Guardar o token quando aprovar

No formulário, descreva o uso com honestidade: relatório interno de desempenho das
próprias campanhas, sem revenda de dados. Pedido vago é o que mais leva a
indeferimento.

**Tempo seu:** ~15 min. **Espera:** dias a semanas.

---

## 2. Token da Meta

Não tem espera de aprovação — ler a própria conta não exige Revisão de App.

- [ ] `developers.facebook.com/apps` → criar app tipo **Empresa**, vinculado ao
      mesmo Gerenciador de Negócios que é dono da conta de anúncio
- [ ] No app: Adicionar produto → **Marketing API**
- [ ] `business.facebook.com/settings` → Usuários do sistema → **Adicionar**
      (nome: `war-room-coletor`, função Funcionário)
- [ ] Adicionar ativos → Contas de anúncios → a conta da Joie → permissão
      **Ver desempenho** (só leitura, de propósito: se o token vazar, ninguém
      altera campanha nem orçamento)
- [ ] **Gerar novo token** → escolher o app → escopos `ads_read` e
      `read_insights` → validade **Nunca expira** → **copiar na hora**
      (a Meta não mostra de novo)
- [ ] Pegar o id da conta no Gerenciador de Anúncios, no formato `act_1234567890`

Passo a passo detalhado: `references/meta-api-setup.md`

**Tempo:** ~15 min.

---

## 3. Credencial OAuth do Google Cloud

Precisa disso para o coletor do Google Ads, independente do item 1.

- [ ] `console.cloud.google.com` → criar projeto
- [ ] APIs e Serviços → ativar a **Google Ads API**
- [ ] Tela de permissão OAuth → tipo Externo → preencher →
      **PUBLICAR O APP**
      ⚠ Se ficar em modo "Teste", o refresh token **expira em 7 dias** e a
      coleta quebra sozinha na semana seguinte. É o erro mais comum aqui.
- [ ] Credenciais → ID do cliente OAuth → tipo **App para computador**
- [ ] Em URIs de redirecionamento autorizados, adicionar exatamente
      `http://localhost:8899`
- [ ] Copiar o **ID do cliente** e a **Chave secreta**

**Tempo:** ~10 min.

---

## 4. Gerar o refresh token (depois do item 3)

```bash
export GOOGLE_ADS_CLIENT_ID='....apps.googleusercontent.com'
export GOOGLE_ADS_CLIENT_SECRET='...'
cd scripts
python google_ads_oauth.py
```

- [ ] Abrir o link que ele imprime, autorizar na conta que acessa o Google Ads
- [ ] Guardar o refresh token que ele imprime

**Tempo:** ~2 min.

---

## 5. Reexportar a planilha de Auction Insights

O arquivo atual está **corrompido** por locale: um export em inglês (`0.1408`)
colado em planilha pt-BR virou o inteiro `1408`. O estrago não é reversível por
cálculo (`592` pode ter vindo de 0,592 ou 0,0592), então o importador recusa o
arquivo em vez de adivinhar.

Escolha **um** caminho:

- [ ] No Google Ads, trocar o idioma da conta para Português e exportar de novo
      (sai `14,08%`), **ou**
- [ ] Baixar em .csv e usar **Arquivo → Importar** no Sheets (não colar), **ou**
- [ ] Formatar a coluna de destino como **Texto simples** antes de colar

Isso destrava o dado real na aba Keywords & Leilão. Lembrando: essa tabela de
domínios **não** vem por API (só contas em allowlist do Google), então o export
manual é o caminho definitivo, não um paliativo.

**Tempo:** ~10 min.

---

## 6. Rodar na sua máquina

Se ainda não fez o primeiro uso local:

```powershell
# Windows (PowerShell), na pasta do projeto
py -m pip install openpyxl
cd scripts
copy config.example.json config.json
py servidor.py --config config.json
```

- [ ] Abrir `http://127.0.0.1:8787`
- [ ] Confirmar que a aba Seleção Manual mostra "backend conectado" (barra verde)

**Tempo:** ~5 min.

---

## 7. Me avisar, com os resumos

Quando tiver os tokens, rode cada coletor com `--debug-raw` e me mande **o resumo
que eles imprimem** (não os tokens):

```bash
python meta_ads_api.py --dias 7 --debug-raw --out ../outputs/meta-insights.json \
    --criativos-out ../outputs/meta-criativos.json

python google_ads_api.py --dias 7 --debug-raw \
    --keywords-out ../outputs/gads-keywords.json \
    --campanhas-out ../outputs/gads-campanhas.json
```

- [ ] Comparar os totais com o Gerenciador de Anúncios / interface do Google Ads
- [ ] Me mandar o resumo para eu conferir os nomes de campo e regenerar o painel

Se as **compras** da Meta divergirem, é o `action_type` do pixel: o script tenta
três nomes e imprime qual usou; ajusto para o da sua conta.

---

## O que NÃO fazer

- [ ] ~~Repointar o conector Windsor para a outra conta~~ — **cancelado.** Com os
      coletores próprios, do Windsor só precisamos da GA4, que a conta atual já
      tem. Trocar faria você perder a GA4 para ganhar um Google Ads que passou a
      vir direto da fonte.
- **Não mande tokens pelo chat.** Eles vivem em variável de ambiente na sua
  máquina. Um token da Meta que "nunca expira" colado numa conversa fica gravado
  em log.
- **Não coloque token no `config.json`.** Esse arquivo é gitignored justamente
  por isso, mas variável de ambiente é o lugar certo.

---

## Oportunidade paralela (opcional, sem pressa)

O conector **Semrush** está disponível na sua organização, ainda não autenticado.
Não traz seu gasto nem seu CTR — mas traz **palavra-chave paga e tráfego dos
concorrentes**, que hoje está simulado nas abas de Keywords e Descoberta. Se
quiser, autentique e me avise que eu integro.

---

## Estado atual do dado no painel

| Aba | Fonte |
|---|---|
| GA4 · Jornada | **real medido** (GA4 via Windsor) |
| Metas & Evolução | **real** (cruza GA4 com as metas do config) |
| Mercado Livre / Radar | **real** (Apify, precisa do `APIFY_TOKEN`) |
| Keywords & Leilão | simulado — destrava com o item 1 e o item 5 |
| Meta Ads (lado plataforma) | simulado — destrava com o item 2 |
| Marketplaces (Google Shopping) | simulado |
