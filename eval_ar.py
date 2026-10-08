import csv, time, sys
from laya import Router

sys.stdout.reconfigure(encoding="utf-8")

QUESTIONS = {
    "request_type": {
        "type": "choice",
        "instructions": "ما نوع طلب الموظف الأساسي؟",
        "criteria": {
            "leave": "طلب إجازة أو استئذان أو غياب",
            "payroll": "استفسار أو اعتراض على الراتب أو الخصومات أو البدلات فقط، وليس طلب شهادة",
            "attendance": "مشكلة في البصمة أو الحضور والانصراف",
            "certificate_request": "طلب شهادة أو خطاب أو تعريف بالراتب أو العمل",
            "employee_card": "بطاقة الموظف أو الهوية أو بدل فاقد",
            "other": "أي شيء آخر لا ينتمي للأقسام السابقة",
        },
    }
}

router = Router()
router.predict("تسخين", QUESTIONS, model="multilingual")

rows = list(csv.DictReader(open("data.csv", encoding="utf-8-sig")))
out, stats = [], {}
for row in rows:
    t = time.time()
    r = router.predict(row["text"], QUESTIONS, model="multilingual")
    ms = (time.time() - t) * 1000
    a = r["answers"]["request_type"]
    ok = a["choice"] == row["expected"]
    s = stats.setdefault(row["group"], [0, 0]); s[0] += ok; s[1] += 1
    out.append({**row, "got": a["choice"], "ok": int(ok), "ms": round(ms),
                "answer_conf": a["answer_confidence"], "conf": a["confidence"]})

with open("results.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=out[0].keys()); w.writeheader(); w.writerows(out)

for g, (k, n) in stats.items():
    print(f"{g}: {k}/{n} = {k/n:.0%}")
print("متوسط الزمن ms:", round(sum(o["ms"] for o in out) / len(out)))