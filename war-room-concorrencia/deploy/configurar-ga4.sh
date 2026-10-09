#!/usr/bin/env bash
# Configura a credencial da GA4 nesta máquina e valida antes de coletar (macOS/Linux).
# Cobre os passos 7 em diante de references/ga4-api-setup.md — os passos 4, 5 e 6
# (baixar a chave JSON, dar Leitor na propriedade, copiar o ID) são cliques na sua
# conta Google e precisam estar feitos antes.
#
# Uso, dentro da pasta do projeto:
#
#   bash deploy/configurar-ga4.sh
#
# Sem argumentos ele abre uma janela para você ESCOLHER o arquivo com o mouse
# (osascript no macOS, zenity/kdialog no Linux) e outra para colar o ID. Se não
# houver interface gráfica, ele pergunta no terminal.
#
# Também aceita tudo por argumento:
#   bash deploy/configurar-ga4.sh --chave ~/credenciais/ga4.json --property-id 304174518 --dias 30
#   --somente-testar   valida e para, sem gravar variável nem coletar
set -uo pipefail

RAIZ=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
SCRIPTS="$RAIZ/scripts"
CHAVE=""
PROPERTY_ID=""
DIAS=30
SOMENTE_TESTAR=0

while [ $# -gt 0 ]; do
  case "$1" in
    --chave|--service-account-json) CHAVE="$2"; shift 2 ;;
    --property-id) PROPERTY_ID="$2"; shift 2 ;;
    --dias) DIAS="$2"; shift 2 ;;
    --somente-testar) SOMENTE_TESTAR=1; shift ;;
    *) echo "argumento desconhecido: $1" >&2; exit 1 ;;
  esac
done

erro() { printf '\nERRO: %s\n' "$1" >&2; exit 1; }

# --- python ---
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || erro "Python não encontrado no PATH."

if ! "$PY" -c "import cryptography" >/dev/null 2>&1; then
  echo "Instalando a dependência 'cryptography' (assinatura do JWT)..."
  "$PY" -m pip install --quiet cryptography || erro "não consegui instalar 'cryptography'. Rode: $PY -m pip install cryptography"
fi

# --- escolher o arquivo com o mouse, quando houver interface gráfica ---
escolher_arquivo() {
  if [ "$(uname)" = "Darwin" ]; then
    osascript -e 'POSIX path of (choose file with prompt "Escolha o JSON da conta de serviço da GA4 (passo 4)" of type {"json","public.json"})' 2>/dev/null
  elif command -v zenity >/dev/null 2>&1; then
    zenity --file-selection \
      --title="Escolha o JSON da conta de serviço da GA4 (passo 4)" \
      --file-filter="Chave de conta de serviço (*.json) | *.json" 2>/dev/null
  elif command -v kdialog >/dev/null 2>&1; then
    kdialog --getopenfilename "$HOME" "*.json" 2>/dev/null
  fi
}

pedir_texto() {  # $1 = título, $2 = mensagem
  if [ "$(uname)" = "Darwin" ]; then
    osascript -e "text returned of (display dialog \"$2\" with title \"$1\" default answer \"\")" 2>/dev/null
  elif command -v zenity >/dev/null 2>&1; then
    zenity --entry --title="$1" --text="$2" 2>/dev/null
  elif command -v kdialog >/dev/null 2>&1; then
    kdialog --title "$1" --inputbox "$2" 2>/dev/null
  fi
}

if [ -z "$CHAVE" ]; then
  echo "Abrindo a janela para você escolher o arquivo da chave..."
  CHAVE=$(escolher_arquivo)
  if [ -z "$CHAVE" ]; then
    # sem interface gráfica (ou cancelado): cai para o terminal
    printf 'Caminho do arquivo JSON da conta de serviço (passo 4): '
    read -r CHAVE
  fi
fi
CHAVE="${CHAVE%\"}"; CHAVE="${CHAVE#\"}"
[ -n "$CHAVE" ] || erro "nenhum arquivo escolhido. Nada foi gravado."
[ -f "$CHAVE" ] || erro "arquivo não encontrado: $CHAVE"
CHAVE=$(cd "$(dirname "$CHAVE")" && pwd)/$(basename "$CHAVE")
echo "  escolhido: $CHAVE"

