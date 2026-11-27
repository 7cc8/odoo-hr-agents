# 🚀 odoo-hr-agents

<div align="center">

![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue?logo=python)
![Odoo Version](https://img.shields.io/badge/Odoo-19.0%2Be%20Enterprise-purple?logo=odoo)
![Tests](https://img.shields.io/badge/Tests-990%2B-brightgreen?logo=pytest)
![Architecture](https://img.shields.io/badge/Architecture-Dual--Track%20%7C%20Vanilla%20Agentic-orange)
![Security](https://img.shields.io/badge/Security-Fail--Closed%20%26%20RBAC-red)

**المنظومة الهجينة الذكية لإدارة وأتمتة الموارد البشرية في Odoo 19 Enterprise**  
*تجمع بين خط أنابيب حتمي صارم لمعالجة بيانات Excel، وفريق عمل من 8 وكلاء ذكاء اصطناعي، ومحرك تحليلات متقدم لنسب التوطين ونطاقات وفق نظام العمل السعودي.*

<p align="center">
  <img src="frontend/images/svg/seraj.svg" width="52" height="52" alt="سراج" title="سراج — المنسق العام" /> &nbsp;
  <img src="frontend/images/svg/fahas.svg" width="52" height="52" alt="فاحص" title="فاحص — استعلام Odoo" /> &nbsp;
  <img src="frontend/images/svg/modaqeq.svg" width="52" height="52" alt="مُدَقِّق" title="مُدَقِّق — الامتثال ونظام العمل" /> &nbsp;
  <img src="frontend/images/svg/hares.svg" width="52" height="52" alt="حارس" title="حارس — الأمان وحجب PII" /> &nbsp;
  <img src="frontend/images/svg/musleh.svg" width="52" height="52" alt="مُصلِح" title="مُصلِح — التشخيص والعلاج" /> &nbsp;
  <img src="frontend/images/svg/mowafaq.svg" width="52" height="52" alt="مُوَفِّق" title="مُوَفِّق — المطابقة الهجينة" /> &nbsp;
  <img src="frontend/images/svg/katib.svg" width="52" height="52" alt="كاتب" title="كاتب — بوابة التنفيذ والكتابة" /> &nbsp;
  <img src="frontend/images/svg/sijil.svg" width="52" height="52" alt="سِجِل" title="سِجِل — التوثيق والتدقيق الجنائي" />
</p>

[المميزات](#-أبرز-المميزات) • [معمارية المسارين](#-المعمارية-الهجينة-ذات-المسارين-dual-track) • [فريق الوكلاء الثمانية](#-فريق-الوكلاء-الذكية-the-8-ai-agents) • [محرك الوكلاء](#-محرك-الوكلاء-بدون-langgraph-vanilla-agentic-runtime) • [مركز العمليات](#-مركز-العمليات-الموحد-ومسارات-التشغيل-unified-cockpit) • [محرك التحليلات والتوطين](#-محرك-التحليلات-التنفيذية-ونظام-التوطين-ونطاقات) • [سيناريوهات الاستخدام](#-سيناريوهات-العمل-ورحلة-المستخدم) • [التشغيل السريع](#-التشغيل-السريع-quickstart) • [دليل الـ API](#-دليل-واجهات-البرمجة-core-api-reference)

---

</div>

## 💡 لماذا odoo-hr-agents؟ (المشكلة والحل)

### 🛑 التحديات المؤلمة في إدارة موظفي Odoo بالطرق التقليدية:
- **تشوه أخطاء الإدخال البشري:** برامج Excel تسقط الصفر في بداية أرقام الجوال السعودية (`50x` بدلاً من `050x`)، وتتداخل صيغ التواريخ، وتتكرر الأخطاء الإملائية في الأقسام والوظائف، مما يلوث قاعدة بيانات Odoo.
- **مخاطر الكتابة المباشرة وتكرار الموظفين:** إدخال ملفات Excel بشكل مباشر قد ينشئ موظفين مكررين ببريد إلكتروني موجود مسبقاً، دون تدقيق مسبق ودون سجل تراجع آمن.
- **صعوبة الامتثال لنظام العمل السعودي والتوطين:** غياب المراقبة اللحظية لنسب التوطين (Saudization) وتصنيف "نطاقات" قبل اتخاذ قرار التعيين، وعدم مطابقة شروط ساعات العمل والعقود بشكل آلي.
- **مخاطر الخصوصية والصلاحيات:** إمكانية تسريب بيانات الرواتب الحساسة أو التعديل غير المصرح به على بيئات الإنتاج الحية.

### ✅ الحل المعماري المتكامل:
يقدم مشروع **odoo-hr-agents** حلاً شاملاً عبر **نظام هجين متطور**:
1. **مسار تنظيف وتدقيق حتمي (Deterministic & Fail-Closed):** يصحح البيانات الشائعة تلقائياً، ويتحقق من السجلات في Odoo 19، ويطلب موافقة بشرية موقعة تشفيرياً (`row_hash`) قبل أي كتابة.
2. **منظومة متكاملة من 8 وكلاء ذكاء اصطناعي:** يتولون التنسيق، الاستعلام الآمن، مطابقة البيانات الضبابية، التدقيق العمالي، حراسة الأمان والخصوصية، وتشخيص الأخطاء.
3. **محرك تحليلات تنفيذية ومحاكاة التوطين:** احتساب نطاقات ونسب السعودة ومخصصات التأمينات، مع محاكاة أثر التعيين قبل تنفيذه.

---

## ✨ أبرز المميزات

- 🧹 **مرحلة تنظيف حتمية ذكية (`cleaning.py`):** استعادة الصفر المفقود للجوال السعودي، تحويل الأرقام الفارسية/الهندية إلى لاتينية، توحيد التواريخ غير الملتبسة، وتطهير الكشيدة وحروف الكاف والياء.
- 🛡️ **فحص تكرار آمن (Fail-Closed):** لا يتم قبول أي موظف بصمت إذا انقطع الاتصال بـ Odoo؛ بل يتحول إلى مراجعة بشرية فورية.
- ⚖️ **حراسة أمنية وتدقيق عمالي استباقي:** مدقق ومطابق لقوانين العمل ولوائح وزارة الموارد البشرية، مع حجب تلقائي للبيانات الحساسة PII.
- 📊 **محاكاة التوطين ونطاقات (`simulate-saudization`):** تجربة تعيين الموظفين الجدد واكتشاف أثرهم على نطاق المنشأة بضغطة زر.
- 💬 **محادثة فورية مع Odoo:** استعلام باللغة العربية الطبيعية وسؤال الوكيل الذكي عن الهيكل الإداري والموظفين والإحصائيات.
- 🌐 **واجهات تشغيل متعددة:** لوحة تحكم ويب متكاملة (FastAPI) مع مركز رفع منفصل وبث حي للأحداث (SSE)، إلى جانب بوت تيليجرام تفاعلي، ومقر بصري تفاعلي للوكلاء (`odoo_hr_hq/`).
- 🧩 **محرك وكلاء بدون أطر خارجية (Vanilla Agentic):** حلقة استدعاء أدوات موحدة في `agent_runtime.py` بسقف للأدوار ومهلة لكل أداة، بدلاً من رسوم LangGraph السابقة.

---

## 🏛️ المعمارية الهجينة ذات المسارين (Dual-Track Architecture)

يعتمد النظام فصلاً تاماً بين عمليات **التعديل والكتابة** الحساسة، وعمليات **الاستعلام والمحادثة**:

```mermaid
flowchart TD
    classDef primary fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff
    classDef strict fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff
    classDef agent fill:#4c1d95,stroke:#8b5cf6,stroke-width:2px,color:#fff
    classDef result fill:#1f2937,stroke:#64748b,stroke-width:1px,color:#fff

    User(["👤 المستخدم / موظف الموارد البشرية"])
    
    subgraph Core ["odoo-hr-agents Engine"]
        Router{"توجيه العملية"}
    end

    subgraph Track1 ["المسار الأول: خط المعالجة الحتمي الصارم (Strict Pipeline)"]
        direction TB
        Upload["📁 رفع ملف Excel (الويب / تيليجرام)"]
        Cleaning["🧹 1. التنظيف الحتمي (cleaning.py)<br/>استعادة 05x • توحيد التواريخ • إزالة التطويل"]
        Validation["🛡️ 2. التدقيق الصارم (validator.py)<br/>مطابقة الهيكل • فحص البريد في Odoo (Fail-Closed)"]
        DryRun["📋 3. تقرير الفحص التجريبي وتوليد الـ Hashes"]
        Approval["✍️ 4. الاعتماد البشري الرسمي (approval_schema.py)"]
        Writer["💾 5. كاتب Odoo الموثوق (writer.py)<br/>إعادة التحقق من الـ Hash والكتابة المقيدة"]
        SijilLog["📝 سجل تدقيق جنائي غير قابل للتلاعب (JSONL)"]

        Upload --> Cleaning --> Validation --> DryRun --> Approval --> Writer --> SijilLog
    end

    subgraph Track2 ["المسار الثاني: مركز عمليات الوكلاء ومسارات التشغيل التكيفية (Adaptive Agent Cockpit)"]
        direction TB
        Cockpit["🎛️ مركز العمليات الموحد (frontend/dashboard.html على /dashboard)"]
        Seraj["🧠 سراج (Seraj) — المنسق العام وإدارة النوايا وتحديد المسار"]
        RouterDAG{"🧭 التوجيه داخل chat_turn<br/>(seraj_llm_service.py + agent_runtime.py)"}
        
        Cockpit --> Seraj --> RouterDAG
        
        Path1["⚖️ مسار استشارة نظام العمل (3 مراحل)<br/>سراج ➔ مدقق ➔ سراج"]
        Path2["🔍 مسار الاستعلام وقراءة Odoo (3 مراحل)<br/>سراج ➔ فاحص ➔ سراج"]
        Path3["🛡️ مسار الإجراءات المباشرة والحوكمة (6 مراحل)<br/>سراج ➔ فاحص ➔ مدقق ➔ حارس ➔ كاتب ➔ سجل"]
        Path4["👥 مسار الاستيراد الشامل والدفعات (8 مراحل كاملة)<br/>سراج ➔ فاحص ➔ مدقق ➔ موفق ➔ مصلح ➔ حارس ➔ كاتب ➔ سجل"]
        
        RouterDAG --> Path1
        RouterDAG --> Path2
        RouterDAG --> Path3
        RouterDAG --> Path4
        
        EventsStream["📡 بث الأحداث اللحظية والأثر المعرفي للوكيل<br/>(SSE: Action Tags • Cognitive Reasoning • Tabular Timestamps)"]
        
        Path1 -.-> EventsStream
        Path2 -.-> EventsStream
        Path3 -.-> EventsStream
        Path4 -.-> EventsStream
        EventsStream -.-> Cockpit
    end

    OdooDB[("🏢 Odoo 19.0+e Enterprise Database")]

    User --> Router
    Router -->|ملف موظفين Excel| Upload
    Router -->|استعلام / محادثة / إدارة عمليات| Cockpit
    Writer -.->|كتابة مقيدة ومحمية| OdooDB
    Path2 -.->|قراءة واستعلام آمن فقط عبر فاحص| OdooDB
    Path3 -.->|تنفيذ مقيد عبر كاتب بعد اعتماد حارس| OdooDB
    Path4 -.->|ترحيل السجلات المعتمدة عبر كاتب| OdooDB

    class User,Router primary
    class Upload,Cleaning,Validation,DryRun,Approval,Writer,SijilLog strict
    class Cockpit,Seraj,RouterDAG,Path1,Path2,Path3,Path4,EventsStream agent
    class OdooDB result
```

---

## 🚀 تفاصيل المسار الأول: خط معالجة ملفات Excel الصارم

جميع ملفات الموظفين تمر عبر مراحل حتمية نقية، لا يتدخل فيها أي نموذج ذكاء اصطناعي باتخاذ قرارات القبول أو التعديل:

1. **المحلل ومرحلة التنظيف الحتمية (`parser.py` + `cleaning.py`):**
   - **الجوال:** معالجة الأرقام العربية/الفارسية، توحيد البادئات الدولية (`+966`)، واستعادة الصفر المفقود تلقائياً (`50xxxxxxx` ← `050xxxxxxx`).
   - **البريد:** تنظيف المسافات والتحويل لأحرف صغيرة (`lower()`).
   - **التاريخ:** تحويل الصيغ الواضحة غير الملتبسة فقط إلى `YYYY-MM-DD`. الحالات الملتبسة (مثل `05-06-2026`) أو التواريخ الهجرية تُترك كما هي ويُبلّغ عنها كـ `cleaning_issues`.
   - **النصوص:** إزالة التطويل (الكشيدة) وتوحيد الحروف الفارسية (`ک` و `ی`).
   - **قالب الموظفين الرسمي:** تخطي صف المثال التوضيحي تلقائياً (`template_example_row_skipped`).
2. **المدقق الصارم (`validator.py`):**
   - مطابقة الشركات والأقسام والمسميات الوظيفية مقابل لقطة Odoo الحية.
   - التحقق من تكرار البريد الإلكتروني في Odoo مع سياسة إغلاق آمنة عند تعذر الاتصال (`Fail-Closed`).
   - تصنيف النتائج إلى: `accepted` (مقبول)، `needs_review` (يحتاج مراجعة)، أو `rejected` (مرفوض).
3. **تقرير الفحص التجريبي (`dry_run_report.py`):**
   - توليد تقرير فحص تفصيلي يحتوي على ملخص الأخطاء، سجل التصحيحات، والتوقيع الفريد لكل صف (`row_hash`).
4. **الموافقة والاعتماد (`approval_schema.py`):**
   - إنشاء ملف اعتماد رسمي مشفر بالتوقيعات لضمان عدم التلاعب بمحتوى الملف بعد الفحص.
5. **الكاتب الموثوق (`writer.py`):**
   - يعيد تحليل الملف من الصفر للتأكد من مطابقة الـ `row_hash` الحية مع التقرير المعتمد.
   - الكتابة المقيدة على سجلات `hr.employee` في Odoo مع التحقق الفوري بعد الإنشاء (`readback`).
   - تسجيل كل عملية في ملف سجلات غير قابل للتعديل (`output/writer_results_*.jsonl`).

> 📖 **تفاصيل معايير الفحص وترتيبها:** راجع وثيقة [دليل الـ Validator وموفق المعتمد](docs/validator_and_matching.md).

---

## 🤖 فريق الوكلاء الذكية (The 8 AI Agents)

يعمل النظام عبر نموذج **تنسيق الوكلاء متعددي المهام (Multi-Agent Orchestration)**؛ يقودهم المنسق العام "سراج"، ويتعاونون تحت بيئة تشغيل موحدة ومحصنة ضد التعليق وانفجار الموارد (`agent_runtime.py`):

### 👥 معرض الوكلاء الذكية (Agent Avatars Gallery)

| <img src="frontend/images/svg/seraj.svg" width="80" /><br/>**🧠 سراج (Seraj)**<br/><sub>المنسق العام ومدير النوايا</sub> | <img src="frontend/images/svg/fahas.svg" width="80" /><br/>**🔍 فاحص (Fahas)**<br/><sub>الاستعلام وقراءة Odoo</sub> | <img src="frontend/images/svg/modaqeq.svg" width="80" /><br/>**⚖️ مُدَقِّق (Mudaqqiq)**<br/><sub>الامتثال لنظام العمل</sub> | <img src="frontend/images/svg/hares.svg" width="80" /><br/>**🛡️ حارس (Hares)**<br/><sub>الأمان وحجب PII والبيئة</sub> |
| :---: | :---: | :---: | :---: |
| <img src="frontend/images/svg/musleh.svg" width="80" /><br/>**🩺 مُصلِح (Musleh)**<br/><sub>التشخيص وعلاج الرفض</sub> | <img src="frontend/images/svg/mowafaq.svg" width="80" /><br/>**🎯 مُوَفِّق (Muwaffaq)**<br/><sub>المطابقة الهجينة الذكية</sub> | <img src="frontend/images/svg/katib.svg" width="80" /><br/>**✍️ كاتب (Katib)**<br/><sub>بوابة الكتابة والتنفيذ</sub> | <img src="frontend/images/svg/sijil.svg" width="80" /><br/>**📜 سِجِل (Sijil)**<br/><sub>التوثيق الجنائي (JSONL)</sub> |

```mermaid
graph TD
    classDef lead fill:#1e3a8a,stroke:#3b82f6,stroke-width:3px,color:#fff
    classDef inspect fill:#065f46,stroke:#10b981,stroke-width:2px,color:#fff
    classDef guard fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff
    classDef helper fill:#581c87,stroke:#a855f7,stroke-width:2px,color:#fff
    classDef exec fill:#1e293b,stroke:#64748b,stroke-width:2px,color:#fff

    Seraj["🧠 سراج (Seraj)<br/><b>Orchestrator & Meta-Agent</b><br/>إدارة الحوار، تصنيف النوايا، وتوزيع المهام"]

    Fahas["🔍 فاحص (Fahas)<br/><b>Query Agent</b><br/>استعلام وقراءة Odoo فقط"]
    Mudaqqiq["⚖️ مُدَقِّق (Mudaqqiq)<br/><b>Compliance Agent</b><br/>فحص الامتثال لنظام العمل السعودي"]
    Hares["🛡️ حارس (Hares)<br/><b>Security Agent</b><br/>حجب PII، حراسة البيئة، وتقييم المخاطر"]
    Musleh["🩺 مُصلِح (Musleh)<br/><b>Healing Agent</b><br/>تشخيص أسباب الرفض واقتراح الرقع"]
    Muwaffaq["🎯 مُوَفِّق (Muwaffaq)<br/><b>Matching Engine</b><br/>مطابقة ضبابية وهجينة للسجلات"]
    Katib["✍️ كاتب (Katib)<br/><b>Execution Gateway</b><br/>بوابة الكتابة المعتمدة في Odoo"]
    Sijil["📜 سِجِل (Sijil)<br/><b>Audit Agent</b><br/>التسجيل الجنائي للأحداث (JSONL)"]

    Seraj -->|تفويض الاستعلام| Fahas
    Seraj -->|تدقيق الأنظمة واللوائح| Mudaqqiq
    Seraj -->|فحص الأمان والخصوصية| Hares
    Seraj -->|تشخيص الأخطاء| Musleh
    Seraj -->|مطابقة الأسماء المتباينة| Muwaffaq
    Seraj -->|طلب التنفيذ المعتمد| Katib
    Katib -->|توثيق العمليات| Sijil

    class Seraj lead
    class Fahas,Mudaqqiq inspect
    class Hares guard
    class Musleh,Muwaffaq helper
    class Katib,Sijil exec
```

### 1. سراج (Seraj) — المنسق العام ومدير المحادثة (The Orchestrator)

<table>
  <tr>
    <td width="90" align="center" valign="top">
      <img src="frontend/images/svg/seraj.svg" width="80" alt="سراج" />
    </td>
    <td>
      <ul>
        <li><b>الدور:</b> الواجهة العقلية للنظام. يستقبل استفسارات المستخدم، يحلل النية (Intent Classification)، ويفوض المهام إلى الوكلاء المعنيين بترتيب مدروس.</li>
        <li><b>التقنية:</b> محرك LLM تفاعلي مع خط حماية خوارزمي احترازي عند تعذر النماذج.</li>
        <li><b>الملف المرجعي:</b> <code>agents/seraj_meta_agent.py</code> و <code>seraj_llm_service.py</code>.</li>
      </ul>
    </td>
  </tr>
</table>

### 2. فاحص (Fahas) — وكيل الفحص والاستعلام (The Query Agent)

<table>
  <tr>
    <td width="90" align="center" valign="top">
      <img src="frontend/images/svg/fahas.svg" width="80" alt="فاحص" />
    </td>
    <td>
      <ul>
        <li><b>الدور:</b> عين النظام داخل Odoo. ينفذ عمليات البحث والاستعلام والقراءة فقط دون أي صلاحية تعديل.</li>
        <li><b>الأدوات:</b> فحص سجلات الموظفين، البحث عن الشركات، جرد الأقسام، واستخراج بيانات الحضور والإجازات.</li>
        <li><b>الملف المرجعي:</b> <code>fahas_service.py</code>.</li>
      </ul>
    </td>
  </tr>
</table>

### 3. مُدَقِّق (Mudaqqiq) — وكيل الامتثال ونظام العمل (The Compliance Agent)

<table>
  <tr>
    <td width="90" align="center" valign="top">
      <img src="frontend/images/svg/modaqeq.svg" width="80" alt="مدقق" />
    </td>
    <td>
      <ul>
        <li><b>الدور:</b> قاضي الامتثال القانوني واللوائح السعودية. يفحص توافق البيانات والعقود والإجازات مع <b>نظام العمل السعودي</b>.</li>
        <li><b>المهام الحيوية:</b>
          <ul>
            <li>التحقق من ساعات العمل في شهر رمضان والحدود الأسبوعية (المادتان 98 و 99).</li>
            <li>تدقيق شروط العقود وفترات التجربة ولوائح الجزاءات ونسب ساعات العمل الإضافية.</li>
            <li>إيقاف العمليات التي تنتهك اللوائح وتوجيهها للمراجعة القانونية الفورية.</li>
          </ul>
        </li>
        <li><b>الملف المرجعي:</b> <code>agents/mudaqqiq_agent.py</code>.</li>
      </ul>
    </td>
  </tr>
</table>

### 4. حارس (Hares) — حارس الأمان والخصوصية (The Security Guard Agent)

<table>
  <tr>
    <td width="90" align="center" valign="top">
      <img src="frontend/images/svg/hares.svg" width="80" alt="حارس" />
    </td>
    <td>
      <ul>
        <li><b>الدور:</b> حماية البيانات الحساسة وحراسة بوابات الوصول والبيئة الحية.</li>
        <li><b>المهام الحيوية:</b>
          <ul>
            <li><b>حجب البيانات الشخصية والحساسة (Data Masking & PII):</b> إخفاء الهويات وأرقام الحسابات والرواتب في سجلات العرض والدردشة.</li>
            <li><b>حراسة البيئة (Environment Policy Gate):</b> منع أي عملية كتابة على بيئات الإنتاج الحية دون تفويض استثنائي.</li>
            <li><b>تقييم المخاطر (Risk Assessment):</b> فحص الصلاحيات ومنع ثغرات الحقن وتضارب الأوامر.</li>
          </ul>
        </li>
        <li><b>الملف المرجعي:</b> <code>agents/hares_agent.py</code> و <code>environment_policy.py</code>.</li>
      </ul>
    </td>
  </tr>
</table>

### 5. مُصلِح (Musleh) — خبير التشخيص والعلاج (The Healing & Diagnostic Agent)

<table>
  <tr>
    <td width="90" align="center" valign="top">
      <img src="frontend/images/svg/musleh.svg" width="80" alt="مصلح" />
    </td>
    <td>
      <ul>
        <li><b>الدور:</b> تشخيص أسباب رفض الصفوف في ملفات الإكسل، واقتراح حلول ورقع تصحيحية ذكية.</li>
        <li><b>المهام:</b> معالجة التناقضات بين الأقسام والوظائف، تقديم تقارير استشارية لإصلاح الخلل، وتطبيق التصحيحات المعتمدة.</li>
        <li><b>الملف المرجعي:</b> <code>musleh_service.py</code>.</li>
      </ul>
    </td>
  </tr>
</table>

### 6. مُوَفِّق (Muwaffaq) — محرك المطابقة الضبابية الذكي (The Matching Engine)

<table>
  <tr>
    <td width="90" align="center" valign="top">
      <img src="frontend/images/svg/mowafaq.svg" width="80" alt="موفق" />
    </td>
    <td>
      <ul>
        <li><b>الدور:</b> حل مشكلات تباين الأسماء والمصطلحات بين الإكسل وقاعدة بيانات Odoo.</li>
        <li><b>التقنية:</b> يعتمد خوارزمية هجينة (<code>difflib</code> SequenceMatcher + مطابقة تامة بعد التطبيع + تعزيز سياق القسم المشترك +0.15) مع نسب ثقة مركزية في <code>matching_thresholds.py</code>.</li>
        <li><b>الملف المرجعي:</b> <code>agents/muwaffaq_agent.py</code> و <code>matching_thresholds.py</code>.</li>
      </ul>
    </td>
  </tr>
</table>

### 7. كاتب (Katib) — منفذ العمليات المعتمدة (The Execution Gateway)

<table>
  <tr>
    <td width="90" align="center" valign="top">
      <img src="frontend/images/svg/katib.svg" width="80" alt="كاتب" />
    </td>
    <td>
      <ul>
        <li><b>الدور:</b> البوابة الحصرية المخولة بإنشاء وتعديل السجلات في Odoo.</li>
        <li><b>الأمان الصارم:</b> لا يعمل إلا بعد اجتياز التحقق والاعتماد ومطابقة الـ <code>row_hash</code> الحية. معزول تماماً عن صلاحية الحذف العام (<code>unlink</code>).</li>
        <li><b>الملف المرجعي:</b> <code>katib_service.py</code> و <code>writer.py</code>.</li>
      </ul>
    </td>
  </tr>
</table>

### 8. سِجِل (Sijil) — حارس التدقيق الجنائي (The Audit & Provenance Agent)

<table>
  <tr>
    <td width="90" align="center" valign="top">
      <img src="frontend/images/svg/sijil.svg" width="80" alt="سجل" />
    </td>
    <td>
      <ul>
        <li><b>الدور:</b> التوثيق الشامل غير القابل للتعديل لجميع العمليات.</li>
        <li><b>المهام:</b> توليد ملفات السجلات الجنائية بصيغة JSONL مع أرقام العمليات وتوقيعات الـ Hash لكل صف تم إنشاؤه لضمان التتبع والمصداقية.</li>
        <li><b>الملف المرجعي:</b> <code>agents/sijil_agent.py</code> و <code>sijil_audit_service.py</code>.</li>
      </ul>
    </td>
  </tr>
</table>

---

## 🧩 محرك الوكلاء بدون LangGraph (Vanilla Agentic Runtime)

في الفرع `refactor/vanilla-agentic-ai-clean` أُزيل مجلد `graph/` (رسوم LangGraph للقراءة والكتابة وExcel) وملف `langgraph.json`، وأصبح التنسيق بين الوكلاء مكتوباً بلغة Python مباشرة دون إطار تنسيق خارجي. نُقلت اختبارات الرسوم القديمة إلى `docs/archive/graph/tests/` للرجوع إليها فقط.

```mermaid
flowchart LR
    classDef core fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff
    classDef rt fill:#4c1d95,stroke:#8b5cf6,stroke-width:2px,color:#fff
    classDef tool fill:#065f46,stroke:#10b981,stroke-width:2px,color:#fff

    UI["💬 /api/chat<br/>أو بوت تيليجرام"] --> Turn["🧠 SerajLLMService.chat_turn()<br/>seraj_llm_service.py"]
    Turn --> Pending["تأكيد/إلغاء العمليات المعلقة<br/>واستيضاح الحذف أو الأرشفة"]
    Turn --> Mutations["طلبات الإضافة والتعديل والحذف<br/>حارس ➔ اعتماد صريح ➔ كاتب ➔ تحقق فاحص"]
    Turn --> Rules["أسئلة نظام العمل المحسوبة<br/>نهاية الخدمة • GOSI • العمل الإضافي • الإجازة"]
    Turn --> Loop["حلقة استدعاء الأدوات<br/>_run_tool_calling_loop"]
    Loop --> Runtime["⚙️ agent_runtime.run_agent()"]
    Runtime --> Registry["🧰 agents/tool_registry.py"]
    Registry --> Fahas["🔍 فاحص — قراءة Odoo فقط"]
    Turn --> Fallback["الوضع الاحترازي عند تعذر النموذج<br/>_fallback_odoo_or_rules"]

    class Turn core
    class Loop,Runtime rt
    class Registry,Fahas tool
```

| المكوّن | الملف | الدور |
|---|---|---|
| **منسق المحادثة** | `seraj_llm_service.py` (`chat_turn`) | نقطة الدخول لكل رسالة: إدارة الجلسة وسياق الشركة، معالجة العمليات المعلقة، مسار الحذف والأرشفة المحكوم، تحضير طلبات الإضافة والتعديل، ثم تفويض الاستعلامات لفاحص. |
| **وقت التشغيل الموحد** | `agent_runtime.py` (`run_agent`) | حلقة استدعاء أدوات عامة: سقف لعدد الأدوار (`max_turns`، وسراج يعمل بـ 5)، مهلة لكل أداة (افتراضياً 60 ثانية)، قص نتائج الأدوات الطويلة (افتراضياً 8000 حرف)، وسجل `AgentStep` لكل استدعاء مع بث الأحداث. لا يكتب في Odoo بنفسه؛ ينفذ فقط الأدوات التي يمررها المستدعي. |
| **سجل الأدوات** | `agents/tool_registry.py` | تسجيل الأدوات في أربع مجموعات: قراءة Odoo، استعلامات فاحص، خدمات الموارد البشرية ونظام العمل، وأدوات الكتابة الخاصة بكاتب (تتطلب خطة اعتماد مسبقة). |
| **تعليمات الوكلاء** | `agents/prompts.py` | تعليمات النظام لكل وكيل وتنسيق سياق Odoo المختصر. |
| **جلسات المحادثة** | `seraj_session_manager.py` | حفظ سياق كل محادثة (الاتصال، الشركة، الاستيضاحات المعلقة). |

> عند تعذر الوصول إلى النموذج اللغوي، يتحول سراج إلى الوضع الاحترازي فيستعلم من Odoo مباشرة أو يطبق القواعد الحتمية لضمان استمرار الخدمة.

---

## 🎛️ مركز العمليات الموحد ومسارات التشغيل (Unified Cockpit)

يقدم النظام واجهة تشغيل مركزية وموحدة للمشغّل البشري (`frontend/dashboard.html` مع `frontend/css/dashboard.css` و`frontend/js/dashboard.js`، وتُعرض على `/` و`/dashboard`) تجمع بين سرعة الاستجابة الحية، الحوكمة الأمنية، والشفافية الجنائية الكاملة:

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ 🎛️ لوحة قيادة منظومة الوكلاء الموحدة (Unified Agent Cockpit)                            │
├──────────────────────────────────────────┬─────────────────────────────────────────────┤
│ 1️⃣ خط سير العملية المباشر (Adaptive DAG) │ 💬 المحادثة التفاعلية واستشارات نظام العمل │
│ ───────────────────────────────────────  │ ─────────────────────────────────────────── │
│ مسار تكيفي ديناميكي يتغير حسب نوع الطلب: │ تفاعل فوري بلغة عربية رسمية مع التوثيق     │
│ • استشارة عمالية: 3 من 3 مراحل (100%)    │ المرجعي والمواد النظامية (المادتان 98 و 99) │
│ • إجراء مباشر: 6 مراحل بحوكمة HITL صريحة ├─────────────────────────────────────────────┤
│ • دفعة شاملة: 8 مراحل للوكلاء الثمانية   │ 📊 مقاييس الأداء الرقابي والاتصال الحي      │
├──────────────────────────────────────────┴─────────────────────────────────────────────┤
│ 2️⃣ سجل التتبع الزمني والأثر الرقابي للوكلاء (Forensic Agent Timeline & Cognitive Trace)│
│ ─────────────────────────────────────────────────────────────────────────────────────── │
│ ⏱ 07:26:37  #3  [إجراء: labor_law_consultation]  مسار: سراج ➔ مدقق  [مطابق ومعتمد]      │
│ 💡 التعليل المنطقي واستدلال الوكيل (Cognitive Reasoning):                               │
│    "تدقيق ومطابقة بنود المعاملة مع نصوص مواد نظام العمل واللوائح التنفيذية..."          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 🌟 أبرز ركائز مركز العمليات التشغيلي:

1. **خط السير التكيفي المباشر (Adaptive Dynamic Stepper):**
   - التخلص التام من فرضية المراحل الخمس الثابتة الجامدة؛ تحدد الواجهة (`frontend/js/dashboard.js`) نوع الرحلة تلقائياً من أحداث الوكلاء المسجلة لكل عملية، وتعرض المراحل المناسبة لها:
     - **استشارات نظام العمل (`labor_law`):** مسار استشاري رشيق من 3 مراحل (`سراج ➔ مدقق ➔ سراج`) ينتهي باكتمال 100% فور تقديم الرأي النظامي المعتمد، دون ترك محطات وهمية معلقة.
     - **استعلامات وقراءة Odoo (`odoo_query`):** 3 مراحل (`سراج ➔ فاحص ➔ سراج`) لاستخراج السجلات الحية وتنظيم تقرير العرض.
     - **الإجراءات المباشرة المشروطة (`direct_action`):** 6 مراحل (`سراج ➔ فاحص ➔ مدقق ➔ حارس ➔ كاتب ➔ سجل`) لضمان فحص السجل، تدقيق السياسة، واشتراط اعتماد المشغّل (HITL) قبل الكتابة.
     - **الاستيراد الشامل والدفعات (`full_enterprise`):** 8 مراحل كاملة تُفعّل منظومة الوكلاء الثمانية بالكامل، مستعيدةً دور **موفق** للمطابقة الدلالية وفك الالتباس، و**مصلح** للتشخيص والعزل بالحجر الصحي.

2. **سجل التتبع الزمني والاستدلال المعرفي (Forensic Agent Timeline):**
   - **صندوق التعليل المنطقي واستدلال الوكيل (Cognitive Reasoning):** يوضح لكل حدث سبب اتخاذ الوكيل للإجراء استناداً إلى نصوص نظام العمل أو سياسات Odoo المعتمدة.
   - **وسوم الإجراءات الفنية:** وسم `[إجراء: ...]` بالخط أحادي المسافة (`monospace`) لتحديد الدالة والحدث التشغيلي المنفذ بدقة.
   - **التوقيت اللحظي الثنائي:** توقيت زمني دقيق بالثواني (`⏱ HH:MM:SS`) بأرقام جدولية ثابتة (`font-variant-numeric: tabular-nums`) لمنع ارتعاش الشاشة أثناء البث اللحظي.
   - **مسار التوجيه المشترك:** بطاقات `مسار: الوكيل أ ➔ الوكيل ب` لتوثيق التسليم البيني للمهام بين الوكلاء.

3. **الفصل الجنائي الصارم بين التنفيذ والتوثيق:**
   - عزل صلاحية كاتب Odoo (`كاتب`) عن صلاحية الختم الجنائي اللاتراجعي (`سجل`).
   - توليد بصمة تجزئة مشفرة (`SHA-256`) لكل عملية ناجحة وحفظها في الدفتر اللاتراجعي غير القابل للتعديل لضمان عدم التلاعب.

---

## 🌐 واجهات التشغيل الأخرى

- **بوت تيليجرام (`bot/`):** قُسّم البوت إلى حزمة مستقلة: `client.py` (الاتصال والصلاحيات وسجل التدقيق)، `polling.py`، `navigation.py`، `keyboards.py`، `callbacks.py`، `media_handlers.py` (استقبال ملفات Excel والوسائط)، و`domain_wizards.py` (معالجات خدمات الموارد البشرية خطوة بخطوة). بقي `telegram_bot.py` واجهة توافق تعيد تصدير رموز الحزمة. يستدعي البوت خادم الـ API المركزي للكتابة ويطلب تأكيداً كتابياً قبل التنفيذ.
- **مقر سراج التفاعلي (`odoo_hr_hq/`):** واجهة بصرية مستقلة بأسلوب Pixel Art تُظهر الوكلاء في مكاتبهم. تُعرض من الخادم على `/hq` (أو `/odoo-hr-hq`)، أو تُشغّل منفردة عبر `python odoo_hr_hq/launch_hq.py` على `http://localhost:5174/`.

---

## 📊 محرك التحليلات التنفيذية ونظام التوطين ونطاقات

يضم النظام محرك تحليلات متقدم ومخصص لبيئة الأعمال السعودية (`analytics_service.py`)، يدعم المتابعة الحية وحساب مؤشرات الأداء (KPIs):

- **مؤشر التوطين ونطاقات (`/api/analytics/workforce`):** احتساب نسب السعودة الحالية وتحديد نطاق المنشأة وفق معايير وزارة الموارد البشرية.
- **محاكاة التوطين الفورية (`/api/analytics/simulate-saudization`):** محاكاة تأثير تعيين موظفين جدد (سعوديين أو مقيمين) على نطاق المنشأة قبل اتخاذ قرار التعيين الفعلي.
- **الالتزامات المالية والتأمينات (`/api/analytics/financial`):** حساب اشتراكات التأمينات الاجتماعية (GOSI)، ومخصصات مكافأة نهاية الخدمة (EOS)، والرواتب.
- **الامتثال والعمليات (`/api/analytics/compliance` و `/api/analytics/operations`):** متابعة سريان الإقامات، عقود العمل، الإجازات، ومعدلات الدوران الوظيفي.

---

## 💼 سيناريوهات العمل ورحلة المستخدم (Real Workflows)

### 📄 السيناريو 1: استيراد وتطهير دفعة موظفين جدد (Excel Onboarding)
1. يقوم موظف الـ HR برفع ملف Excel عبر **مركز الرفع الموحد**.
2. المحلل يمرر الملف عبر `cleaning.py`: يتم تلقائياً استرجاع الأصفار الساقطة من أرقام الجوال، توحيد صيغ التواريخ الواضحة، وتطهير النصوص.
3. المدقق يفحص السجلات مقابل Odoo؛ إذا وُجد بريد مكرر أو قسم غير موجود يُصنف الصف كـ `needs_review` أو `rejected`.
4. يظهر تقرير الـ **Dry-Run** الشامل موضحاً جدول التصحيحات والـ Hashes.
5. يضغط المشرف على "اعتماد وتنفيذ"؛ يقوم الكاتب `writer.py` بإعادة تحليل الملف، مطابقة التوقيعات، وإنشاء الموظفين في Odoo مع تسجيل تقرير JSONL فوري.

### 💬 السيناريو 2: استعلام استراتيجي ومحادثة تفاعلية (Smart HR Chat)
1. يسأل المدير في الشات: *"كم عدد الموظفين في قسم التقنية؟ ومن هم الموظفون الذين تنتهي إقاماتهم الشهر القادم؟"*
2. يستقبل **سراج** السؤال، ويطلب من **فاحص** جلب البيانات من Odoo عبر `execute_query_task`.
3. يتدخل **حارس** لحجب أي بيانات رواتب حساسة، ويصيغ **سراج** إجابة عربية واضحة ودقيقة.

### 📈 السيناريو 3: محاكاة التوطين ونطاقات قبل التعيين (Saudization Simulation)
1. ترغب الشركة في توظيف 3 مهندسين غير سعوديين، وتخشى هبوط نطاقها من الأخضر المرتفع إلى الأخضر المنخفض.
2. عبر استدعاء منفذ المحاكاة `/api/analytics/simulate-saudization`، يقوم محرك التحليلات باحتساب عدد الكوادر الوطنية مقابل الوافدين، وعرض نسبة التوطين المتوقعة والنطاق الناتج فوراً قبل توقيع العقود.

---

## 📂 هيكل المجلدات الرئيسي (Project Tree)

```text
odoo-hr-agents/
├── agents/                   # الوكلاء الثمانية + prompts.py (التعليمات) + tool_registry.py (سجل الأدوات)
├── api/
│   ├── common.py             # المصادقة (WRITE_API_TOKEN) ودوال مشتركة
│   └── routers/              # مسارات FastAPI مقسمة حسب المجال
│       ├── excel.py          # الرفع، الفحص التجريبي، الاعتماد، الكتابة، القوالب
│       ├── chat.py           # المحادثة مع سراج والمساعدين
│       ├── audit.py          # سجل، الحالة، أحداث عمليات الوكلاء والإعدادات
│       └── hr_services.py    # خدمات الموارد البشرية والتحليلات
├── bot/                      # حزمة بوت تيليجرام (العميل، الاستقبال، المعالجات خطوة بخطوة)
├── config/                   # ملفات ضبط لوحة التحكم وبيئة العمل
├── docs/                     # التوثيق المعماري والأدلة (+ archive/graph لاختبارات LangGraph المؤرشفة)
├── frontend/                 # مركز العمليات: dashboard.html + css/ + js/ + images/ (صور الوكلاء)
├── memory/                   # إدارة ذاكرة الجلسات وسجلات المحادثة
├── observability/            # مقاييس الأداء (Metrics)، التتبع اللحظي (Tracer)، والرصد
├── odoo_hr_hq/               # مقر سراج التفاعلي المستقل (Pixel Art)
├── templates/                # قوالب Excel المعيارية (master / modular) وقوالب سجل
├── tests/                    # حزمة الاختبارات الآلية (حوالي 990 اختباراً)
├── agent_runtime.py          # وقت تشغيل حلقة استدعاء الأدوات الموحد والمهل
├── analytics_service.py      # محرك التحليلات السعودية (نطاقات، التأمينات، محاكاة التوطين)
├── cleaning.py               # مرحلة التنظيف الحتمية للمدخلات العربية
├── dry_run_report.py         # بناء تقارير الفحص التجريبي وتوليد الـ Hashes
├── matching_thresholds.py    # ثوابت وعتبات نسب التشابه الموحدة
├── parser.py                 # محلل ملفات Excel واستخراج الحقول
├── seraj_llm_service.py      # منسق المحادثة chat_turn وحلقة تفويض الأدوات
├── seraj_session_manager.py  # جلسات المحادثة وسياق الشركة
├── telegram_bot.py           # واجهة توافق تعيد تصدير حزمة bot/
├── validator.py              # المدقق الصارم وقواعد المطابقة مع Odoo
├── web_service.py            # تطبيق FastAPI: يركّب الـ routers ويعرض الواجهات
└── writer.py                 # كاتب Odoo الموثوق وإعادة التحقق من التوقيعات
```

---

## ⚡ التشغيل السريع (Quickstart)

### المتطلبات الأساسية
- **Python:** 3.12 أو أحدث.
- **Odoo:** Odoo 19.0+e Enterprise (صلاحيات قراءة وإنشاء على موديل `hr.employee`).
- **نموذج الذكاء الاصطناعي:** Ollama محلي (الموديل الموصى به: `qwen3.5:9b`) أو مفتاح سحابي (Groq / OpenAI / Anthropic).

### 1. إعداد المتغيرات (`.env`)
انسخ ملف المثال ثم عدّل القيم:

```bash
cp .env.example .env
```

```bash
# Odoo Connection Settings
ODOO_URL=http://localhost:8069
ODOO_DB=your_database_name
ODOO_USERNAME=your_username_or_email
ODOO_API_KEY=your_odoo_api_key

# مطلوب لكل منافذ الكتابة والإعدادات — ولّد قيمة عشوائية طويلة ولا ترفعها للمستودع
WRITE_API_TOKEN=replace_with_a_long_random_secret

# أصول المتصفح المسموح لها باستدعاء الـ API
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000

# Telegram Bot Integration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id

# Local LLM Configuration (Ollama)
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2.5:7b
LLM_TIMEOUT=120
LLM_MAX_TOKENS=1024

# Audio / Transcription (Optional)
WHISPER_MODEL=base
GROQ_API_KEY=your_groq_api_key
OPENAI_API_KEY=your_openai_api_key
```

لتوليد رمز كتابة آمن:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. تثبيت التبعيات وبدء التشغيل

```powershell
# تثبيت المتطلبات
pip install -r requirements.txt

# تشغيل خادم FastAPI والواجهة الموحدة
uvicorn web_service:app --host 0.0.0.0 --port 8000 --reload

# تشغيل بوت تيليجرام (اختياري، في نافذة منفصلة)
python telegram_bot.py
```

افتح المتصفح على الرابط: **`http://localhost:8000`** (مركز العمليات على `/dashboard`، والمقر التفاعلي على `/hq`).

> ⚠️ ملف `start_chat.bat` ما زال يحاول تشغيل LangGraph Studio (`langgraph dev`) من المعمارية السابقة، لذلك يُفضّل تشغيل `uvicorn` مباشرة حتى يُحدَّث.

---

## 📡 دليل واجهات البرمجة (Core API Reference)

| المسار (Endpoint) | الطريقة | الحماية المطلوبة | الوظيفة التقنية |
|---|---|---|---|
| **`/api/upload`** | `POST` | مفتوح للجلسة | رفع ملف Excel وفحصه المبدئي وحفظه في الجلسة |
| **`/api/dry-run`** | `POST` | مفتوح للجلسة | تنفيذ الفحص التجريبي الصارم وتوليد تقرير الـ Hashes |
| **`/api/approve`** | `POST` | `X-API-Key` | اعتماد الصفوف المقبولة وتوليد تصريح الكتابة |
| **`/api/write`** | `POST` | `X-API-Key` | تنفيذ الكتابة المقيدة في Odoo للصفوف المعتمدة |
| **`/api/write/{run_id}/stream`** | `GET` | مفتوح للجلسة | بث أحداث الكتابة اللحظي للمشرف (Server-Sent Events) |
| **`/api/chat`** | `POST` | مفتوح للجلسة | إرسال استفسار أو أمر لسراج وتوجيه المهام وبث استجابة الوكلاء |
| **`/api/agents/operations/{operation_id}/events`** | `GET` | مفتوح للجلسة | سجل أحداث عملية الوكلاء والاستدلال المعرفي والتعليل المنطقي (JSON) |
| **`/api/agents/operations/{operation_id}/stream`** | `GET` | مفتوح للجلسة | بث أحداث عملية الوكلاء لحظياً (SSE) |
| **`/api/sijil/recent`** | `GET` | `X-API-Key` | استرجاع سجلات التدقيق الجنائي اللاتراجعي والبصمات المشفرة (SHA-256) |
| **`/api/approve-conditional`** | `POST` | `X-API-Key` | حوكمة واعتماد القرارات المشروطة بتدخل المشغّل البشري (HITL) |
| **`/api/analytics/dashboard`** | `GET` | مفتوح للجلسة | لوحة المؤشرات التنفيذية والإحصائيات الشاملة |
| **`/api/analytics/workforce`** | `GET` | مفتوح للجلسة | مؤشرات التوطين، نسبة السعودة، وتصنيف نطاقات |
| **`/api/analytics/simulate-saudization`**| `POST` | مفتوح للجلسة | محاكاة فورية لتأثير التعيين الجديد على نطاق الشركة |
| **`/api/template/generate`** | `POST` | مفتوح للجلسة | توليد نموذج Excel رسمي للموظفين معتمد ومتوافق مع Odoo |
| **`/api/leaves/summary/{emp_id}`** | `GET` | مفتوح للجلسة | استعلام رصيد وسجل إجازات موظف محدد |
| **`/api/status`** | `GET` | عام | فحص جاهزية النظام والاتصال بقاعدة Odoo |

> 🔒 **ملاحظة أمنية:** منافذ التعديل والكتابة تتطلب رمز `WRITE_API_TOKEN` عبر الترويسة `X-API-Key` (أو `Authorization: Bearer <token>` أو `X-Auth-Token`). إذا لم يُضبط الرمز في الخادم تُرجع هذه المنافذ `503` وتبقى الكتابة معطلة.

> 🗂️ **تنظيم المسارات:** يركّب `web_service.py` أربعة routers من `api/routers/` (`excel` و`chat` و`audit` و`hr_services`)، ويقارب مجموع المسارات المعرّفة 150 مساراً (بعضها أسماء بديلة لنفس المنفذ مثل `/write` و`/api/write`). الجدول أعلاه يعرض المنافذ الأساسية فقط.

---

## 🧪 الاختبارات وضمان الجودة (Testing Suite)

المشروع مغطى بحزمة تضم حوالي **990 اختباراً آلياً** تغطي المسارات الحتمية، الوكلاء، وحالات الخطأ. بعض الاختبارات (سيناريوهات سراج، رفع القوالب، وبعض منافذ الويب) تحتاج اتصالاً فعلياً بـ Odoo عبر `.env`، وتفشل بدونه برسالة `Missing Odoo connection settings`.

```powershell
# تشغيل جميع اختبارات المسار الحتمي ووقت تشغيل الوكلاء
pytest tests -q --ignore=tests/integration --ignore=tests/performance --ignore=tests/ad_hoc

# تشغيل اختبارات وقت تشغيل الوكلاء الجديد (Agent Runtime)
pytest tests/test_agent_runtime.py -v

# تشغيل اختبارات مرحلة تنظيف البيانات والحالات المتسقة
pytest tests/test_cleaning_stage.py tests/test_failure_code_status_consistency.py -v

# تشغيل اختبارات التحقق من نظام العمل والمدقق
pytest tests/test_labor_law_mudaqqiq_routing.py -v
```

---

## 🔒 الأمان وحوكمة البيانات (Enterprise Governance)

1. **عزل صلاحيات الحذف بالكامل (`Unlink Isolation`):** بوابة الكتابة `OdooWriteGateway` لا تحتوي كودياً على أي صلاحية حذف. أدوات التنظيف معزولة في بوابة خاصة `OdooCleanupGateway`، وتتطلب تأكيداً يدوياً صريحاً `--confirm` ومطابقة حية للبريد.
2. **فحص البيئات الصارم (`Environment Policy`):** منع الكتابة على أي بيئة إنتاج حية إلا بشروط صريحة واستثنائية ومحصورة في قواعد Odoo 19 المصرح بها.
3. **حماية الخصوصية ومراقبة الجلسات:** يتولى الوكيل "حارس" إخفاء البيانات الشخصية (PII Masking) لضمان عدم تسريب الرواتب والبيانات الحساسة في السجلات.
4. **التطابق التشفيري (`Hash Provenance`):** لا يمكن إدخال أي سجل إلى Odoo إذا تم تعديل حرف واحد في الملف بين مرحلتي الفحص والاعتماد.
5. **حماية الـ Endpoints برمز أمان قوي:** يُلزم بتعيين رمز كتابة عشوائي (`WRITE_API_TOKEN`)، ويرفض الخادم أي قيمة منشورة علناً في المستودع، مع تفعيل بروتوكول HTTPS في البيئات الإنتاجية.

---

## 📚 وثائق ومراجع إضافية
- [دليل الـ Validator وموفق المعتمد من الكود](docs/validator_and_matching.md)
- [دليل استخدام الواجهة الموحدة](docs/UNIFIED_DASHBOARD_GUIDE.md)
- [خطة التدقيق والمطابقة وإدارة الفشل](failure_codes.py)

---

<div align="center">
صُمم وطُوّر بأعلى معايير الأمان البرمجي لبيئات الأعمال والموارد البشرية السعودية 🇸🇦
</div>
