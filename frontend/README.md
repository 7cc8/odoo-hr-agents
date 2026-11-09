# 🖥️ واجهة المستخدم لمنظومة وكلاء Odoo HR (Frontend)

تم تفكيك وبناء الواجهة الأمامية معمارياً بنظام **الفصل المعياري للمسؤوليات (Separation of Concerns)**، لضمان أعلى أداء وسهولة في الصيانة.

---

## 🏛️ مصدر الحقيقة التشغيلي المعتمد (Modular Production Architecture)

الملف الإنتاجي الأساسي والمعتمد رسمياً هو قمرة القيادة الموحدة، مقسمة إلى 3 ملفات معيارية:

1. 📄 **الهيكل والعناصر (HTML):** [`frontend/dashboard.html`](./dashboard.html)
2. 🎨 **التنسيقات ونظام التصميم (CSS):** [`frontend/css/dashboard.css`](./css/dashboard.css)
3. ⚡ **المحرك التفاعلي وحالة الوكلاء (JS):** [`frontend/js/dashboard.js`](./js/dashboard.js)

---

## 📁 هيكلية المجلد (`frontend/`)

```
frontend/
├── dashboard.html                    # 🚀 مركز العمليات الهيكلي (HTML دلالي نظيف)
├── css/                              # 🎨 مجلد أنماط CSS
│   └── dashboard.css                 # نظام التصميم الكامل والتنسيقات (6,760 سطراً)
├── js/                               # ⚡ مجلد البرمجة التفاعلية
│   └── dashboard.js                  # محرك جافاسكريبت والاتصال اللحظي والوكلاء (6,940 سطراً)
├── images/                           # 🖼️ أصول وصور الوكلاء الثمانية والأيقونات (SVG / WebP / JPG)
│   └── svg/
└── temp/                             # 📦 مجلد العزل والنسخ الاحتياطية
    ├── dashboard.html.original_monolithic.bak # نسخة احتياطية من الملف الأحادي الأصلي
    ├── design_preview.html           # مسودة معاينة التصميم التجريبية
    ├── design_preview.test.html      # نسخة الاختبار المسودة
    ├── agents_redesign_proposals.html# مقترحات التصاميم البديلة
    ├── tokens.css                    # مسودات الرموز غير المستخدمة
    └── base.css                      # مسودات التنسيق غير المستخدمة
```

---

## 🔗 التكامل المباشر مع خادم FastAPI (`web_service.py`)

تم تأمين كافة المسارات لمنع أي خطأ 404 صامت:
- **مسار الملف الرئيسي:** يتم تقديم `dashboard.html` عند المسارات: `/` و `/dashboard` و `/chat` و `/sijil` و `/diagram/companies`.
- **مسار التنسيقات (CSS):** متاح عبر `/frontend/css/dashboard.css` وأيضاً عبر `/css/dashboard.css`.
- **مسار السكربتات (JS):** متاح عبر `/frontend/js/dashboard.js` وأيضاً عبر `/js/dashboard.js`.
- **مسار الصور (Images):** متاح عبر `/images/...` وعبر `/frontend/images/...`.
