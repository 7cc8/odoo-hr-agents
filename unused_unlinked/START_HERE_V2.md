# 🚀 Agentic AI Framework - Quick Start Guide
## تحويل كامل لوكلاء Odoo HR الذكية

**آخر تحديث**: يناير 2025  
**الحالة**: ✅ المرحلة 1 مكتملة (~95%)  
**الإصدار**: v2.0-agentic

---

## 📋 جدول المحتويات

1. [نظرة عامة](#overview)
2. [ما الجديد](#whats-new)
3. [البدء السريع](#quick-start)
4. [خيارات LLM](#llm-options)
5. [الاختبار](#testing)
6. [أمثلة الاستخدام](#examples)
7. [حل المشاكل](#troubleshooting)

---

<a name="overview"></a>
## 🎯 نظرة عامة

تم تحويل المشروع من **Service-Based Architecture** إلى **True Agentic AI**:

### قبل التحويل ❌
```python
# مجرد تنفيذ tools بدون تفكير
def fahas_service(tool_name, args):
    return odoo.search_read(model, domain, fields)
```

### بعد التحويل ✅
```python
# وكيل ذكي كامل مع Goal → Plan → Execute → Reflect
class FahasAgent(BaseAgent):
    def perceive(goal, context):  # 🧠 فهم الهدف والسياق
    def plan(goal, perception):    # 📋 وضع خطة تنفيذية
    def execute(plan):             # ⚡ تنفيذ الخطة
    def reflect(goal, result):     # 🔍 مراجعة النتائج
```

---

<a name="whats-new"></a>
## 🆕 ما الجديد في v2.0

### ✅ تم إنجازه

| المكون | الوصف | الملف |
|--------|--------|------|
| **BaseAgent** | فئة أساسية لكل الوكلاء مع agentic loop | `agents/base_agent.py` |
| **ToolRegistry** | مدير مركزي للأدوات + permissions | `agents/tool_registry.py` |
| **LLM Provider** | دعم متعدد (OpenRouter/Ollama/Fallback) | `agents/llm_provider.py` |
| **FahasAgent** | أول وكيل ذكي كامل (query agent) | `agents/fahas_agent.py` |
| **LangGraph** | integration جاهز + routing logic | `graph/agentic_nodes.py` |
| **LangSmith** | observability مُفعّل | `.env` |
| **Testing** | integration tests شاملة | `test_integration.py` |

### 🔄 الوكلاء المتبقية (Phase 2)

- [ ] MuslehAgent (diagnostic)
- [ ] KatibAgent (write operations)
- [ ] HaresAgent (security/policies)
- [ ] MuwaffaqAgent (optimization)
- [ ] SijilAgent (logging)
- [ ] MudaqqiqAgent (validation)

---

<a name="quick-start"></a>
## ⚡ البدء السريع (3 دقائق)

### 1️⃣ اختر LLM Provider

لديك 3 خيارات:

#### Option A: OpenRouter (مدفوع، الأقوى) 💳
```env
# في .env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

#### Option B: Ollama (محلي، مجاني) 🆓
```powershell
# 1. تثبيت Ollama
# من https://ollama.com/download

# 2. تحميل نموذج
ollama pull llama3.2

# 3. تكوين
# في .env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```
📚 [دليل Ollama الكامل](OLLAMA_SETUP.md)

#### Option C: Auto (اكتشاف تلقائي) 🤖
```env
# في .env
LLM_PROVIDER=auto
# يختار تلقائياً: OpenRouter → Ollama → Fallback
```

---

### 2️⃣ تفعيل الوكيل الجديد

```env
# في .env
ENABLE_AGENTIC_FAHAS=1
```

---

### 3️⃣ اختبار

```powershell
# Integration test كامل
python test_integration.py

# أو اختبار FahasAgent مباشرة
python test_new_agents.py
```

---

<a name="llm-options"></a>
## 🤖 مقارنة LLM Providers

| Provider | Cost | Speed | Quality | Best For |
|----------|------|-------|---------|----------|
| **OpenRouter** | 💳 مدفوع | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | Production |
| **Ollama** | 🆓 مجاني | ⚡⚡ | ⭐⭐⭐⭐ | Development |
| **Fallback** | 🆓 مجاني | ⚡⚡⚡⚡ | ⭐⭐ | Testing |

### نماذج Ollama الموصى بها

```bash
# للتطوير السريع (3B - سريع جداً)
ollama pull llama3.2

# للإنتاج (8B - متوازن)
ollama pull llama3.1:8b

# للعربية (8B - دعم أفضل للعربية)
ollama pull aya:8b

# للكود (7B - متخصص)
ollama pull codellama
```

---

<a name="testing"></a>
## 🧪 الاختبار

### Test 1: Integration Test (موصى به)

```powershell
python test_integration.py
```

**ماذا يختبر:**
- ✅ Tool Registry (تسجيل الأدوات)
- ✅ LLM Provider (OpenRouter/Ollama/Fallback)
- ✅ BaseAgent framework
- ✅ FahasAgent (standalone)
- ✅ LangGraph integration

**النتيجة المتوقعة:**
```
✅ Tool Registry: PASSED (15 tools)
✅ LLM Provider: PASSED (ollama/llama3.2)
✅ FahasAgent: PASSED (5 records)
✅ LangGraph: PASSED
✅ Full Pipeline: SKIPPED (ENABLE_AGENTIC_FAHAS=0)

TOTAL: 4/5 tests passed
🎉 ALL TESTS PASSED! Framework ready.
```

---

### Test 2: FahasAgent Only

```powershell
python test_new_agents.py
```

**ماذا يختبر:**
- FahasAgent مع goal حقيقي
- اتصال Odoo
- Agentic loop كامل

---

### Test 3: Unit Tests

```powershell
pytest tests/test_agentic_agents.py -v
```

---

<a name="examples"></a>
## 💡 أمثلة الاستخدام

### مثال 1: استخدام FahasAgent مباشرة

```python
from agents.fahas_agent import FahasAgent, create_fahas_query_goal

# إنشاء هدف
goal = create_fahas_query_goal(
    "أعطني كل الموظفين في قسم IT",
    context={"company_id": 1}
)

# تشغيل الوكيل
fahas = FahasAgent()
result = fahas.run(goal)

# عرض النتائج
if result['status'] == 'success':
    data = result['result']['data']
    print(f"Found {len(data)} employees")
    for emp in data:
        print(f"  - {emp['name']}")
```

---

### مثال 2: استخدام BaseAgent لوكيل جديد

```python
from agents.base_agent import BaseAgent, AgentGoal, AgentPlan, AgentReflection

class MuslehAgent(BaseAgent):
    """وكيل التشخيص"""
    
    def __init__(self):
        super().__init__(
            name="Musleh",
            role="Diagnostic Agent",
        )
    
    def perceive(self, goal, context=None):
        """تحليل المشكلة"""
        return {
            "issue_type": "data_quality",
            "severity": "high",
        }
    
    def plan(self, goal, perception):
        """وضع خطة الحل"""
        plan = AgentPlan(plan_id="musleh-001")
        plan.add_step({"action": "identify_duplicates"})
        plan.add_step({"action": "suggest_merges"})
        return plan
    
    def execute(self, plan):
        """تنفيذ الخطة"""
        # ... implementation
        return {"fixed": 5, "remaining": 2}
    
    def reflect(self, goal, plan, result):
        """مراجعة النتائج"""
        return AgentReflection(
            success=True,
            confidence=0.95,
        )
```

---

### مثال 3: عبر LangGraph

```python
from graph.build_graph import build_graph
from langgraph.checkpoint.memory import MemorySaver

# بناء الـ graph
checkpointer = MemorySaver()
graph = build_graph(checkpointer=checkpointer)

# استدعاء
result = graph.invoke(
    {
        "messages": [
            {"role": "user", "content": "كم عدد الموظفين؟"}
        ],
    },
    config={"configurable": {"thread_id": "test-1"}}
)
```

---

<a name="troubleshooting"></a>
## 🔧 حل المشاكل

### مشكلة: "OpenRouter HTTP 402"

**السبب**: API key يحتاج رصيد

**الحل**:
```env
# استخدم Ollama مجاناً
LLM_PROVIDER=ollama
```

---

### مشكلة: "Ollama not found"

**الحل**:
```powershell
# 1. تثبيت Ollama
# من https://ollama.com/download

# 2. تشغيل الخادم
ollama serve

# 3. تحميل نموذج
ollama pull llama3.2
```

---

### مشكلة: "Tool not registered"

**الحل**:
```python
# تأكد من أن tool_registry.py يُحمّل عند الاستيراد
from agents.tool_registry import ToolRegistry
registry = ToolRegistry.get_instance()
print(len(registry.tools))  # يجب أن يكون > 0
```

---

### مشكلة: "ENABLE_AGENTIC_FAHAS has no effect"

**الحل**:
```powershell
# تأكد من إعادة تشغيل Python بعد تغيير .env
python test_integration.py  # fresh start
```

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────┐
│           User Input / LangGraph            │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              BaseAgent                       │
│  ┌─────────────────────────────────────┐   │
│  │ 1. Perceive (فهم الهدف)             │   │
│  │ 2. Plan (وضع خطة)                   │   │
│  │ 3. Execute (تنفيذ)  ◄──┐            │   │
│  │ 4. Reflect (مراجعة)    │            │   │
│  └─────────────────────────┼────────────┘   │
│                            │retry?          │
└────────────┬───────────────┴────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│           Tool Registry                      │
│  • search_hr_employees                       │
│  • count_hr_employees                        │
│  • get_company_info                          │
│  • ... 15+ tools                             │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│              Odoo API                        │
│  (via OdooReadonlyRepository)                │
└─────────────────────────────────────────────┘
```

---

## 🎯 Next Steps

### للمطورين:

1. ✅ **اختبر Framework**: `python test_integration.py`
2. ✅ **جرّب Ollama**: اتبع [OLLAMA_SETUP.md](OLLAMA_SETUP.md)
3. 🔲 **افحص Traces**: راجع `trace_log` في النتائج
4. 🔲 **ابني وكيل جديد**: انسخ `fahas_agent.py` كـ template

### لمدراء المشاريع:

1. ✅ **راجع Architecture**: الرسم أعلاه
2. ✅ **افهم Capabilities**: ما يمكن للوكيل فعله
3. 🔲 **حدد Priorities**: أي وكيل نبني بعد Fahas؟
4. 🔲 **خطط Phase 2**: Musleh → Hares → Katib

---

## 📚 الملفات المهمة

| الملف | الوصف |
|------|-------|
| `agents/base_agent.py` | الفئة الأساسية |
| `agents/fahas_agent.py` | مثال وكيل كامل |
| `agents/tool_registry.py` | مدير الأدوات |
| `agents/llm_provider.py` | مدير LLM |
| `test_integration.py` | اختبار شامل |
| `OLLAMA_SETUP.md` | دليل Ollama |
| `.env` | التكوين |

---

## 🤝 المساهمة

لإضافة وكيل جديد:

1. انسخ `agents/fahas_agent.py`
2. ورث من `BaseAgent`
3. طبّق الدوال الأربع: `perceive`, `plan`, `execute`, `reflect`
4. سجّل tools جديدة في `tool_registry.py`
5. أضف عقدة في `graph/agentic_nodes.py`
6. اختبر مع `test_integration.py`

---

## 📞 الدعم

- **الوثائق**: هذا الملف + `OLLAMA_SETUP.md`
- **الاختبارات**: `test_integration.py`
- **الأمثلة**: `test_new_agents.py`

---

**🎉 الآن أنت جاهز لاستخدام Agentic AI في Odoo HR!**

آخر تحديث: يناير 2025
