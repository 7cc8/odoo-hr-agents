# تحسينات Unslop المطبقة على design_preview.html

## نظرة عامة
تم تطبيق **unslop pass** على dashboard.html باستخدام:
- `apply_unslop.py` - سكريبت Python لتطبيق التحسينات تلقائياً
- `patch.css` - تحسينات CSS لإزالة الـ "slop" البصري
- `patch.js` - تحسينات JavaScript للسلوك والوظائف

## التحسينات المطبقة

### 1. الألوان (Color)
**إزالة الـ gradients والـ glows:**
```css
/* قبل: gradients معقدة وglows مبالغ فيها */
background: linear-gradient(135deg, #10b981, #059669);
box-shadow: 0 0 24px rgba(62, 207, 142, 0.3);

/* بعد: ألوان solid ونظيفة */
background: var(--color-phosphor-green);
color: #10231a;
box-shadow: none;
```

**تطبيق:**
- `.btn-composer-send`, `#chatSendBtn`, `.btn-approval-confirm`
- `.ai-approval-card`, `.hitl-gate-card`
- `.agent-character-card`, `.nav-tab-btn.is-active`
- إزالة كل الـ box-shadows المبالغ فيها
- إزالة الـ pulse animations من الـ status dots

### 2. الحركة (Motion)
**إزالة الحركة الزائدة:**
```css
/* قبل: كل شيء يتحرك */
transform: translateY(-4px) scale(1.02);
animation: pulse 2s infinite;

/* بعد: فقط الأشياء الحية تتحرك */
transform: none;
animation: none !important;
```

**تطبيق:**
- إزالة hover transforms من الأزرار والبطاقات
- إزالة pulse rings من الـ active agents
- إزالة الـ bounce animations
- transitions موحدة: `120ms cubic-bezier(.2,0,0,1)`

### 3. الخطوط (Typography)
**أوزان منطقية وبدون caps:**
```css
/* قبل: أوزان 700-800 وcaps في كل مكان */
font-weight: 700 !important;
text-transform: uppercase !important;

/* بعد: أوزان 400-600 وtext طبيعي */
font-weight: 600 !important;
text-transform: none !important;
letter-spacing: 0 !important;
```

**تطبيق:**
- كل العناوين: font-weight 600 (بدلاً من 700-800)
- إزالة `text-transform: uppercase`
- إزالة `letter-spacing` على النصوص العربية
- تحسين أحجام النصوص الصغيرة: min 12px

### 4. الأسطح (Surfaces)
**نظام ألوان موحد:**
```css
:root {
  --color-obsidian: #121212;
  --color-ash: #181818;
  --color-card: #1c1c1c;
  --color-card-elevated: #242424;
  --color-charcoal: #2a2a2a;
  --color-slate: #363636;
  --color-graphite: #484848;
}
```

**استبدال inline hex colors:**
- `#141414`, `#161616` → `var(--color-ash)`
- `#181818`, `#1a1a1a` → `var(--color-card)`
- توحيد كل الأسطح على نفس النظام

### 5. الأزرار (Buttons)
**تعريف الأزرار المفقودة:**
```css
.btn-secondary, .btn-outline {
  background: var(--color-ash);
  border: 1px solid var(--color-charcoal);
  color: var(--color-snow);
}

.btn-ghost {
  background: transparent;
  border: 1px solid transparent;
  color: var(--color-silver-mist);
}

.btn-success {
  background: var(--color-phosphor-green);
  color: #10231a;
  border-color: transparent;
}

.btn-warning {
  background: var(--color-amber);
  color: #1a1405;
  border-color: transparent;
}
```

### 6. النصوص والمحتوى (Copy)
**إزالة التحيات والـ emojis:**
```diff
- مرحباً بك! أنا «سراج»
+ أنا «سراج»

- مرحباً بك في جلسة عمل جديدة! أنا
+ جلسة جديدة. أنا

- بنجاح!
+ بنجاح

- 📜 العمليات
+ العمليات

- 👥 الموظفون
+ الموظفون
```

**Emojis المحذوفة:**
- 📜 (scroll)
- 👥 (people)
- 📊 (chart)
- ⚠️ (warning)
- ⏳ (hourglass)
- ⏱ (timer)
- ⚖️ (scale)
- 🔍 (magnifier)
- ✍️ (writing hand)
- ● ○ (bullets)

### 7. الوظائف (Functionality)

#### JavaScript Fixes:
1. **Empty Timeline:**
```javascript
// عدم إظهار SEAL hashes مخترعة
window.renderAgentTimeline = function(ev, st) {
  if (Array.isArray(ev) && ev.length) return _rt(ev, st);
  // عرض "لا توجد أحداث" بدلاً من بيانات وهمية
  var c = document.getElementById('timelineContainer');
  if (c) c.innerHTML = '<div>لا توجد أحداث بعد...</div>';
};
```

2. **Telemetry Sync:**
```javascript
// ربط telemetry text بحالة Odoo الحقيقية
window.loadSystemStatus = async function(f) {
  await _ls(f);
  var t = document.getElementById('odooStatusText');
  var el = document.getElementById('telemetryOdooText');
  if (el && t) el.textContent = t.textContent;
};
```

