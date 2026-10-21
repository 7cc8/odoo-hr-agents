# odoo-hr-agents

مشروع بناء مسار آمن لأتمتة إنشاء موظفين في Odoo HR من ملف Excel، مع تحقق مسبق، مطابقة مع بيانات Odoo، موافقة مرتبطة بنفس نسخة الملف، وإنشاء مقيد في بيئة اختبار. هذا هو **المسار A (MVP)**؛ منظومة الوكلاء الثمانية الكاملة ما زالت رؤية مستقبلية.

## الحالة الحالية

المسار البرمجي الحالي يعمل كالتالي:

```
Excel → parser → normalization → validator → dry-run report
   → approval schema → writer → Odoo create/readback → JSONL audit
```

تم التحقق من الآتي:

- `124` اختباراً آلياً ناجحاً.
- تشغيل writer حي ضد قاعدة Odoo الاختبارية في `output/`.
- إنشاء 3 موظفين مع readback ناجح والتحقق من الحقول.
- رفض البيئات غير المسموح بها قبل أي mutation.
- إنشاء `approval.json` من تقرير dry-run عبر `make_approval.py` دون تحرير يدوي.
- اختبار multi-company حي على شركة الاختبار `17`: إنشاء، تحقق من `company_id`، تنظيف داخل `try/finally`، ثم تحقق نهائي بنتيجة فارغة.
- الكاتب الحالي ينفذ `create` و`read` فقط؛ لا ينفذ `write` العام أو `unlink`.
- صلاحية `unlink` معزولة في `OdooCleanupGateway` ولا توجد داخل `OdooWriteGateway`.
- أداة التنظيف مرتبطة بملف `writer_results.jsonl` محدد، وتدعم `--dry-run` وتتطلب `--confirm` قبل أي حذف.
- اختبار `allowed_company_ids` الصريح أثبت أن سياق `[15]` يمنع إنشاء سجل `hr.employee` بقيمة `company_id=17` عبر `AccessError`.

الدليل الحي الأخير محفوظ في:

`output/writer_20260930T102926Z/writer_results_ba465f8956d83e02.jsonl`

هذا لا يعني أن النظام جاهز للإنتاج؛ قاعدة الكتابة الحالية محمية كقاعدة اختبار، والحد الافتراضي للكاتب هو 3 صفوف لكل تشغيل.

## بنية المشروع

```
odoo-hr-agents/
├── parser.py                 # قراءة Excel والتحقق من بنيته وإنشاء hashes
├── normalization.py          # تطبيع القيم ومفاتيح المطابقة
├── validator.py              # التحقق والمطابقة وتصنيف الصفوف
├── dry_run_report.py         # تقارير JSON وCSV وXLSX
├── approval_schema.py         # التحقق من الموافقة وربطها بالتقرير
├── make_approval.py           # اختيار الصفوف المقبولة وإنشاء approval.json
├── writer.py                  # إعادة التحقق والإنشاء المقيد والتدقيق
├── odoo_readonly_repository.py# قراءة بيانات Odoo
├── odoo_write_gateway.py      # بوابة create/read مع حارس البيئة
├── odoo_cleanup_gateway.py    # بوابة unlink معزولة للاختبارات فقط
├── cleanup_test_employees.py  # تنظيف provenance-bound مع تحقق البريد الحي
├── environment_policy.py      # قواعد البيئات المسموح لها بالكتابة
├── scripts/                   # تجارب Odoo وتشغيلات المسار A
│   └── test_allowed_company_context.py # probe معزول لسياق الشركات
├── tests/                    # الاختبارات الآلية
├── docs/                     # وثائق MVP والرؤية المستقبلية
├── logs/                     # سجلات التجارب الحية
└── output/                   # تقارير dry-run ونتائج writer
```

## تجربة Odoo الحية الأساسية

تم تشغيل `scripts/01_test_create_employee.py` على بيئة اختبار فعلية للتحقق من:

1. نجاح `create()` على `hr.employee` بالحد الأدنى من الحقول.
2. الحقول المطلوبة فعلياً وسلوك `resource_id` و`version_id`.
3. أثر الموديولات المخصصة التي ترث على نموذج الموظف.
4. إنشاء موظف بحقول آمنة، ثم قراءته ومقارنة القيم، ثم تنظيف سجل الاختبار.

هذه التجارب منفصلة عن الإنتاج، ولا تعني السماح بالكتابة على قاعدة حقيقية.

## hiring_date

يحتوي `excel_template_spec.json` على عمود `hiring_date` اختيارياً من النوع `date`.
هذا الحقل موثق في القالب فقط ولا يدخل في payload الكاتب الحالي. إذا احتاج موظف HR
تعديل تاريخ التعيين من واجهة Odoo العادية، يجب تعبئته أو تعديله يدوياً من الشاشة؛
لأن الحقل مطلوب في الـview، حتى لو لم يكن مطلوباً على مستوى قاعدة البيانات.

