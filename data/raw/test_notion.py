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

        title = await page.title()
        print(f'Title: {title}')

        count = await page.evaluate(
            '() => document.querySelectorAll(\'a[href*="attestation/0x"]\').length'
        )
        print(f'Attestation links: {count}')

        if count > 17:
            hashes = await page.evaluate('''
                () => Array.from(document.querySelectorAll('a[href*="attestation/0x"]'))
                    .map(a => a.getAttribute('href').split('attestation/')[1].split('?')[0].trim())
            ''')
            print(f'All {len(hashes)} hashes:')
            for h in hashes:
                print(f'  {h}')
        else:
            # Debug: show all links
            links = await page.evaluate('''
                () => Array.from(document.querySelectorAll('a'))
                    .filter(a => a.getAttribute('href'))
                    .map(a => ({ href: a.getAttribute('href').substring(0, 100), text: (a.textContent||'').trim().substring(0, 50) }))
            ''')
            print(f'All links ({len(links)}):')
            for l in links:
                print(f'  {l["text"][:50]:50s} {l["href"][:80]}')

        await browser.close()

asyncio.run(main())
