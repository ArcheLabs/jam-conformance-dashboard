import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(
            'https://www.notion.so/2ef96f88d0a78051b94ef4a6d6c9be8c?v=2ef96f88d0a78036b33a000c2cb9a0b1',
            wait_until='domcontentloaded', timeout=30000
        )
        await asyncio.sleep(8)
        c = await page.evaluate(
            "() => document.querySelectorAll('a[href*=\"attestation/0x\"]').length"
        )
        print(f'Attestation links: {c}')
        await browser.close()

asyncio.run(main())
