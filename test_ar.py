import sys, time, json
from laya import Router

sys.stdout.reconfigure(encoding="utf-8")

QUESTIONS = {
    "request_type": {
        "type": "choice",
        "instructions": "ما نوع طلب الموظف الأساسي؟",
        "criteria": {
            "leave": "طلب إجازة أو استئذان أو غياب",
            "payroll": "استفسار أو اعتراض على الراتب أو الخصومات أو البدلات",
            "attendance": "مشكلة في البصمة أو الحضور والانصراف",
            "other": "أي شيء آخر لا ينتمي للأقسام السابقة",
        },
    },
    "urgency": {
        "type": "score",
        "instructions": "ما مدى استعجال الطلب؟",
        "criteria": ["غير مستعجل", "خلال أسبوع", "عاجل"],
    },
    "needs_manager": {
        "type": "noul",
        "instructions": "هل يحتاج الطلب موافقة المدير المباشر؟",
    },
}

DATA = [
    ("فصحى", "أرجو الموافقة على إجازة اعتيادية من العاشر إلى الرابع عشر من الشهر القادم.", "leave"),
    ("فصحى", "لاحظت وجود خصم غير مبرر في راتب الشهر الماضي، أرجو المراجعة.", "payroll"),
    ("فصحى", "جهاز البصمة لم يسجل حضوري صباح أمس رغم وجودي في الدوام.", "attendance"),
    ("فصحى", "أرغب في الحصول على شهادة تعريف بالراتب لتقديمها للبنك.", "other"),
    ("سعودي", "السلام عليكم، ابغى إجازة من يوم الأحد الجاي لين الخميس.", "leave"),
    ("سعودي", "الراتب نزل ناقص ٣٠٠ ريال وما أدري ليش، ممكن تشيكون؟", "payroll"),
    ("سعودي", "البصمة ما قرت إصبعي اليوم وطلعت غايب، وانا داوم من ٧.", "attendance"),
    ("سعودي", "وين اطلع كرت الموظف؟ ضاع مني وابغى بدله.", "other"),
    ("مختلط", "ابغى annual leave من 20 لين 25 اذا ممكن.", "leave"),
    ("مختلط", "الـ payslip فيه deduction غريب، ابغى اعرف السبب.", "payroll"),
    ("مختلط", "الـ fingerprint ما سجل check-in اليوم.", "attendance"),
    ("مختلط", "ابغى طلب HR letter للسفارة.", "other"),
]

def get_choice(ans):
    if isinstance(ans, str):
        return ans
    if isinstance(ans, dict):
        for k in ("choice", "label", "answer", "value", "prediction"):
            if k in ans:
                return str(ans[k])
    return str(ans)

router = Router()

print("=== مثال تفصيلي ===")
t0 = time.time()
r = router.predict(DATA[5][1], QUESTIONS, model="multilingual")
print(f"الزمن: {(time.time() - t0) * 1000:.0f} ms")
print(json.dumps(r, ensure_ascii=False, indent=2, default=str))

print("\n=== اختبار الدقة ===")
stats = {}
for group, text, expected in DATA:
    r = router.predict(text, QUESTIONS, model="multilingual")
    got = get_choice(r["answers"]["request_type"])
    ok = got == expected
    s = stats.setdefault(group, [0, 0])
    s[0] += ok
    s[1] += 1
    print(f"[{'OK ' if ok else 'XX '}] {group:6} متوقع={expected:10} طلع={got:10} | {text[:40]}")

print()
total_ok = sum(s[0] for s in stats.values())
total = sum(s[1] for s in stats.values())
for g, (a, b) in stats.items():
    print(f"{g}: {a}/{b} = {a / b:.0%}")
print(f"الإجمالي: {total_ok}/{total} = {total_ok / total:.0%}")