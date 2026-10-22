# دليل الـ validator وموفّق (مضبوط على الكود)

> كل ما في هذا الملف مأخوذ من الكود نفسه (`validator.py` و`failure_codes.py` و`matching_thresholds.py`
> و`musleh_service.py` و`agents/muwaffaq_agent.py`) وليس من وصف عام. ما لا يفعله النظام مذكور صراحة.
> إذا تغيّر الكود فحدّث هذا الملف؛ الاختبار `tests/test_failure_code_status_consistency.py` يحرس تطابق الأكواد والحالات.

## 1. موقع الـ validator في المسار

`parser.py` (قراءة الملف وتطبيع القيم وحساب `row_hash`) ← **`validator.py`** (قراءة فقط من Odoo، لا يكتب) ←
تقرير dry-run ← اعتماد ← `writer.py`. الصفوف `needs_review` و`rejected` يعالجها «مصلح» (`musleh_service.py`) عند طلبه.

الـ validator **لا يحسب** `run_id` ولا `row_hash` ولا `source_hash`؛ يمرّرها كما وصلت من المحلل. وهي تجزئات (hash)، لا تشفير.

## 2. ترتيب الفحص (كما في الكود) والنتيجة

| # | الفحص | الحالة | الكود |
|---|-------|--------|-------|
| 1 | علامة المحلل `duplicate_in_file` | needs_review | `duplicate_in_file` |
| 2 | اسم الموظف فارغ | rejected | `validation_error` |
| 3 | صيغة البريد غير صالحة (إن وُجد بريد) | rejected | `invalid_work_email` |
| 4 | الشركة غير موجودة | rejected | `reference_not_found` |
| 4 | الشركة تطابق أكثر من سجل | needs_review | `reference_ambiguous` |
| 4 | الشركة مؤرشفة | needs_review | `archived_reference_match` |
| 5 | القسم (إن كُتب) غير موجود في هذه الشركة | rejected | `reference_not_found` (مع «أقرب تطابق» إن وُجد) |
| 5 | القسم ملتبس / مؤرشف | needs_review | `reference_ambiguous` / `archived_reference_match` |
| 6 | المسمى الوظيفي (إن كُتب): نفس قواعد القسم | — | — |
| 7 | فشل البحث عن البريد في Odoo | needs_review | `duplicate_check_unavailable` |
| 7 | موظف واحد بنفس البريد | needs_review | `duplicate_existing_employee` |
| 7 | أكثر من موظف بنفس البريد | needs_review | `ambiguous_duplicate` |
| 8 | لا بريد ولا جوال | needs_review | `insufficient_duplicate_signal` |
| 9 | علامة المحلل `possible_duplicate_in_file` (اسم + جوال متطابقان داخل الملف) | needs_review | `possible_duplicate_in_file` |
| 10 | لا بريد لكن فيه جوال | needs_review | `unverified_no_email` |
| 11 | اجتاز كل ما سبق | **accepted** | — |

تفاصيل مهمة:
- الأقسام والمسميات تُطابق **داخل الشركة المحددة فقط**، مطابقة تامة على `reference_match_key`. والقسم يُطابق على اسمه الكامل
  (`complete_name`، مثل «الإدارة العليا / الموارد البشرية»).
- فحص البريد في Odoo **يفشل مغلقاً**: إذا رمى البحث خطأً يصير الصف `needs_review` ولا يُقبل بصمت.
- «أقرب تطابق» في رسالة الرفض اقتراح نصي فقط؛ الصف يبقى `rejected` ولا يتغير شيء.

## 3. ما لا يفحصه الـ validator

- `hiring_date` وصيغة الجوال ورقم الهوية والراتب وأي قاعدة من نظام العمل. (المحلل يطبّع التاريخ والجوال كنص ولا يتحقق منهما أيضاً.)
- التكرار مقابل Odoo **بالبريد فقط** (مطابقة تامة بعد lower/strip). موظف أُعيد إرساله ببريد مختلف يمر `accepted`.
  الاسم والجوال لا يُفحصان مقابل Odoo.

لذلك `accepted` تعني «اجتاز هذه الفحوصات»، وليست «البيانات صحيحة 100%».

## 4. التطبيع (للمطابقة فقط، لا للقيم المخزّنة)

