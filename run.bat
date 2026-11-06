@echo off
cd /d "%~dp0"
if not exist .venv py -m venv .venv
.venv\Scripts\python.exe -m pip install -q -r requirements.txt
.venv\Scripts\python.exe -m streamlit run app\main.py
pause
