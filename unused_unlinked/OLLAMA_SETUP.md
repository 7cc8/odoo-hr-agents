# Ollama Setup Guide - دليل تثبيت Ollama
## نموذج لغوي محلي مجاني (Local Free LLM)

Ollama بديل مجاني محلي لـ OpenRouter، يعمل على جهازك بدون رسوم API.

---

## 🚀 التثبيت السريع

### Windows

1. **تحميل Ollama**:
   ```powershell
   # تحميل من الموقع الرسمي
   # https://ollama.com/download/windows
   ```

2. **التثبيت**:
   - شغّل `OllamaSetup.exe`
   - اتبع خطوات التثبيت
   - سيتم تشغيل Ollama تلقائياً في الخلفية

3. **تحميل نموذج**:
   ```powershell
   # نموذج صغير وسريع (3B parameters)
   ollama pull llama3.2
   
   # أو نموذج أكبر وأقوى (8B parameters)
   ollama pull llama3.1:8b
   
   # أو نموذج متخصص بالعربية
   ollama pull aya:8b
   ```

4. **التحقق من التشغيل**:
   ```powershell
   ollama list  # عرض النماذج المثبتة
   ollama serve  # تشغيل الخادم (يعمل تلقائياً عادةً)
   ```

---

### Linux / macOS

```bash
# تثبيت Ollama
curl -fsSL https://ollama.com/install.sh | sh

# تحميل نموذج
ollama pull llama3.2

# التحقق
ollama list
```

---

## ⚙️ تكوين المشروع

### 1. تعيين Provider في `.env`

```env
# استخدام Ollama
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2

# أو استخدام Auto (يختار تلقائياً)
LLM_PROVIDER=auto
```

### 2. تفعيل الوكيل الجديد

```env
ENABLE_AGENTIC_FAHAS=1
```

### 3. اختبار

```powershell
python test_new_agents.py
```

---

## 📊 مقارنة النماذج

| النموذج | الحجم | السرعة | الدقة | التوصية |
|---------|-------|---------|--------|----------|
| `llama3.2` | 3B | ⚡⚡⚡ | ⭐⭐⭐ | **للتطوير السريع** |
| `llama3.1:8b` | 8B | ⚡⚡ | ⭐⭐⭐⭐ | **الأفضل للإنتاج** |
| `aya:8b` | 8B | ⚡⚡ | ⭐⭐⭐⭐ | **دعم العربية** |
| `mistral` | 7B | ⚡⚡ | ⭐⭐⭐⭐ | بديل قوي |
| `codellama` | 7B | ⚡⚡ | ⭐⭐⭐⭐⭐ | متخصص بالكود |

---

## 🔧 Troubleshooting - حل المشاكل

### المشكلة: "Ollama not running"

**الحل**:
```powershell
# Windows
ollama serve

# أو من قائمة ابدأ: Start → Ollama
```

---

### المشكلة: "Model not found"

**الحل**:
```powershell
ollama pull llama3.2
```

---

### المشكلة: "Out of memory"

**الحل**:
```powershell
# استخدم نموذج أصغر
ollama pull llama3.2  # 3B فقط
```

---

### المشكلة: بطء الأداء

**الحل**:
```powershell
# تأكد من:
# 1. GPU مُفعّل (NVIDIA/AMD)
# 2. استخدام نموذج 3B للتطوير
# 3. إغلاق البرامج الأخرى
```

---

## 🌐 استخدام OpenRouter بدلاً من Ollama

إذا كنت تفضل OpenRouter (مدفوع، أقوى):

```env
# في .env
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-your-key-here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
```

---

## 🔄 الترتيب الافتراضي (Auto Mode)

عند استخدام `LLM_PROVIDER=auto`:

1. ✅ **OpenRouter** - إذا وُجد `OPENROUTER_API_KEY`
2. ✅ **Ollama** - إذا كان يعمل على `localhost:11434`
3. ✅ **Fallback** - rule-based classification

---

## 📚 موارد إضافية

- **موقع Ollama الرسمي**: https://ollama.com
- **قائمة النماذج**: https://ollama.com/library
- **GitHub**: https://github.com/ollama/ollama
- **Discord Community**: https://discord.gg/ollama

---

## 💡 نصائح

1. **للتطوير**: استخدم `llama3.2` (سريع، صغير)
2. **للإنتاج**: استخدم `llama3.1:8b` أو OpenRouter
3. **للعربية**: جرّب `aya:8b`
4. **للكود**: جرّب `codellama`

---

## ✅ التحقق من النجاح

```powershell
# 1. تأكد من تشغيل Ollama
ollama list

# 2. اختبر API محلياً
curl http://localhost:11434/api/tags

# 3. شغّل اختبار المشروع
python test_new_agents.py

# 4. تفقد اللوق
# يجب أن ترى: "LLM Provider initialized: ollama with model llama3.2"
```

---

## 🎯 الخطوة التالية

بعد تثبيت Ollama:

```powershell
# 1. تأكد من تشغيله
ollama serve

# 2. فعّل الوكيل الجديد
# في .env: ENABLE_AGENTIC_FAHAS=1

# 3. اختبر
python test_new_agents.py
```

---

**🎉 الآن أنت جاهز لاستخدام Agentic AI مجاناً!**
