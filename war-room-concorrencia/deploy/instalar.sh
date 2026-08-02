#!/usr/bin/env bash
# Instalador do war room num VPS Ubuntu/Debian. Um comando, do zero ao painel
# publicado com HTTPS e senha.
#
# Serve em qualquer provedor com root + SSH (HostGator VPS, Hostinger, Oracle,
# DigitalOcean, Contabo...). NÃO serve em hospedagem compartilhada de cPanel:
# lá não se mantém processo Python vivo nem se escuta em porta própria.
#
# Uso (como root, dentro da pasta do projeto já enviada ao servidor):
#
#   sudo DOMINIO=painel.seudominio.com.br \
#        USUARIO_PAINEL=joie \
#        SENHA_PAINEL='uma-senha-boa' \
#        APIFY_TOKEN='apify_api_...' \
#        bash deploy/instalar.sh
#
# Sem DOMINIO ele instala só em HTTP na porta 8787 (útil para testar antes de
# apontar o DNS), e nesse caso NÃO há senha nem criptografia — não deixe assim.
#
# É idempotente: rodar de novo atualiza a instalação sem duplicar nada.
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/war-room}
APP_USER=${APP_USER:-warroom}
PORTA=${PORTA:-8787}
DOMINIO=${DOMINIO:-}
USUARIO_PAINEL=${USUARIO_PAINEL:-}
SENHA_PAINEL=${SENHA_PAINEL:-}
APIFY_TOKEN=${APIFY_TOKEN:-}
ORIGEM=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

