import asyncio
import os
from playwright.async_api import async_playwright

BASE_DIR = os.path.abspath("justtemp/ideas-preview")
RECREATE_DIR = os.path.join(BASE_DIR, "recreate")
CAPTURAS_DIR = os.path.join(BASE_DIR, "capturas")

async def test_recreate():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = await p.chromium.launch(headless=True)
            
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        errors = {}

        # 1. Test Despliegue Rebuild
        errors["despliegue-rebuild.html"] = []
        page.on("console", lambda msg: errors["despliegue-rebuild.html"].append(f"CONSOLE: {msg.text}") if msg.type in ["error"] else None)
        page.on("pageerror", lambda err: errors["despliegue-rebuild.html"].append(f"PAGEERROR: {err}"))

        url_desp = f"file:///{os.path.join(RECREATE_DIR, 'despliegue-rebuild.html').replace(os.sep, '/')}"
        await page.goto(url_desp)
        await page.wait_for_timeout(300)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "recreate-despliegue-before.png"))

        # Click Card 1 (#02)
        await page.click('.card[data-idx="1"]')
        await page.wait_for_timeout(180) # Mid expansion & sinking
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "recreate-despliegue-during.png"))

        await page.wait_for_timeout(450) # Fully open
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "recreate-despliegue-after.png"))

        # Close it
        await page.click("#btn-close")
        await page.wait_for_timeout(400)

        # 2. Test Charla Rebuild
        errors["charla-rebuild.html"] = []
        page.on("console", lambda msg: errors["charla-rebuild.html"].append(f"CONSOLE: {msg.text}") if msg.type in ["error"] else None)
        page.on("pageerror", lambda err: errors["charla-rebuild.html"].append(f"PAGEERROR: {err}"))

        url_charla = f"file:///{os.path.join(RECREATE_DIR, 'charla-rebuild.html').replace(os.sep, '/')}"
        await page.goto(url_charla)
        await page.wait_for_timeout(300)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "recreate-charla-before.png"))

        # Click Pill 1
        await page.click("#pill-1")
        await page.wait_for_timeout(240) # Mid parabolic flight
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "recreate-charla-during.png"))

        await page.wait_for_timeout(600) # Landed & checkmark drawn
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "recreate-charla-after.png"))

        await browser.close()

        print("=== RECREATE TEST RESULTS ===")
        for f, errs in errors.items():
            print(f"{f}: {len(errs)} errors")
            for e in errs:
                print(f"  {e}")

if __name__ == "__main__":
    asyncio.run(test_recreate())

