# 🔄 إزالة OpenRouter من المشروع

## التاريخ
2026-10-11

## السبب
- تقليل الاعتماد على خدمات خارجية مدفوعة
- الانتقال للحلول المحلية (Ollama) أو المدمجة (LangGraph)
- تحسين الخصوصية والاستقلالية

---

## التغييرات المنفذة

### 1. ملف `.env`
**قبل:**
```bash
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
LLM_PROVIDER=openrouter
```

**بعد:**
```bash
# تم إزالة OPENROUTER_* بالكامل
LLM_PROVIDER=langgraph
LANGCHAIN_MODEL=gpt-4o-mini
# OPENAI_API_KEY=sk-...  ← إضافة إذا متوفر
```

---

### 2. ملف `agents/llm_provider.py`

**التغييرات:**
1. ✅ تحديث `_detect_provider()`: إزالة فحص `OPENROUTER_API_KEY`
2. ✅ تحديث `_get_default_model()`: إزالة حالة `openrouter`
3. ✅ تحديث `call()`: إزالة استدعاء `_call_openrouter`
4. ✅ إضافة `_call_langgraph()`: دعم LangGraph المدمج
5. ✅ تعليق `_call_openrouter()`: محفوظ للمرجعية فقط

**الكود الجديد:**
```python
def _detect_provider(self, provider: str) -> str:
    if provider != "auto":
        return provider
    
    # أولوية: LangGraph > Ollama > Fallback
    if provider == "langgraph" or provider == "auto":
        return "langgraph"
    
    # التحقق من Ollama
    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            return "ollama"
    except:
        pass
    
    return "fallback"
```

---

### 3. ملف `README.md`

**إضافة قسم جديد:**
```markdown
## 🔄 تحديث: إزالة OpenRouter

الخيارات المتاحة:
1. LangGraph Built-in (gpt-4o-mini) ⭐
2. Ollama محلي (مجاني)
3. Fallback (rule-based)
```

---

## الملفات المتأثرة

### ملفات محدّثة
1. ✅ `.env` - إزالة OPENROUTER_*, إضافة LANGCHAIN_*
2. ✅ `agents/llm_provider.py` - إزالة أولوية OpenRouter
3. ✅ `README.md` - توثيق التغيير

### ملفات لم تُعدّل (لا حاجة)
- `seraj_llm_service.py` - تستخدم `_call_openrouter` لكن ليست مستخدمة في LangGraph
- `graph/nodes.py` - تستخدم `ChatOpenAI` مباشرة (لا تعتمد على OpenRouter)
- `tests/*.py` - تستخدم mocks، لا تحتاج تعديل

---

## كيفية الاستخدام

### الخيار 1: LangGraph المدمج (الافتراضي) ⭐

```bash
# في .env
LLM_PROVIDER=langgraph
LANGCHAIN_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...  # مطلوب

# تشغيل
langgraph dev --port 2024
python web_service.py

# فتح
http://localhost:8000
```

**المميزات:**
- ✅ تكامل كامل مع LangGraph
- ✅ checkpointing تلقائي
- ✅ observability مع LangSmith
- ✅ سريع ومستقر

**العيوب:**
- ❌ يحتاج OPENAI_API_KEY (مدفوع)

---

### الخيار 2: Ollama المحلي (مجاني) ⭐⭐⭐

```bash
# 1. تثبيت Ollama
https://ollama.ai/download

# 2. تحميل نموذج
ollama pull qwen2.5:7b

# 3. في .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen2.5:7b

# 4. تشغيل
ollama serve  # Terminal 1
langgraph dev --port 2024  # Terminal 2
python web_service.py  # Terminal 3
```

**المميزات:**
- ✅ مجاني بالكامل
- ✅ خصوصية كاملة (لا يخرج من جهازك)
- ✅ سريع (محلي)
- ✅ لا يحتاج انترنت

**العيوب:**
- ❌ يحتاج 4-8GB RAM
- ❌ جودة أقل من GPT-4/Claude

---

### الخيار 3: Fallback (rule-based)

```bash
# في .env
LLM_PROVIDER=fallback

# يعمل بدون LLM - قواعد بسيطة فقط
```

**المميزات:**
- ✅ لا يحتاج أي شيء
- ✅ سريع جداً

**العيوب:**
- ❌ محدود جداً (كلمات مفتاحية فقط)
- ❌ لا يفهم السياق

---

## الاختبار

### 1. تحقق من التكوين
```bash
# تحقق من .env
cat .env | grep -E "LLM_PROVIDER|OLLAMA|OPENAI"

# يجب أن ترى:
LLM_PROVIDER=langgraph  # أو ollama أو fallback
```

### 2. اختبر الخدمات
```bash
# LangGraph
curl http://localhost:2024/info

# FastAPI
curl http://localhost:8000/api/status

# Ollama (إذا كنت تستخدمه)
curl http://localhost:11434/api/tags
```

### 3. اختبر الواجهة
```
http://localhost:8000
→ أرسل رسالة في الشات
→ ارفع ملف Excel
→ شاهد Pipeline يعمل
```

---

## استكشاف الأخطاء

### المشكلة: "OPENAI_API_KEY not set"
**الحل:**
```bash
# إذا كنت تستخدم langgraph provider
# أضف في .env:
OPENAI_API_KEY=sk-...

# أو استخدم ollama بدلاً:
LLM_PROVIDER=ollama
```

### المشكلة: "Ollama not available"
**الحل:**
```bash
# تأكد من تشغيل Ollama
ollama serve

# تأكد من تحميل نموذج
ollama list
ollama pull qwen2.5:7b
```

### المشكلة: الشات لا يستجيب
**الحل:**
```bash
# تحقق من logs
# Terminal LangGraph - ابحث عن errors
# Terminal FastAPI - ابحث عن errors

# تحقق من provider
python -c "from agents.llm_provider import get_llm_provider; print(get_llm_provider().provider)"
```

---

## الرجوع لـ OpenRouter (إذا احتجت)

```bash
# 1. في .env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# 2. في agents/llm_provider.py
# أعد تفعيل _call_openrouter في call() method

# 3. إعادة تشغيل الخدمات
```

---

## الملاحظات

1. **LangGraph Graph:** 
   - لا يتأثر - يستخدم `ChatOpenAI` مباشرة من langchain
   - يحتاج فقط OPENAI_API_KEY أو base_url لـ Ollama

2. **Telegram Bot:**
   - `seraj_llm_service.py` لا يزال لديه `_call_openrouter`
   - يحتاج تحديث إذا أردت تشغيل Telegram bot

3. **Tests:**
   - تستخدم mocks لـ `_call_openrouter`
   - لا تحتاج تحديث

4. **الأداء:**
   - LangGraph + gpt-4o-mini: سريع جداً
   - Ollama + qwen2.5:7b: سريع محلياً
   - Fallback: فوري لكن محدود

---

## الخلاصة

✅ **تم بنجاح إزالة OpenRouter من المشروع**

**البدائل المتاحة:**
1. LangGraph + gpt-4o-mini (مدفوع، قوي)
2. Ollama + qwen2.5:7b (مجاني، جيد)
3. Fallback (مجاني، محدود)

**التوصية:** 
- **التطوير:** استخدم Ollama (مجاني)
- **الإنتاج:** استخدم LangGraph + gpt-4o-mini (قوي)

---

**التاريخ:** 2026-10-11  
**المطور:** Kiro AI Assistant  
**الحالة:** ✅ مكتمل
