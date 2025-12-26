"""
Turnstile Solver v2 - Otimizado para Browserless
- Usa o browser existente do Browserless (não cria novo contexto com proxy)
- Múltiplas abas no mesmo browser
- Injeção de JS para clique rápido
- Reconexão automática
"""

import asyncio
import json
import time
import random
import argparse
import os
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

try:
    from playwright.async_api import async_playwright, Browser, Page
except ImportError:
    import subprocess
    subprocess.run(["pip", "install", "playwright"])
    from playwright.async_api import async_playwright, Browser, Page

# Configurações
DEFAULT_SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
DEFAULT_URL = "https://7k.bet.br/"

# HTML para servir localmente
PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Turnstile Solver</title>
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onloadTurnstileCallback" async defer></script>
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        .container {
            text-align: center;
            color: #fff;
            padding: 40px;
        }
        h2 { 
            color: #e94560;
            margin-bottom: 30px;
        }
        #status {
            margin-top: 20px;
            padding: 15px 25px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            font-size: 14px;
        }
        .cf-turnstile {
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>🔐 Turnstile Solver</h2>
        <div class="cf-turnstile" data-sitekey="{sitekey}" data-callback="onTokenReceived"></div>
        <div id="status">⏳ Aguardando...</div>
    </div>
    <script>
        window.turnstileToken = null;
        window.tokenTimestamp = null;
        
        function onTokenReceived(token) {
            window.turnstileToken = token;
            window.tokenTimestamp = Date.now();
            document.getElementById('status').innerText = '✅ Token obtido!';
            document.getElementById('status').style.background = 'rgba(0, 255, 100, 0.2)';
            console.log('[TURNSTILE_SOLVED]' + token);
        }
        
        function onloadTurnstileCallback() {
            console.log('[TURNSTILE_LOADED]');
            document.getElementById('status').innerText = '🔄 Resolvendo...';
        }
    </script>
</body>
</html>
"""

@dataclass
class TabInfo:
    """Informação de uma aba"""
    id: int
    page: Optional[Page] = None
    status: str = "idle"
    token: Optional[str] = None
    start_time: float = 0
    solve_count: int = 0
    click_count: int = 0


class TurnstileSolverV2:
    """Solver otimizado para Browserless"""
    
    def __init__(self, endpoint: str, num_tabs: int = 5, sitekey: str = DEFAULT_SITEKEY):
        self.endpoint = endpoint if endpoint.endswith("/chrome") else endpoint + "/chrome"
        self.num_tabs = num_tabs
        self.sitekey = sitekey
        self.page_html = PAGE_HTML.replace("{sitekey}", sitekey)
        
        self.browser: Optional[Browser] = None
        self.tabs: List[TabInfo] = []
        self.running = True
        self.total_solved = 0
        self.start_time = time.time()
        self.playwright = None
        
        # Tokens salvos
        self.tokens: List[dict] = []
        
    def log(self, msg: str, level: str = "info"):
        """Log formatado"""
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"info": "ℹ️", "success": "✅", "error": "❌", "warn": "⚠️", "token": "🎟️"}
        print(f"[{ts}] {icons.get(level, '•')} {msg}")
    
    async def connect(self) -> bool:
        """Conecta ao Browserless"""
        try:
            self.playwright = await async_playwright().start()
            
            self.log(f"Conectando a: {self.endpoint}")
            self.browser = await self.playwright.chromium.connect_over_cdp(
                self.endpoint,
                timeout=60000
            )
            
            self.log("Conectado ao Browserless!", "success")
            return True
            
        except Exception as e:
            self.log(f"Erro ao conectar: {e}", "error")
            return False
    
    async def create_tab(self, tab_id: int) -> TabInfo:
        """Cria uma aba no browser existente"""
        tab = TabInfo(id=tab_id)
        
        try:
            # Usa o contexto padrão do browser (já tem proxy configurado no Browserless)
            contexts = self.browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = await self.browser.new_context()
            
            # Cria nova página
            tab.page = await context.new_page()
            
            # Configura rota para interceptar a URL alvo
            async def route_handler(route):
                if DEFAULT_URL.rstrip('/') in route.request.url:
                    await route.fulfill(
                        body=self.page_html,
                        content_type="text/html",
                        status=200
                    )
                else:
                    await route.continue_()
            
            await tab.page.route("**/*", route_handler)
            
            tab.status = "ready"
            self.log(f"Tab #{tab_id} criada")
            
        except Exception as e:
            self.log(f"Erro ao criar tab #{tab_id}: {e}", "error")
            tab.status = "error"
            
        return tab
    
    async def solve_captcha(self, tab: TabInfo) -> Optional[str]:
        """Resolve captcha em uma aba"""
        tab.status = "solving"
        tab.start_time = time.time()
        tab.token = None
        tab.click_count = 0
        
        try:
            # Navega para a URL (será interceptada)
            self.log(f"Tab #{tab.id}: Navegando...")
            await tab.page.goto(DEFAULT_URL, wait_until="domcontentloaded", timeout=30000)
            
            # Aguarda o iframe do Turnstile
            self.log(f"Tab #{tab.id}: Aguardando Turnstile...")
            
            max_wait = 45  # segundos
            start = time.time()
            
            while time.time() - start < max_wait and self.running:
                # Verifica se token já foi resolvido (via callback JS)
                token = await tab.page.evaluate("window.turnstileToken")
                
                if token and len(str(token)) > 50:
                    solve_time = time.time() - tab.start_time
                    tab.token = token
                    tab.status = "solved"
                    tab.solve_count += 1
                    self.total_solved += 1
                    
                    self.save_token(token, tab.id, solve_time)
                    self.log(f"Tab #{tab.id}: TOKEN #{tab.solve_count} em {solve_time:.1f}s | Total: {self.total_solved}", "token")
                    self.log(f"   → {token[:60]}...", "success")
                    
                    return token
                
                # Tenta clicar no iframe se existir
                if tab.click_count < 10:
                    clicked = await self.try_click_turnstile(tab)
                    if clicked:
                        tab.click_count += 1
                
                await asyncio.sleep(0.5)
            
            self.log(f"Tab #{tab.id}: Timeout", "warn")
            tab.status = "timeout"
            
        except Exception as e:
            self.log(f"Tab #{tab.id}: Erro: {e}", "error")
            tab.status = "error"
            
        return None
    
    async def try_click_turnstile(self, tab: TabInfo) -> bool:
        """Tenta clicar no checkbox do Turnstile"""
        try:
            # Procura iframe do Cloudflare
            iframe = await tab.page.query_selector('iframe[src*="challenges.cloudflare.com"]')
            
            if iframe:
                box = await iframe.bounding_box()
                if box and box["width"] > 0:
                    # Clica no centro do iframe
                    x = box["x"] + box["width"] / 2 + random.randint(-3, 3)
                    y = box["y"] + box["height"] / 2 + random.randint(-3, 3)
                    await tab.page.mouse.click(x, y)
                    return True
                    
        except Exception:
            pass
            
        return False
    
    def save_token(self, token: str, tab_id: int, solve_time: float):
        """Salva token em arquivo"""
        data = {
            "token": token,
            "tab_id": tab_id,
            "solve_time": round(solve_time, 2),
            "timestamp": datetime.now().isoformat(),
            "sitekey": self.sitekey,
            "total": self.total_solved
        }
        
        self.tokens.append(data)
        
        # Append ao arquivo
        try:
            with open("turnstile_tokens.json", "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception:
            pass
    
    async def close_tab(self, tab: TabInfo):
        """Fecha uma aba"""
        try:
            if tab.page:
                await tab.page.close()
                tab.page = None
            tab.status = "closed"
        except Exception:
            pass
    
    async def tab_loop(self, tab_id: int):
        """Loop de uma aba - resolve continuamente"""
        tab = await self.create_tab(tab_id)
        self.tabs.append(tab)
        
        while self.running:
            try:
                # Se tab está sem página, recria
                if not tab.page or tab.status == "error":
                    await self.close_tab(tab)
                    tab = await self.create_tab(tab_id)
                    self.tabs[tab_id - 1] = tab
                    
                    if tab.status == "error":
                        await asyncio.sleep(5)
                        continue
                
                # Resolve
                token = await self.solve_captcha(tab)
                
                if token:
                    # Sucesso! Recarrega para próximo
                    await asyncio.sleep(1)
                    try:
                        await tab.page.reload()
                    except:
                        pass
                else:
                    # Timeout/erro - recarrega
                    try:
                        await tab.page.reload()
                    except:
                        tab.status = "error"
                    
                    await asyncio.sleep(2)
                    
            except Exception as e:
                self.log(f"Tab #{tab_id} loop error: {e}", "error")
                tab.status = "error"
                await asyncio.sleep(3)
    
    async def run(self):
        """Executa o solver"""
        self.log("=" * 60)
        self.log("🚀 TURNSTILE SOLVER V2")
        self.log("=" * 60)
        self.log(f"Endpoint: {self.endpoint}")
        self.log(f"Sitekey: {self.sitekey}")
        self.log(f"Tabs: {self.num_tabs}")
        self.log("=" * 60)
        
        if not await self.connect():
            self.log("Falha ao conectar. Saindo.", "error")
            return
        
        try:
            # Inicia todas as abas em paralelo
            self.log(f"Iniciando {self.num_tabs} abas em paralelo...")
            tasks = [self.tab_loop(i + 1) for i in range(self.num_tabs)]
            await asyncio.gather(*tasks)
            
        except KeyboardInterrupt:
            self.log("Interrompido pelo usuário", "warn")
            self.running = False
            
        finally:
            # Fecha tudo
            self.log("Fechando...")
            for tab in self.tabs:
                await self.close_tab(tab)
            
            if self.browser:
                await self.browser.close()
            
            # Stats
            elapsed = time.time() - self.start_time
            rate = self.total_solved / (elapsed / 60) if elapsed > 60 else self.total_solved
            
            self.log("=" * 60)
            self.log(f"📊 Total: {self.total_solved} tokens")
            self.log(f"⏱️  Tempo: {elapsed/60:.1f} min")
            self.log(f"📈 Taxa: {rate:.1f}/min")
            self.log("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description="Turnstile Solver V2")
    parser.add_argument("-e", "--endpoint", required=True, help="WebSocket endpoint (ws://ip:port)")
    parser.add_argument("-t", "--tabs", type=int, default=5, help="Número de abas (default: 5)")
    parser.add_argument("-s", "--sitekey", default=DEFAULT_SITEKEY, help="Sitekey do Turnstile")
    
    args = parser.parse_args()
    
    solver = TurnstileSolverV2(
        endpoint=args.endpoint,
        num_tabs=args.tabs,
        sitekey=args.sitekey
    )
    
    await solver.run()


if __name__ == "__main__":
    asyncio.run(main())










