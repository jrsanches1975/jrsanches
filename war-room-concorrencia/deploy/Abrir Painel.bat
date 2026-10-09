@echo off
REM Abre o painel do War Room COM BACKEND, que e o que torna a aba
REM "Selecao Manual" editavel: sem servidor o HTML e estatico e nao grava nada.
REM
REM O servidor escuta so em 127.0.0.1 (apenas esta maquina) e abre o navegador
REM sozinho. Para parar, feche esta janela ou pressione Ctrl+C nela.
setlocal
cd /d "%~dp0..\scripts"

if not exist "config.json" (
  if exist "config.example.json" (
    echo config.json nao existe ainda. Criando a partir do exemplo...
    copy /y "config.example.json" "config.json" >nul
    echo.
  ) else (
    echo ERRO: nao encontrei config.json nem config.example.json nesta pasta.
    echo Voce esta na pasta certa do projeto?
    pause
    exit /b 1
  )
)

set PY=py
where py >nul 2>&1 || set PY=python

echo Abrindo o painel em http://127.0.0.1:8787
echo Deixe esta janela ABERTA enquanto usa o painel.
echo.
%PY% servidor.py --config config.json %*
if errorlevel 1 (
  echo.
  echo O servidor terminou com erro. A mensagem acima diz o motivo.
  pause
)
endlocal
