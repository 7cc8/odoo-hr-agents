# 💬 دليل تشغيل شات سِراج LangGraph

## نظرة عامة

هذا المشروع يدمج **LangGraph Studio** مع واجهة شات ويب عربية جميلة لنظام **سِراج** لإدارة الموارد البشرية.

---

## 🏗️ البنية المعمارية

```
┌─────────────────────────────────────────────────────────────┐
│                     المستخدم (المتصفح)                      │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Web Service (Port 8000)                │
│  - templates/chat.html (واجهة الشات)                       │
│  - /api/chat (Proxy to LangGraph)                          │
│  - /api/status, /api/chat/threads                          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│           LangGraph Studio API (Port 2024)                  │
│  - Graph: seraj (من langgraph.json)                        │
│  - Streaming API                                            │
│  - Checkpointing & Memory                                   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Graph Execution Engine                     │
│  8 Agents:                                                  │
│  - seraj_meta_orchestration (المنسق)                       │
│  - fahas (الفَحَّاص - محلل البيانات)                       │
│  - katib (الكاتِب - منفذ العمليات)                         │
│  - mudaqqiq (المُدَقِّق - مراجع الامتثال)                  │
│  - hares (الحَرَس - فاحص الأمان)                           │
│  - musleh (المُصلِح - معالج الأخطاء)                       │
│  - sijil (السِّجِل - مسجل العمليات)                        │
│  - muwaffaq (المُوَفِّق - منسق التطابق)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 التشغيل السريع

### الطريقة 1: استخدام السكريبت الجاهز (Windows)

```bash
start_chat.bat
```

هذا السكريبت سيقوم بـ:
1. تفعيل البيئة الافتراضية `.venv`
2. تشغيل LangGraph Studio على المنفذ `2024`
3. تشغيل FastAPI على المنفذ `8000`

### الطريقة 2: التشغيل اليدوي

#### الخطوة 1: تشغيل LangGraph Studio

```bash
# في Terminal 1
langgraph dev --port 2024
```

#### الخطوة 2: تشغيل FastAPI Web Service

```bash
# في Terminal 2
python -m uvicorn web_service:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🌐 الوصول إلى الخدمات

| الخدمة | الرابط | الوصف |
|--------|--------|-------|
| **شات الويب** | http://localhost:8000 | واجهة الشات العربية |
| **LangGraph Studio** | http://localhost:2024 | لوحة تحكم LangGraph |
| **Dashboard** | http://localhost:8000/dashboard | لوحة العمليات الكاملة |
| **API Docs** | http://localhost:8000/docs | توثيق FastAPI التلقائي |

---

## 📋 المتطلبات

### 1. ملف `.env`

تأكد من وجود الإعدادات التالية:

```env
# Odoo Configuration
ODOO_URL=https://your-odoo-instance.com
ODOO_DB=your-database
ODOO_USERNAME=your-username
ODOO_API_KEY=your-api-key

# LLM Configuration
LLM_PROVIDER=openrouter
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=your-llm-key
LLM_MODEL=your-model-name

# Optional: LangGraph API URL (default: http://localhost:2024)
LANGGRAPH_API_URL=http://localhost:2024

# Security
# ولّد قيمة عشوائية: python -c "import secrets; print(secrets.token_urlsafe(32))"
# (القيم المنشورة في المستودع تُرفض: الخادم يعيد 503 حتى تغيّر الرمز)
WRITE_API_TOKEN=
```

### 2. ملف `langgraph.json`

موجود في المشروع ويحتوي على:

```json
{
  "dependencies": ["."],
  "graphs": {
    "seraj": "./graph/graph.py:graph"
  },
  "env": ".env"
}
```

---

## 🧪 اختبار الشات

### 1. افتح الشات في المتصفح

```
http://localhost:8000
```

### 2. جرّب الرسائل التالية:

```
👤 "مرحباً، كيف يمكنني إضافة موظف جديد؟"

👤 "أريد معرفة عدد الموظفين في الشركة"

👤 "ما هي المستندات المطلوبة لإنهاء خدمة موظف؟"

👤 "ساعدني في رفع ملف Excel يحتوي على بيانات موظفين جدد"
```

---

## 📁 الملفات المضافة/المعدّلة

### ✅ الملفات الجديدة

1. **`templates/chat.html`**
   - واجهة شات عربية جميلة
   - تصميم داكن (Dark Mode) حديث
   - تكامل كامل مع LangGraph API
   - دعم الرسائل الطويلة والأكواد

2. **`start_chat.bat`**
   - سكريبت تشغيل سريع
   - يشغل LangGraph + FastAPI معاً

3. **`CHAT_SETUP.md`**
   - التوثيق الكامل (هذا الملف)

### 🔧 الملفات المعدّلة

1. **`web_service.py`**
   - إضافة `/api/chat` - Proxy إلى LangGraph
   - إضافة `/api/chat/threads` - قائمة المحادثات
   - إضافة `/api/chat/threads/{thread_id}/history` - سجل المحادثة
   - إضافة `/` - صفحة الشات الرئيسية
   - إضافة `/dashboard` - لوحة العمليات

---

## 🔌 API Endpoints الجديدة

### 1. POST `/api/chat`

