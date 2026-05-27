import asyncio
from playwright.async_api import async_playwright

async def run():
    cookie_value = "AQEDATev1kMFDbb2AAABnj6uvwcAAAGehsxzO1YARyp-8QUtzYy9vpe_rSraahSFuJcN5DPlk7C48NOT4KsMk_wX0yveABinHfL1Fg-2vdm4UIGIYk9E9dqUTmPo5lxtLDhcSk1SjUsTtukWRFWBgrVL"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies([{
            "name": "li_at",
            "value": cookie_value,
            "domain": ".linkedin.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None"
        }])
        page = await context.new_page()
        try:
            print("Navigating to feed...")
            await page.goto("https://www.linkedin.com/feed/", wait_until="commit", timeout=15000)
            print("Successfully reached:", page.url)
            print("Page title:", await page.title())
        except Exception as e:
            print("Error during navigation:", str(e))
        finally:
            await browser.close()

asyncio.run(run())