msg()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
erro() { printf '\n\033[1;31mERRO:\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || erro "rode como root (use sudo)"
[[ -f "$ORIGEM/scripts/servidor.py" ]] || erro "não achei scripts/servidor.py em $ORIGEM — rode de dentro da pasta do projeto"

if [[ -n "$DOMINIO" ]]; then
  # com domínio, o painel fica público: senha deixa de ser opcional
  [[ -n "$USUARIO_PAINEL" && -n "$SENHA_PAINEL" ]] || \
    erro "com DOMINIO definido o painel fica acessível pela internet, então USUARIO_PAINEL e SENHA_PAINEL são obrigatórios.
      Este painel EXECUTA comando no servidor: sem senha, qualquer um que descubra o endereço dispara rodadas e queima seu saldo de API."
  (( ${#SENHA_PAINEL} >= 12 )) || erro "SENHA_PAINEL com menos de 12 caracteres — é a única porta entre a internet e um endpoint que executa comando"
fi

# ------------------------------------------------------------------- pacotes
msg "Instalando pacotes do sistema"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip rsync curl ca-certificates ufw >/dev/null

# ------------------------------------------------------------------- usuário
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  msg "Criando usuário de serviço '$APP_USER' (sem shell de login)"
  useradd --system --create-home --shell /usr/sbin/nologin "$APP_USER"
else
  msg "Usuário '$APP_USER' já existe"
fi

# ------------------------------------------------------------------ aplicação
msg "Copiando aplicação para $APP_DIR"
mkdir -p "$APP_DIR"
# --exclude protege o que é do servidor: config.json e histórico vivem lá e não
# devem ser sobrescritos por um deploy
rsync -a --delete \
  --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
  --exclude 'outputs/' \
  --exclude 'scripts/config.json' --exclude 'scripts/config.json.bak-*' \
  --exclude 'scripts/history/' \
  "$ORIGEM"/ "$APP_DIR"/
mkdir -p "$APP_DIR/outputs" "$APP_DIR/scripts/history"

if [[ ! -f "$APP_DIR/scripts/config.json" ]]; then
  msg "Primeiro deploy: criando config.json a partir do exemplo"
  cp "$APP_DIR/scripts/config.example.json" "$APP_DIR/scripts/config.json"
else
  msg "config.json existente preservado (produtos e concorrentes intactos)"
fi

msg "Preparando ambiente Python (só openpyxl é externo; o resto é biblioteca padrão)"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet openpyxl

chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ------------------------------------------------------------------ segredos
msg "Gravando segredos em /etc/war-room/env (fora do repositório, modo 600)"
mkdir -p /etc/war-room
if [[ -n "$APIFY_TOKEN" ]]; then
  printf 'APIFY_TOKEN=%s\n' "$APIFY_TOKEN" > /etc/war-room/env
elif [[ ! -f /etc/war-room/env ]]; then
  # arquivo precisa existir: o systemd falha se o EnvironmentFile não estiver lá
  printf '# APIFY_TOKEN=apify_api_...  <- preencha para a coleta real rodar\n' > /etc/war-room/env
fi
chown root:"$APP_USER" /etc/war-room/env
chmod 640 /etc/war-room/env

# ------------------------------------------------------------------- systemd
msg "Instalando serviço systemd (sobe sozinho no boot, reinicia se cair)"
sed -e "s|__APP_DIR__|$APP_DIR|g" \
    -e "s|__APP_USER__|$APP_USER|g" \
    -e "s|__PORTA__|$PORTA|g" \
    "$ORIGEM/deploy/war-room.service" > /etc/systemd/system/war-room.service
systemctl daemon-reload
systemctl enable --quiet war-room.service
systemctl restart war-room.service

sleep 2
systemctl is-active --quiet war-room.service || {
  journalctl -u war-room.service -n 30 --no-pager
  erro "o serviço não subiu — o log acima mostra o motivo"
}

# --------------------------------------------------------------- painel gerado
msg "Gerando o painel pela primeira vez"
# --simulate-ml usa o exemplo embutido: sem token do Apify a coleta real não
# roda, e é melhor subir com painel de demonstração do que com página de erro
if grep -q '^APIFY_TOKEN=' /etc/war-room/env; then
  EXTRA=()
else
  # caminho ABSOLUTO: este comando não roda de dentro de scripts/, e um caminho
  # relativo aqui simplesmente não seria encontrado
  EXTRA=(--simulate-ml "$APP_DIR/scripts/examples/ml-simulado-rodada2.json")
  echo "    (sem APIFY_TOKEN ainda: primeiro painel sai com dado de exemplo)"
fi
# roda de dentro de scripts/, igual ao serviço, para o comportamento ser o mesmo
(cd "$APP_DIR/scripts" && sudo -u "$APP_USER" env HOME="/home/$APP_USER" \
  "$APP_DIR/.venv/bin/python" "$APP_DIR/scripts/war_room.py" \
  --config "$APP_DIR/scripts/config.json" \
  --out "$APP_DIR/outputs/war-room.xlsx" \
  --html "$APP_DIR/outputs/war-room.html" \
  "${EXTRA[@]}" >/dev/null) \
  || echo "    aviso: a primeira geração falhou; use o botão do painel depois de configurar o token"

# ----------------------------------------------------------- proxy com HTTPS
if [[ -n "$DOMINIO" ]]; then
  msg "Instalando Caddy (HTTPS automático via Let's Encrypt) e publicando $DOMINIO"
  if ! command -v caddy >/dev/null 2>&1; then
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https >/dev/null
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
      | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
      > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy >/dev/null
  fi
  HASH=$(caddy hash-password --plaintext "$SENHA_PAINEL")
  sed -e "s|__DOMINIO__|$DOMINIO|g" \
      -e "s|__PORTA__|$PORTA|g" \
      -e "s|__USUARIO__|$USUARIO_PAINEL|g" \
      -e "s|__HASH__|$HASH|g" \
      "$ORIGEM/deploy/Caddyfile" > /etc/caddy/Caddyfile
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null \
    || erro "Caddyfile inválido"
  systemctl restart caddy

  msg "Firewall: liberando SSH, HTTP e HTTPS; a porta $PORTA fica fechada de fora"
  ufw allow 22/tcp  >/dev/null
  ufw allow 80/tcp  >/dev/null
  ufw allow 443/tcp >/dev/null
  ufw --force enable >/dev/null

  cat <<FIM

────────────────────────────────────────────────────────────────────────
  Pronto. Abra de qualquer lugar:  https://$DOMINIO
  Usuário: $USUARIO_PAINEL   (senha: a que você passou)

  O painel escuta em 127.0.0.1:$PORTA e SÓ é alcançável pelo Caddy, que
  põe HTTPS e senha na frente. A porta $PORTA não está aberta na internet.
────────────────────────────────────────────────────────────────────────

  Comandos do dia a dia:
    systemctl status war-room      # está de pé?
    journalctl -u war-room -f      # log ao vivo
    bash deploy/atualizar.sh       # aplicar nova versão do código

  Falta fazer:
    - aponte o DNS de $DOMINIO para o IP deste servidor (registro A), se
      ainda não apontou — o certificado só é emitido depois disso
$( grep -q '^APIFY_TOKEN=' /etc/war-room/env || echo "    - preencha APIFY_TOKEN em /etc/war-room/env e rode:
        systemctl restart war-room" )
FIM
else
  cat <<FIM

────────────────────────────────────────────────────────────────────────
  Instalado SEM domínio: http://$(hostname -I | awk '{print $1}'):$PORTA

  ATENÇÃO: nesse modo não há HTTPS nem senha. Serve para testar de dentro
  da rede. Antes de usar de fora, rode de novo com DOMINIO, USUARIO_PAINEL
  e SENHA_PAINEL — o painel executa comando no servidor.
────────────────────────────────────────────────────────────────────────
FIM
  # sem domínio, o servidor precisa escutar em todas as interfaces para ser
  # alcançado; e aí o próprio servidor.py exige token
  echo "  (para escutar fora do localhost sem Caddy, veja deploy/README.md)"
fi
