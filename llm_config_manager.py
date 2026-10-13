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
        "model": "qwen3.5:0.8b",
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

    env_cloud_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if env_cloud_key and not config["cloud"].get("api_key"):
        config["cloud"]["api_key"] = env_cloud_key

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
        if "provider" in cld and str(cld["provider"]).strip():
            current["cloud"]["provider"] = str(cld["provider"]).strip()
        if "base_url" in cld and str(cld["base_url"]).strip():
            current["cloud"]["base_url"] = str(cld["base_url"]).strip()
        if "model" in cld and str(cld["model"]).strip():
            current["cloud"]["model"] = str(cld["model"]).strip()
        if "timeout" in cld and isinstance(cld["timeout"], (int, float)):
            current["cloud"]["timeout"] = int(cld["timeout"])

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

    # تحديث متغيرات البيئة المحلية لمزامنة العمليات الفورية
    if current["cloud"].get("api_key"):
        os.environ["OPENROUTER_API_KEY"] = current["cloud"]["api_key"]
        os.environ["LLM_API_KEY"] = current["cloud"]["api_key"]

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
            "model": config["local"].get("model", "qwen3.5:0.8b"),
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


def check_local_health(base_url: Optional[str] = None) -> Dict[str, Any]:
    """فحص صحة اتصال خادم Ollama المحلي"""
    url = base_url or load_llm_config()["local"].get("base_url", "http://localhost:11434/v1")
    parsed = urllib.parse.urlparse(url)
    clean_base = f"{parsed.scheme}://{parsed.netloc}"
    tags_url = f"{clean_base}/api/tags"

    start_t = time.time()
    try:
        req = urllib.request.Request(tags_url, headers={"User-Agent": "OdooHRAgents/1.0"})
        with urllib.request.urlopen(req, timeout=4) as res:
            latency_ms = int((time.time() - start_t) * 1000)
            if res.status == 200:
                data = json.loads(res.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "status": "online",
                    "available": True,
                    "latency_ms": latency_ms,
                    "models": models,
                    "message": f"الخادم المحلي متصل بنجاح ({latency_ms}ms) - تم العثور على {len(models)} نماذج",
                }
    except Exception as exc:
        latency_ms = int((time.time() - start_t) * 1000)
        return {
            "status": "offline",
            "available": False,
            "latency_ms": latency_ms,
            "models": [],
            "message": f"تعذر الاتصال بـ Ollama محلياً ({exc}). تأكد من تشغيل `ollama serve`.",
        }

    return {"status": "offline", "available": False, "message": "غير متاح"}


def check_cloud_health(
    provider_name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """فحص صحة اتصال المشغل السحابي مع مفتاح الـ API"""
    config = load_llm_config()
    p_name = provider_name or config["cloud"].get("provider", "openrouter")
    url = base_url or config["cloud"].get("base_url") or "https://openrouter.ai/api/v1"
    key = api_key if api_key is not None else config["cloud"].get("api_key", "")

    if not key or not str(key).strip():
        return {
            "status": "missing_key",
            "available": False,
            "message": "لم يتم إدخال مفتاح API Key لهذا المشغل السحابي بعد.",
        }

    # اختبار نقطة النهاية المناسبة للتحقق من صلاحية المفتاح
    clean_url = url.rstrip("/")
    if "openrouter" in p_name.lower() or "openrouter.ai" in clean_url:
        test_url = "https://openrouter.ai/api/v1/auth/key"
    else:
        test_url = f"{clean_url}/models"


    headers = {
        "Authorization": f"Bearer {key.strip()}",
        "User-Agent": "OdooHRAgents/1.0",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Odoo HR Agents",
    }

    start_t = time.time()
    try:
        req = urllib.request.Request(test_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as res:
            latency_ms = int((time.time() - start_t) * 1000)
            if res.status in (200, 201):
                return {
                    "status": "online",
                    "available": True,
                    "latency_ms": latency_ms,
                    "message": f"الاتصال بالمشغل السحابي ناجح ومفتاح الـ API صالح ({latency_ms}ms).",
                }
    except urllib.error.HTTPError as h_err:
        latency_ms = int((time.time() - start_t) * 1000)
        if h_err.code in (401, 403):
            return {
                "status": "invalid_key",
                "available": False,
                "latency_ms": latency_ms,
                "message": f"مفتاح API غير صالح أو غير مصرح له (رمز الخطأ: {h_err.code}).",
            }
        elif h_err.code == 429:
            return {
                "status": "rate_limited",
                "available": False,
                "latency_ms": latency_ms,
                "message": "تم تجاوز حد الطلبات المسموح به (Rate Limit - 429).",
            }
        else:
            return {
                "status": "http_error",
                "available": False,
                "latency_ms": latency_ms,
                "message": f"استجاب الخادم السحابي بالرمز {h_err.code}: {h_err.reason}",
            }
    except Exception as exc:
        latency_ms = int((time.time() - start_t) * 1000)
        return {
            "status": "network_error",
            "available": False,
            "latency_ms": latency_ms,
            "message": f"خطأ شبكة أثناء فحص المشغل السحابي: {exc}",
        }

    return {"status": "unknown", "available": False, "message": "حالة غير محددة"}


def test_provider_connection(target: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """اختبار عام للاتصال بناءً على الهدف (local أو cloud)"""
    payload = payload or {}
    if target == "local":
        base_url = payload.get("base_url")
        return check_local_health(base_url)
    elif target == "cloud":
        provider_name = payload.get("provider")
        base_url = payload.get("base_url")
        api_key = payload.get("api_key")
        # إذا كان المفتاح مرسلاً كقناع ولم يتغير، نجلب المفتاح الفعلي من التخزين
        if api_key and ("••••" in api_key):
            api_key = load_llm_config()["cloud"].get("api_key")
        return check_cloud_health(provider_name, base_url, api_key)
    else:
        return {"status": "error", "message": f"الهدف غير معروف: {target}"}
