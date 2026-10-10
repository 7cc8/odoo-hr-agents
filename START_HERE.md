# 🚀 دليل البدء السريع - الوكلاء الذكية

## ✅ التحضيرات

### 1. تأكد من البيئة
```powershell
# تحقق من Python
python --version  # يجب أن يكون 3.11+

# تحقق من المتغيرات
$env:OPENROUTER_API_KEY  # يجب أن يكون موجود
$env:ODOO_URL            # يجب أن يكون موجود
```

### 2. تثبيت المتطلبات (إن لم تكن مثبتة)
```powershell
pip install -r requirements-langgraph.txt
```

---

## 🧪 الاختبار السريع

### الطريقة 1: اختبار مباشر للوكيل
```powershell
# من جذر المشروع
python test_new_agents.py
```

**ماذا سيحدث:**
1. ✅ ينشئ وكيل فاحص جديد
2. ✅ يُعطيه هدف: "كم عدد الموظفين؟"
3. ✅ يراقب كل خطوة (perceive → plan → execute → reflect)
4. ✅ يعرض النتائج والـ trace log

---

### الطريقة 2: عبر LangGraph Studio (مستقبلاً)
```powershell
# بعد التكامل الكامل
langgraph dev
```

---

## 📁 هيكل المشروع الجديد

```
odoo-hr-agents-2/
├── agents/                    ← 🆕 الوكلاء الذكية
│   ├── __init__.py           ✅
│   ├── base_agent.py         ✅ (الأساس)
│   ├── tool_registry.py      ✅ (مدير الأدوات)
│   ├── fahas_agent.py        ✅ (فاحص - جاهز)
│   │
│   ├── musleh_agent.py       ⏳ (التالي)
│   ├── hares_agent.py        ⏳
│   ├── katib_agent.py        ⏳
│   └── ...
│
├── graph/                     ← موجود (LangGraph)
│   ├── agentic_nodes.py      🆕 (عقد الوكلاء الجدد)
│   └── ...
│
├── test_new_agents.py         🆕 (نقطة الدخول للاختبار)
├── START_HERE.md             🆕 (هذا الملف)
│
└── [الملفات القديمة تعمل كما هي]
    ├── fahas_service.py      ✅ (باقي كما هو)
    ├── seraj_llm_service.py  ✅ (سنحسّنه لاحقاً)
    └── ...
```

---

## 🔄 المسار التدريجي

### المرحلة 1: الأساس (الآن) ✅
- [x] BaseAgent class
- [x] ToolRegistry
- [x] FahasAgent (مثال كامل)
- [x] نقطة اختبار

### المرحلة 2: باقي الوكلاء (أسبوعان)
- [ ] MuslehAgent (مصلح)
- [ ] HaresAgent (حارس)
- [ ] KatibAgent (كاتب)
- [ ] MudaqqiqAgent (مدقق)
- [ ] MuwaffaqAgent (موفّق)
- [ ] SijilAgent (سجل)

### المرحلة 3: التكامل (أسبوع)
- [ ] دمج مع LangGraph
- [ ] تحسين سراج
- [ ] نظام الذاكرة
- [ ] المراقبة والحوكمة

---

## 🎯 الخطوة التالية المباشرة

### خيار أ: اختبار فاحص الجديد
```powershell
python test_new_agents.py
```

### خيار ب: بناء مصلح التالي
```powershell
# انسخ fahas_agent.py كقالب
copy agents\fahas_agent.py agents\musleh_agent.py

# عدّل حسب دور مصلح
# (راجع القوالب في الـ artifacts)
```

### خيار ج: تشغيل الاختبارات الموجودة
```powershell
python -m pytest tests/test_agentic_agents.py -v
```

---

## 📊 مقارنة: قديم vs جديد

| الجانب | القديم (Service) | الجديد (Agent) |
|--------|------------------|----------------|
| **الاستدعاء** | `fahas.execute_query_task("search", {...})` | `fahas.run(goal)` |
| **التخطيط** | ❌ لا يوجد | ✅ يُخطط ديناميكياً |
| **التعلم** | ❌ لا يوجد | ✅ يتعلم من الأخطاء |
| **الشفافية** | ⚠️ محدودة | ✅ trace كامل |
| **المرونة** | ⚠️ مسارات ثابتة | ✅ يتكيف حسب النتائج |

---

## 🐛 استكشاف الأخطاء

### مشكلة: `ModuleNotFoundError: agents`
```powershell
# تأكد أنك في جذر المشروع
cd d:\mjrm0\Documents\odoo-hr-agents-2

# أعد المحاولة
python test_new_agents.py
```

### مشكلة: `OPENROUTER_API_KEY not set`
```powershell
# ضع المفتاح
$env:OPENROUTER_API_KEY="sk-or-v1-your-key"

# أو ضعه في .env
echo "OPENROUTER_API_KEY=sk-or-v1-your-key" >> .env
```

### مشكلة: الوكيل لا يتصل بـ Odoo
```powershell
# تحقق من متغيرات Odoo
$env:ODOO_URL
$env:ODOO_DB
$env:ODOO_USERNAME
$env:ODOO_API_KEY
```

---

## 📚 الموارد

- **القوالب**: راجع الـ artifacts في الدردشة
- **الاختبارات**: `tests/test_agentic_agents.py`
- **خارطة الطريق**: راجع artifact "خارطة الطريق"
- **الوثائق**: `agents/base_agent.py` (docstrings مفصلة)

---

## ✅ نقاط التحقق

قبل المتابعة، تأكد:
- [x] Python 3.11+ مثبت
- [x] المتغيرات موجودة (OPENROUTER_API_KEY, ODOO_*)
- [x] المجلد `agents/` موجود
- [x] الملف `test_new_agents.py` موجود
- [ ] اختبار `test_new_agents.py` يعمل بنجاح

---

## 🚀 ابدأ الآن!

```powershell
python test_new_agents.py
```

**Good luck! 🎉**
