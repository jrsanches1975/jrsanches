@echo off
REM Lancador de duplo clique para o configurador da GA4.
REM Evita a briga com a politica de execucao do PowerShell: o -ExecutionPolicy
REM Bypass vale SO para esta chamada e nao altera a configuracao do Windows.
setlocal
cd /d "%~dp0.."
echo Abrindo o configurador da GA4...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0configurar-ga4.ps1" %*
if errorlevel 1 (
  echo.
  echo O configurador terminou com erro. A mensagem acima diz o que faltou.
  pause
)
endlocal
