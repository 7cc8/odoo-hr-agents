# أداة التصفح والأتمتة واختبار الويب — Playwright CLI

تم تثبيت وضبط أداة **Playwright CLI** (`@playwright/cli` من Microsoft) في بيئة العمل وتثبيت مهارات الأتمتة (`SKILL.md`) في:
- `.agents/skills/playwright-cli/`
- `.claude/skills/playwright-cli/`

---

## 🚀 لماذا Playwright CLI (بدلاً من MCP)؟

1. **كفاءة التوكنز (Token-Efficient)**: لا تفرض شجرة الـ DOM كاملة أو شجرة إمكانية الوصول على نافذة سياق النموذج (Context Window)، بل تعتمد على مقتطفات مدمجة ومعرفات مرجعية خفيفة (`ref: e1, e2, ...`).
2. **التحكم والسرعة**: تنفيذ أوامر مباشرة وسريعة للتنقل، النقر، التعبئة، والتصوير.
3. **الدعم المباشر لوكلاء الأكواد (Coding Agents)**: مصممة خصيصاً كـ Skill لـ Antigravity و Claude Code و Copilot.

---

## 📋 الأوامر الأساسية الشائعة

```bash
# 1. فتح متصفح جديد والتنقل إلى رابط
playwright-cli open https://example.com

# 2. أخذ لقطة هيكلية للصفحة (Snapshot) لاستخراج معرفات العناصر (Refs)
playwright-cli snapshot

# 3. البحث عن نص أو زر محدد للحصول على رقمه
playwright-cli find "تسجيل الدخول"

# 4. النقر أو التعبئة باستخدام الـ Ref
playwright-cli click e12
playwright-cli fill e5 "admin@example.com" --submit

# 5. أخذ لقطة شاشة وحفظها
playwright-cli screenshot --filename=screen.png

# 6. إغلاق الجلسة
playwright-cli close
```

---

## 🖥️ تشغيل الخادم الدائم (Daemon / Sessions)
على بيئات ويندوز، في حال الرغبة في إبقاء جلسة المتصفح حية ومستمرة عبر أوامر متعددة:
```bash
playwright-cli -s=test open https://example.com --persistent
playwright-cli -s=test snapshot
playwright-cli -s=test close
```
