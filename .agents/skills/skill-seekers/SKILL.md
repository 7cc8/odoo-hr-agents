---
name: skill-seekers
description: Convert documentation websites, GitHub repositories, PDFs, local codebases, videos, and notebooks into structured AI skills (SKILL.md), RAG knowledge bases, and vector stores using Skill Seekers CLI and FastMCP server.
---

# Skill Seekers — أداة تحويل المصادر والتوثيق إلى مهارات ذكاء اصطناعي

أداة متقدمة لتحويل مواقع التوثيق الرسمية، مستودعات GitHub، ملفات PDF، والأكواد البرمجية إلى مهارات AI منظمة (`SKILL.md`) وحزم معرفية جاهزة للوكلاء والنماذج التوليدية (Claude, Gemini, Cursor, Antigravity).

---

## 🚀 التشغيل المباشر من بيئة المشروع

الأداة مثبتة وجاهزة داخل البيئة الافتراضية للمشروع:
- **المسار التنفيذي:** `.\.venv\Scripts\skill-seekers.exe`
- **أو عبر بايثون:** `.\.venv\Scripts\python.exe -m skill_seekers.cli`
- **مستودع الكود والأمثلة:** `.\Skill_Seekers`

---

## 📌 أوامر الاستخدام الأساسية (CLI Workflows)

### 1. استكشاف نوع المصدر مسبقاً (Detect)
لفحص الرابط وتحديد كيفية قراءته وتقدير عدد الصفحات:
```bash
.\.venv\Scripts\skill-seekers.exe detect https://docs.djangoproject.com/ --json
```

### 2. إنشاء مهارة جديدة (Create Skill)
* **من رابط توثيق عبر الويب:**
  ```bash
  .\.venv\Scripts\skill-seekers.exe create https://docs.fastapi.tiangolo.com/ --name fastapi
  ```
* **من مستودع GitHub:**
  ```bash
  .\.venv\Scripts\skill-seekers.exe create tiangolo/fastapi --name fastapi-repo
  ```
* **من مجلد أو مشروع محلي:**
  ```bash
  .\.venv\Scripts\skill-seekers.exe create ./my-project --name my-project-skill
  ```
* **من ملف PDF:**
  ```bash
  .\.venv\Scripts\skill-seekers.exe create ./manual.pdf --name user-guide
  ```

### 3. مسح واكتشاف حزمة المشروع تلقائياً (Scan)
لفحص مجلد مشروع محلي واستخراج توصيف ومعلومات التقنيات المستخدمة:
```bash
.\.venv\Scripts\skill-seekers.exe scan . --out ./configs/scanned/
```

### 4. تحسين المهارة بالذكاء الاصطناعي (Enhance)
```bash
.\.venv\Scripts\skill-seekers.exe enhance output/fastapi/
```

### 5. حزم وتثبيت المهارة للوكلاء (Package & Install)
* **تجهيز حزمة المهارة:**
  ```bash
  .\.venv\Scripts\skill-seekers.exe package output/fastapi/ --target claude
  ```
* **تثبيت المهارة في مسارات الوكلاء مباشرة:**
  ```bash
  .\.venv\Scripts\skill-seekers.exe install-agent output/fastapi/ --agent claude
  ```

### 6. تشغيل واجهة التحكم الرسومية (Seeker HUD Web UI)
```bash
.\.venv\Scripts\skill-seekers.exe ui
```

---

## 🔌 خادم MCP (Model Context Protocol)

توفر الأداة خادم FastMCP متكامل يحتوي على أكثر من 35 أداة برمجية لاستدعائها آلياً من داخل بيئات الوكلاء:
```bash
.\.venv\Scripts\python.exe -m skill_seekers.mcp.server_fastmcp
```

### إعدادات خادم MCP الموصى بها في `mcp_config.json`:
```json
{
  "mcpServers": {
    "skill-seekers": {
      "command": "D:\\mjrm0\\Documents\\odoo-hr-agents-2\\.venv\\Scripts\\python.exe",
      "args": [
        "-m",
        "skill_seekers.mcp.server_fastmcp"
      ],
      "type": "stdio"
    }
  }
}
```

---

## 🩺 فحص الصحة والاعتماديات (Health Check)
```bash
.\.venv\Scripts\skill-seekers.exe doctor
```

