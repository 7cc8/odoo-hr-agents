@echo off
chcp 65001 >nul
echo ========================================================
echo   تشغيل محرك الذكاء الاصطناعي المحلي (Ollama Service)
echo ========================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "OLLAMA_EXE=%SCRIPT_DIR%AI\ollama.exe"
set "OLLAMA_MODELS=%SCRIPT_DIR%AI\models"

if not exist "%OLLAMA_EXE%" (
    echo [خطأ] لم يتم العثور على ملف Ollama في: %OLLAMA_EXE%
    pause
    exit /b 1
)

echo [1/2] ضبط مسار النماذج المحلية: %OLLAMA_MODELS%
echo [2/2] بدء تشغيل الخادم على http://localhost:11434 ...
echo.
echo ========================================================
echo   الخادم يعمل الآن في هذه النافذة (أو يمكنك تصغيرها).
echo   لإيقاف الخادم اضغط Ctrl+C
echo ========================================================
echo.

"%OLLAMA_EXE%" serve

pause
