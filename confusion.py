import csv, collections, sys
sys.stdout.reconfigure(encoding="utf-8")

rows = list(csv.DictReader(open("results.csv", encoding="utf-8-sig")))
per = collections.defaultdict(lambda: [0, 0])
conf = collections.Counter()
for r in rows:
    per[r["expected"]][1] += 1
    per[r["expected"]][0] += int(r["ok"])
    if r["ok"] == "0":
        conf[(r["expected"], r["got"])] += 1

print("الدقة لكل فئة:")
for k, (a, b) in per.items():
    print(f"  {k:20} {a}/{b}")
print("\nأكثر الأخطاء تكرارًا (المتوقع -> طلع):")
for (e, g), n in conf.most_common():
    print(f"  {e:20} -> {g:20} x{n}")
ok = [float(r["answer_conf"]) for r in rows if r["ok"] == "1"]
bad = [float(r["answer_conf"]) for r in rows if r["ok"] == "0"]
print(f"\nمتوسط answer_conf للصحيح: {sum(ok)/len(ok):.2f} | للخطأ: {sum(bad)/len(bad):.2f}")