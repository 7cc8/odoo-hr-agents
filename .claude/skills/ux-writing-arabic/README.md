# ux-writing-arabic

**دليل احترافي لكتابة نصوص واجهة المستخدم بالعربية**
An expert guide for writing Arabic UI text — buttons, errors, empty states, microcopy, and more.

---

## ما هو هذا المشروع؟ · What is this?

مهارة ذكاء اصطناعي تحمّل دليل أسلوب المحتوى العربي الكامل مباشرةً داخل أي محادثة مع الـ AI.
بمجرد تثبيتها، يعرف الـ agent كيف يكتب ويراجع أي نص عربي في الواجهات بشكل صحيح.

An AI skill that injects a complete Arabic content style guide into any agent conversation.
Once installed, the agent knows how to write and review any Arabic UI text correctly.

**يُستخدم لـ · Use for:**

- أزرار، تسميات، إشعارات · Buttons, labels, notifications
- رسائل الخطأ والنجاح · Error & success messages
- الحالات الفارغة · Empty states
- النصوص المصغّرة (Microcopy) · Microcopy
- تدفقات الإعداد · Onboarding flows

---

## التثبيت · Installation

### الأمر الصحيح · The correct command

```bash
npx skills add itady74/ux-writing-arabic --yes
```

> الـ `--yes` مهم. من غيره الـ CLI بيوقفك عند prompt تختار فيه الـ agents يدويًا.
> The `--yes` flag is required. Without it the CLI pauses at an interactive agent-selector prompt.

---

### ايه اللي بيحصل لما تشغّل الأمر · What happens when you run it

```
◇  Source: https://github.com/itady74/ux-writing-arabic.git
◇  Repository cloned
◇  Found 1 skill

●  Skill: ux-writing-arabic
│  دليل شامل لكتابة تجربة المستخدم (UX Writing) والتصميم المحتوى العربي.

◇  41 agents
●  Installing to: Antigravity, Claude Code, Codex, Cursor, Gemini CLI, OpenCode

◇  Installation Summary
│  .agents/skills/ux-writing-arabic
│    universal: Codex, Cursor, Gemini CLI, OpenCode, Amp +3 more
│    symlink → Antigravity, Claude Code

◇  Installation complete
✓  Installed 1 skill
```

الـ CLI بيعمل 3 حاجات تلقائيًا:

1. يـ clone الـ repo من GitHub
2. يحط الملفات في `.agents/skills/ux-writing-arabic` (المسار العالمي)
3. يعمل symlinks لـ Antigravity و Claude Code في مساراتهم الخاصة

The CLI automatically:

1. Clones the repo from GitHub
2. Places files in `.agents/skills/ux-writing-arabic` (the universal path)
3. Creates symlinks for Antigravity and Claude Code in their dedicated paths

---

### الـ agents المدعومة وطريقة التثبيت · Supported agents & how they connect

| Agent                                         | النوع     | المسار                             |
| --------------------------------------------- | --------- | ---------------------------------- |
| **Antigravity**                               | Symlink   | `.agent/skills/ux-writing-arabic`  |
| **Claude Code**                               | Symlink   | `.claude/skills/ux-writing-arabic` |
| **Cursor**                                    | Universal | `.agents/skills/ux-writing-arabic` |
| **Codex**                                     | Universal | `.agents/skills/ux-writing-arabic` |
| **Gemini CLI**                                | Universal | `.agents/skills/ux-writing-arabic` |
| **OpenCode**                                  | Universal | `.agents/skills/ux-writing-arabic` |
| **Amp, Cline, GitHub Copilot, Kimi Code CLI** | Universal | `.agents/skills/ux-writing-arabic` |

> **Universal** = الملفات موجودة فعلاً في الـ path ده.
> **Symlink** = الـ agent بيشوف نفس الملفات عن طريق shortcut من مساره الخاص.

---

### لو ظهرلك prompt التحديد (بدون `--yes`) · If the agent-selector prompt appears

لو نسيت الـ `--yes` وظهر الـ prompt ده:

```
◆  Which agents do you want to install to?
│  ── Universal (.agents/skills) ── always included ────────
│    • Amp  • Cline  • Codex  • Cursor  • Gemini CLI
│    • GitHub Copilot  • Kimi Code CLI  • OpenCode
│
│  ── Additional agents ──────────────────────────────────
│  ❯ ○ Antigravity (.agent/skills)
│    ○ Claude Code (.claude/skills)
│    ...
```

اضغط **Ctrl+C** واشغّل الأمر تاني مع `--yes`.
Press **Ctrl+C** and re-run with `--yes`.

---

### استدعاء المهارة بعد التثبيت · Using the skill after installation

```
/ux-writing-arabic راجع نص الزر ده: "إرسال"
/ux-writing-arabic اكتب رسالة خطأ لفشل الدفع
/ux-writing-arabic هل الحالة الفارغة دي صح؟ "لا توجد نتائج"
```

---

## محتوى المهارة · Skill Contents

| الملف          | المحتوى                    |
| -------------- | -------------------------- |
| `SKILL.md`     | الدليل الكامل — 8 أقسام    |
| `checklist.md` | قائمة مراجعة قبل الإطلاق   |
| `examples.md`  | أمثلة تطبيقية موسعة        |
| `glossary.md`  | مسرد المصطلحات ثنائي اللغة |
| `reference.md` | مرجع سريع للمصطلحات        |

---

## الجمهور المستهدف · Audience

كتّاب UX · مصممو منتجات · مطورو واجهات عربية · مديرو منتجات · استراتيجيو المحتوى

---

_v1.0.0 · MIT · itady74_
