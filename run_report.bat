@echo off
cd /d "C:\Users\user\smart-asset-pilot\news_bot"
call venv\Scripts\activate
python main.py
:: 執行完畢後休眠
shutdown /h
