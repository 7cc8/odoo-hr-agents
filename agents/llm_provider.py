"""
LLM Provider Manager - إدارة مزودي النماذج اللغوية
====================================================
يدعم:
- OpenRouter (مدفوع)
- Ollama (مجاني/محلي)
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
        provider: str = "auto",  # auto, openrouter, ollama, fallback
        model: Optional[str] = None,
    ):
        self.provider = self._detect_provider(provider)
        self.model = model or self._get_default_model()
        logger.info(f"LLM Provider initialized: {self.provider} with model {self.model}")
    
    def _detect_provider(self, provider: str) -> str:
        """اكتشاف المزود المتاح"""
        if provider != "auto":
            return provider
        
        # أولوية: OpenRouter > Ollama > Fallback
        if os.environ.get("OPENROUTER_API_KEY"):
            return "openrouter"
        
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
        if self.provider == "openrouter":
            return os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
        elif self.provider == "ollama":
            return os.environ.get("OLLAMA_MODEL", "llama3.2")  # 3B model سريع
        else:
            return "fallback-rule-based"
    
    def call(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """استدعاء موحد للنماذج"""
        
        if self.provider == "openrouter":
            return self._call_openrouter(messages, tools, temperature)
        elif self.provider == "ollama":
            return self._call_ollama(messages, tools, temperature)
        else:
            return self._call_fallback(messages)
    
    # ═══════════════════════════════════════════════════════════════
    # OpenRouter Implementation
    # ═══════════════════════════════════════════════════════════════
    
    def _call_openrouter(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]],
        temperature: float,
    ) -> Dict[str, Any]:
        """استدعاء OpenRouter API"""
        import urllib.request
        import urllib.error
        
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            logger.warning("OPENROUTER_API_KEY not set, falling back")
            return self._call_fallback(messages)
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.environ.get("APP_URL", "https://github.com/your-repo"),
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                if result.get("choices"):
                    message = result["choices"][0].get("message", {})
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": message.get("tool_calls"),
                        "provider": "openrouter",
                    }
        
        except urllib.error.HTTPError as e:
            if e.code == 402:
                logger.error("OpenRouter: Payment required (402)")
            else:
                logger.error(f"OpenRouter HTTP error {e.code}: {e.reason}")
        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
        
        # Fallback
        logger.warning("OpenRouter failed, using fallback")
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
        """استدعاء Ollama محلياً"""
        try:
            import httpx
            
            # تحويل الرسائل لصيغة Ollama
            prompt = self._messages_to_prompt(messages)
            
            url = "http://localhost:11434/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "temperature": temperature,
                "stream": False,
            }
            
            response = httpx.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            content = result.get("response", "")
            
            # محاولة استخراج JSON من النص
            # Ollama لا يدعم tool calling مباشرة، نحتاج parsing
            return {
                "content": content,
                "tool_calls": None,  # نحتاج parsing يدوي
                "provider": "ollama",
            }
        
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return self._call_fallback(messages)
    
    def _messages_to_prompt(self, messages: List[Dict[str, Any]]) -> str:
        """تحويل messages لـ prompt واحد"""
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                parts.append(f"System: {content}")
            elif role == "user":
                parts.append(f"User: {content}")
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
        
        parts.append("Assistant:")  # للحصول على الرد
        return "\n\n".join(parts)
    
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
        
        # تصنيف بسيط بالكلمات المفتاحية
        operation = "search"
        model = "hr.employee"
        domain = []
        fields = ["name", "job_id", "department_id"]
        limit = 10
        
        # اكتشاف نوع العملية
        if any(kw in user_query for kw in ["كم", "عدد", "count", "how many"]):
            operation = "count"
            fields = None
        
        # اكتشاف النموذج
        if any(kw in user_query for kw in ["موظف", "موظفين", "employee"]):
            model = "hr.employee"
        elif any(kw in user_query for kw in ["قسم", "أقسام", "department"]):
            model = "hr.department"
        elif any(kw in user_query for kw in ["وظيفة", "وظائف", "job"]):
            model = "hr.job"
        elif any(kw in user_query for kw in ["شركة", "منشأة", "company"]):
            model = "res.company"
        
        # اكتشاف filters بسيطة
        if any(kw in user_query for kw in ["تقنية", "تكنولوجيا", "tech", "it"]):
            if model == "hr.employee":
                domain = [("department_id.name", "ilike", "IT")]
            elif model == "hr.department":
                domain = [("name", "ilike", "IT")]
        
        response = {
            "operation": operation,
            "model": model,
            "domain": domain,
            "fields": fields,
            "limit": limit,
            "reasoning": "Rule-based fallback: LLM unavailable",
        }
        
        return {
            "content": json.dumps(response, ensure_ascii=False),
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
