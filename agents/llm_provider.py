"""
LLM Provider Manager - إدارة مزودي النماذج اللغوية
====================================================
يدعم:
- Ollama (محلي/مجاني) 
- Fallback (rule-based)
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("llm_provider")


class LLMProvider:
    """مدير موحد لمزودي LLM"""
    
    def __init__(
        self,
        provider: str = "auto",  # auto, ollama, fallback
        model: Optional[str] = None,
    ):
        self.provider = self._detect_provider(provider)
        self.model = model or self._get_default_model()
        logger.info(f"LLM Provider initialized: {self.provider} with model {self.model}")
    
    def _detect_provider(self, provider: str) -> str:
        """اكتشاف المزود المتاح"""
        if provider != "auto":
            return provider
        
        # أولوية: Ollama > Fallback (مجاناً فقط)
        
        # التحقق من Ollama محلياً
        try:
            import httpx
            response = httpx.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                logger.info("Ollama detected locally")
                return "ollama"
        except Exception:
            pass
        
        logger.warning("No LLM provider available, using fallback")
        return "fallback"
    
    def _get_default_model(self) -> str:
        """الحصول على النموذج الافتراضي"""
        if self.provider == "ollama":
            return os.environ.get("LLM_MODEL", "qwen2.5:7b")
        else:
            return "fallback-rule-based"
    
    def call(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """استدعاء موحد للنماذج"""
        
        if self.provider == "ollama":
            return self._call_ollama(messages, tools, temperature)
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
            
            # استخدام Chat Completions API المتوافق مع OpenAI
            url = "http://localhost:11434/v1/chat/completions"
            
            payload = {
                "model": self.model,
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
            with urllib.request.urlopen(req, timeout=120) as response:
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
            # إضافة معلومات مفيدة للمستخدم باللغة العربية
            error_msg = f"لم أستطع الاتصال بخادم Ollama المحلي.\n\nالرجاء التأكد من:\n• تشغيل Ollama: ollama serve\n• وجود النموذج: ollama pull {self.model}\n\nالخطأ التقني: {e}"
            return {
                "content": error_msg,
                "tool_calls": None,
                "provider": "ollama_error",
            }

    
    # ═══════════════════════════════════════════════════════════════
    # Fallback Implementation
    # ═══════════════════════════════════════════════════════════════
    
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
