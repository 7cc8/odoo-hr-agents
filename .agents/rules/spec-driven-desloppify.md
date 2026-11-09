# ميثاق التطوير الموجه بالمواصفات وجودة الكود — Specification-Driven Development & Code Health Charter

تم تثبيت واعتماد أداتي **Spec Kit** و **Desloppify** رسمياً ومحلياً لمشروع `odoo-hr-agents-2` داخل البيئة المحلية `.venv` ومجلد الوكلاء `.agents/skills/` و `.specify/`:

| الأداة | المستودع الأصلي | موضع التثبيت المحلي | الاستخدام والاعتماد الإلزامي |
| :--- | :--- | :--- | :--- |
| **`Spec Kit` (`specify-cli`)** | `github/spec-kit` | `.venv/Scripts/specify.exe`<br>`.specify/`<br>`.agents/skills/speckit-*` | **منهجية التطوير الموجه بالمواصفات (SDD):** حظر كتابة أي ميزة أو تعديل كبير قبل صياغة المواصفات والتخطيط والمهام الذرية عبر أوامر السكيلز المعتمدة (`/speckit-specify`, `/speckit-plan`, `/speckit-tasks`, `/speckit-implement`, `/speckit-converge`). |
| **`Desloppify`** | `peteromallet/desloppify` | `.venv/Scripts/desloppify.exe`<br>`.desloppify/config.json`<br>`.agents/skills/desloppify` | **مراقبة صحة الكود ومكافحة الشوائب (Anti-Slop):** تتبع الديون التقنية، الأكواد الميتة، عيوب المعمارية وتوجيه دورة التحسين المستمر (**scan → plan → next → execute/autofix → rescan**) مع استهداف Strict Score لا يقل عن **85/100**. |

---

## 🔒 قواعد العزل المحلي الصارم (Local-Only Mandate)
- **يمنع منعاً باتاً** تعديل أو تثبيت أي إعدادات عامة على مستوى نظام التشغيل أو مسارات المستخدم (`~/.gemini/skills`, `~/.claude`, إلخ) أو التأثير على بيئات الـ IDEs الأخرى.
- كل العمليات والسكيلز والأدوات تعمل **حصراً** داخل مسار هذا المشروع:
  - تشغيل بايثون والأدوات عبر البيئة الافتراضية الخاصة بالمشروع: `.\.venv\Scripts\python.exe`، `.\.venv\Scripts\desloppify.exe`، `.\.venv\Scripts\specify.exe`.
  - تخزين السكيلز محلياً في `.agents/skills/`.
  - تخزين القواعد محلياً في `.agents/rules/`.
  - إدارة المواصفات محلياً في `.specify/`.

---

## 🛠️ أوامر وحركات العمل المعتمدة

### 1. أوامر Spec Kit (تطوير الميزات وإدارتها)
- `/speckit-constitution`: مراجعة المبادئ الدستورية للمشروع (`.specify/memory/constitution.md`).
- `/speckit-specify [feature-description]`: صياغة مواصفة معيارية كاملة للميزة.
- `/speckit-clarify`: توضيح الأسئلة المفتوحة وإزالة الغموض.
- `/speckit-plan`: بناء الخطة المعمارية والتقنية لتنفيذ المواصفة.
- `/speckit-tasks`: تفكيك الخطة إلى قائمة مهام تنفيذية مرتبة حسب الاعتمادات.
- `/speckit-implement`: تنفيذ المهام خطوة بخطوة مع الفحص المستمر.
- `/speckit-converge`: تقييم الكود المنفذ ومطابقته التامة للمواصفة.

### 2. أوامر Desloppify (فحص وتنظيف الكود)
- فحص صحة المشروع:
  ```powershell
  .\.venv\Scripts\desloppify.exe scan --path . --skip-slow --no-badge
  ```
- عرض لوحة الحالة والنقاط:
  ```powershell
  .\.venv\Scripts\desloppify.exe status
  ```
- جلب المهمة التالية من خطة التنظيف الحية:
  ```powershell
  .\.venv\Scripts\desloppify.exe next
  ```
- عرض الخطة الحية الكاملة:
  ```powershell
  .\.venv\Scripts\desloppify.exe plan
  ```
- تصحيح المشاكل الميكانيكية تلقائياً:
  ```powershell
  .\.venv\Scripts\desloppify.exe autofix
  ```

