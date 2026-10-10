# 🤖 Odoo HR Agentic AI Framework
## تحويل كامل من Service-Based إلى True Agentic AI

[![Phase 1](https://img.shields.io/badge/Phase%201-Complete-success)](PHASE1_COMPLETE.md)
[![Tests](https://img.shields.io/badge/Tests-5%2F5%20Passing-success)](test_integration.py)
[![LLM](https://img.shields.io/badge/LLM-Multi--Provider-blue)](agents/llm_provider.py)
[![Framework](https://img.shields.io/badge/Framework-Production%20Ready-green)](agents/base_agent.py)

---

## 🎯 Overview

تم تحويل مشروع **Odoo HR Agents** من معمارية خدمية بسيطة إلى **Agentic AI Framework** كامل مع:

- 🧠 **Goal Understanding** - فهم الأهداف بالذكاء الاصطناعي
- 📋 **Dynamic Planning** - تخطيط ديناميكي
- ⚡ **Autonomous Execution** - تنفيذ مستقل
- 🔍 **Self-Reflection** - مراجعة ذاتية + retry logic
- 💾 **Memory System** - ذاكرة متقدمة (working + episodic + semantic)

---

## 🚀 Quick Start (1 دقيقة)

```powershell
# 1. Clone & setup
cd d:\mjrm0\Documents\odoo-hr-agents-2

# 2. تكوين LLM (اختر واحد):
# Option A: Ollama (free) - راجع OLLAMA_SETUP.md
# Option B: OpenRouter (paid) - أضف API key في .env
# Option C: Auto (يختار تلقائياً)

# 3. اختبر
python test_integration.py

# ✅ يجب أن ترى: 5/5 tests passed!
```

📚 **للدليل الكامل**: اقرأ [`START_HERE_V2.md`](START_HERE_V2.md)

---

## 📊 Before vs After

### ❌ قبل (Service-Based)
```python
def fahas_service(tool_name, args):
    """مجرد تنفيذ tool بدون تفكير"""
    return odoo.search_read(model, domain, fields)
```

**المشاكل**:
- لا goal understanding
- لا planning
- لا reflection
- hard-coded logic

---

### ✅ بعد (Agentic AI)
```python
class FahasAgent(BaseAgent):
    """وكيل ذكي كامل مع agentic loop"""
    
    def perceive(self, goal, context):
        """فهم الهدف والسياق"""
        # تحليل ذكي عبر LLM
        return perception
    
    def plan(self, goal, perception):
        """وضع خطة تنفيذية ديناميكية"""
        # خطة تتكيف مع الموقف
        return plan
    
    def execute(self, plan):
        """تنفيذ مع error handling"""
        # تنفيذ خطوة بخطوة
        return result
    
    def reflect(self, goal, plan, result):
        """مراجعة + إمكانية retry"""
        # تقييم ذاتي
        return reflection
```

**المميزات**:
- ✅ Goal understanding
- ✅ Dynamic planning
- ✅ Self-reflection
- ✅ Memory + context
- ✅ Extensible architecture

---

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│       User Input / LangGraph        │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│          BaseAgent                   │
│  ┌───────────────────────────────┐  │
│  │ PERCEIVE  (فهم)               │  │
│  │    ↓                          │  │
│  │ PLAN      (تخطيط)             │  │
│  │    ↓                          │  │
│  │ EXECUTE   (تنفيذ) ◄──┐        │  │
│  │    ↓                 │        │  │
│  │ REFLECT   (مراجعة)   │        │  │
│  └──────────────────────┼────────┘  │
│                         │ retry?    │
└────────────────┬────────┴───────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│         Tool Registry                │
│  • 6+ registered tools               │
│  • Permission checking               │
│  • Usage tracking                    │
└────────────────┬────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│            Odoo API                  │
└─────────────────────────────────────┘
```

---

## 🤖 LLM Provider Options

| Provider | Cost | Speed | Quality | Best For |
|----------|------|-------|---------|----------|
| **OpenRouter** | 💳 Paid | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ | Production |
| **Ollama** | 🆓 Free | ⚡⚡ | ⭐⭐⭐⭐ | Development |
| **Fallback** | 🆓 Free | ⚡⚡⚡⚡ | ⭐⭐ | Testing |

### Configuration

```env
# في .env
LLM_PROVIDER=auto  # يجرّب OpenRouter → Ollama → Fallback

# أو حدد واحد:
# LLM_PROVIDER=ollama
# LLM_PROVIDER=openrouter
```

📚 **Ollama Setup**: راجع [`OLLAMA_SETUP.md`](OLLAMA_SETUP.md)

---

## 📁 Project Structure

```
odoo-hr-agents-2/
│
├── 🆕 agents/                    ← Agentic AI Framework
│   ├── base_agent.py            ← BaseAgent (459 lines)
│   ├── tool_registry.py         ← Tool Registry (183 lines)
│   ├── llm_provider.py          ← Multi-LLM support (306 lines)
│   └── fahas_agent.py           ← Example agent (389 lines)
│
├── 🔄 graph/                     ← Updated for integration
│   ├── agentic_nodes.py         ← New nodes
│   ├── nodes.py                 ← + routing logic
│   └── build_graph.py           ← + fahas_agentic node
│
├── 🧪 Testing
│   ├── test_integration.py      ← Full integration tests (5/5 ✅)
│   ├── test_new_agents.py       ← FahasAgent demo
│   └── tests/test_agentic_agents.py  ← Unit tests
│
└── 📚 Documentation
    ├── START_HERE_V2.md         ← Complete guide (580 lines)
    ├── OLLAMA_SETUP.md          ← Ollama installation (270 lines)
    ├── PHASE1_COMPLETE.md       ← Summary
    └── README_AGENTIC.md        ← This file
```

---

## 🧪 Testing

### Full Integration Test

```powershell
python test_integration.py
```

**Tests**:
1. ✅ Tool Registry (6 tools registered)
2. ✅ LLM Provider (OpenRouter/Ollama/Fallback)
3. ✅ FahasAgent (standalone)
4. ✅ LangGraph Integration
5. ✅ Full Pipeline (ready)

**Result**: **5/5 PASSED** ✅

---

### FahasAgent Demo

```powershell
python test_new_agents.py
```

**ماذا يفعل**:
- ينشئ FahasAgent
- يعطيه هدف: "كم عدد الموظفين؟"
- يعرض كل خطوة (perceive → plan → execute → reflect)
- يعرض النتائج + trace log

---

## 💡 Usage Examples

### مثال 1: استخدام FahasAgent

```python
from agents.fahas_agent import FahasAgent, create_fahas_query_goal

# إنشاء هدف
goal = create_fahas_query_goal(
    "أعطني موظفي قسم IT",
    context={"company_id": 1}
)

# تشغيل الوكيل
fahas = FahasAgent()
result = fahas.run(goal)

# النتائج
if result['status'] == 'success':
    data = result['result']['data']
    print(f"Found {len(data)} employees")
```

---

### مثال 2: بناء وكيل جديد

```python
from agents.base_agent import BaseAgent, AgentGoal, AgentPlan, AgentReflection

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="MyAgent",
            role="My Custom Role"
        )
    
    def perceive(self, goal, context=None):
        # فهم الهدف
        return {"key": "value"}
    
    def plan(self, goal, perception):
        # وضع خطة
        plan = AgentPlan(plan_id="my-001")
        plan.add_step({"action": "do_something"})
        return plan
    
    def execute(self, plan):
        # تنفيذ
        return {"done": True}
    
    def reflect(self, goal, plan, result):
        # مراجعة
        return AgentReflection(
            success=True,
            confidence=0.95
        )

# استخدام
agent = MyAgent()
result = agent.run(my_goal)
```

---

## 🎯 Phase 1 Status

### ✅ Completed (100%)

- [x] BaseAgent framework
- [x] Tool Registry
- [x] Multi-LLM Provider
- [x] FahasAgent (complete example)
- [x] LangGraph integration
- [x] LangSmith observability
- [x] Integration tests (5/5 ✅)
- [x] Complete documentation

### 🔜 Phase 2 (Next)

- [ ] MuslehAgent (diagnostic)
- [ ] KatibAgent (write operations)
- [ ] HaresAgent (security/policies)
- [ ] MuwaffaqAgent (optimization)
- [ ] SijilAgent (logging)
- [ ] MudaqqiqAgent (validation)

---

## 📚 Documentation

| الملف | الوصف | الحجم |
|------|-------|------|
| [`START_HERE_V2.md`](START_HERE_V2.md) | دليل كامل مع أمثلة | 580 lines |
| [`OLLAMA_SETUP.md`](OLLAMA_SETUP.md) | تثبيت Ollama خطوة بخطوة | 270 lines |
| [`PHASE1_COMPLETE.md`](PHASE1_COMPLETE.md) | ملخص المرحلة الأولى | Quick ref |
| In-code docs | Docstrings + comments | 800+ lines |

**Total Documentation**: ~1,650 lines

---

## 🔧 Configuration

### Environment Variables

```env
# Odoo connection
ODOO_URL=https://your-instance.odoo.com/
ODOO_DB=your-database
ODOO_USERNAME=your-username
ODOO_API_KEY=your-api-key

# LLM Provider (choose one)
LLM_PROVIDER=auto  # or: openrouter, ollama, fallback
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OLLAMA_MODEL=llama3.2

# LangSmith (observability)
LANGSMITH_API_KEY=lsv2_pt_...
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=odoo-hr-agents-agentic

# Features
ENABLE_AGENTIC_FAHAS=0  # 0=disabled, 1=enabled
```

---

## 🏆 Features

### ✅ Core Capabilities

- **Goal Understanding** - فهم الأهداف بالذكاء الاصطناعي
- **Dynamic Planning** - خطط تتكيف مع الموقف
- **Autonomous Execution** - تنفيذ مستقل مع error handling
- **Self-Reflection** - مراجعة ذاتية + retry logic
- **Memory System** - ذاكرة عمل + episodic + semantic

### ✅ Advanced Features

- **Multi-LLM Support** - 3 providers (OpenRouter/Ollama/Fallback)
- **Tool Registry** - إدارة مركزية للأدوات
- **Observability** - LangSmith integration + trace logs
- **Security** - Guardrails + permission checking
- **Extensibility** - سهل إضافة وكلاء جديدة

---

## 🤝 Contributing

لإضافة وكيل جديد:

1. انسخ `agents/fahas_agent.py` كـ template
2. ورث من `BaseAgent`
3. طبّق الدوال الأربع: `perceive`, `plan`, `execute`, `reflect`
4. سجّل tools جديدة في `tool_registry.py` إن لزم
5. أضف عقدة في `graph/agentic_nodes.py` للتكامل
6. اختبر مع `test_integration.py`

---

## 🔧 Troubleshooting

### "OpenRouter HTTP 402"
```env
# استخدم Ollama مجاناً
LLM_PROVIDER=ollama
```

### "Ollama not found"
```powershell
# تثبيت من https://ollama.com/download
ollama pull llama3.2
ollama serve
```

### "Tests failing"
```powershell
# تأكد من .env صحيح
python test_integration.py
```

📚 **المزيد**: راجع [START_HERE_V2.md](START_HERE_V2.md#troubleshooting)

---

## 📞 Support

- **Integration Tests**: `python test_integration.py`
- **Demo**: `python test_new_agents.py`
- **Full Guide**: [START_HERE_V2.md](START_HERE_V2.md)
- **Ollama Setup**: [OLLAMA_SETUP.md](OLLAMA_SETUP.md)

---

## 📊 Stats

- **Total Code**: ~2,400 lines (new framework)
- **Documentation**: ~1,650 lines
- **Tests**: 5/5 passing ✅
- **Agents**: 1 complete (FahasAgent), 7 planned
- **LLM Providers**: 3 supported
- **Tools**: 6+ registered

---

## 🎉 Summary

**Phase 1 is COMPLETE!** ✅

تم بناء framework قوي ومرن لـ Agentic AI مع:
- ✅ بنية تحتية كاملة
- ✅ دعم multi-LLM
- ✅ مثال عملي (FahasAgent)
- ✅ integration مع LangGraph
- ✅ observability عبر LangSmith
- ✅ documentation شامل
- ✅ testing كامل

**الفريق جاهز لـ Phase 2!**

---

## 📄 License

[Your License Here]

---

**🚀 Let's build intelligent agents!**

*Last updated: January 2025*  
*Framework version: v2.0-agentic*
