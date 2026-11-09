import asyncio
import os
from playwright.async_api import async_playwright

BASE_DIR = os.path.abspath("justtemp/ideas-preview")
CAPTURAS_DIR = os.path.join(BASE_DIR, "capturas")

async def test_lab():
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = await p.chromium.launch(headless=True)
            
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        
        errors = []
        page.on("console", lambda msg: errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type in ["error"] else None)
        page.on("pageerror", lambda err: errors.append(f"PAGEERROR: {err}"))

        url = f"file:///{os.path.join(BASE_DIR, 'lab.html').replace(os.sep, '/')}"
        await page.goto(url)
        await page.wait_for_timeout(300)

        # 1. Lab 1: Reparent FLIP
        card1 = page.locator("#card-lab-1")
        await card1.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-01-before.png"))
        await page.click("#btn-run-1")
        await page.wait_for_timeout(450)
        await card1.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-01-after.png"))

        # 2. Lab 2: Spring solver
        card2 = page.locator("#card-lab-2")
        await card2.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-02-before.png"))
        await page.click("#btn-run-2")
        await page.wait_for_timeout(650)
        await card2.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-02-after.png"))

        # 3. Lab 3: Parabolic Flight
        card3 = page.locator("#card-lab-3")
        await card3.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-03-before.png"))
        await page.click("#btn-run-3")
        await page.wait_for_timeout(550)
        await card3.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-03-after.png"))

        # 4. Lab 4: Distance Stagger
        card4 = page.locator("#card-lab-4")
        await card4.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-04-before.png"))
        await page.click("#btn-run-4")
        await page.wait_for_timeout(400)
        await card4.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-04-after.png"))

        # 5. Lab 5: 3-Piece Scaler
        card5 = page.locator("#card-lab-5")
        await card5.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-05-before.png"))
        await page.click("#btn-run-5")
        await page.wait_for_timeout(450)
        await card5.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-05-after.png"))

        # 6. Lab 6: Adaptive Streamer
        card6 = page.locator("#card-lab-6")
        await card6.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-06-before.png"))
        await page.click("#btn-run-6")
        await page.wait_for_timeout(800)
        await card6.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-06-after.png"))

        # 7. Lab 7: pathLength=1 Vector Drawing
        card7 = page.locator("#card-lab-7")
        await card7.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-07-before.png"))
        await page.click("#btn-run-7")
        await page.wait_for_timeout(450)
        await card7.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-07-after.png"))

        # 8. Lab 8: Obstacle-Avoiding Guide Line
        card8 = page.locator("#card-lab-8")
        await card8.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-08-before.png"))
        await page.click("#btn-run-8")
        await page.wait_for_timeout(650)
        await card8.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-08-after.png"))

        # Full page lab screenshot
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "lab-full.png"))

        await browser.close()
        print(f"LAB TESTS COMPLETE: {len(errors)} errors found.")
        for e in errors:
            print(f"  {e}")

if __name__ == "__main__":
    asyncio.run(test_lab())

