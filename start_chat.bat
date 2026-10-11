@echo off
echo ========================================
echo   تشغيل شات سِراج LangGraph
echo ========================================
echo.

REM التحقق من وجود .venv
if not exist ".venv" (
    echo [خطأ] لم يتم العثور على البيئة الافتراضية .venv
    echo يرجى تشغيل: python -m venv .venv
    pause
    exit /b 1
)

REM تفعيل البيئة الافتراضية
call .venv\Scripts\activate.bat

echo [1/3] تفعيل البيئة الافتراضية... ✓
echo.

REM تشغيل LangGraph Studio في الخلفية (Port 2024)
echo [2/3] تشغيل LangGraph Studio...
start "LangGraph Studio" cmd /c "langgraph dev --port 2024"
timeout /t 3 /nobreak >nul
echo ✓ LangGraph Studio يعمل على http://localhost:2024
echo.

REM تشغيل FastAPI Web Service (Port 8000)
echo [3/3] تشغيل واجهة الشات...
echo ✓ الشات متاح على http://localhost:8000
echo.
echo ========================================
echo   الخدمات تعمل الآن:
echo   - LangGraph Studio: http://localhost:2024
echo   - شات الويب: http://localhost:8000
echo ========================================
echo.
echo اضغط Ctrl+C لإيقاف الخدمات
echo.

REM تشغيل FastAPI
python -m uvicorn web_service:app --host 0.0.0.0 --port 8000 --reload

pause