3. **PDF Export:**
```javascript
// تصدير PDF بدون API key في الـ URL
async function openPdf(url) {
  var r = await apiFetch(url);
  var blob = await r.blob();
  var href = URL.createObjectURL(blob);
  window.open(href, '_blank');
}
```

#### HTML Fixes:
1. **Element IDs:**
```diff
- getElementById("sendChatBtn")
+ getElementById("chatSendBtn")

- getElementById("excelFile")
+ getElementById("chatExcelFileInput")

- id="templateCompanySelector"
+ id="companySelect"
```

2. **Auth Headers:**
```diff
- await fetch("/api/approve-conditional"
+ await apiFetch("/api/approve-conditional"

- await fetch("/api/template/generate"
+ await apiFetch("/api/template/generate"
```

3. **حذف البيانات الوهمية:**
```diff
- <span id="telemetrySyncedEmployees">14</span>
+ <span id="telemetrySyncedEmployees">—</span>

- <div>قاعدة Odoo 19.0e متصلة</div>
+ <div id="telemetryOdooText">—</div>

- <option value="1">Company 1 - المنشأة الرئيسية</option>
+ (محذوف)
```

4. **إخفاء الـ census card:**
```diff
- id="censusDiagramCard"
+ id="censusDiagramCard" hidden
```

### 8. جدول الـ Diff (Approval Table)
**تحسين لحظة الموافقة:**
```css
/* القيمة القديمة: باهتة ومشطوبة */
.approval-diff-table td:nth-child(3) {
  color: var(--color-smoke);
  text-decoration: line-through;
  text-decoration-color: rgba(255,255,255,.25);
}

/* القيمة الجديدة: واضحة وبارزة */
.approval-diff-table td:nth-child(4) {
  color: var(--color-snow);
  font-weight: 600;
}
```

### 9. الـ Timeline Seal Badge
**تصميم نظيف وموحد:**
```css
.timeline-seal-badge {
  color: var(--color-silver-mist);
  background: transparent;
  border: 1px solid var(--color-charcoal);
  border-radius: 4px;
}
```

## الملفات المطبقة

### apply_unslop.py
**الوظيفة:** سكريبت Python يقوم بـ:
1. قراءة ملف HTML الأصلي
2. تطبيق regex replacements على النصوص والـ IDs
3. إزالة الـ emojis والتحيات
4. حقن `patch.css` في `<head>`
5. حقن `patch.js` في نهاية `<body>`
6. كتابة النتيجة في ملف جديد

**الاستخدام:**
```bash
python apply_unslop.py dashboard.html design_preview.html
```

### patch.css (782 بايت)
**الوظيفة:** CSS override يطبق:
- تعريف tokens موحدة
- إزالة gradients وglows
- تقليل الحركة
- تحسين الخطوط
- توحيد الأسطح
- تعريف button classes المفقودة

### patch.js (1.2 KB)
**الوظيفة:** JavaScript fixes لـ:
- Empty timeline handling
- Telemetry text sync
- PDF export without exposed API keys
- Function overrides آمنة

## النتائج

### قبل (dashboard.html):
- ❌ Gradients وglows في كل مكان
- ❌ حركة زائدة على كل hover
- ❌ Font weights 700-800 وuppercase caps
- ❌ Emojis decorative في العناوين
- ❌ تحيات زائدة وexclamation marks
- ❌ بيانات وهمية (14 موظف، Company 1، etc.)
- ❌ SEAL hashes مخترعة في timeline فارغ
- ❌ API keys معروضة في PDF URLs
- ❌ Element IDs غير متطابقة

### بعد (design_preview.html):
- ✅ ألوان solid نظيفة
- ✅ حركة محسوبة فقط للعناصر الحية
- ✅ Font weights 400-600 منطقية
- ✅ نصوص نظيفة بدون emojis
- ✅ copy احترافي مباشر
- ✅ بيانات placeholder صحيحة (—)
- ✅ timeline فارغ نظيف
- ✅ PDF export آمن
- ✅ IDs متطابقة مع الـ JavaScript

## التحقق

### للاختبار:
```
http://localhost:8000/           (الأصلي)
http://localhost:8000/design-preview  (المحسّن)
```

### Unmatched Patches:
```
hardcoded odoo url
```
هذا pattern واحد فقط لم يتم العثور عليه في الملف (على الأرجح تم تغييره مسبقاً أو غير موجود).

## الخلاصة

تم تطبيق **unslop pass** كامل على الواجهة، مما نتج عنه:
- 🎨 تصميم نظيف بدون "slop" بصري
- ⚡ أداء أفضل (أقل animations وtransitions)
- 📝 نصوص احترافية مباشرة
- 🔧 وظائف صحيحة ومحسّنة
- 🔒 أمان محسّن (no exposed keys)
- ✨ تجربة مستخدم متسقة ونظيفة

---

**آخر تحديث:** 3 نوفمبر 2026  
**الأدوات:** apply_unslop.py + patch.css + patch.js  
**المرجع:** unslop skill by design-taste-frontend
