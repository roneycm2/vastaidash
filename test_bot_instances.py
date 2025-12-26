"""
Bot Multi-Instâncias via Playwright CDP
Executa múltiplas instâncias simultâneas conectando via CDP ao Browserless
"""
import asyncio
from playwright.async_api import async_playwright

# Endpoint padrão para acesso aos workers
DEFAULT_WS_ENDPOINT = "ws://69.63.236.184:26586/chrome"

# Número de instâncias a serem executadas
NUM_INSTANCES = 20

# Configuração do proxy
PROXY_CONFIG = {
    "server": "http://pybpm-ins-760sn4t2.pyproxy.io:2510",
    "username": "extract1-zone-adam-region-br",
    "password": "p2ssword",
}


async def run_bot(instance_number, ws_endpoint=DEFAULT_WS_ENDPOINT):
    """
    Executa uma instância do bot.
    
    Args:
        instance_number: Número da instância
        ws_endpoint: Endpoint WebSocket para conexão CDP
    """
    try:
        print(f"[Instance {instance_number}] Starting...")
        
        async with async_playwright() as p:
            # Conectar ao browser via CDP
            browser = await p.chromium.connect_over_cdp(ws_endpoint)
            
            # Criar contexto com proxy
            context = await browser.new_context(proxy=PROXY_CONFIG)
            page = await context.new_page()
            
            # Acessar Google
            await page.goto("https://www.google.com", timeout=60000)
            
            # Aguardar um pouco para carregar
            await page.wait_for_timeout(2000)
            
            content = await page.content()
            title = await page.title()
            print(f"[Instance {instance_number}] Title: {title}")
            print(f"[Instance {instance_number}] Content length: {len(content)} chars")
            
            # Fechar browser
            await browser.close()
            
        print(f"[Instance {instance_number}] Completed successfully")
        
    except Exception as error:
        print(f"[Instance {instance_number}] Error: {error}")


async def main():
    """Executa todas as instâncias em paralelo."""
    print(f"Starting {NUM_INSTANCES} instances...\n")
    
    # Criar lista de tasks para executar em paralelo
    tasks = [run_bot(i) for i in range(1, NUM_INSTANCES + 1)]
    
    # Executar todas as tasks em paralelo e aguardar conclusão
    await asyncio.gather(*tasks, return_exceptions=True)
    
    print("\nAll instances finished.")


if __name__ == "__main__":
    asyncio.run(main())

