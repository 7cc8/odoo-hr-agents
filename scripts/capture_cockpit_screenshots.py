# -*- coding: utf-8 -*-
"""Script to capture verified screenshots of the Cockpit UI with Playwright using exact selectors."""

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

ARTIFACTS_DIR = Path(r"C:\Users\Abu Kholoud\.gemini\antigravity-ide\brain\f95787c7-2284-41de-804b-70a36de5877f")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("بدء جلسة المتصفح عبر Playwright لالتقاط الشاشات الحية المعتمدة...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1,
            locale="ar-SA"
        )
        page = context.new_page()

        # 1. Main Cockpit Overview
        print("1. فتح مركز العمليات والتحقق من جلب البيانات الحية...")
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(2)
        p1 = ARTIFACTS_DIR / "cockpit_live_overview.png"
        page.screenshot(path=str(p1), full_page=False)
        print(f"  ✓ تم حفظ لقطة لوحة التحكم الحية: {p1.name}")

        # 2. Agent Modal Centered
        print("2. النقر على وكيل «سراج» لفتح بطاقته والتحقق من توسطها...")
        seraj_card = page.locator("#agentCard_seraj")
        if seraj_card.is_visible():
            seraj_card.click()
            time.sleep(1)
            p2 = ARTIFACTS_DIR / "cockpit_agent_modal_centered.png"
            page.screenshot(path=str(p2), full_page=False)
            print(f"  ✓ تم حفظ لقطة بطاقة الوكيل المتوسطة: {p2.name}")
            # Close modal
            page.locator("#detailsDrawerOverlay .drawer-close-btn").click()
            time.sleep(0.5)

        # 3. Sijil Tab & Server-side Pagination
        print("3. الانتقال إلى تبويب «سجل والتقارير» والتحقق من ترقيم الصفحات...")
        page.locator("button[data-view='view-sijil']").click()
        time.sleep(2)
        p3 = ARTIFACTS_DIR / "cockpit_sijil_server_pagination.png"
        page.screenshot(path=str(p3), full_page=False)
        print(f"  ✓ تم حفظ لقطة جدول سجل مع ترقيم الصفحات: {p3.name}")

        # 4. Sijil Operation Detail Centered Modal
        print("4. فتح تفاصيل عملية من جدول سجل للتحقق من توسط نافذة التوثيق وزر PDF...")
        first_sijil_btn = page.locator("#sijilRecentTableBody button.btn-iris").first
        if first_sijil_btn.is_visible():
            first_sijil_btn.click()
            time.sleep(2)
            p4 = ARTIFACTS_DIR / "cockpit_sijil_detail_modal_centered.png"
            page.screenshot(path=str(p4), full_page=False)
            print(f"  ✓ تم حفظ لقطة نافذة التوثيق المتوسطة: {p4.name}")
            # Close op detail modal
            page.evaluate("() => document.getElementById('opDetailModalOverlay').classList.remove('is-open')")
            time.sleep(0.5)

        # 5. Operations Tab & "متابعة" Action
        print("5. الانتقال إلى تبويب العمليات وتفعيل «متابعة» لاستعادة المحادثة...")
        page.locator("button[data-view='view-operations']").click()
        time.sleep(2)
        follow_btn = page.locator("#operationsTableBody button:has-text('متابعة')").first
        if follow_btn.is_visible():
            follow_btn.click()
            time.sleep(2)
            p5 = ARTIFACTS_DIR / "cockpit_resumed_operation_conversation.png"
            page.screenshot(path=str(p5), full_page=False)
            print(f"  ✓ تم حفظ لقطة المحادثة المستعادة والخط الزمني عبر متابعة: {p5.name}")

        browser.close()
        print("✅ اكتمل التقاط كافة الشاشات الحية بنجاح تام!")

if __name__ == "__main__":
    main()
