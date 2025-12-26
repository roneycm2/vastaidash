"""
Turnstile Solver para Browserless + Vast.ai
Baseado em: https://github.com/Body-Alhoha/turnaround
Usa Patchright-style para resolver Cloudflare Turnstile

Características:
- Redireciona domínio 7k.bet.br para servir HTML local com captcha
- Usa proxy BR sempre
- Múltiplas abas paralelas (passado por parâmetro)
- Injeção de JS para clique automático (mais rápido)
- Fecha abas que já tem token resolvido para economizar processamento
- Salva tokens e mostra nos logs
"""

import asyncio
import json
import time
import random
import argparse
import os
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, field

# Importar de playwright async
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
except ImportError:
    print("Instalando playwright...")
    import subprocess
    subprocess.run(["pip", "install", "playwright"])
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Configurações padrão
DEFAULT_SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
DEFAULT_URL = "https://7k.bet.br/"
DEFAULT_TABS = 5
DEFAULT_PROXY_HOST = "fb29d01db8530b99.shg.na.pyproxy.io"
DEFAULT_PROXY_PORT = "16666"
DEFAULT_PROXY_USER = "liderbet1-zone-mob-region-br"
DEFAULT_PROXY_PASS = "Aa10203040"

# HTML template para servir com Turnstile
PAGE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Turnstile Solver</title>
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onloadTurnstileCallback" async defer></script>
    <style>
        body {{
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: #1a1a2e;
            font-family: Arial, sans-serif;
        }}
        .container {{
            text-align: center;
            color: #fff;
        }}
        #status {{
            margin-top: 20px;
            padding: 10px;
            background: #16213e;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Turnstile Solver</h2>
        <div class="cf-turnstile" data-sitekey="{sitekey}" data-callback="onTokenReceived"></div>
        <div id="status">Aguardando resolução...</div>
    </div>
    <script>
        window.turnstileToken = null;
        
        function onTokenReceived(token) {{
            window.turnstileToken = token;
            document.getElementById('status').innerText = 'Token obtido!';
            document.getElementById('status').style.background = '#0f3460';
            console.log('[TURNSTILE_TOKEN]' + token);
        }}
        
        function onloadTurnstileCallback() {{
            console.log('Turnstile API carregada');
        }}
        
        // Auto-click no checkbox após carregamento (injeção JS)
        function autoClickTurnstile() {{
            const iframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
            if (iframe) {{
                try {{
                    const rect = iframe.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {{
                        // Simula click no centro do iframe
                        const event = new MouseEvent('click', {{
                            view: window,
                            bubbles: true,
                            cancelable: true,
                            clientX: rect.left + rect.width / 2,
                            clientY: rect.top + rect.height / 2
                        }});
                        iframe.dispatchEvent(event);
                        return true;
                    }}
                }} catch (e) {{
                    console.log('Erro ao clicar:', e);
                }}
            }}
            return false;
        }}
        
        // Tenta clicar automaticamente a cada 500ms
        setInterval(autoClickTurnstile, 500);
    </script>
