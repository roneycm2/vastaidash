import asyncio
import tempfile

from patchright.async_api import async_playwright


async def main():
    data_path = r"C:\Users\outros\liderbet\plugin"

    # Cria diretório temporário que será excluído automaticamente
    with tempfile.TemporaryDirectory() as user_data_dir:
        print(f"📁 Diretório temporário: {user_data_dir}")

        async with async_playwright() as p:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                args=[
                    f'--disable-extensions-except={data_path}',
                    f'--load-extension={data_path}',
                ],
            )

            page = await browser.new_page()

            try:
                await page.goto("https://anti-captcha.com/demo/?page=recaptcha_v2_textarea", wait_until="networkidle")
            except Exception as e:
                print(f"Error while loading the page: {e}")

            # Disable navigation timeout errors
            page.set_default_navigation_timeout(0.0)

            # Fill in the login field
            await page.fill('#login', "Test login")

            # Fill in the password field
            await page.fill('#password', "Test password")
            
            await page.wait_for_selector('.antigate_solver.solved')
            print("reCAPTCHA Solved")

            await asyncio.gather(
                page.click('#submitButton'),
                page.wait_for_navigation(wait_until="networkidle0")
            )

            print('Task completed, form with reCaptcha bypassed')

            # Close the browser
            await browser.close()

        print("🗑️ Diretório temporário excluído!")


asyncio.run(main())
