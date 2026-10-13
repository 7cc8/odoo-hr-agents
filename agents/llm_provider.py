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
            return self.config.get("local", {}).get("model") or os.environ.get("LLM_MODEL", "qwen3.5:0.8b")
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
            if res.get("provider") == "cloud" and not res.get("provider", "").endswith("_error"):
                return res

            # التبديل التلقائي: إذا لم يستجب المشغل السحابي أو تعطل، التحول فوراً للمحرك المحلي
            if mode == "auto" or fallback_enabled:
                logger.warning("Cloud AI provider failed or did not respond. Automatically falling back to local Ollama engine so agents keep running...")
                local_res = self._call_ollama(messages, tools, temperature)
                if local_res.get("provider") == "ollama" and not local_res.get("provider", "").endswith("_error"):
                    return local_res
                logger.warning("Local Ollama also unavailable. Falling back to safety rule-based response...")

            return self._call_fallback(messages)

        # 2. إذا كان المشغل النشط هو المحرك المحلي:
        elif active == "local":
            res = self._call_ollama(messages, tools, temperature)
            if res.get("provider") == "ollama" and not res.get("provider", "").endswith("_error"):
                return res

            # التبديل التلقائي إذا تعثر المحلي وتوفر مفتاح سحابي:
            cloud_key = self.config.get("cloud", {}).get("api_key") or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("LLM_API_KEY")
            if cloud_key and (mode == "auto" or fallback_enabled):
                logger.warning("Local Ollama unavailable. Automatically switching to Cloud AI provider fallback...")
                cloud_res = self._call_cloud(messages, tools, temperature)
                if cloud_res.get("provider") == "cloud" and not cloud_res.get("provider", "").endswith("_error"):
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
            local_model = loc_cfg.get("model") or "qwen3.5:0.8b"
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
            error_msg = f"لم أستطع الاتصال بخادم Ollama المحلي.\n\nالرجاء التأكد من:\n• تشغيل Ollama: ollama serve\n• وجود النموذج: ollama pull {self.config.get('local', {}).get('model', 'qwen3.5:0.8b')}\n\nالخطأ التقني: {e}"
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

            data = json.dumps(payload).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key.strip()}",
                "User-Agent": "OdooHRAgents/1.0",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "Odoo HR Agents",
            }

            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
                if result.get("choices"):
                    message = result["choices"][0].get("message", {})
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": message.get("tool_calls"),
                        "provider": "cloud",
                    }
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
        """Rule-based fallback عندما لا يتوفر LLM"""
        
        # استخراج آخر سؤال من المستخدم
        user_query = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_query = msg.get("content", "").lower()
                break
        
        logger.info(f"Fallback processing query: {user_query[:50]}...")
        
        # ردود بسيطة بناءً على كلمات مفتاحية
        if any(kw in user_query for kw in ["مرحب", "السلام", "هلا", "أهلا", "اهلا", "hello", "hi", "hey"]):
            response_text = "أهلاً وسهلاً! 👋 أنا سراج، مساعدك في إدارة الموارد البشرية.\n\n" \
                           "يمكنني مساعدتك في:\n" \
                           "• الاستفسار عن الموظفين 👥\n" \
                           "• عرض الأقسام 📁\n" \
                           "• معلومات الشركات 🏢\n" \
                           "• معالجة ملفات Excel 📊\n\n" \
                           "💬 جرّب أن تسأل: 'كم عدد الموظفين؟' أو 'مساعدة'"
        
        elif any(kw in user_query for kw in ["كم", "عدد", "count", "how many"]):
            if "موظف" in user_query or "employee" in user_query:
                response_text = "📊 لعرض عدد الموظفين، يحتاج النظام للاتصال بقاعدة بيانات Odoo.\n\n" \
                               "حالياً في وضع Fallback المحدود. للحصول على البيانات الفعلية:\n" \
                               "1. ثبّت Ollama (مجاني): https://ollama.ai\n" \
                               "2. أو أضف OPENAI_API_KEY في ملف .env"
            else:
                response_text = "أحتاج لمعرفة ماذا تريد أن تعد؟ (موظفين، أقسام، شركات؟)"
        
        elif any(kw in user_query for kw in ["قسم", "أقسام", "department"]):
            response_text = "📁 لعرض الأقسام، يحتاج النظام للاتصال بقاعدة بيانات Odoo.\n\n" \
                           "حالياً في وضع Fallback المحدود."
        
        elif any(kw in user_query for kw in ["شركة", "منشأة", "company"]):
            response_text = "🏢 لعرض الشركات، يحتاج النظام للاتصال بقاعدة بيانات Odoo.\n\n" \
                           "حالياً في وضع Fallback المحدود."
        
        elif any(kw in user_query for kw in ["help", "مساعدة", "ساعد", "إيش", "ايش", "شو", "وش"]):
            response_text = "🤖 **سراج - المساعد الذكي للموارد البشرية**\n\n" \
                           "**الوضع الحالي:** Fallback (محدود)\n\n" \
                           "**ما يمكنني فعله الآن:**\n" \
                           "• الرد على التحيات البسيطة\n" \
                           "• شرح كيفية تحسين النظام\n" \
                           "• إرشادات الاستخدام\n\n" \
                           "**🚀 للحصول على الوظائف الكاملة:**\n" \
                           "1. **Ollama (مجاني):** تحميل من ollama.ai\n" \
                           "2. **OpenAI API (مدفوع):** إضافة OPENAI_API_KEY\n\n" \
                           "بعدها ستحصل على:\n" \
                           "✅ استعلام حقيقي من Odoo\n" \
                           "✅ معالجة ملفات Excel\n" \
                           "✅ إجابات ذكية ومفصلة"
        
        else:
            # رد افتراضي ودود
            response_text = f"مرحباً! 👋 فهمت أنك تريد: '{user_query[:50]}'\n\n" \
                           "أعتذر، حالياً أعمل في **وضع Fallback المحدود** ولا أستطيع معالجة هذا الطلب بذكاء.\n\n" \
                           "🎯 **ما يمكنك فعله:**\n" \
                           "• جرّب كلمات بسيطة: 'مساعدة'، 'كم عدد الموظفين؟'\n" \
                           "• ارفع ملف Excel من الواجهة (يعمل بدون LLM)\n\n" \
                           "🚀 **لتفعيل الذكاء الكامل (اختياري):**\n\n" \
                           "**الطريقة الأسهل (مجاني):**\n" \
                           "```bash\n" \
                           "# تحميل Ollama من https://ollama.ai\n" \
                           "ollama pull qwen2.5:7b\n" \
                           "ollama serve\n" \
                           "```\n" \
                           "ثم في ملف `.env`: `LLM_PROVIDER=ollama`\n\n" \
                           "**أو استخدام OpenAI:**\n" \
                           "```bash\n" \
                           "LLM_PROVIDER=langgraph\n" \
                           "OPENAI_API_KEY=sk-...\n" \
                           "```\n\n" \
                           "💡 النظام يعمل أساساً - الـ LLM مجرد تحسين!"
        
        return {
            "content": response_text,
            "tool_calls": None,
            "provider": "fallback",
        }


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
