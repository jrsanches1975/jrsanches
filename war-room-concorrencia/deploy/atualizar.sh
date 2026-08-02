#!/usr/bin/env bash
# Aplica uma nova versão do código no servidor, sem tocar nos seus dados.
#
#   cd /caminho/do/repositorio && sudo bash deploy/atualizar.sh
#
# Preserva: scripts/config.json (produtos e concorrentes que você selecionou),
# scripts/history/ (os snapshots de que o diff depende) e outputs/.
# Perder o history apagaria a memória das rodadas anteriores e a próxima rodada
# viraria "primeira rodada" — sem diffs, sem alertas.
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/war-room}
APP_USER=${APP_USER:-warroom}
ORIGEM=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

msg()  { printf '\n\033[1;36m==>\033[0m %s\n' "$*"; }
erro() { printf '\n\033[1;31mERRO:\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || erro "rode como root (use sudo)"
[[ -d "$APP_DIR" ]] || erro "$APP_DIR não existe — rode deploy/instalar.sh primeiro"
[[ -f "$ORIGEM/scripts/servidor.py" ]] || erro "rode de dentro da pasta do projeto"

msg "Atualizando código em $APP_DIR (dados preservados)"
rsync -a --delete \
  --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
  --exclude 'outputs/' \
  --exclude 'scripts/config.json' --exclude 'scripts/config.json.bak-*' \
  --exclude 'scripts/history/' \
  "$ORIGEM"/ "$APP_DIR"/

msg "Conferindo dependências"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade openpyxl
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

msg "Reiniciando o serviço"
systemctl restart war-room.service
sleep 2
if systemctl is-active --quiet war-room.service; then
  echo "  no ar. Versão instalada:"
  git -C "$ORIGEM" log --oneline -1 2>/dev/null | sed 's/^/    /' || true
else
  journalctl -u war-room.service -n 30 --no-pager
  erro "não subiu depois da atualização — o log acima mostra o motivo"
fi
