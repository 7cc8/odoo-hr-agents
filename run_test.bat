@echo off
chcp 65001 >nul
set USE_TF=0
set PYTHONUTF8=1
set LAYA_DEVICE=cpu
$env:USE_TF="0"; 
.\.venv\Scripts\python.exe confusion.py
pause