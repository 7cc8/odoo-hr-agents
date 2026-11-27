"""
LLM Configuration Manager - مدير إعدادات ومزودي الذكاء الاصطناعي
===============================================================
يدير التبديل الذكي بين المحرك المحلي (Local Ollama) والذكاء الاصطناعي السحابي (Cloud Providers)،
ويدعم إضافة مفاتيح API Key لأي مشغل مخصص أو معتمد (OpenRouter, OpenAI, Groq, DeepSeek, Custom).
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("llm_config_manager")

CONFIG_PATH = Path("config/llm_config.json")

PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "gemini": {
        "name": "Google Gemini (رسمي)",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-flash-lite-latest",
        "suggested_models": [
            "gemini-flash-lite-latest",
            "gemini-flash-latest",
            "gemini-3.8-flash",
        ],
        "env_key": "GEMINI_API_KEY",
    },
    "openrouter": {
        "name": "OpenRouter (شامل وموصى به)",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openrouter/auto",
        "suggested_models": [
            "openrouter/auto",
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
            "meta-llama/llama-3.3-70b-instruct",
            "qwen/qwen-2.5-72b-instruct",
        ],
        "env_key": "OPENROUTER_API_KEY",
    },
    "openai": {
        "name": "OpenAI (رسمي)",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "suggested_models": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-3.5-turbo",
        ],
        "env_key": "OPENAI_API_KEY",
    },
    "groq": {
        "name": "Groq (سرعة استجابة فائقة)",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "suggested_models": [
            "llama-3.3-70b-versatile",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ],
        "env_key": "GROQ_API_KEY",
    },
    "deepseek": {
        "name": "DeepSeek (اقتصادي ومتقدم)",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "suggested_models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "env_key": "DEEPSEEK_API_KEY",
    },
    "custom": {
        "name": "مشغل مخصص (أي مشغل متوافق مع OpenAI API)",
        "base_url": "https://api.your-provider.com/v1",
        "default_model": "default-model",
        "suggested_models": [],
        "env_key": "LLM_API_KEY",
    },
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "mode": "auto",  # "auto" (تبديل تلقائي ذكي) | "manual" (يدوي صريح)
    "active_provider": "local",  # "local" | "cloud"
    "fallback_enabled": True,  # التراجع للقواعد عند تعطل المزودات
    "local": {
        "provider": "ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen3.5:9b",
        "timeout": 120,
    },
    "cloud": {
        "provider": "openrouter",
        "api_key": "",
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openrouter/auto",
        "timeout": 45,
    },
}


def mask_api_key(key: Optional[str]) -> str:
    """إخفاء مفتاح الـ API للعرض الآمن"""
    if not key or not str(key).strip():
        return ""
    s = str(key).strip()
    if len(s) <= 8:
        return "••••••••"
    return f"{s[:6]}••••••••{s[-4:]}"


def load_llm_config() -> Dict[str, Any]:
    """تحميل الإعدادات مع دمج المتغيرات البيئية والقيم الافتراضية"""
    config = dict(DEFAULT_CONFIG)
    config["local"] = dict(DEFAULT_CONFIG["local"])
    config["cloud"] = dict(DEFAULT_CONFIG["cloud"])

    # 1. إذا كان الملف موجوداً، نقرأ منه
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    if "mode" in saved:
                        config["mode"] = saved["mode"]
                    if "active_provider" in saved:
                        config["active_provider"] = saved["active_provider"]
                    if "fallback_enabled" in saved:
                        config["fallback_enabled"] = bool(saved["fallback_enabled"])
                    if "local" in saved and isinstance(saved["local"], dict):
                        config["local"].update(saved["local"])
                    if "cloud" in saved and isinstance(saved["cloud"], dict):
                        config["cloud"].update(saved["cloud"])
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", CONFIG_PATH, exc)

    # 2. استكمال القيم الناقصة من متغيرات البيئة إن وجدت
    env_local_url = os.environ.get("LLM_BASE_URL")
    if env_local_url and not config["local"].get("base_url"):
        config["local"]["base_url"] = env_local_url

    env_local_model = os.environ.get("LLM_MODEL")
    if env_local_model and not config["local"].get("model"):
        config["local"]["model"] = env_local_model

    preset = PROVIDER_PRESETS.get(config["cloud"].get("provider"), PROVIDER_PRESETS["custom"])
    env_cloud_key = os.environ.get(preset["env_key"])
    if env_cloud_key and not config["cloud"].get("api_key"):
        config["cloud"]["api_key"] = env_cloud_key

    # تصحيح نموذج Gemini إذا كان معلقاً على openrouter/auto أو اسماً قديماً
    cld_prov = str(config["cloud"].get("provider") or "").lower()
    cld_url = str(config["cloud"].get("base_url") or "").lower()
    cld_mod = str(config["cloud"].get("model") or "").lower()
    if (cld_prov == "gemini" or "generativelanguage.googleapis.com" in cld_url) and (cld_mod == "openrouter/auto" or not cld_mod):
        config["cloud"]["model"] = PROVIDER_PRESETS["gemini"]["default_model"]

    # التحقق من صحة الوضع
    if config["mode"] not in ("auto", "manual"):
        config["mode"] = "auto"
    if config["active_provider"] not in ("local", "cloud"):
        config["active_provider"] = "local"

    return config


def save_llm_config(new_data: Dict[str, Any]) -> Dict[str, Any]:
    """حفظ الإعدادات بأمان في ملف json وتحديث البيئة"""
    current = load_llm_config()

    if "mode" in new_data and new_data["mode"] in ("auto", "manual"):
        current["mode"] = new_data["mode"]

    if "active_provider" in new_data and new_data["active_provider"] in ("local", "cloud"):
        current["active_provider"] = new_data["active_provider"]

    if "fallback_enabled" in new_data:
        current["fallback_enabled"] = bool(new_data["fallback_enabled"])

    if "local" in new_data and isinstance(new_data["local"], dict):
        loc = new_data["local"]
        if "base_url" in loc and str(loc["base_url"]).strip():
            current["local"]["base_url"] = str(loc["base_url"]).strip()
        if "model" in loc and str(loc["model"]).strip():
            current["local"]["model"] = str(loc["model"]).strip()
        if "timeout" in loc and isinstance(loc["timeout"], (int, float)):
            current["local"]["timeout"] = int(loc["timeout"])

    if "cloud" in new_data and isinstance(new_data["cloud"], dict):
        cld = new_data["cloud"]
        provider = str(cld.get("provider") or current["cloud"]["provider"]).strip()
        base_url = str(cld.get("base_url") or current["cloud"]["base_url"]).strip().rstrip("/")
        if provider != current["cloud"]["provider"] or base_url != current["cloud"]["base_url"].rstrip("/"):
            current["cloud"]["api_key"] = ""
        current["cloud"]["provider"] = provider
        if "base_url" in cld and str(cld["base_url"]).strip():
            current["cloud"]["base_url"] = str(cld["base_url"]).strip()
        if "model" in cld and str(cld["model"]).strip():
            current["cloud"]["model"] = str(cld["model"]).strip()
        if "timeout" in cld and isinstance(cld["timeout"], (int, float)):
            current["cloud"]["timeout"] = int(cld["timeout"])

        # تطبيع اسم النموذج لمزود Google Gemini لمنع بقاء openrouter/auto أو اسماً قديماً
        cld_prov = str(current["cloud"].get("provider") or "").lower()
        cld_url = str(current["cloud"].get("base_url") or "").lower()
        cld_mod = str(current["cloud"].get("model") or "").lower()
        if (cld_prov == "gemini" or "generativelanguage.googleapis.com" in cld_url) and (cld_mod == "openrouter/auto" or not cld_mod):
            current["cloud"]["model"] = PROVIDER_PRESETS["gemini"]["default_model"]

        # معالجة الـ api_key: إذا أرسل المستخدم قيمة جديدة غير خالية وليست مشفرة/مقنعة
        if "api_key" in cld:
            incoming_key = str(cld["api_key"]).strip()
            if incoming_key and not incoming_key.startswith("••••") and "••••••••" not in incoming_key:
                current["cloud"]["api_key"] = incoming_key
            elif incoming_key == "":
                current["cloud"]["api_key"] = ""

    # كتابة الإعدادات للملف
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    if current["local"].get("base_url"):
        os.environ["LLM_BASE_URL"] = current["local"]["base_url"]
    if current["local"].get("model"):
        os.environ["LLM_MODEL"] = current["local"]["model"]

    logger.info("Saved LLM configuration: mode=%s, active_provider=%s", current["mode"], current["active_provider"])
    return current


def get_masked_llm_config() -> Dict[str, Any]:
    """إرجاع الإعدادات مع إخفاء الـ API Key وإرفاق تفاصيل المشغلات والحالة الفورية"""
    config = load_llm_config()
    masked = {
        "mode": config.get("mode", "auto"),
        "active_provider": config.get("active_provider", "local"),
        "fallback_enabled": config.get("fallback_enabled", True),
        "local": {
            "provider": config["local"].get("provider", "ollama"),
            "base_url": config["local"].get("base_url", "http://localhost:11434/v1"),
            "model": config["local"].get("model", "qwen3.5:9b"),
            "timeout": config["local"].get("timeout", 120),
        },
        "cloud": {
            "provider": config["cloud"].get("provider", "openrouter"),
            "base_url": config["cloud"].get("base_url", "https://openrouter.ai/api/v1"),
            "model": config["cloud"].get("model", "openrouter/auto"),
            "timeout": config["cloud"].get("timeout", 45),
            "has_api_key": bool(config["cloud"].get("api_key")),
            "api_key_masked": mask_api_key(config["cloud"].get("api_key")),
        },
        "presets": PROVIDER_PRESETS,
    }
    return masked


def start_local_ollama_process() -> Tuple[bool, str]:
    """تشغيل خادم Ollama المحلي في الخلفية مع ربطه بمجلد النماذج المحلي"""
    import shutil
    import subprocess
    base_dir = Path(__file__).resolve().parent
    ollama_exe = base_dir / "AI" / "ollama.exe"
    models_dir = base_dir / "AI" / "models"

    if not ollama_exe.exists():
        system_ollama = shutil.which("ollama")
        if not system_ollama:
            return False, "لم يتم العثور على ملف تشغيل Ollama في المجلد المحلي AI/ollama.exe أو في مسار النظام."
        ollama_bin = system_ollama
    else:
        ollama_bin = str(ollama_exe)

    env = os.environ.copy()
    if models_dir.exists():
        env["OLLAMA_MODELS"] = str(models_dir)

    try:
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            if hasattr(subprocess, "DETACHED_PROCESS"):
                creationflags |= subprocess.DETACHED_PROCESS
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags |= subprocess.CREATE_NO_WINDOW

        subprocess.Popen(
            [ollama_bin, "serve"],
            env=env,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True if os.name != "nt" else False,
        )
        logger.info("Launched local Ollama daemon (%s) with models: %s", ollama_bin, models_dir)
        return True, "تم إطلاق خادم Ollama في الخلفية بنجاح."
    except Exception as exc:
        logger.error("Failed to launch local Ollama process: %s", exc)
        return False, f"فشل تشغيل خادم Ollama: {exc}"


def check_local_health(base_url: Optional[str] = None, auto_start: bool = True, model: Optional[str] = None) -> Dict[str, Any]:
    """فحص صحة اتصال خادم Ollama المحلي واكتشاف النماذج تلقائياً مع محاولة التشغيل الذاتي"""
    cfg = load_llm_config()
    url = base_url or cfg["local"].get("base_url", "http://localhost:11434/v1")
    parsed = urllib.parse.urlparse(url)
    clean_base = f"{parsed.scheme}://{parsed.netloc}"
    tags_url = f"{clean_base}/api/tags"

    def _query_tags(timeout_sec: float = 8.0) -> Optional[List[str]]:
        try:
            req = urllib.request.Request(tags_url, headers={"User-Agent": "OdooHRAgents/1.0"})
            with urllib.request.urlopen(req, timeout=timeout_sec) as res:
                if res.status == 200:
                    data = json.loads(res.read().decode("utf-8"))
                    return [m.get("name") for m in data.get("models", [])]
        except Exception:
            return None
        return None

    start_t = time.time()
    models = _query_tags(timeout_sec=4.0)

    # إذا تعذر الاتصال وكان auto_start مفعلاً، نحاول إطلاق خادم Ollama المحلي وإعادة المحاولة
    if models is None and auto_start:
        base_dir = Path(__file__).resolve().parent
        ollama_exe = base_dir / "AI" / "ollama.exe"
        if ollama_exe.exists() or shutil.which("ollama"):
            try:
                start_local_ollama_process()
                time.sleep(2.5)
                models = _query_tags(timeout_sec=8.0)
            except Exception:
                pass

    if models is not None:
        latency_ms = int((time.time() - start_t) * 1000)
        configured_model = model or cfg["local"]["model"]
        available = configured_model in models or f"{configured_model}:latest" in models
        return {
            "status": "online" if available else "model_missing",
            "available": available,
            "latency_ms": latency_ms,
            "models": models,
            "active_model": configured_model if available else None,
            "message": "خادم Ollama متصل والنموذج مثبّت." if available else "خادم Ollama متصل، لكن النموذج المحدد غير مثبّت.",
        }

    latency_ms = int((time.time() - start_t) * 1000)
    return {
        "status": "offline",
        "available": False,
        "latency_ms": latency_ms,
        "models": [],
        "message": "تعذر الاتصال بـ Ollama محلياً. تأكد من تشغيل `ollama serve` أو انقر على تشغيل المحرك المحلي.",
    }


def chat_request_target(base_url: str, api_key: Optional[str]) -> Tuple[str, Dict[str, str], bool]:
    """Build the transport shared by the model probe and Seraj."""
    from urllib.parse import urlparse

    base_url = base_url.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("Invalid provider URL")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("Invalid provider URL")
    native = parsed.hostname == "api.anthropic.com"
    suffix = "/messages" if native else "/chat/completions"
    url = base_url if base_url.endswith(suffix) else base_url + suffix
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "OdooHRAgents/1.0",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Odoo HR Agents",
    }
    if api_key and native:
        headers["x-api-key"] = api_key.strip()
        headers["anthropic-version"] = "2023-06-01"
    elif api_key:
        headers["Authorization"] = f"Bearer {api_key.strip()}"
    return url, headers, native


def chat_generation_options(url: str, max_tokens: int) -> Dict[str, Any]:
    from urllib.parse import urlparse

    if urlparse(url).hostname == "api.openai.com":
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens, "temperature": 0.1}


def check_cloud_health(
    provider_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify that the selected model can handle a minimal chat completion."""
    cloud = load_llm_config()["cloud"]
    provider = provider_name or cloud["provider"]
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["custom"])
    same_provider = provider == cloud["provider"]
    url = (base_url or (cloud["base_url"] if same_provider else preset["base_url"])).strip().rstrip("/")
    model_name = model or (cloud.get("model") if same_provider else preset["default_model"])
    same_endpoint = provider == cloud["provider"] and url == cloud["base_url"].rstrip("/")
    key = (api_key or "").strip()
    if not key or "••••" in key:
        key = cloud.get("api_key", "") if same_endpoint else ""
    if not key or not model_name:
        return {"status": "missing_settings", "available": False, "message": "أدخل مفتاح المزود واسم النموذج."}

    started = time.perf_counter()
    result = {"provider": provider, "model": model_name, "available": False}
    try:
        endpoint, headers, native = chat_request_target(url, key)
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": "Reply with OK."}],
            **chat_generation_options(endpoint, 64),
        }
        if not native:
            payload["tools"] = [{"type": "function", "function": {
                "name": "connection_probe",
                "description": "Optional connection check",
                "parameters": {"type": "object", "properties": {}},
            }}]
            payload["tool_choice"] = "auto"
        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
        message = (data.get("choices") or [{}])[0].get("message") or {}
        has_reply = any(block.get("type") == "text" and block.get("text") for block in data.get("content", [])) if native else bool(message.get("content") or message.get("tool_calls"))
        if not has_reply:
            return {**result, "status": "empty_response", "message": "لم يُرجع النموذج استجابة محادثة."}
        return {**result, "status": "online", "available": True, "latency_ms": round((time.perf_counter() - started) * 1000)}
    except urllib.error.HTTPError as error:
        status = "invalid_key" if error.code in (401, 403) else "http_error"
        if error.code == 404 and provider == "gemini":
            return {**result, "status": "not_found", "message": (
                f"تعذّر العثور على نموذج {model_name} في رابط Gemini المحدد (404). "
                "اختر Google Gemini واستخدم رابط المزود الافتراضي واسم نموذج متاح لمشروعك في Google AI Studio."
            )}
        return {**result, "status": status, "message": cloud_failure_message(error)}
    except (OSError, ValueError, TypeError, AttributeError) as error:
        return {**result, "status": "probe_error", "message": cloud_failure_message(error)}


