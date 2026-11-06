"""مقر شركة سراج الذكي (Odoo HR HQ) — مشغل الخادم المحلي الفوري.
يقوم هذا السكريبت بتشغيل خادم محلي مصغر وفتح واجهة المقر مباشرة في المتصفح.
"""

from __future__ import annotations

import http.server
import os
import socketserver
import sys
import webbrowser
from pathlib import Path

PORT = 5174

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # تفعيل تسجيل نظيف
        sys.stdout.write(f"[{self.log_date_time_string()}] {args[0]} {args[1]}\n")

def main():
    hq_dir = Path(__file__).resolve().parent
    os.chdir(hq_dir)

    url = f"http://localhost:{PORT}/index.html"
    print("=" * 65)
    print(" 👑 مقر شركة سراج الذكي لوكلاء الموارد البشرية | Odoo HR HQ")
    print(f" 🌐 جاري التشغيل على الرابط: {url}")
    print(" 🚪 اضغط Ctrl+C لإيقاف الخادم")
    print("=" * 65)

    try:
        # السماح بإعادة استخدام المنفذ فورياً
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
            # فتح المتصفح تلقائياً
            webbrowser.open(url)
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[OK] تم إيقاف خادم المقر بنجاح.")
    except OSError as e:
        print(f"\n[!] المنفذ {PORT} مستخدم أو غير متاح ({e}). سيتم فتح الملف مباشرة في المتصفح...")
        webbrowser.open(str(hq_dir / "index.html"))

if __name__ == "__main__":
    main()
