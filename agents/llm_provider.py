"""
LLM Provider Manager - إدارة مزودي النماذج اللغوية
====================================================
يدعم:
- Ollama (محلي/مجاني)
- Cloud AI (OpenRouter, OpenAI, Groq, DeepSeek, Custom API Key)
- التبديل التلقائي الذكي (Auto Switching)
- Fallback (rule-based)
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("llm_provider")


class LLMProvider:
    """مدير موحد لمزودي LLM (محلي، سحابي، تلقائي، وتراجعي)"""
    
    def __init__(
        self,
        provider: str = "auto",  # auto, ollama, cloud, fallback
        model: Optional[str] = None,
    ):
        try:
            from llm_config_manager import load_llm_config
            self.config = load_llm_config()
        except Exception:
            self.config = {}

        self.provider = self._detect_provider(provider)
        self.model = model or self._get_default_model()
        logger.info(f"LLM Provider initialized: {self.provider} with model {self.model}")
    
    def _detect_provider(self, provider: str) -> str:
        """اكتشاف المزود المتاح بناءً على الإعدادات أو الكشف التلقائي"""
        if provider not in ("auto", None):
            return provider

        mode = self.config.get("mode", "auto")
        active = self.config.get("active_provider", "local")

        # إذا كان الوضع يدوياً: نتقيد بالمشغل النشط
        if mode == "manual":
            if active == "cloud" and bool(self.config.get("cloud", {}).get("api_key")):
                return "cloud"
            elif active == "local":
                return "ollama"

        # وضع التبديل التلقائي (Auto):
        # 1. إذا كان المشغل النشط سحابياً وله مفتاح، أو كان مفتاح الـ API متوفراً
        cloud_key = self.config.get("cloud", {}).get("api_key") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
        if active == "cloud" and cloud_key:
            return "cloud"

        # 2. فحص Ollama محلياً
        try:
            import urllib.request
            local_url = self.config.get("local", {}).get("base_url", "http://localhost:11434/v1")
            clean_url = local_url.replace('/v1', '').rstrip('/') + '/api/tags'
            req = urllib.request.Request(clean_url, headers={"User-Agent": "OdooHRAgents/1.0"})
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    logger.info("Ollama detected locally")
                    return "ollama"
        except Exception:
            pass

        # 3. إذا لم يتوفر المحلي ولكن يوجد مفتاح سحابي
        if cloud_key:
            logger.info("Cloud API key available, using cloud provider")
            return "cloud"
        
        logger.warning("No LLM provider available, using fallback")
        return "fallback"
    
    def _get_default_model(self) -> str:
        """الحصول على النموذج الافتراضي للمزود النشط"""
        if self.provider == "cloud":
            return self.config.get("cloud", {}).get("model") or os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
        elif self.provider == "ollama":
            return self.config.get("local", {}).get("model") or os.environ.get("LLM_MODEL", "qwen3.5:9b")
        else:
            return "fallback-rule-based"
    
    def call(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """استدعاء موحد للنماذج مع التبديل التلقائي الفوري من السحابي للمحلي عند عدم الاستجابة"""
        # تحديث الإعدادات ديناميكياً لضمان قراءة أي تغيير من لوحة الإعدادات فوراً
        from llm_config_manager import load_llm_config
        self.config = load_llm_config()
        mode = self.config.get("mode", "auto")
        active = self.config.get("active_provider", "local")
        fallback_enabled = self.config.get("fallback_enabled", True)

        # 1. إذا كان المشغل النشط هو الذكاء الاصطناعي السحابي:
        if active == "cloud":
            res = self._call_cloud(messages, tools, temperature)
            if res.get("provider") == "cloud" and (res.get("content") or res.get("tool_calls")):
                return res

            # التبديل التلقائي: إذا لم يستجب المشغل السحابي أو تعطل، التحول فوراً للمحرك المحلي
            if mode == "auto" and fallback_enabled:
                logger.warning("Cloud AI provider failed or did not respond. Automatically falling back to local Ollama engine so agents keep running...")
                local_res = self._call_ollama(messages, tools, temperature)
                if local_res and local_res.get("provider") == "ollama" and (local_res.get("content") or local_res.get("tool_calls")):
                    return local_res
                logger.warning("Local Ollama also unavailable. Falling back to safety rule-based response...")

            return self._call_fallback(messages)

        # 2. إذا كان المشغل النشط هو المحرك المحلي:
        elif active == "local":
            res = self._call_ollama(messages, tools, temperature)
            if res and res.get("provider") == "ollama" and (res.get("content") or res.get("tool_calls")):
                return res

            # التبديل التلقائي إذا تعثر المحلي وتوفر مفتاح سحابي:
            cloud_key = self.config.get("cloud", {}).get("api_key") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
            if cloud_key and mode == "auto" and fallback_enabled:
                logger.warning("Local Ollama unavailable. Automatically switching to Cloud AI provider fallback...")
                cloud_res = self._call_cloud(messages, tools, temperature)
                if cloud_res.get("provider") == "cloud" and (cloud_res.get("content") or cloud_res.get("tool_calls")):
                    return cloud_res

            logger.warning("No live LLM engine responded. Falling back to safety rule-based response...")
            return self._call_fallback(messages)

        else:
            return self._call_fallback(messages)
    
    # ═══════════════════════════════════════════════════════════════
    # Ollama Implementation
    # ═══════════════════════════════════════════════════════════════
    
    def _call_ollama(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
    ) -> Dict[str, Any]:
        """استدعاء Ollama محلياً عبر Chat Completions API"""
        try:
            import urllib.request
            import urllib.error
            
            loc_cfg = self.config.get("local", {})
            base_url = loc_cfg.get("base_url") or "http://localhost:11434/v1"
            local_model = loc_cfg.get("model") or "qwen3.5:9b"
            timeout = int(loc_cfg.get("timeout", 60))

            clean_url = base_url.rstrip("/")
            if not clean_url.endswith("/chat/completions"):
                url = f"{clean_url}/chat/completions"
            else:
                url = clean_url
            
            payload = {
                "model": local_model,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
                "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "1024")),
            }
            if local_model.startswith("qwen3.5"):
                payload["reasoning_effort"] = "none"
            
            # إضافة الأدوات إذا كانت متاحة
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            
            data = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
            }
            
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                
                if result.get("choices"):
                    message = result["choices"][0].get("message", {})
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": message.get("tool_calls"),
                        "provider": "ollama",
                    }
        
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            error_msg = f"لم أستطع الاتصال بخادم Ollama المحلي.\n\nالرجاء التأكد من:\n• تشغيل Ollama: ollama serve\n• وجود النموذج: ollama pull {self.config.get('local', {}).get('model', 'qwen3.5:9b')}\n\nالخطأ التقني: {e}"
            return {
                "content": error_msg,
                "tool_calls": None,
                "provider": "ollama_error",
            }

    # ═══════════════════════════════════════════════════════════════
    # Cloud Implementation (OpenRouter, OpenAI, Groq, DeepSeek, Custom)
    # ═══════════════════════════════════════════════════════════════

    def _call_cloud(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
    ) -> Dict[str, Any]:
        """استدعاء المشغل السحابي مع دعم أي مشغل متوافق ومفتاح API"""
        try:
            import urllib.request
            import urllib.error

            cloud_cfg = self.config.get("cloud", {})
            base_url = cloud_cfg.get("base_url") or "https://openrouter.ai/api/v1"
            api_key = cloud_cfg.get("api_key") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
            cloud_model = cloud_cfg.get("model") or "openrouter/auto"
            timeout = int(cloud_cfg.get("timeout", 45))

            if not api_key:
                return {
                    "content": "⚠️ لم يتم تكوين مفتاح API Key للمشغل السحابي. يرجى إضافته من صفحة الإعدادات.",
                    "tool_calls": None,
                    "provider": "cloud_error",
                }

            clean_url = base_url.rstrip("/")
            if not clean_url.endswith("/chat/completions"):
                url = f"{clean_url}/chat/completions"
            else:
                url = clean_url

            payload = {
                "model": cloud_model,
                "messages": messages,
                "temperature": temperature,
                "stream": False,
                "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "1024")),
            }
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key.strip()}",
                "User-Agent": "OdooHRAgents/1.0",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Odoo HR Agents",
            }

            deadline = time.monotonic() + timeout
            for _ in range(2):
                remaining = deadline - time.monotonic()
                if remaining <= 1:
                    break
                req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
                with urllib.request.urlopen(req, timeout=remaining) as response:
                    result = json.load(response)
                choice = (result.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                if message.get("content") or message.get("tool_calls"):
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": message.get("tool_calls"),
                        "provider": "cloud",
                    }
                if choice.get("finish_reason") != "length" or payload["max_tokens"] >= 4096:
                    break
                payload["max_tokens"] = min(payload["max_tokens"] * 2, 4096)
        except Exception as e:
            logger.error(f"Cloud provider error: {e}")
            return {
                "content": f"واجه المشغل السحابي خطأ: {e}",
                "tool_calls": None,
                "provider": "cloud_error",
            }

        return {
            "content": "استجابة غير متوقعة من المشغل السحابي",
            "tool_calls": None,
            "provider": "cloud_error",
        }
    
    def _call_fallback(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Report an unavailable model to the caller."""
        return {"content": "", "tool_calls": None, "provider": "fallback"}


# ═══════════════════════════════════════════════════════════════
# Singleton Instance
# ═══════════════════════════════════════════════════════════════

_provider_instance: Optional[LLMProvider] = None


def get_llm_provider() -> LLMProvider:
    """الحصول على مزود LLM المُكوّن"""
    global _provider_instance
    if _provider_instance is None:
        provider_type = os.environ.get("LLM_PROVIDER", "auto")
        _provider_instance = LLMProvider(provider=provider_type)
    return _provider_instance


def set_llm_provider(provider: str, model: Optional[str] = None) -> None:
    """تعيين مزود LLM يدوياً"""
    global _provider_instance
    _provider_instance = LLMProvider(provider=provider, model=model)
