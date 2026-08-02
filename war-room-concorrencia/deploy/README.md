# Publicar o war room num servidor (abrir de qualquer lugar)

Kit de instalação do backend num VPS Ubuntu/Debian: um comando leva do servidor
vazio ao painel publicado com HTTPS, senha e serviço que sobe sozinho no boot.

Funciona em qualquer provedor com **root + SSH** — HostGator VPS, Hostinger,
Oracle Cloud (o *always free* ARM roda isso folgado), DigitalOcean, Contabo.

## O que NÃO serve

**Hospedagem compartilhada de cPanel** (os planos de "hospedagem de site"). Ela é
feita para PHP: não deixa manter um processo Python vivo nem escutar numa porta
própria. Se você já tem um plano desses, ele não roda este backend — precisa ser
VPS ou dedicado.

**Duplo clique no HTML também não dispara rodada**, e isso não é proteção que se
desligue: um arquivo aberto como `file://` não executa Python, e alguém precisa
executar o `war_room.py` para a coleta acontecer. O painel continua abrindo por
duplo clique para *consulta* — só os botões de rodar ficam desabilitados, com
aviso na tela.

## Passo a passo

**1. Contrate o VPS.** 1 vCPU e 2 GB de RAM sobram: o trabalho pesado de raspagem
é o Apify que faz, na nuvem dele. Escolha Ubuntu 22.04 ou 24.04.

**2. Aponte o DNS.** Crie um registro **A** do subdomínio que você quiser
(ex.: `painel.seudominio.com.br`) para o IP do servidor. O certificado HTTPS só é
emitido depois que isso propaga.

**3. Envie o código.** Do seu computador:

```bash
git clone https://github.com/jrsanches1975/jrsanches.git
cd jrsanches/war-room-concorrencia
rsync -a --exclude .git ./ root@SEU_IP:/root/war-room-fonte/
```

Ou, direto no servidor, `git clone` e siga de dentro de `war-room-concorrencia/`.

**4. Rode o instalador.** Uma vez, como root:

```bash
cd /root/war-room-fonte
sudo DOMINIO=painel.seudominio.com.br \
     USUARIO_PAINEL=joie \
     SENHA_PAINEL='uma-senha-longa-de-verdade' \
     APIFY_TOKEN='apify_api_...' \
     bash deploy/instalar.sh
```

Pronto: `https://painel.seudominio.com.br`, com login. Abre no celular.

O instalador é **idempotente** — rodar de novo atualiza sem duplicar nada, e
preserva seu `config.json`, o `scripts/history/` e as saídas.

## Atualizar depois

```bash
cd /root/war-room-fonte && git pull
sudo bash deploy/atualizar.sh
```

Preserva `config.json` (os produtos e concorrentes que você selecionou),
`scripts/history/` (os snapshots de que o diff depende) e `outputs/`. Perder o
history apagaria a memória das rodadas anteriores e a próxima viraria "primeira
rodada": snapshot sem diff, sem alerta nenhum.

## Rodada automática na cadência

O botão do painel dispara na hora. Para as rodadas automáticas, um cron no
próprio servidor (ajuste a cadência ao valor de `cadencia_sugerida_horas`):

```bash
sudo crontab -e
# a cada 6 horas
0 */6 * * * curl -s -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:8787/api/rodar
```

Chamando por `127.0.0.1` o cron não passa pelo Caddy, então não precisa de senha —
e continua inalcançável de fora.

## Segurança — por que cada peça está aí

O painel **executa comando no servidor**. Isso muda o padrão do que é aceitável:

- **O app escuta só em `127.0.0.1`.** Quem fala com a internet é o Caddy. A porta
  8787 nunca fica aberta; o firewall libera apenas 22, 80 e 443.
- **Senha é obrigatória quando há domínio.** O instalador se recusa a subir sem
  `USUARIO_PAINEL`/`SENHA_PAINEL` (mínimo 12 caracteres) se você definir
  `DOMINIO` — sem isso, quem descobrisse o endereço dispararia rodadas e queimaria
  seu saldo de API.
- **A senha protege a API também**, não só a página. O navegador reenvia a
  credencial sozinho depois do login, então os botões seguem funcionando sem token
  embutido no HTML.
- **`header_up Host {host}` no Caddyfile não é decoração.** O `servidor.py`
  compara `Origin` com `Host` para recusar pedido de outra origem; se o proxy não
  preservar o Host, **todos os POSTs passam a dar 403** — verificado em teste.
- **Segredos fora do repositório**, em `/etc/war-room/env` modo 640
  (`root:warroom`). Nunca em `config.json`, que vai para o Git.
- **O serviço roda como usuário de sistema sem shell**, com
  `ProtectSystem=strict`, `NoNewPrivileges` e permissão de escrita só em
  `outputs/` e `scripts/`.

## Suas outras aplicações na mesma máquina

Essa é a vantagem do VPS sobre CI. Cada aplicação numa porta local, cada uma num
subdomínio; o Caddy cuida do certificado de todas. Em `/etc/caddy/Caddyfile`:

```
outroapp.seudominio.com.br {
	reverse_proxy 127.0.0.1:3000
}

site.seudominio.com.br {
	root * /var/www/site
	file_server
}
```

Depois `sudo systemctl reload caddy`. Não precisa reinstalar nada.

## Diagnóstico

```bash
systemctl status war-room       # está de pé?
journalctl -u war-room -f       # log ao vivo do backend
journalctl -u caddy -n 50       # problema de certificado aparece aqui
curl -s localhost:8787/api/estado   # o app responde por dentro?
```

| Sintoma | Causa provável |
|---|---|
| HTTPS não emite | DNS ainda não aponta para o IP, ou porta 80 fechada |
| Painel abre mas botão dá 403 | proxy sem `header_up Host {host}` |
| Rodada falha "sem token Apify" | `/etc/war-room/env` sem `APIFY_TOKEN` → preencha e `systemctl restart war-room` |
| Serviço não sobe | `journalctl -u war-room -n 30` mostra o motivo; erro de escrita costuma ser `ReadWritePaths` |

## O que este kit não resolve

**GA4 e Google Ads continuam chegando por esta conversa** (via Windsor MCP), não
por script com credencial própria. No servidor, a coleta de Mercado Livre e a
geração do painel rodam sozinhas; as abas de GA4, Metas e Meta Ads seguem sendo
atualizadas a partir dos JSONs que eu gero. Mudar isso exigiria uma chave da API
REST do Windsor no servidor — e ainda bateria no limite de 1 conector do plano
Free.

## Estado dos testes

Testado neste ambiente, sem um VPS real:

- sintaxe dos dois scripts (`bash -n`) e validação do unit pelo `systemd-analyze`
- **preservação de dados entre deploys**: `config.json` alterado, `history/`,
  `outputs/` e os backups sobrevivem à atualização; `.git` e `__pycache__` não são
  copiados
- geração inicial do painel e subida do servidor com os caminhos exatos do systemd
- comportamento atrás de proxy: `Host` preservado → 200; `Host` não preservado →
  403; origem externa → 403

Não testado (exige servidor de verdade): `apt-get`, criação do usuário, emissão do
certificado pelo Let's Encrypt, `ufw` e o systemd em execução.
