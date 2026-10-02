@echo off
rem Grafico XAUUSD: avvia il server e apre il browser. Aggiungere --mt5 per i prezzi dal vivo.
start "" http://127.0.0.1:8095
python "%~dp0server.py" %*
