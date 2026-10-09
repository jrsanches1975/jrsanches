# Configura a credencial da GA4 nesta maquina e valida antes de coletar.
# Cobre os passos 7 em diante de references\ga4-api-setup.md — os passos 4, 5 e 6
# (baixar a chave JSON, dar Leitor na propriedade, copiar o ID) sao cliques na sua
# conta Google e tem de ser feitos antes.
#
# Uso (PowerShell, dentro da pasta do projeto):
#
#   .\deploy\configurar-ga4.ps1 -ChaveJson "C:\Users\Voce\credenciais\ga4-service-account.json" -PropertyId 304174518
#
# Sem parametros, ele pergunta os dois.
# Parametros opcionais:
#   -Dias 30        janela da coleta final (default 30)
#   -SomenteTestar  valida a credencial e para, sem gravar variavel nem coletar

param(
    [string]$ChaveJson,
    [string]$PropertyId,
    [int]$Dias = 30,
    [switch]$SomenteTestar
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$scripts = Join-Path $raiz "scripts"

function Erro($msg) { Write-Host "`nERRO: $msg" -ForegroundColor Red; exit 1 }

# --- python ---
$py = $null
foreach ($cand in @("py", "python", "python3")) {
    if (Get-Command $cand -ErrorAction SilentlyContinue) { $py = $cand; break }
}
if (-not $py) { Erro "Python nao encontrado no PATH. Instale em python.org e abra um terminal novo." }

# --- dependencia de assinatura ---
& $py -c "import cryptography" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Instalando a dependencia 'cryptography' (assinatura do JWT)..." -ForegroundColor Yellow
    & $py -m pip install --quiet cryptography
    if ($LASTEXITCODE -ne 0) { Erro "nao consegui instalar 'cryptography'. Rode: $py -m pip install cryptography" }
}

# --- perguntas ---
# --- selecao do arquivo: janela do Windows, com o mouse ---
if (-not $ChaveJson) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    Write-Host "Abrindo a janela para voce escolher o arquivo da chave..." -ForegroundColor Cyan
    $dlg = New-Object System.Windows.Forms.OpenFileDialog
    $dlg.Title = "Escolha o JSON da conta de servico da GA4 (baixado no passo 4)"
    $dlg.Filter = "Chave de conta de servico (*.json)|*.json|Todos os arquivos (*.*)|*.*"
    $dlg.InitialDirectory = Join-Path $env:USERPROFILE "Downloads"
    $dlg.RestoreDirectory = $true
    # traz a janela para a frente em vez de deixar piscando na barra de tarefas
    $frente = New-Object System.Windows.Forms.Form -Property @{TopMost = $true}
    if ($dlg.ShowDialog($frente) -ne [System.Windows.Forms.DialogResult]::OK) {
        Write-Host "`nCancelado — nenhum arquivo escolhido. Nada foi gravado." -ForegroundColor Yellow
        exit 1
    }
    $ChaveJson = $dlg.FileName
    Write-Host "  escolhido: $ChaveJson"
}
$ChaveJson = $ChaveJson.Trim('"', " ")
if (-not (Test-Path $ChaveJson)) { Erro "arquivo nao encontrado: $ChaveJson" }
$ChaveJson = (Resolve-Path $ChaveJson).Path

# a chave nunca pode morar dentro do repositorio — iria para o Git
if ($ChaveJson.StartsWith($raiz, [StringComparison]::OrdinalIgnoreCase)) {
    Erro "esse arquivo esta DENTRO da pasta do projeto ($raiz).`n" +
         "  Mova a chave para fora (ex.: $env:USERPROFILE\credenciais\) e rode de novo —`n" +
         "  dentro do repositorio ela acabaria no Git."
}

