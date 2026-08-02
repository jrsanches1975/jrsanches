# Roda uma rodada completa do war room sem precisar abrir nada na tela — é o
# script que a Tarefa Agendada do Windows chama sozinha, no horário configurado.
#
# Diferença do botão "Salvar e rodar agora" da aba Seleção Manual: aquele exige o
# servidor.py aberto e alguém clicando. Este roda mesmo com você longe do
# computador, contanto que o Windows esteja ligado.
#
# Pré-requisito ÚNICO que só você pode fazer uma vez (a Tarefa Agendada roda numa
# sessão nova, sem as variáveis do seu PowerShell interativo):
#
#   setx APIFY_TOKEN "apify_api_..."
#
# setx grava a variável de forma PERMANENTE pro seu usuário do Windows — abra um
# terminal NOVO depois de rodar, a mudança não aparece no mesmo terminal. Isto é
# diferente de "$env:APIFY_TOKEN = ...", que vale só pra aquela janela e some
# assim que ela fecha — por isso o botão manual funciona hoje mas uma tarefa
# agendada, sem isso, rodaria sem token.
#
# Este script NÃO grava o token em lugar nenhum do repositório — ele só lê a
# variável de ambiente que você já configurou.

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
$Log = Join-Path $Raiz "..\outputs\rotina.log"
New-Item -ItemType Directory -Force -Path (Split-Path $Log) | Out-Null

function Registrar($linha) {
    $carimbo = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$carimbo  $linha" | Tee-Object -FilePath $Log -Append
}

if (-not $env:APIFY_TOKEN) {
    Registrar "ERRO: APIFY_TOKEN não está definido nesta sessão. Rode 'setx APIFY_TOKEN ...' uma vez e abra um terminal novo (ou reinicie a Tarefa Agendada) antes de tentar de novo."
    exit 1
}

Registrar "=== rodada automática iniciando ==="
Push-Location $Raiz
try {
    # os --*-json abaixo reaproveitam a última coleta real de cada fonte que não
    # é re-coletável por aqui (GA4/Meta/Keywords dependem do Windsor, que exige a
    # sessão do Claude ou as chaves de API das contas — ver PROXIMOS-PASSOS.md).
    # Só o Radar do Mercado Livre é recoletado de verdade a cada execução deste
    # script, porque é o único lado 100% automatizável sem depender de outra
    # sessão. Ajuste os caminhos abaixo se algum arquivo não existir na sua máquina.
    $argumentos = @(
        "--config", "config.json",
        "--out", "..\outputs\war-room.xlsx",
        "--html", "..\outputs\war-room.html"
    )
    foreach ($extra in @(
        @("--own-performance", "..\outputs\own-performance-por-produto.json"),
        @("--descoberta-json", "..\outputs\descoberta.json"),
        @("--keywords-relatorio-json", "..\outputs\keywords-relatorio.json"),
        @("--ga4-json", "..\outputs\ga4-jornada.json"),
        @("--metas-json", "..\outputs\metas.json"),
        @("--meta-ads-performance-json", "..\outputs\meta-ads-performance.json")
    )) {
        if (Test-Path $extra[1]) { $argumentos += $extra }
    }

    py war_room.py @argumentos 2>&1 | Tee-Object -FilePath $Log -Append
    $codigo = $LASTEXITCODE
    if ($codigo -eq 0) {
        Registrar "=== rodada OK ==="
    } else {
        Registrar "=== rodada terminou com erro (código $codigo) — veja as linhas acima ==="
    }
    exit $codigo
} finally {
    Pop-Location
}