## إعداد الاتصال

لا تكتب بيانات الاتصال داخل الكود مباشرة. استخدم متغيرات بيئة:

```
ODOO_URL=https://your-instance.odoo.com
ODOO_DB=your_db_name
ODOO_USERNAME=your_username
ODOO_API_KEY=your_api_key_or_password
```

على ويندوز (PowerShell) قبل تشغيل السكربت:

```powershell
$env:ODOO_URL="https://your-instance.odoo.com"
$env:ODOO_DB="your_db_name"
$env:ODOO_USERNAME="your_username"
$env:ODOO_API_KEY="your_api_key"
python scripts/01_test_create_employee.py
```

## المسارات

- **المسار A** (الأولوية الحالية): إنشاء موظفين جدد من Excel على حقول `hr.employee` المسموح بها، مع dry-run وموافقة وإعادة تحقق قبل الكتابة. لا نلمس `prosys_hr_contract_total` أو `nthub_hr_disciplinary` أو أي موديول مخصص آخر في هذه المرحلة.
- **المسار B** (مرجع معماري، لا يُنفذ الآن): خريطة الموديولات كطبقات (Core → Payroll → Contract → Governance/Aggregators)، محفوظة في `docs/02_architecture_reference.md`.
- **المسار C** (بعد إثبات MVP في الاستخدام المحدود): سراج كمنسق فعلي، الوكلاء المتخصصون، ثم توسيع النطاق بدءاً من الطبقة الأقرب لبيانات الموظف الأساسية.

## إنشاء الموافقة

بعد إنشاء تقرير dry-run، اعرض الصفوف وحالاتها:

```powershell
py make_approval.py --report output\<run>\dry_run_report.json --list
```

أنشئ موافقة للصفوف التي حالتها `accepted` فقط:

```powershell
py make_approval.py `
   --report output\<run>\dry_run_report.json `
   --input path\to\employees.xlsx `
   --approved-by hr-reviewer `
   --rows 2 10 11 `
   --out output\<run>\approval.json
```

الأمر يرفض الصفوف غير المقبولة، الصفوف غير الموجودة، الصفوف المكررة، والكتابة فوق ملف موافقة موجود. وهو offline ولا يتصل بـOdoo.

## تنظيف سجلات الاختبار

يجب تمرير ملف نتائج writer محدد. المعاينة لا تحذف شيئاً:

```powershell
py cleanup_test_employees.py `
   --results output\<run>\writer_results_<run_id>.jsonl `
   --dry-run
```

التنفيذ الفعلي يتطلب `--confirm`، ويقرأ البريد الحالي من Odoo قبل كل حذف ويقارنه بالبريد المسجل في صف `created` داخل نفس الملف:

```powershell
py cleanup_test_employees.py `
   --results output\<run>\writer_results_<run_id>.jsonl `
   --confirm
```

لا تقبل الأداة IDs حرة؛ ولا تحذف سجلاً إذا كان غير موجود في ملف النتائج، أو لم يكن `status == "created"`، أو اختلف بريده الحالي عن البريد المسجل.

## ما تبقى قبل Pilot محدود

1. إضافة retry محدود للقراءات العابرة مثل `404` و`ResponseNotReady` بعد فصلها عن أخطاء `create`.
2. إنتاج قالب Excel رسمي قابل للتوزيع.
3. تجربة أمر الموافقة مع موظف HR، ثم بناء واجهة رسومية فقط إذا أثبت الأمر أنه غير كافٍ.
4. وضع سياسة احتفاظ وصلاحيات وحذف آمن لملفات النتائج.
5. مراجعة أمنية وتشغيلية قبل أي انتقال من قاعدة الاختبار.

## تشغيل الاختبارات

```powershell
py -m unittest discover -s tests -v
```

## تصنيف الأخطاء (6 فئات)

1. `validation` — فشل تحقق من صحة البيانات المُدخلة
2. `mapping` — فشل في مطابقة الحقول بين المصدر و Odoo
3. `access` — صلاحيات غير كافية
4. `workflow` — خطأ في تسلسل العملية
5. `system` — خطأ تقني عام (اتصال، timeout، إلخ)
6. `module_conflict` (جديد) — تعارض مع موديول مخصص (قيد Python/SQL، onchange، حقل مطلوب ضمنياً بسبب inherit).
   **لا يُصلح تلقائياً** — يوقف الصف فوراً ويُصعّد لمراجعة بشرية مع حفظ payload كامل.

---

## 🌟 الواجهة الموحدة الجديدة (Unified Dashboard)

تم إضافة واجهة ويب موحدة احترافية تجمع جميع مكونات النظام في صفحة واحدة سلسة.

### 🚀 الوصول السريع

```bash
# تشغيل تلقائي
.\start_chat.bat

