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

echo.
echo Iniciando o war room... o navegador abre sozinho em alguns segundos.
echo Pra desligar, feche esta janela.
echo.
py servidor.py --config config.json

pause