# --- ID da propriedade: caixa de dialogo, tambem com o mouse ---
if (-not $PropertyId) {
    # se o JSON escolhido ja estiver acompanhado de um ID, nem pergunta
    Add-Type -AssemblyName Microsoft.VisualBasic
    Write-Host "Abrindo a caixa para o ID da propriedade..." -ForegroundColor Cyan
    $PropertyId = [Microsoft.VisualBasic.Interaction]::InputBox(
        "Cole o ID numerico da propriedade GA4.`r`n`r`n" +
        "Onde achar: analytics.google.com > Admin (engrenagem) > coluna Propriedade >`r`n" +
        "Detalhes da propriedade > 'ID da propriedade' (so o numero, ex.: 304174518).`r`n`r`n" +
        "Nao e o 'G-XXXXXXX' do fluxo de dados.",
        "War Room - propriedade GA4", "")
    if ([string]::IsNullOrWhiteSpace($PropertyId)) {
        Write-Host "`nCancelado — nenhum ID informado. Nada foi gravado." -ForegroundColor Yellow
        exit 1
    }
}
$PropertyId = $PropertyId.Trim() -replace '^properties/', ''
if ($PropertyId -notmatch '^\d+$') {
    Erro "o ID da propriedade deve ser so numeros (ex.: 304174518). Recebi: '$PropertyId'`n" +
         "  Nao e o 'G-XXXXXXX' do fluxo de dados — e o ID em Admin > Detalhes da propriedade."
}

# --- validacao (passo 8, antes de gravar nada) ---
Write-Host ""
Push-Location $scripts
try {
    & $py ga4_verificar.py --service-account-json $ChaveJson --property-id $PropertyId
    $okValidacao = ($LASTEXITCODE -eq 0)
} finally { Pop-Location }
if (-not $okValidacao) {
    Write-Host "`nNada foi gravado. Corrija o ponto acima e rode este script de novo." -ForegroundColor Yellow
    exit 1
}

if ($SomenteTestar) { Write-Host "`n-SomenteTestar: validado, nada gravado." -ForegroundColor Green; exit 0 }

# --- gravar as variaveis (passo 7) ---
Write-Host "`nGravando as variaveis de ambiente (permanentes, so para o seu usuario)..."
setx GA4_SERVICE_ACCOUNT_JSON "$ChaveJson" | Out-Null
setx GA4_PROPERTY_ID "$PropertyId" | Out-Null
# tambem nesta sessao, para a coleta logo abaixo funcionar sem reabrir o terminal
$env:GA4_SERVICE_ACCOUNT_JSON = $ChaveJson
$env:GA4_PROPERTY_ID = $PropertyId
Write-Host "  GA4_SERVICE_ACCOUNT_JSON e GA4_PROPERTY_ID gravadas." -ForegroundColor Green
Write-Host "  (em terminais NOVOS elas ja vem prontas; o atual so tem por causa desta sessao)"

# --- coleta de conferencia + coleta real (passos 8 e 9) ---
$outputs = Join-Path $raiz "outputs"
New-Item -ItemType Directory -Force -Path $outputs | Out-Null

Push-Location $scripts
try {
    Write-Host "`n--- Coleta de conferencia (7 dias, com --debug-raw) ---" -ForegroundColor Cyan
    Write-Host "Compare os numeros abaixo com a interface da GA4 antes de confiar no painel."
    & $py ga4_api.py --dias 7 --debug-raw --saida-dir $env:TEMP
    if ($LASTEXITCODE -ne 0) { Erro "a coleta de conferencia falhou — veja a mensagem acima." }

    Write-Host "`n--- Coleta real ($Dias dias) ---" -ForegroundColor Cyan
    & $py ga4_api.py --dias $Dias --saida-dir $outputs
    if ($LASTEXITCODE -ne 0) { Erro "a coleta real falhou — veja a mensagem acima." }
} finally { Pop-Location }

Write-Host "`nPronto. Os 7 blocos e o ga4-jornada.json estao em $outputs" -ForegroundColor Green
Write-Host "`nPara montar o painel com a aba 'GA4 - Jornada':"
Write-Host "  cd scripts"
Write-Host "  $py war_room.py --config config.json --ga4-json ..\outputs\ga4-jornada.json \"
Write-Host "      --out ..\outputs\war-room.xlsx --html ..\outputs\war-room.html"
