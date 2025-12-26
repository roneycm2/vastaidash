"""
Teste Proxy via Playwright CDP - Método da Documentação
https://docs.browserless.io/baas/features/proxies#using-proxies-with-playwright
"""
import asyncio
from playwright.async_api import async_playwright

TOKEN = "2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72"
WS_ENDPOINT = f"wss://production-sfo.browserless.io?token={TOKEN}"

# Proxy BR
PROXY_CONFIG = {
    "server": "http://fb29d01db8530b99.shg.na.pyproxy.io:16666",
    "username": "liderbet1-zone-resi-region-br",
    "password": "Aa10203040"
}

async def test_proxy():
    print("=" * 60)
    print("TESTE PLAYWRIGHT CDP COM PROXY BR")
    print("=" * 60)
    print(f"Endpoint: {WS_ENDPOINT[:60]}...")
    print(f"Proxy: {PROXY_CONFIG['server']}")
    print("=" * 60)
    
    async with async_playwright() as p:
        print("\n🔗 Conectando ao Browserless via CDP...")
        
        browser = await p.chromium.connect_over_cdp(WS_ENDPOINT)
        
        print("✅ Conectado!")
        print("\n🌐 Criando contexto com proxy BR...")
        
        context = await browser.new_context(proxy=PROXY_CONFIG)
        page = await context.new_page()
        
        print("📄 Acessando ipinfo.io...")
        await page.goto("https://ipinfo.io/json", timeout=60000)
        
        content = await page.content()
        print(f"\n📥 Resposta ({len(content)} bytes):")
        
        # Extrair dados
        import re
        ip_match = re.search(r'"ip":\s*"([^"]+)"', content)
        city_match = re.search(r'"city":\s*"([^"]+)"', content)
        region_match = re.search(r'"region":\s*"([^"]+)"', content)
        country_match = re.search(r'"country":\s*"([^"]+)"', content)
        org_match = re.search(r'"org":\s*"([^"]+)"', content)
        
        ip = ip_match.group(1) if ip_match else "N/A"
        city = city_match.group(1) if city_match else "N/A"
        region = region_match.group(1) if region_match else "N/A"
        country = country_match.group(1) if country_match else "N/A"
        org = org_match.group(1) if org_match else "N/A"
        
        print("\n" + "=" * 60)
        print("RESULTADO:")
        print("=" * 60)
        print(f"🌐 IP: {ip}")
        print(f"🏙️  Cidade: {city}")
        print(f"📍 Região: {region}")
        print(f"🏳️  País: {country}")
        print(f"🏢 Org: {org}")
        
        if country == "BR":
            print("\n" + "=" * 60)
            print("✅ SUCESSO! IP DO BRASIL! 🇧🇷")
            print("=" * 60)
        else:
            print(f"\n⚠️ IP não é do Brasil (país: {country})")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_proxy())

