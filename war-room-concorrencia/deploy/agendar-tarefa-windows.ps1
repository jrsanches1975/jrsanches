# Registra a Tarefa Agendada do Windows que roda a coleta automaticamente, sem
# precisar abrir o painel nem clicar em nada. Rode este script UMA VEZ.
#
# Uso (PowerShell comum, não precisa ser Administrador):
#   cd war-room-concorrencia\deploy
#   .\agendar-tarefa-windows.ps1                  # padrão: a cada 6 horas
#   .\agendar-tarefa-windows.ps1 -IntervaloHoras 4
#
# O que isto faz: cria/atualiza uma Tarefa Agendada chamada "WarRoomRodada" que
# chama scripts\rodar_rotina.ps1 no intervalo escolhido, começando em 5 minutos.
# É idempotente — rodar de novo só atualiza o agendamento existente.
#
# Antes de rodar isto, faça a única coisa que só você pode fazer (uma vez só):
#   setx APIFY_TOKEN "apify_api_..."
# Sem isso a tarefa vai rodar e falhar silenciosamente por falta de token — o
# log em outputs\rotina.log vai dizer exatamente isso.
#
# Limitação a saber: a tarefa fica registrada no seu usuário do Windows sem senha
# guardada em lugar nenhum, então ela só dispara enquanto VOCÊ estiver com sessão
# aberta no Windows (tela bloqueada tudo bem, computador desligado ou deslogado
# não). Para rodar mesmo com ninguém logado, seria preciso um servidor sempre
# ligado (ver deploy/instalar.sh, o caminho de VPS) — outra decisão, não este script.

param(
    [int]$IntervaloHoras = 6
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ScriptRotina = Join-Path $Raiz "scripts\rodar_rotina.ps1"

if (-not (Test-Path $ScriptRotina)) {
    Write-Error "Não achei $ScriptRotina — rode este script de dentro da pasta 'deploy' do projeto."
    exit 1
}

if (-not $env:APIFY_TOKEN) {
    Write-Warning "APIFY_TOKEN não está definido NESTA sessão. Isso é só um aviso — se você já rodou 'setx APIFY_TOKEN ...' antes, a tarefa vai encontrar o valor na hora de rodar, mesmo sem aparecer aqui. Se nunca rodou, faça isso agora antes de continuar:`n    setx APIFY_TOKEN `"apify_api_...`""
}

$Nome = "WarRoomRodada"
$Acao = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptRotina`""
$Gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours $IntervaloHoras) `
    -RepetitionDuration ([TimeSpan]::MaxValue)
$Config = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $Nome -Action $Acao -Trigger $Gatilho -Settings $Config `
    -Description "War room: recoleta o Radar do Mercado Livre e regenera o painel, sem precisar do botão manual." `
    -Force | Out-Null

Write-Host "Pronto. Tarefa '$Nome' agendada a cada $IntervaloHoras hora(s), começando em ~5 minutos."
Write-Host "Para conferir:      Get-ScheduledTask -TaskName $Nome | Get-ScheduledTaskInfo"
Write-Host "Para rodar na hora: Start-ScheduledTask -TaskName $Nome"
Write-Host "Para desativar:     Disable-ScheduledTask -TaskName $Nome"
Write-Host "Para remover:       Unregister-ScheduledTask -TaskName $Nome -Confirm:`$false"
Write-Host "Log de cada rodada: outputs\rotina.log"
