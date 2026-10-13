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

echo [1/4] تفعيل البيئة الافتراضية... ✓
echo.

REM التحقق من خادم Ollama المحلي وتشغيله إن لم يكن يعمل
echo [2/4] فحص خادم الذكاء الاصطناعي المحلي (Ollama)...
curl -s http://127.0.0.1:11434/api/tags >nul 2>&1
if errorlevel 1 (
    if exist "%~dp0AI\ollama.exe" (
        echo   - جاري بدء تشغيل Ollama المحلي في الخلفية...
        set "OLLAMA_MODELS=%~dp0AI\models"
        start "Ollama Local Service" /min "%~dp0AI\ollama.exe" serve
        timeout /t 2 /nobreak >nul
        echo   ✓ تم إطلاق خادم Ollama المحلي
    ) else (
        echo   [تنبيه] لم يتم العثور على AI\ollama.exe
    )
) else (
    echo   ✓ خادم Ollama يعمل ومتاح مسبقاً
)
echo.

REM تشغيل LangGraph Studio في الخلفية (Port 2024)
echo [3/4] تشغيل LangGraph Studio...
start "LangGraph Studio" cmd /c "langgraph dev --port 2024"
timeout /t 3 /nobreak >nul
echo ✓ LangGraph Studio يعمل على http://localhost:2024
echo.

REM تشغيل FastAPI Web Service (Port 8000)
echo [4/4] تشغيل واجهة الشات...
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
