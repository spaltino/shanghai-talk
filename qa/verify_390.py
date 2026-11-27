import asyncio, json
from playwright.async_api import async_playwright

URL = "https://spaltino.github.io/shanghai-talk/?cb=v24"
OUT = "/workspace/work/shanghai-talk/qa"

async def main():
    errs = []
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width":390,"height":844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        pg = await ctx.new_page()
        pg.on("console", lambda m: errs.append(("console", m.type, m.text)) if m.type in ("error","warning") else None)
        pg.on("pageerror", lambda e: errs.append(("pageerror", str(e))))
        r = await pg.goto(URL, wait_until="networkidle")
        print("HTTP", r.status if r else None)
        try:
            await pg.evaluate("navigator.serviceWorker.ready")
        except Exception as e:
            print("SW ready err", e)
        await pg.wait_for_timeout(2500)
        print("cache keys:", await pg.evaluate("caches.keys()"))
        print("title:", await pg.title())

        # card count
        total = await pg.evaluate("document.querySelectorAll('[data-card]').length")
        print("home rendered cards (should be 0):", total)

        def overflow_js():
            return """() => {
              const w = document.documentElement.clientWidth;
              const bad = [];
              document.querySelectorAll('body *').forEach(el=>{
                const r = el.getBoundingClientRect();
                if (r.width === 0 || r.height === 0) return;
                const cs = getComputedStyle(el);
                if (cs.visibility === 'hidden' || cs.display === 'none') return;
                if (r.right > w + 0.6 || r.left < -0.6) {
                  bad.push((el.tagName+'.'+(el.className||'')).slice(0,60)+' right='+r.right.toFixed(1)+' left='+r.left.toFixed(1));
                }
              });
              return {w, scrollW: document.documentElement.scrollWidth, bad: bad.slice(0,15), n: bad.length};
            }"""

        print("home overflow:", json.dumps(await pg.evaluate(overflow_js()), ensure_ascii=False))
        await pg.screenshot(path=f"{OUT}/01-home-390.png", full_page=False)

        FORBID = ["5毫克", "wǔ háokè", "두 달", "两个月", "처방받아", "약통", "이미 복용"]
        per_place = {}
        for pid in ["hospital","pharmacy","taxi","airport","store","help"]:
            await pg.click(f'[data-place="{pid}"]')
            await pg.wait_for_timeout(250)
            ov = await pg.evaluate(overflow_js())
            if ov["n"]:
                print(f"[{pid}] scene-list overflow:", json.dumps(ov, ensure_ascii=False))
            nscene = await pg.evaluate("document.querySelectorAll('[data-scene]').length")
            for si in range(nscene):
                await pg.click(f'[data-scene="{si}"]')
                await pg.wait_for_timeout(180)
                data = await pg.evaluate("""() => Array.from(document.querySelectorAll('[data-card]')).map(c=>({
                    zh: c.querySelector('.zh').textContent, py: c.querySelector('.py').textContent, ko: c.querySelector('.ko').textContent}))""")
                name = await pg.evaluate("document.getElementById('ledeScene').textContent")
                ov2 = await pg.evaluate(overflow_js())
                if ov2["n"]:
                    print(f"[{pid}/{si} {name}] card overflow:", json.dumps(ov2, ensure_ascii=False))
                for i,c in enumerate(data):
                    joined = c["zh"]+c["py"]+c["ko"]
                    for f in FORBID:
                        if f in joined:
                            print(f"!! FORBIDDEN '{f}' in {pid}/{name} card {i+1}: {joined[:120]}")
                per_place.setdefault(pid, []).append((name, len(data)))
                if pid=="hospital" and si in (1,4):
                    await pg.screenshot(path=f"{OUT}/02-{pid}-scene{si}-390.png")
                if pid=="pharmacy" and si in (0,1):
                    await pg.screenshot(path=f"{OUT}/03-{pid}-scene{si}-390.png")
                await pg.click("#btnBack"); await pg.wait_for_timeout(180)
                await pg.click(f'[data-scene="{si}"]') if False else None
                # go back to scene list properly
                await pg.click(f'[data-scene="{si}"]') if False else None
                await pg.click("#btnBack"); await pg.wait_for_timeout(150)
                # now on place list? check
                if await pg.evaluate("document.getElementById('view1').hidden === false"):
                    await pg.click(f'[data-place="{pid}"]'); await pg.wait_for_timeout(200)
            await pg.click("#btnHome"); await pg.wait_for_timeout(200)
        print("scene card counts:", json.dumps(per_place, ensure_ascii=False))

        # 2.5mg presence
        cnt = await pg.evaluate("""() => {
            const t = document.documentElement.innerHTML;
            return {mg25: (t.match(/2\\.5毫克/g)||[]).length, mg5: (t.match(/5毫克/g)||[]).length};
        }""")
        print("mg counts in DOM:", cnt)
        print("errors:", json.dumps(errs, ensure_ascii=False)[:2000])
        await b.close()

asyncio.run(main())
