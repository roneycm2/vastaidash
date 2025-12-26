"""
Teste simples de conexão Browserless - YouTube
Usando Playwright com conexão CDP (BaaS v2)
"""
import asyncio

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

import aiohttp

BROWSERLESS_API_KEY = "2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72"
BROWSERLESS_WS_URL = f"wss://production-sfo.browserless.io?token={BROWSERLESS_API_KEY}"
BROWSERLESS_REST_URL = "https://production-sfo.browserless.io"
YOUTUBE_URL = "https://www.youtube.com/watch?v=3Hj4wZk97JM"


async def test_with_content_api():
    """Testa usando a API /content do Browserless."""
    print("=" * 60)
    print("🧪 TESTE BROWSERLESS - API /content")
    print("=" * 60)
    print(f"🔑 API Key: {BROWSERLESS_API_KEY[:20]}...")
    print(f"📺 YouTube URL: {YOUTUBE_URL}")
    print("=" * 60)
    print()
    
    # Primeiro, testar com ipinfo para verificar conexão
    print("🔍 Verificando IP do navegador Browserless...")
    
    ip_url = f"{BROWSERLESS_REST_URL}/content?token={BROWSERLESS_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Testar IP primeiro
            payload = {
                "url": "https://ipinfo.io/json",
                "waitForTimeout": 5000
            }
            
            async with session.post(ip_url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    ip_content = await resp.text()
                    print(f"✅ IP Info: {ip_content[:200]}")
                else:
                    print(f"⚠️ IP Check falhou: {resp.status}")
            
            print()
            print("📺 Acessando YouTube...")
            
            # Agora testar YouTube
            payload = {
                "url": YOUTUBE_URL,
                "waitForTimeout": 10000,
                "gotoOptions": {
                    "waitUntil": "domcontentloaded"
                }
            }
            
            async with session.post(ip_url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                print(f"📡 Status HTTP: {resp.status}")
                
                if resp.status == 200:
                    content = await resp.text()
                    print()
                    print("✅ CONEXÃO BEM SUCEDIDA!")
                    print("=" * 60)
                    
                    # Verificar se é uma página do YouTube
                    if "youtube" in content.lower() or "yt" in content.lower():
                        print("✓ Página do YouTube carregada!")
                    
                    # Mostrar parte do título se existir
                    if "<title>" in content:
                        start = content.find("<title>") + 7
                        end = content.find("</title>")
                        title = content[start:end] if end > start else "N/A"
                        print(f"📄 Título da página: {title[:100]}")
                    
                    # Mostrar tamanho do conteúdo
                    print(f"📦 Tamanho do conteúdo: {len(content)} caracteres")
                    
                    print()
                    print("=" * 60)
                    print("🎉 TESTE CONCLUÍDO COM SUCESSO!")
                    print("=" * 60)
                    return True
                else:
                    error = await resp.text()
                    print(f"❌ Erro HTTP {resp.status}: {error[:200]}")
                    return False
                    
    except Exception as e:
        print(f"❌ Exceção: {str(e)}")
        return False


async def test_with_scrape_api():
    """Testa usando a API /scrape do Browserless."""
    print()
    print("=" * 60)
    print("🧪 TESTE BROWSERLESS - API /scrape")
    print("=" * 60)
    
    scrape_url = f"{BROWSERLESS_REST_URL}/scrape?token={BROWSERLESS_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "url": YOUTUBE_URL,
                "elements": [
                    {"selector": "title"},
                    {"selector": "meta[name='title']", "attribute": "content"},
                    {"selector": "#owner-name"},
                    {"selector": "video", "attribute": "src"}
                ],
                "waitForTimeout": 10000
            }
            
            async with session.post(scrape_url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                print(f"📡 Status HTTP: {resp.status}")
                
                if resp.status == 200:
                    result = await resp.json()
                    print()
                    print("✅ SCRAPE BEM SUCEDIDO!")
                    print("=" * 60)
                    print(f"📊 Resultado: {result}")
                    print("=" * 60)
                    return True
                else:
                    error = await resp.text()
                    print(f"❌ Erro: {error[:200]}")
                    return False
                    
    except Exception as e:
        print(f"❌ Exceção: {str(e)}")
        return False


async def test_with_playwright():
    """Testa usando Playwright com CDP."""
    if not PLAYWRIGHT_AVAILABLE:
        print("⚠️ Playwright não disponível. Instale com: pip install playwright")
        return False
    
    print()
    print("=" * 60)
    print("🧪 TESTE BROWSERLESS - Playwright CDP")
    print("=" * 60)
    print(f"🔌 WebSocket URL: wss://production-sfo.browserless.io?token=...")
    print()
    
    try:
        async with async_playwright() as p:
            print("🚀 Conectando via CDP...")
            browser = await p.chromium.connect_over_cdp(BROWSERLESS_WS_URL)
            
            print("✓ Conectado ao navegador!")
            
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            
            # Primeiro verificar IP
            print("🔍 Verificando IP...")
            await page.goto("https://ipinfo.io/json", wait_until="domcontentloaded")
            ip_content = await page.content()
            print(f"📍 IP Info obtido: {ip_content[:150]}...")
            
            # Agora acessar YouTube
            print()
            print("📺 Acessando YouTube...")
            await page.goto(YOUTUBE_URL, wait_until="domcontentloaded", timeout=60000)
            
            # Aguardar um pouco
            await page.wait_for_timeout(5000)
            
            title = await page.title()
            url = page.url
            
            print()
            print("✅ CONEXÃO BEM SUCEDIDA!")
            print("=" * 60)
            print(f"📄 Título: {title}")
            print(f"🔗 URL: {url}")
            
            # Verificar se tem vídeo
            try:
                video = await page.query_selector("video")
                if video:
                    print("🎬 Elemento de vídeo: ✓ Encontrado")
            except:
                pass
            
            await browser.close()
            
            print()
            print("=" * 60)
            print("🎉 TESTE PLAYWRIGHT CONCLUÍDO COM SUCESSO!")
            print("=" * 60)
            return True
            
    except Exception as e:
        print(f"❌ Exceção: {str(e)}")
        return False


async def main():
    print("\n" + "=" * 60)
    print("🚀 BROWSERLESS CONNECTION TEST")
    print("=" * 60 + "\n")
    
    # Tentar primeiro com a API /content (mais simples)
    success = await test_with_content_api()
    
    if not success:
        # Se falhar, tentar scrape
        success = await test_with_scrape_api()
    
    # Tentar Playwright se disponível
    if PLAYWRIGHT_AVAILABLE:
        await test_with_playwright()
    else:
        print("\n⚠️ Para teste completo com Playwright, instale:")
        print("   pip install playwright")
        print("   playwright install chromium")


if __name__ == "__main__":
    asyncio.run(main())

