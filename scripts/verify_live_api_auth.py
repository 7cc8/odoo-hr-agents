# -*- coding: utf-8 -*-
import json
import os
import sys
import urllib.error
import urllib.request
import dotenv

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

dotenv.load_dotenv()
token = os.getenv("WRITE_API_TOKEN", "").strip()
if not token:
    sys.exit("WRITE_API_TOKEN غير مضبوط: اضبط رمز الكتابة الفعلي للخادم في البيئة أو ملف .env ثم أعد التشغيل.")

print("==================================================")
print("اختبار مصادقة واجهة API الحية (/api/sijil/recent)")
print("==================================================")

# 1. طلب بدون توكن (Unauthenticated Request)
url = "http://127.0.0.1:8000/api/sijil/recent?limit=5"
try:
    urllib.request.urlopen(url)
    print("❌ خطأ: تم قبول الطلب غير المصرح به بدون توكن!")
except urllib.error.HTTPError as err:
    print(f"1. طلب بدون توكن: تم الرفض بنجاح بحالة HTTP {err.code} ({err.reason})")
    body = err.read().decode("utf-8")
    print(f"   نص الاستجابة: {body}")

# 2. طلب مع توكن صحيح مع إخفاء القيمة الفعلية
req = urllib.request.Request(url, headers={"X-API-Key": token})
try:
    with urllib.request.urlopen(req) as resp:
        print(f"2. طلب بتوكن مصرح [REDACTED]: تم القبول بنجاح بحالة HTTP {resp.status} ({resp.reason})")
        data = json.loads(resp.read().decode("utf-8"))
        print(f"   المفاتيح المعادة: {list(data.keys())}")
        print(f"   إجمالي السجلات: {data.get('total')}, الحد: {data.get('limit')}, الإزاحة: {data.get('offset')}")
        print(f"   عدد السجلات المسترجعة بالصفحة: {len(data.get('operations', []))}")
        if data.get('operations'):
            first_op = data['operations'][0]
            print(f"   السجل الأول: معرف={first_op.get('identifier')}, نوع={first_op.get('type')}, حالة={first_op.get('status')}")
except Exception as exc:
    print(f"❌ خطأ في الطلب المصرح: {exc}")
