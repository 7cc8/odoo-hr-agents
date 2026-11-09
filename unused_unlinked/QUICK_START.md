# 🚀 البدء السريع - Odoo HR Agents

## الحالة الحالية ✅

النظام يعمل الآن **بدون OpenRouter** مع **Fallback Provider** (rule-based).

---

## 🎯 الوصول للنظام

### الواجهة الموحدة
```
http://localhost:8000
```

**المميزات:**
- 💬 شات ذكي مع LangGraph
- 📁 رفع ملفات Excel
- ⚙️ معالجة تلقائية عبر 8 وكلاء
- 📊 إحصائيات مباشرة

---

## ⚡ LLM Provider الحالي

**الوضع الحالي:** Fallback (Rule-based)

```bash
LLM_PROVIDER=fallback
```

**ماذا يعني ذلك؟**
- ✅ يعمل بدون API keys
- ✅ يعمل بدون تثبيت إضافي
- ⚠️ محدود (كلمات مفتاحية فقط)
- ⚠️ لا يفهم السياق المعقد

**الأسئلة التي يدعمها Fallback:**
```
✅ كم عدد الموظفين؟
✅ اعرض الموظفين
✅ ما الأقسام المتاحة؟
✅ موظفين قسم التقنية
❌ أسئلة معقدة (يحتاج LLM حقيقي)
```

---

## 🎨 ترقية LLM Provider

لتحسين الأداء والحصول على فهم أعمق، اختر أحد الخيارات:

### الخيار 1: Ollama (مجاني تماماً) ⭐⭐⭐

**الخطوات:**

1. **تحميل Ollama**
   ```
   https://ollama.ai/download
   ```

2. **تثبيت وتشغيل**
   ```bash
   # بعد التثبيت
   ollama pull qwen2.5:7b
   ollama serve
   ```

3. **تحديث .env**
   ```bash
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=qwen2.5:7b
   ```

4. **إعادة تشغيل**
   ```bash
   # إيقاف FastAPI (Ctrl+C)
   # إعادة تشغيل
   python web_service.py
   ```

**المميزات:**
- ✅ مجاني 100%
- ✅ خصوصية كاملة (لا يخرج من جهازك)
- ✅ سريع
- ✅ يفهم السياق
- ✅ دعم tool calling

**المتطلبات:**
- 4-8GB RAM
- مساحة: ~5GB للنموذج

---

### الخيار 2: OpenAI (مدفوع لكن قوي) ⭐⭐

**الخطوات:**

1. **احصل على API Key**
   ```
   https://platform.openai.com/api-keys
   ```

2. **تحديث .env**
   ```bash
   LLM_PROVIDER=langgraph
   LANGCHAIN_MODEL=gpt-4o-mini
   OPENAI_API_KEY=sk-...
   ```

3. **إعادة تشغيل**
   ```bash
   python web_service.py
   ```

**المميزات:**
- ✅ أقوى أداء
- ✅ فهم عميق للسياق
- ✅ دعم كامل لجميع المميزات

**التكلفة:**
- gpt-4o-mini: $0.15/$0.60 per 1M tokens
- ~$0.001 لكل محادثة عادية

---

### الخيار 3: البقاء مع Fallback ⚡

```bash
# لا حاجة لفعل أي شيء
# يعمل الآن بدون إعداد إضافي
```

**مناسب لـ:**
- الاختبار السريع
- الأسئلة البسيطة
- عدم توفر API keys
- عدم الرغبة بتثبيت برامج إضافية

---

## 🧪 اختبار النظام

### 1. تحقق من الحالة
```bash
curl http://localhost:8000/api/status
```

### 2. اختبر الشات
```
http://localhost:8000
# أرسل: "مرحباً"
# أو: "كم عدد الموظفين؟"
```

### 3. ارفع ملف Excel
```
http://localhost:8000
# اسحب ملف .xlsx
# اضغط "معالجة الملف"
```

---

## 📚 الأدلة المتاحة

- **[دليل المستخدم](docs/UNIFIED_DASHBOARD_GUIDE.md)** - كيفية استخدام الواجهة
- **[إزالة OpenRouter](docs/OPENROUTER_REMOVAL.md)** - التغييرات المنفذة
- **[نشر LangGraph](docs/LANGGRAPH_DEPLOYMENT.md)** - نشر في الإنتاج
- **[README](README.md)** - معلومات عامة

---

## 🎯 الخطوات التالية

### للاستخدام الفوري ✅
```
النظام جاهز الآن - افتح http://localhost:8000
```

### لتحسين الأداء
```
1. اختر provider (Ollama أو OpenAI)
2. اتبع خطوات التثبيت أعلاه
3. أعد تشغيل الخدمات
4. اختبر
```

### للنشر في الإنتاج
```
راجع: docs/LANGGRAPH_DEPLOYMENT.md
```

---

## 🆘 مساعدة سريعة

### المشكلة: الشات لا يرد
**الحل:**
```bash
# تحقق من LangGraph
curl http://localhost:2024/info

# إعادة تشغيل
langgraph dev --port 2024
```

### المشكلة: الواجهة لا تفتح
**الحل:**
```bash
# تحقق من FastAPI
curl http://localhost:8000/api/status

# إعادة تشغيل
python web_service.py
```

### المشكلة: رفع الملف لا يعمل
**الحل:**
```bash
# تأكد من:
- حجم الملف < 2MB
- صيغة .xlsx أو .xls
- الملف غير تالف
```

---

## 💡 نصائح

1. **للتطوير:** استخدم Fallback (سريع، بدون إعداد)
2. **للاختبار:** استخدم Ollama (مجاني، جودة جيدة)
3. **للإنتاج:** استخدم OpenAI (أفضل أداء)

---

## ✅ قائمة التحقق

```
[✅] FastAPI يعمل (http://localhost:8000)
[✅] LangGraph يعمل (http://localhost:2024)
[✅] Odoo متصل
[✅] Telegram مكوّن
[✅] Fallback Provider نشط
[ ] Ollama مثبت (اختياري)
[ ] OPENAI_API_KEY مكوّن (اختياري)
```

---

**الحالة:** ✅ النظام جاهز للاستخدام  
**Provider:** Fallback (rule-based)  
**الترقية:** اختيارية لتحسين الأداء

**ابدأ الآن:** http://localhost:8000 🚀
