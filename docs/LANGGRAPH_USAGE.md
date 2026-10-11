# 🎯 دليل استخدام LangGraph في مشروع سِراج

## نظرة عامة

هذا المشروع يستخدم **LangGraph** بثلاث طرق مختلفة:

1. **LangGraph Studio UI** - للتطوير والاختبار
2. **FastAPI Chat Web UI** - للمستخدمين النهائيين
3. **Python Direct** - للتكامل البرمجي

---

## 📊 مقارنة الطرق الثلاث

| الميزة | Studio UI | Web Chat | Python Direct |
|--------|-----------|----------|---------------|
| **الهدف** | التطوير | المستخدمون | التكامل |
| **الواجهة** | Studio UI | شات عربي | كود Python |
| **Port** | 2024 | 8000 | N/A |
| **Checkpointing** | ✓ تلقائي | ✓ تلقائي | يدوي |
| **Streaming** | ✓ | ✓ | ✓ |
| **Memory** | ✓ | ✓ | حسب الإعداد |
| **Authentication** | محلي | Token | N/A |

---

## 1️⃣ LangGraph Studio UI

### الاستخدام
```bash
langgraph dev --port 2024
```

### متى تستخدمه؟
- ✅ أثناء التطوير
- ✅ اختبار الگراف
- ✅ تصحيح الأخطاء (Debug)
- ✅ مراقبة سير العمليات

### المميزات
- واجهة رسومية جميلة
- رسم بياني للگراف
- عرض الحالة (State) في كل خطوة
- Time-travel debugging
- عرض الذاكرة (Memory)

### الوصول
```
http://localhost:2024
```

### مثال: اختبار الگراف

```
1. افتح http://localhost:2024
2. اختر Assistant: seraj
3. أرسل: "أريد إضافة موظف جديد"
4. راقب سير العملية:
   - ingest_user_message
   - classify_intent
   - seraj_meta_orchestration
   - seraj_think
   - ...
```

---

## 2️⃣ FastAPI Web Chat UI

### الاستخدام
```bash
# الطريقة 1: السكريبت الجاهز
start_chat.bat

# الطريقة 2: يدوياً
# Terminal 1
langgraph dev --port 2024

# Terminal 2
python -m uvicorn web_service:app --port 8000
```

### متى تستخدمه؟
- ✅ للمستخدمين النهائيين
- ✅ واجهة إنتاج (Production)
- ✅ تطبيقات الويب
- ✅ بوابة موظفي HR

### المميزات
- تصميم عربي احترافي
- دعم كامل للعربية RTL
- مؤشر كتابة حي
- معالجة أخطاء واضحة
- Mobile-friendly

### الوصول
```
http://localhost:8000
```

### API Endpoints

#### POST `/api/chat`
```python
import httpx

async def send_message(message: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/chat",
            json={
                "message": message,
                "thread_id": "thread_123"
            }
        )
        return response.json()

# الاستخدام
result = await send_message("أريد معرفة عدد الموظفين")
print(result["response"]["content"])
```

#### GET `/api/chat/threads`
```python
async def list_threads():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8000/api/chat/threads"
        )
        return response.json()
```

#### GET `/api/chat/threads/{thread_id}/history`
```python
async def get_history(thread_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/api/chat/threads/{thread_id}/history"
        )
        return response.json()
```

---

## 3️⃣ Python Direct Integration

### الاستخدام المباشر

```python
from dotenv import load_dotenv
load_dotenv()

from graph.build_graph import build_graph
from langgraph.checkpoint.memory import MemorySaver

# إنشاء checkpointer
memory = MemorySaver()

# بناء الگراف
graph = build_graph(checkpointer=memory)

# استدعاء مباشر
result = graph.invoke(
    {"user_query": "أريد إضافة موظف جديد"},
    config={"configurable": {"thread_id": "thread_123"}}
)

print(result["last_assistant"])
```

### مع Streaming

```python
async def stream_chat(message: str):
    """استدعاء مع streaming"""
    
    graph = build_graph(checkpointer=MemorySaver())
    
    async for event in graph.astream_events(
        {"user_query": message},
        config={"configurable": {"thread_id": "thread_123"}},
        version="v2"
    ):
        kind = event["event"]
        
        if kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                print(content, end="", flush=True)

# الاستخدام
await stream_chat("ما هي المستندات المطلوبة؟")
```

### في تطبيق أكبر

```python
from fastapi import FastAPI
from langgraph.checkpoint.sqlite import SqliteSaver

app = FastAPI()

# Checkpointer دائم
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")
graph = build_graph(checkpointer=checkpointer)

@app.post("/api/process")
async def process_query(query: str, thread_id: str):
    """معالجة استعلام مع حفظ الحالة"""
    
    result = graph.invoke(
        {"user_query": query},
        config={"configurable": {"thread_id": thread_id}}
    )
    
    return {
        "response": result["last_assistant"],
        "thread_id": thread_id
    }
```

---

## 🔄 سير العمل الموصى به

### للتطوير
```
1. تشغيل LangGraph Studio
   langgraph dev --port 2024

2. اختبار الگراف في Studio UI
   - http://localhost:2024
   - اختبار المنطق
   - تصحيح الأخطاء

3. عند النجاح: تشغيل Web Chat
   start_chat.bat
   - http://localhost:8000
   - اختبار UX
```

### للإنتاج (Production)
```
1. استخدام SQLite Checkpointer
   from langgraph.checkpoint.sqlite import SqliteSaver
   checkpointer = SqliteSaver.from_conn_string("db.sqlite")

2. تشغيل FastAPI فقط (بدون Studio)
   uvicorn web_service:app --host 0.0.0.0 --port 8000

3. استخدام Nginx/Caddy للـ reverse proxy
   - HTTPS
   - Rate limiting
   - Load balancing
```