</body>
</html>
"""

@dataclass
class SolverConfig:
    """Configuração do solver"""
    sitekey: str = DEFAULT_SITEKEY
    url: str = DEFAULT_URL
    num_tabs: int = DEFAULT_TABS
    proxy_host: str = DEFAULT_PROXY_HOST
    proxy_port: str = DEFAULT_PROXY_PORT
    proxy_user: str = DEFAULT_PROXY_USER
    proxy_pass: str = DEFAULT_PROXY_PASS
    browserless_endpoint: str = ""
    max_solve_time: int = 60  # segundos
    loop_forever: bool = True

@dataclass
class TabState:
    """Estado de uma aba"""
    id: int
    page: Optional[Page] = None
    context: Optional[BrowserContext] = None
    status: str = "idle"
    token: Optional[str] = None
    start_time: float = 0
    solve_count: int = 0

class TurnstileSolver:
    """Solver de Turnstile usando Browserless"""
    
    def __init__(self, config: SolverConfig):
        self.config = config
        self.tabs: List[TabState] = []
        self.tokens: List[Dict] = []
        self.browser: Optional[Browser] = None
        self.running = True
        self.total_solved = 0
        self.start_time = time.time()
        
        # Gera HTML com sitekey
        self.page_html = PAGE_HTML_TEMPLATE.format(sitekey=config.sitekey)
        
    def log(self, message: str, level: str = "info"):
        """Log formatado"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icons = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️", "token": "🎟️"}
        icon = icons.get(level, "•")
        print(f"[{timestamp}] {icon} {message}")
        
    async def route_handler(self, route):
        """Intercepta requisições e serve HTML customizado"""
        if self.config.url in route.request.url:
            await route.fulfill(
                body=self.page_html,
                content_type="text/html",
                status=200
            )
        else:
            await route.continue_()
    
    async def connect_browser(self) -> bool:
        """Conecta ao Browserless via CDP"""
        try:
            playwright = await async_playwright().start()
            
            # Configura proxy
            proxy_config = {
                "server": f"http://{self.config.proxy_host}:{self.config.proxy_port}",
                "username": self.config.proxy_user,
                "password": self.config.proxy_pass
            }
            
            self.log(f"Conectando ao Browserless: {self.config.browserless_endpoint}")
            self.log(f"Proxy BR: {self.config.proxy_host}:{self.config.proxy_port}")
            
            # Conecta via CDP ao Browserless
            self.browser = await playwright.chromium.connect_over_cdp(
                self.config.browserless_endpoint,
                timeout=30000
            )
            
            self.log("Conectado ao Browserless!", "success")
            self.playwright = playwright
            return True
            
        except Exception as e:
            self.log(f"Erro ao conectar: {e}", "error")
            return False
    
    async def create_tab(self, tab_id: int) -> TabState:
        """Cria uma nova aba com contexto e proxy"""
        tab = TabState(id=tab_id)
        
        try:
            # Proxy BR
            proxy_config = {
                "server": f"http://{self.config.proxy_host}:{self.config.proxy_port}",
                "username": self.config.proxy_user,
                "password": self.config.proxy_pass
            }
            
            # Cria contexto com proxy
            tab.context = await self.browser.new_context(
                proxy=proxy_config,
                viewport={"width": 400, "height": 500},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            # Cria página
            tab.page = await tab.context.new_page()
            
            # Intercepta requisições para o domínio alvo
            await tab.page.route(f"{self.config.url}**", self.route_handler)
            
            tab.status = "created"
            self.log(f"Tab #{tab_id} criada", "info")
            
        except Exception as e:
            self.log(f"Erro ao criar tab #{tab_id}: {e}", "error")
            tab.status = "error"
            
        return tab
    
    async def solve_in_tab(self, tab: TabState) -> Optional[str]:
        """Resolve Turnstile em uma aba específica"""
        tab.status = "solving"
        tab.start_time = time.time()
        tab.token = None
        
        try:
            # Navega para a URL (será interceptada e servida o HTML local)
            self.log(f"Tab #{tab.id}: Navegando para {self.config.url}")
            await tab.page.goto(self.config.url, wait_until="domcontentloaded", timeout=30000)
            
            # Aguarda iframe do Turnstile aparecer
            self.log(f"Tab #{tab.id}: Aguardando Turnstile carregar...")
            
            iframe_selector = 'iframe[src*="challenges.cloudflare.com"]'
            try:
                await tab.page.wait_for_selector(iframe_selector, timeout=15000)
            except:
                self.log(f"Tab #{tab.id}: Iframe não apareceu, recarregando...", "warning")
                await tab.page.reload()
                await tab.page.wait_for_selector(iframe_selector, timeout=15000)
            
            # Injeta JS para clicar no checkbox automaticamente
            await self.inject_auto_click(tab)
            
            # Loop para verificar token
            while time.time() - tab.start_time < self.config.max_solve_time:
                if not self.running:
                    break
                    
                # Verifica se token foi resolvido via JS
                token = await tab.page.evaluate("window.turnstileToken")
                
                if token and len(token) > 50:
                    tab.token = token
                    tab.status = "solved"
                    tab.solve_count += 1
                    self.total_solved += 1
                    
                    solve_time = time.time() - tab.start_time
                    self.save_token(token, tab.id, solve_time)
                    
                    self.log(f"Tab #{tab.id}: TOKEN RESOLVIDO em {solve_time:.1f}s (Total: {self.total_solved})", "token")
                    self.log(f"   Token: {token[:50]}...", "success")
                    
                    return token
                
                # Tenta clicar no iframe se ainda não resolveu
                await self.try_click_iframe(tab)
                
                await asyncio.sleep(0.5)
            
            self.log(f"Tab #{tab.id}: Timeout após {self.config.max_solve_time}s", "warning")
            tab.status = "timeout"
            
        except Exception as e:
            self.log(f"Tab #{tab.id}: Erro: {e}", "error")
            tab.status = "error"
            
        return None
    
    async def inject_auto_click(self, tab: TabState):
        """Injeta JS para clicar automaticamente no checkbox"""
        js_code = """
        (function() {
            function clickTurnstile() {
                const iframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
                if (iframe) {
                    const rect = iframe.getBoundingClientRect();
                    if (rect.width > 0) {
                        // Usa click real no centro
                        const x = rect.left + rect.width / 2;
                        const y = rect.top + rect.height / 2;
                        
                        // Cria evento de mouse
                        const clickEvent = new MouseEvent('click', {
                            view: window,
                            bubbles: true,
                            cancelable: true,
                            clientX: x,
                            clientY: y
                        });
                        
                        // Dispara no documento
                        document.elementFromPoint(x, y)?.click();
                        return true;
                    }
                }
                return false;
            }
            
            // Tenta clicar algumas vezes
            let attempts = 0;
            const interval = setInterval(() => {
                if (window.turnstileToken || attempts > 20) {
                    clearInterval(interval);
                    return;
                }
                clickTurnstile();
                attempts++;
            }, 300);
        })();
        """
        try:
            await tab.page.evaluate(js_code)
        except:
            pass
    
    async def try_click_iframe(self, tab: TabState):
        """Tenta clicar no iframe do Turnstile"""
        try:
            iframe = await tab.page.query_selector('iframe[src*="challenges.cloudflare.com"]')
            if iframe:
                box = await iframe.bounding_box()
                if box and box["width"] > 0:
                    x = box["x"] + box["width"] / 2 + random.randint(-5, 5)
                    y = box["y"] + box["height"] / 2 + random.randint(-5, 5)
                    await tab.page.mouse.click(x, y)
        except:
            pass
    
    def save_token(self, token: str, tab_id: int, solve_time: float):
        """Salva token no arquivo JSON"""
        token_data = {
            "token": token,
            "tab_id": tab_id,
            "solve_time": round(solve_time, 2),
            "timestamp": datetime.now().isoformat(),
            "sitekey": self.config.sitekey
        }
        
        self.tokens.append(token_data)
        
        # Salva em arquivo
        tokens_file = "turnstile_tokens.json"
        try:
            existing = []
            if os.path.exists(tokens_file):
                with open(tokens_file, "r") as f:
                    existing = json.load(f)
            existing.append(token_data)
            with open(tokens_file, "w") as f:
                json.dump(existing, f, indent=2)
        except:
            pass
    
    async def close_tab(self, tab: TabState):
        """Fecha uma aba para economizar recursos"""
        try:
            if tab.context:
                await tab.context.close()
            tab.page = None
            tab.context = None
            tab.status = "closed"
            self.log(f"Tab #{tab.id} fechada (economizando recursos)", "info")
        except:
            pass
    
    async def run_tab_loop(self, tab: TabState):
        """Loop de resolução para uma aba"""
        while self.running:
            try:
                # Recria contexto se fechado
                if not tab.page or not tab.context:
                    tab = await self.create_tab(tab.id)
                    self.tabs[tab.id - 1] = tab
                
                # Resolve
                token = await self.solve_in_tab(tab)
                
                if token:
                    # Token obtido - fecha aba para economizar
                    await self.close_tab(tab)
                    
                    if not self.config.loop_forever:
                        break
                    
                    # Espera um pouco antes de reabrir
                    await asyncio.sleep(2)
                    
                else:
                    # Timeout/erro - reload
                    try:
                        await tab.page.reload()
                    except:
                        await self.close_tab(tab)
                    
                    await asyncio.sleep(1)
                    
            except Exception as e:
                self.log(f"Tab #{tab.id}: Erro no loop: {e}", "error")
                await asyncio.sleep(2)
    
    async def run(self):
        """Executa o solver com múltiplas abas em paralelo"""
        self.log("=" * 60)
        self.log("🚀 TURNSTILE SOLVER - BROWSERLESS")
        self.log("=" * 60)
        self.log(f"Endpoint: {self.config.browserless_endpoint}")
        self.log(f"Sitekey: {self.config.sitekey}")
        self.log(f"Tabs: {self.config.num_tabs}")
        self.log(f"Proxy BR: {self.config.proxy_user}@{self.config.proxy_host}")
        self.log(f"Loop infinito: {self.config.loop_forever}")
        self.log("=" * 60)
        
        # Conecta ao browser
        if not await self.connect_browser():
            return
        
        try:
            # Cria todas as abas
            self.log(f"Criando {self.config.num_tabs} abas...")
            for i in range(self.config.num_tabs):
                tab = await self.create_tab(i + 1)
                self.tabs.append(tab)
            
            # Executa todas as abas em paralelo
            self.log("Iniciando resolução em paralelo...")
            tasks = [self.run_tab_loop(tab) for tab in self.tabs]
            await asyncio.gather(*tasks)
            
        except KeyboardInterrupt:
            self.log("Interrompido pelo usuário", "warning")
            self.running = False
            
        finally:
            # Fecha tudo
            self.log("Fechando recursos...")
            for tab in self.tabs:
                await self.close_tab(tab)
            
            if self.browser:
                await self.browser.close()
            
            # Estatísticas finais
            elapsed = time.time() - self.start_time
            rate = self.total_solved / (elapsed / 60) if elapsed > 60 else self.total_solved
            
            self.log("=" * 60)
            self.log(f"📊 ESTATÍSTICAS FINAIS")
            self.log(f"   Total resolvido: {self.total_solved}")
            self.log(f"   Tempo: {elapsed/60:.1f} min")
            self.log(f"   Taxa: {rate:.1f} tokens/min")
            self.log("=" * 60)


async def main():
    """Função principal"""
    parser = argparse.ArgumentParser(description="Turnstile Solver via Browserless")
    parser.add_argument("--endpoint", "-e", required=True, help="WebSocket endpoint do Browserless (ws://IP:PORT)")
    parser.add_argument("--tabs", "-t", type=int, default=5, help="Número de abas paralelas (default: 5)")
    parser.add_argument("--sitekey", "-s", default=DEFAULT_SITEKEY, help="Sitekey do Turnstile")
    parser.add_argument("--url", "-u", default=DEFAULT_URL, help="URL do site")
    parser.add_argument("--no-loop", action="store_true", help="Não executa em loop infinito")
    parser.add_argument("--max-time", type=int, default=60, help="Tempo máximo por tentativa (segundos)")
    
    args = parser.parse_args()
    
    # Ajusta endpoint
    endpoint = args.endpoint
    if not endpoint.endswith("/chrome"):
        endpoint = endpoint.rstrip("/") + "/chrome"
    
    config = SolverConfig(
        browserless_endpoint=endpoint,
        num_tabs=args.tabs,
        sitekey=args.sitekey,
        url=args.url,
        loop_forever=not args.no_loop,
        max_solve_time=args.max_time
    )
    
    solver = TurnstileSolver(config)
    await solver.run()


if __name__ == "__main__":
    asyncio.run(main())