# فتح المتصفح
http://localhost:8000
```

### 🎨 المميزات

- **💬 محادثة ذكية**: محادثة مباشرة مع LangGraph و 8 وكلاء AI
- **📁 رفع ملفات**: Drag & Drop لملفات Excel (حتى 2MB)
- **⚙️ Pipeline مرئي**: خط معالجة تلقائي (Parser → Validator → Dry Run → Approval → Writer)
- **📊 إحصائيات حية**: تحديث مباشر لعدد السجلات ونسبة النجاح
- **🎨 تصميم Supabase Midnight**: واجهة احترافية بألوان داكنة وأخضر فسفوري

### 📖 الأدلة

- **[دليل الواجهة الموحدة الكامل](docs/UNIFIED_DASHBOARD_GUIDE.md)** - دليل استخدام شامل
- **[تكوين Dashboard](config/dashboard_config.json)** - إعدادات قابلة للتخصيص
- **[API Docs](http://localhost:8000/docs)** - Swagger UI

### 🤖 الوكلاء الثمانية

1. **سراج** (Seraj) - Meta Orchestration: منسق عام ومدير المحادثة
2. **فحّاص** (Fahas) - Tools Agent: مزود الأدوات والوظائف
3. **كاتب** (Katib) - Execute Agent: منفذ العمليات النهائية
4. **مُدَقِّق** (Mudaqqiq) - Verify Agent: مدقق البيانات والقوانين
5. **حارس** (Hares) - Guard Agent: حارس الأمان والصلاحيات
6. **مُصلِح** (Musleh) - Heal Agent: مصلح الأخطاء والبيانات
7. **سِجِل** (Sijil) - Log Agent: مسجل الأحداث والسجل التدقيقي
8. **مُوَفِّق** (Muwaffaq) - Match Agent: مطابق البيانات والسجلات

### 🔄 تدفق العمل

#### السيناريو 1: محادثة فقط

```
اكتب سؤالك → Enter → سراج يجيب عبر الوكلاء
```

#### السيناريو 2: رفع ومعالجة تلقائية

```
ارفع Excel → "معالجة الملف" → Pipeline يعمل تلقائياً → النتيجة
```

#### السيناريو 3: رفع + محادثة ذكية

```
ارفع Excel → اكتب "افحص الملف" → LangGraph يعالج → شرح تفصيلي
```

### 🛠️ الخدمات المطلوبة

```bash
# LangGraph Studio (Terminal 1)
langgraph dev --port 2024

# FastAPI Web Service (Terminal 2)
python web_service.py
# أو
uvicorn web_service:app --host 0.0.0.0 --port 8000 --reload
```

### 📡 Endpoints

- `GET /` - الواجهة الموحدة (الصفحة الرئيسية)
- `GET /chat` - شات مستقل
- `POST /api/chat` - محادثة مع LangGraph
- `POST /api/upload` - رفع ملف Excel
- `POST /api/dry-run` - فحص تجريبي
- `POST /api/approve-and-execute` - موافقة وتنفيذ تلقائي
- `GET /api/status` - حالة النظام

### 🎨 نظام التصميم

**Supabase Midnight Theme:**

- الخلفية: `#121212` (Obsidian)
- اللون المميز: `#3ecf8e` (Phosphor Green)
- النصوص: `#fafafa` (Snow)
- الخط: Inter (بديل لـ Circular)
- الأزرار: Pill style (radius: 9999px)
- البطاقات: Soft corners (radius: 16px)

### 📱 Responsive Design

الواجهة تتكيف تلقائياً مع:

- 💻 Desktop (شبكة بعمودين)
- 📱 Tablet (شبكة عمودية)
- 📲 Mobile (تصميم محسّن للمس)

---

## 🔄 تحديث: إزالة OpenRouter

تم إزالة الاعتماد على OpenRouter بالكامل. النظام الآن يدعم:

### الخيارات المتاحة

1. **LangGraph Built-in (gpt-4o-mini)** ⭐ الافتراضي

   ```bash
   LLM_PROVIDER=langgraph
   LANGCHAIN_MODEL=gpt-4o-mini
   OPENAI_API_KEY=sk-...  # مطلوب
   ```

2. **Ollama محلي** (مجاني بالكامل)

   ```bash
   # تثبيت
   https://ollama.ai/download
   ollama pull qwen2.5:7b

   # في .env
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=qwen2.5:7b
   ```

3. **Fallback** (rule-based)
   ```bash
   LLM_PROVIDER=fallback
   ```

### ملاحظات

- تم حذف `OPENROUTER_API_KEY` و `OPENROUTER_MODEL` من `.env`
- `agents/llm_provider.py` محدّث لإزالة أولوية OpenRouter
- النظام الآن أكثر مرونة ويدعم multiple providers

---