`normalization.py` → `generic_match_key` (وعليه `name_match_key` و`reference_match_key`):
`ى`→`ي`، `ک`→`ك`، `أ إ آ ٱ`→`ا`، `ة`→`ه`، حذف التشكيل والتطويل والرموز غير المرئية، الأرقام العربية/الفارسية→لاتينية،
توحيد المسافات، lower. المفاتيح تدخل في `row_hash`، فتغيير التطبيع يعني إعادة dry-run لأي اعتماد قديم.

## 5. موفّق: ما هو فعلاً

`MuwaffaqAgent` في `agents/muwaffaq_agent.py`: كلاس **قواعد بدون LLM** بحلقة perceive/plan/execute/reflect.

| الاستراتيجية | الحالة |
|--------------|--------|
| exact | `strip().lower()` فقط. **لا** يوحّد الألف ولا التاء المربوطة (`أحمد` ≠ `احمد`). |
| fuzzy | `difflib.SequenceMatcher`، يُبقي المرشحين ≥ 0.60 |
| contextual | مثل fuzzy مع +0.15 إذا كان المرشح في نفس القسم |
| phonetic | **غير منفّذة** (ترجع قائمة فارغة) |
| semantic | **غير منفّذة** (TODO، تنتظر embeddings) |

القرار: ≥ 0.90 → `ACCEPT_MATCH`، ≥ 0.70 → `PROPOSE_MATCH`، يوجد مرشح لكن دون 0.70 → `REQUEST_REVIEW`،
لا مرشح ≥ 0.60 → `REJECT_NO_MATCH`. الثابت `MUWAFFAQ_LOW_CONFIDENCE` (0.50) معرَّف ولا يُقرأ في القرار.

**أين يُستخدم:** عقدة `muwaffaq_match` في رسم LangGraph، و`agents/seraj_meta_agent.py`، وسكربت النشر والاختبارات.
**لا** يستدعيه الويب ولا مسار Excel.
وقسم «موفّق» داخل `musleh_service.py` (`muwaffaq_report`) هو كود `difflib` خاص بالخدمة، وليس هذا الوكيل.

## 6. العتبات ومعنى «الثقة»

كل العتبات في `matching_thresholds.py`. الثقة = `2×(الحروف المتطابقة)÷(مجموع طولي النصين)` من `SequenceMatcher.ratio()`:
نسبة تشابه شكلي، **ليست احتمال صحة** ولم تُعايَر على بيانات حقيقية. مثال: «تقنية معلومات» مقابل «تقنية المعلومات» = 0.9286.

| الثابت | القيمة | أين | المعنى |
|--------|--------|-----|--------|
| `AUTO_REPAIR_MIN_CONFIDENCE` | 0.90 | مصلح | تطبيق رقعة تلقائياً. **فقط** مع `auto_repair=True` (الافتراضي False) |
| `PROPOSE_PATCH_MIN_CONFIDENCE` | 0.80 | مصلح | اقتراح رقعة قسم/مسمى |
| `PROPOSE_MISSING_ENTITY_BELOW_CONFIDENCE` | 0.60 | مصلح | أدنى منها والمرجع غير موجود → اقتراح إنشاء كيان |
| `FUZZY_CANDIDATE_CUTOFF` | 0.50 | مصلح | حد جمع المرشحين (`get_close_matches`) |
| `CLOSEST_MATCH_SUGGESTION_CUTOFF` | 0.60 | validator | اقتراح «أقرب تطابق» في رسالة الرفض |
| `MUWAFFAQ_HIGH/MEDIUM/LOW_CONFIDENCE` | 0.90 / 0.70 / 0.50 | موفّق | قبول / اقتراح / (LOW غير مستخدم) |
| `MUWAFFAQ_MIN_CANDIDATE_SIMILARITY` | 0.60 | موفّق | أدنى تشابه لبقاء مرشح |
| `MUWAFFAQ_SAME_DEPARTMENT_BOOST` | 0.15 | موفّق | تعزيز نفس القسم |
| `MISSING_ENTITY_PROPOSAL_CONFIDENCE` | 0.95 | مصلح | قيمة ثابتة تُلصق باقتراح الإنشاء، غير محسوبة |
| `STATIC_CONSULTATION_REPORT_CONFIDENCE` | 0.85 | مصلح | قيمة ثابتة في تقرير الاستشارة، غير محسوبة ولا تدخل القرار |
| `ESCALATION_DECISION_CONFIDENCE` | 0.50 | مصلح | قيمة افتراضية لقرار الإحالة للإنسان، غير محسوبة |

مجموعتان منفصلتان: حدود موفّق (0.90/0.70) غير حدود مصلح (0.90/0.80). لا تُخلط.