def cloud_failure_message(error: Exception) -> str:
    if isinstance(error, urllib.error.HTTPError):
        if error.code in (401, 403):
            return f"رفض المزود المصادقة أو صلاحية استخدام النموذج (HTTP {error.code})."
        if error.code == 429:
            return "رفض المزود الطلب بسبب حد الاستخدام أو الرصيد (HTTP 429)."
        if error.code in (502, 503, 504):
            return f"خدمة المزود غير متاحة مؤقتًا (HTTP {error.code}). أعد المحاولة بعد قليل أو اختر نموذجًا آخر."
        return f"رفض المزود طلب المحادثة للنموذج المحدد (HTTP {error.code})."
    return "تعذر الاتصال بالنموذج السحابي. تحقق من الرابط والنموذج."


def test_provider_connection(target: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """اختبار عام للاتصال بناءً على الهدف (local أو cloud)"""
    payload = payload or {}
    if target == "local":
        base_url = payload.get("base_url")
        return check_local_health(base_url, auto_start=False, model=payload.get("model"))
    elif target == "cloud":
        provider_name = payload.get("provider")
        base_url = payload.get("base_url")
        api_key = payload.get("api_key")
        return check_cloud_health(provider_name, base_url, api_key, payload.get("model"))
    else:
        return {"status": "error", "message": f"الهدف غير معروف: {target}"}