---

## 🔧 الإعدادات

### ملف `langgraph.json`

```json
{
  "dependencies": ["."],
  "graphs": {
    "seraj": "./graph/graph.py:graph"
  },
  "env": ".env"
}
```

### ملف `.env`

```env
# LangGraph API URL (للتطوير)
LANGGRAPH_API_URL=http://localhost:2024

# LLM Provider
LLM_PROVIDER=openrouter
LLM_BASE_URL=http://localhost:1234/v1
LLM_API_KEY=your-key
LLM_MODEL=your-model

# Odoo
ODOO_URL=https://your-instance.com
ODOO_DB=your-db
ODOO_USERNAME=your-user
ODOO_API_KEY=your-key

# Security
WRITE_API_TOKEN=hr-write-secret-token
```

---

## 🧪 الاختبار

### اختبار Studio UI

```bash
# Terminal 1
langgraph dev --port 2024

# Terminal 2
curl http://localhost:2024/health
```

### اختبار Web Chat API

```bash
# Terminal 1
langgraph dev --port 2024

# Terminal 2
python -m uvicorn web_service:app --port 8000

# Terminal 3
python test_chat_api.py
```

### اختبار Python Direct

```bash
python -c "
from graph.build_graph import build_graph
from langgraph.checkpoint.memory import MemorySaver

graph = build_graph(checkpointer=MemorySaver())
result = graph.invoke({'user_query': 'مرحباً'})
print(result['last_assistant'])
"
```

---

## 📝 ملاحظات مهمة

### 1. Checkpointing

⚠️ **مهم جداً:**
- Studio UI: يستخدم checkpointer تلقائي
- Web Chat: يستخدم Studio API (checkpointer تلقائي)
- Python Direct: **يجب** توفير checkpointer للذاكرة

```python
# ❌ بدون checkpointer - لا توجد ذاكرة
graph = build_graph()

# ✅ مع checkpointer - توجد ذاكرة
from langgraph.checkpoint.memory import MemorySaver
graph = build_graph(checkpointer=MemorySaver())
```

### 2. Thread IDs

- كل محادثة تحتاج `thread_id` فريد
- Thread ID يحفظ سياق المحادثة
- استخدم نفس Thread ID للاستمرار في محادثة

```python
# محادثة جديدة
thread_1 = "thread_001"

# الرسالة 1
graph.invoke(
    {"user_query": "اسمي أحمد"},
    config={"configurable": {"thread_id": thread_1}}
)

# الرسالة 2 (في نفس السياق)
graph.invoke(
    {"user_query": "ما اسمي؟"},  # سيتذكر "أحمد"
    config={"configurable": {"thread_id": thread_1}}
)
```

### 3. Error Handling

```python
try:
    result = graph.invoke({"user_query": message})
except Exception as e:
    print(f"خطأ: {e}")
    # معالجة الخطأ
```

---

## 🚀 أفضل الممارسات

### 1. للتطوير
- استخدم Studio UI دائماً أولاً
- راقب logs بعناية
- اختبر كل agent على حدة

### 2. للإنتاج
- استخدم SQLite/Postgres checkpointer
- أضف rate limiting
- راقب الأداء (monitoring)
- استخدم HTTPS
- أضف authentication قوي

### 3. لـ Performance
- استخدم SQLite checkpointer للسرعة
- Cache النتائج المتكررة
- استخدم connection pooling

---

## 📊 مخطط تدفق البيانات

```
┌─────────────┐
│  المستخدم   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│  Web Chat UI (Port 8000)            │
│  - templates/chat.html              │
│  - JavaScript Frontend              │
└──────────┬──────────────────────────┘
           │
           │ HTTP POST /api/chat
           ▼
┌─────────────────────────────────────┐
│  FastAPI Backend                    │
│  - web_service.py                   │
│  - /api/chat endpoint               │
└──────────┬──────────────────────────┘
           │
           │ HTTP POST to LangGraph
           ▼
┌─────────────────────────────────────┐
│  LangGraph Studio API (Port 2024)   │
│  - /runs/stream endpoint            │
│  - Checkpointer (Memory/SQLite)     │
└──────────┬──────────────────────────┘
           │
           │ Graph Execution
           ▼
┌─────────────────────────────────────┐
│  Graph Engine                       │
│  - graph/graph.py                   │
│  - graph/build_graph.py             │
└──────────┬──────────────────────────┘
           │
           │ Node Execution
           ▼
┌─────────────────────────────────────┐
│  Agents                             │
│  - seraj_meta_orchestration         │
│  - fahas_tools                      │
│  - katib_execute                    │
│  - ... (8 agents total)             │
└──────────┬──────────────────────────┘
           │
           │ API Calls
           ▼
┌─────────────────────────────────────┐
│  External Services                  │
│  - Odoo ERP                         │
│  - LLM Provider (OpenRouter/Local)  │
└─────────────────────────────────────┘
```

---

## 🎓 موارد التعلم

### الوثائق الرسمية
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph Tutorials](https://langchain-ai.github.io/langgraph/tutorials/)
- [LangGraph Studio Guide](https://langchain-ai.github.io/langgraph/concepts/langgraph_studio/)

### الأمثلة في المشروع
- `graph/graph.py` - تعريف الگراف
- `graph/build_graph.py` - بناء الگراف
- `graph/nodes.py` - العقد الأساسية
- `graph/agentic_nodes.py` - العقد الذكية

### الاختبارات
- `test_chat_api.py` - اختبار Chat API
- `tests/test_graph_*.py` - اختبارات الگراف

---

**انتهى الدليل** ✅

الآن أنت تعرف كل طرق استخدام LangGraph في هذا المشروع! 🎉
