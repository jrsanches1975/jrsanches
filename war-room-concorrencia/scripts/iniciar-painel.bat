@echo off
rem Duplo-clique nisto liga o war room e abre o navegador sozinho — sem
rem precisar abrir PowerShell nem digitar comando nenhum.
rem
rem Dica: arraste este arquivo pra Área de Trabalho (botão direito -> Enviar
rem para -> Área de trabalho, criar atalho) pra ter um "ícone de app" de verdade.
rem
rem Pra desligar: feche esta janela preta que abrir (ou Ctrl+C nela).

cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python nao foi encontrado ^(comando 'py'^).
  echo Instale em https://python.org/downloads e marque "Add python.exe to PATH".
  echo.
  pause
  exit /b 1
)

if not exist config.json (
  echo.
  echo config.json nao existe nesta pasta ainda.
  echo Copiando config.example.json para config.json...
  copy config.example.json config.json >nul
)

rem Junta automaticamente as fontes reais que voce ja coletou antes (GA4,
rem Meta Ads, Keywords, Metas, Descoberta, Google Shopping) na rodada ao
rem vivo do botao -- sem isso, "Salvar e rodar agora" so refaz o Radar de
rem ML/Shopping e ignora tudo que essas outras fontes ja trouxeram. So entra
rem no comando o que EXISTIR de verdade em ..\outputs; nada e inventado.
setlocal enabledelayedexpansion
set "EXTRA="
if exist "..\outputs\own-performance-por-produto.json" set "EXTRA=!EXTRA! --own-performance ..\outputs\own-performance-por-produto.json"
if exist "..\outputs\ga4-jornada.json" set "EXTRA=!EXTRA! --ga4-json ..\outputs\ga4-jornada.json"
if exist "..\outputs\keywords-relatorio.json" set "EXTRA=!EXTRA! --keywords-relatorio-json ..\outputs\keywords-relatorio.json"
if exist "..\outputs\meta-ads.json" set "EXTRA=!EXTRA! --meta-ads-performance-json ..\outputs\meta-ads.json"
if exist "..\outputs\metas.json" set "EXTRA=!EXTRA! --metas-json ..\outputs\metas.json"
if exist "..\outputs\descoberta.json" set "EXTRA=!EXTRA! --descoberta-json ..\outputs\descoberta.json"
if exist "..\outputs\descoberta-shopping.json" set "EXTRA=!EXTRA! --descoberta-shopping-json ..\outputs\descoberta-shopping.json"
if exist "..\outputs\descoberta-termos.json" set "EXTRA=!EXTRA! --descoberta-termos-json ..\outputs\descoberta-termos.json"
if exist "..\outputs\google-shopping.json" set "EXTRA=!EXTRA! --google-shopping-json ..\outputs\google-shopping.json"
if exist "..\outputs\google-shopping-proprio.json" set "EXTRA=!EXTRA! --google-shopping-proprio-json ..\outputs\google-shopping-proprio.json"

echo.
echo Iniciando o war room... o navegador abre sozinho em alguns segundos.
echo Pra desligar, feche esta janela.
echo.
if defined EXTRA (
  echo Fontes extras encontradas em ..\outputs e incluidas nesta rodada:
  echo !EXTRA!
  echo.
  py servidor.py --config config.json --extra !EXTRA!
) else (
  py servidor.py --config config.json
)

pause