# a chave nunca pode morar dentro do repositório — iria para o Git
case "$CHAVE" in
  "$RAIZ"/*) erro "esse arquivo está DENTRO da pasta do projeto ($RAIZ).
  Mova a chave para fora (ex.: ~/credenciais/) e rode de novo — dentro do
  repositório ela acabaria no Git." ;;
esac

if [ -z "$PROPERTY_ID" ]; then
  echo "Abrindo a caixa para o ID da propriedade..."
  PROPERTY_ID=$(pedir_texto "War Room - propriedade GA4" \
    "Cole o ID numérico da propriedade GA4 (Admin > Detalhes da propriedade, ex.: 304174518). Não é o G-XXXXXXX.")
  if [ -z "$PROPERTY_ID" ]; then
    printf 'ID numérico da propriedade GA4 (passo 6, só o número): '
    read -r PROPERTY_ID
  fi
fi
PROPERTY_ID=$(printf '%s' "$PROPERTY_ID" | tr -d '[:space:]' | sed 's|^properties/||')
case "$PROPERTY_ID" in
  ''|*[!0-9]*) erro "o ID da propriedade deve ser só números (ex.: 304174518). Recebi: '$PROPERTY_ID'
  Não é o 'G-XXXXXXX' do fluxo de dados — é o ID em Admin > Detalhes da propriedade." ;;
esac

# --- validação (antes de gravar nada) ---
echo
( cd "$SCRIPTS" && "$PY" ga4_verificar.py --service-account-json "$CHAVE" --property-id "$PROPERTY_ID" ) || {
  printf '\nNada foi gravado. Corrija o ponto acima e rode este script de novo.\n'
  exit 1
}

if [ "$SOMENTE_TESTAR" = "1" ]; then
  echo
  echo "--somente-testar: validado, nada gravado."
  exit 0
fi

# --- gravar as variáveis no perfil do shell ---
export GA4_SERVICE_ACCOUNT_JSON="$CHAVE"
export GA4_PROPERTY_ID="$PROPERTY_ID"

case "${SHELL:-}" in
  */zsh) PERFIL="$HOME/.zshrc" ;;
  */bash) PERFIL="$HOME/.bashrc" ;;
  *) PERFIL="$HOME/.profile" ;;
esac
# idempotente: remove as linhas antigas do war room antes de reescrever
if [ -f "$PERFIL" ]; then
  grep -v '^export GA4_SERVICE_ACCOUNT_JSON=\|^export GA4_PROPERTY_ID=' "$PERFIL" > "$PERFIL.tmp" && mv "$PERFIL.tmp" "$PERFIL"
fi
{
  echo "export GA4_SERVICE_ACCOUNT_JSON=\"$CHAVE\""
  echo "export GA4_PROPERTY_ID=\"$PROPERTY_ID\""
} >> "$PERFIL"
echo
echo "  variáveis gravadas em $PERFIL (em terminais novos já vêm prontas)."

# --- coleta de conferência + coleta real ---
OUTPUTS="$RAIZ/outputs"
mkdir -p "$OUTPUTS"
cd "$SCRIPTS" || erro "pasta scripts não encontrada"

echo
echo "--- Coleta de conferência (7 dias, com --debug-raw) ---"
echo "Compare os números abaixo com a interface da GA4 antes de confiar no painel."
"$PY" ga4_api.py --dias 7 --debug-raw --saida-dir "${TMPDIR:-/tmp}" || erro "a coleta de conferência falhou — veja a mensagem acima."

echo
echo "--- Coleta real ($DIAS dias) ---"
"$PY" ga4_api.py --dias "$DIAS" --saida-dir "$OUTPUTS" || erro "a coleta real falhou — veja a mensagem acima."

# O ga4_api.py grava os 7 blocos crus e PARA: ele só imprime o comando da compilação,
# não o executa. Sem este passo não existe ga4-jornada.json, que é o único arquivo
# que o war_room.py consome.
echo
echo "--- Compilando a aba GA4 Jornada ---"
"$PY" ga4_jornada.py \
  --overview "$OUTPUTS/ga4-overview.json" \
  --funil    "$OUTPUTS/ga4-funil.json" \
  --canais   "$OUTPUTS/ga4-canais.json" \
  --devices  "$OUTPUTS/ga4-devices.json" \
  --landing  "$OUTPUTS/ga4-landing.json" \
  --serie    "$OUTPUTS/ga4-serie.json" \
  --campanhas "$OUTPUTS/ga4-campanhas.json" \
  --periodo  "últimos $DIAS dias" \
  --out      "$OUTPUTS/ga4-jornada.json" || erro "a compilação da aba GA4 falhou — veja a mensagem acima."

[ -f "$OUTPUTS/ga4-jornada.json" ] || erro "a compilação terminou sem gerar o ga4-jornada.json."

echo
echo "Pronto. Os 7 blocos e o ga4-jornada.json estão em $OUTPUTS"
echo
echo "Para montar o painel com a aba 'GA4 · Jornada':"
echo "  cd scripts"
echo "  $PY war_room.py --config config.json --ga4-json ../outputs/ga4-jornada.json \\"
echo "      --out ../outputs/war-room.xlsx --html ../outputs/war-room.html"
