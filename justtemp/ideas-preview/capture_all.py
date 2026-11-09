import asyncio
import os
import time
from playwright.async_api import async_playwright

BASE_DIR = os.path.abspath("justtemp/ideas-preview")
CAPTURAS_DIR = os.path.join(BASE_DIR, "capturas")

files = [
    {
        "id": "01-analizador",
        "file": "analizador.html",
        "action": async_playwright
    }
]

async def run():
    async with async_playwright() as p:
        # Launch browser with msedge channel or chromium
        try:
            browser = await p.chromium.launch(channel="msedge", headless=True)
        except Exception:
            browser = await p.chromium.launch(headless=True)
            
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        errors = {}

        def setup_listeners(filename):
            errors[filename] = []
            page.on("console", lambda msg: errors[filename].append(f"CONSOLE {msg.type}: {msg.text}") if msg.type in ["error", "warning"] else None)
            page.on("pageerror", lambda err: errors[filename].append(f"PAGEERROR: {err}"))

        # 0. Portal Index
        setup_listeners("index.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'index.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(300)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "00-portal-index.png"))

        # 1. Analizador
        setup_listeners("analizador.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'analizador.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "01-analizador-antes.png"))
        await page.click("#start-btn")
        await page.wait_for_timeout(500)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "01-analizador-اثناء.png"))
        await page.wait_for_timeout(1800)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "01-analizador-بعد.png"))

        # 2. Registro
        setup_listeners("registro.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'registro.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "02-registro-antes.png"))
        await page.click("#stamp-btn")
        await page.wait_for_timeout(260) # Mid flight parabolic arc
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "02-registro-اثناء.png"))
        await page.wait_for_timeout(400)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "02-registro-بعد.png"))

        # 3. Visor Fichas
        setup_listeners("visor-fichas.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'visor-fichas.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "03-visor-fichas-antes.png"))
        await page.click('.card[data-id="1"]')
        await page.wait_for_timeout(200) # Expanding circular clip-path
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "03-visor-fichas-اثناء.png"))
        await page.wait_for_timeout(400)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "03-visor-fichas-بعد.png"))

        # 4. Desplegador
        setup_listeners("desplegador.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'desplegador.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "04-desplegador-antes.png"))
        await page.click("#start-btn")
        await page.wait_for_timeout(1450) # Step 2 shake failure & retry
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "04-desplegador-اثناء.png"))
        await page.wait_for_timeout(2500) # Folded summary bar
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "04-desplegador-بعد.png"))

        # 5. Alcancia
        setup_listeners("alcancia.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'alcancia.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "05-alcancia-antes.png"))
        await page.click("#commit-btn")
        await page.wait_for_timeout(180) # Particles flying, morphing card
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "05-alcancia-اثناء.png"))
        await page.wait_for_timeout(600) # Morphed floating button
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "05-alcancia-بعد.png"))

        # 6. Control Stock
        setup_listeners("control-stock.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'control-stock.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "06-control-stock-antes.png"))
        await page.click('button.chip[data-idx="1"]')
        await page.click('button.chip[data-idx="2"]')
        await page.wait_for_timeout(150)
        await page.click("#rewind-btn")
        await page.wait_for_timeout(180) # Mid rewind step
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "06-control-stock-اثناء.png"))

        # 7. Agenda Bloques
        setup_listeners("agenda-bloques.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'agenda-bloques.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "07-agenda-bloques-antes.png"))
        # Pin first block
        await page.click('.shift-block[data-id="1"] .pin-btn')
        # Lift second block with mouse down
        box = await page.locator('.shift-block[data-id="2"]').bounding_box()
        if box:
            await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            await page.mouse.down()
            await page.wait_for_timeout(200)
            await page.screenshot(path=os.path.join(CAPTURAS_DIR, "07-agenda-bloques-اثناء.png"))
            await page.mouse.up()

        # 8. Consola Comandos
        setup_listeners("consola-comandos.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'consola-comandos.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "08-consola-comandos-antes.png"))
        await page.click('.template-chip[data-cmd="audit --verify-signatures"]')
        await page.wait_for_timeout(450) # Hero ghost faded, terminal typing
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "08-consola-comandos-اثناء.png"))

        # 9. Validador Acceso
        setup_listeners("validador-acceso.html")
        await page.goto(f"file:///{os.path.join(BASE_DIR, 'validador-acceso.html').replace(os.sep, '/')}")
        await page.wait_for_timeout(200)
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "09-validador-acceso-antes.png"))
        await page.click("#request-auth-btn")
        await page.wait_for_timeout(200) # Dialog open
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "09-validador-acceso-اثناء.png"))
        await page.click("#confirm-btn")
        await page.wait_for_timeout(500) # Gauge at 100%
        await page.screenshot(path=os.path.join(CAPTURAS_DIR, "09-validador-acceso-بعد.png"))

        await browser.close()

        print("=== CONSOLE ERRORS SUMMARY ===")
        for f, err_list in errors.items():
            clean_errs = [e for e in err_list if "error" in e.lower() or "pageerror" in e.lower()]
            print(f"{f}: {len(clean_errs)} errors")
            for err in clean_errs:
                print(f"   {err}")
        print("=== CAPTURE COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(run())