**الطلب:**
```json
{
  "message": "مرحباً، كيف يمكنني إضافة موظف؟",
  "thread_id": "thread_123456789",
  "file_path": "/path/to/file.xlsx"
}
```

**الاستجابة:**
```json
{
  "status": "success",
  "thread_id": "thread_123456789",
  "response": {
    "content": "مرحباً! لإضافة موظف جديد...",
    "type": "text"
  },
  "current_agent": "seraj_meta_orchestration",
  "full_stream": [...]
}
```

### 2. GET `/api/chat/threads`

**الاستجابة:**
```json
{
  "threads": [
    {
      "thread_id": "thread_123456789",
      "created_at": "2026-10-11T10:30:00Z",
      "last_message": "مرحباً، كيف يمكنني..."
    }
  ]
}
```

### 3. GET `/api/chat/threads/{thread_id}/history`

**الاستجابة:**
```json
{
  "thread_id": "thread_123456789",
  "messages": [
    {
      "role": "user",
      "content": "مرحباً",
      "timestamp": "2026-10-11T10:30:00Z"
    },
    {
      "role": "assistant",
      "content": "أهلاً بك!",
      "timestamp": "2026-10-11T10:30:05Z",
      "agent": "seraj"
    }
  ]
}
```

---

## 🎨 مميزات واجهة الشات

✨ **التصميم:**
- تصميم داكن (Dark Mode) احترافي
- خطوط عربية جميلة (IBM Plex Sans Arabic)
- رموز تعبيرية (Emojis) للوكلاء
- رسوم متحركة سلسة (Smooth Animations)

💬 **التفاعل:**
- مؤشر الكتابة (Typing Indicator)
- دعم الأكواد (Code Highlighting)
- تلقائي للتمرير (Auto-scroll)
- حالة الاتصال (Connection Status)

📱 **الاستجابة:**
- يعمل على جميع الأجهزة
- تجربة مستخدم سلسة
- معالجة الأخطاء بشكل واضح

---

## 🐛 استكشاف الأخطاء

### المشكلة: `Connection refused على Port 2024`

**الحل:**
```bash
# تأكد من تشغيل LangGraph Studio
langgraph dev --port 2024
```

### المشكلة: `404 Not Found من LangGraph API`

**الحل:**
- تأكد من وجود `langgraph.json`
- تأكد من صحة مسار الگراف: `./graph/graph.py:graph`

### المشكلة: `LLM API Error`

**الحل:**
- تأكد من صحة `LLM_BASE_URL` في `.env`
- تأكد من تشغيل LM Studio أو OpenRouter

### المشكلة: الشات لا يستجيب

**الحل:**
```bash
# افحص logs في Terminal
# LangGraph Studio يطبع logs مفصلة
```

---

## 📊 مراقبة الأداء

### عرض Logs في الوقت الفعلي

```bash
# Terminal 1: LangGraph Studio
langgraph dev --port 2024

# سترى:
# ✓ Node: seraj_meta_orchestration
# ✓ Node: fahas_tools
# ✓ Node: finalize
```

### فحص حالة النظام

```bash
curl http://localhost:8000/api/status
```

**الاستجابة:**
```json
{
  "status": "online",
  "odoo": {
    "connected": true,
    "url": "https://your-instance.com"
  },
  "langgraph": {
    "connected": true,
    "url": "http://localhost:2024"
  }
}
```

---

## 🔒 الأمان

⚠️ **ملاحظات مهمة:**

1. **لا تستخدم في Production بدون:**
   - HTTPS (SSL/TLS)
   - Authentication قوي
   - Rate Limiting
   - CORS محدود

2. **API Token:**
   - غيّر `WRITE_API_TOKEN` في `.env`
   - لا تشارك الـ token أبداً

3. **Firewall:**
   - Port 8000: للمستخدمين فقط
   - Port 2024: محلي فقط (localhost)

---

## 📚 موارد إضافية

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Odoo API Reference](https://www.odoo.com/documentation/)

---

## 🎯 الخطوات التالية

### مقترحات للتطوير:

1. **إضافة رفع الملفات:**
   - دعم رفع Excel/CSV مباشرة من الشات
   - معاينة الملف قبل المعالجة

2. **تحسين الذاكرة:**
   - حفظ المحادثات في قاعدة بيانات
   - استرجاع المحادثات السابقة

3. **Multi-Agent Visualization:**
   - عرض خريطة الوكلاء النشطين
   - رسم بياني لسير العملية

4. **Voice Input:**
   - دعم الإدخال الصوتي بالعربية
   - تحويل النص إلى كلام للردود

---

## ✅ اختبار النجاح

عند التشغيل الناجح، يجب أن ترى:

```
✓ LangGraph Studio running on http://localhost:2024
✓ FastAPI running on http://localhost:8000
✓ Chat interface accessible
✓ All 8 agents loaded
✓ Connection to Odoo successful
```

---

## 💡 نصائح للاستخدام

1. **ابدأ بسؤال بسيط** لاختبار الاتصال
2. **استخدم الأوامر الواضحة** بالعربية الفصحى
3. **راقب Terminal** لرؤية سير العملية
4. **اختبر في بيئة Test أولاً** قبل Production

---

**تم بنجاح! 🎉**

الآن لديك شات LangGraph كامل يعمل مع 8 وكلاء أذكياء! 🚀
