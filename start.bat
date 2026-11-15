@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist config.yaml (
  copy config.example.yaml config.yaml >nul
  echo Создан config.yaml - впишите в него токен бота и chat id, затем запустите снова.
  notepad config.yaml
  pause
  exit /b
)
python -m pip install -q -r requirements.txt
python -m avito_monitor --test-telegram
python -m avito_monitor
pause
