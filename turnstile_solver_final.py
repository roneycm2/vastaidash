#!/usr/bin/env python3
"""
Turnstile Solver Final - Baseado no turnaround
https://github.com/Body-Alhoha/turnaround

Características:
- Intercepta URL e serve HTML local com Turnstile widget
- Usa proxy BR sempre
- Múltiplas abas em paralelo
- Injeção de JS para clique automático
- Reconexão automática quando browser fecha
- Salva tokens em arquivo JSON
"""

import time
import random
import json
import os
import argparse
import warnings
from datetime import datetime
from typing import Optional, List, Dict, Any
from threading import Thread, Lock
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

# Playwright sync API (mais estável para múltiplos workers)
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
except ImportError:
    print("Instalando playwright...")
    import subprocess
    subprocess.run(["pip", "install", "playwright"])
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# ========================================
# CONFIGURAÇÕES
# ========================================
DEFAULT_SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
TARGET_URL = "https://7k.bet.br/"

# Proxy BR padrão
PROXY_HOST = "fb29d01db8530b99.shg.na.pyproxy.io"
PROXY_PORT = "16666"
PROXY_USER = "liderbet1-zone-mob-region-br"
PROXY_PASS = "Aa10203040"

# HTML template para servir - simples e eficiente
PAGE_HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Turnstile Solver</title>
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js?onload=onloadTurnstileCallback" async defer></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
            font-family: 'Segoe UI', system-ui, sans-serif;
        }}
        .solver-container {{
            text-align: center;
            padding: 2rem;
        }}
        h1 {{
            color: #fff;
            font-size: 1.5rem;
            margin-bottom: 1.5rem;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }}
        .cf-turnstile {{
            display: inline-block;
            margin: 1rem 0;
        }}
        #status {{
            color: #aaa;
            font-size: 0.9rem;
            margin-top: 1rem;
            padding: 0.5rem 1rem;
            background: rgba(255,255,255,0.1);
            border-radius: 8px;
        }}
        .solved {{
            color: #4ade80 !important;
            background: rgba(74, 222, 128, 0.2) !important;
        }}
    </style>
</head>
<body>
    <div class="solver-container">
        <h1>🔐 Turnstile Solver</h1>
        <div class="cf-turnstile" data-sitekey="{sitekey}" data-callback="onSuccess" data-theme="dark"></div>
        <div id="status">Aguardando...</div>
    </div>
    <script>
        window.turnstileToken = null;
        window.tokenTime = null;
        
        function onSuccess(token) {{
            window.turnstileToken = token;
            window.tokenTime = Date.now();
            document.getElementById('status').innerText = '✅ Token obtido!';
            document.getElementById('status').className = 'solved';
            console.log('[TOKEN_SOLVED]' + token);
        }}
        
        function onloadTurnstileCallback() {{
            console.log('[TURNSTILE_READY]');
            document.getElementById('status').innerText = '🔄 Resolvendo...';
        }}
        
        // Auto-click após carregamento
        (function autoClick() {{
            setTimeout(function() {{
                var iframe = document.querySelector('iframe[src*="challenges.cloudflare.com"]');
                if (iframe && !window.turnstileToken) {{
                    try {{
                        var rect = iframe.getBoundingClientRect();
                        if (rect.width > 0) {{
                            var x = rect.left + rect.width / 2;
                            var y = rect.top + rect.height / 2;
                            var el = document.elementFromPoint(x, y);
                            if (el) el.click();
                        }}
                    }} catch(e) {{}}
                    setTimeout(autoClick, 500);
                }}
            }}, 1000);
        }})();
    </script>
</body>
</html>'''


@dataclass
class SolverStats:
    """Estatísticas do solver"""
    total_solved: int = 0
    total_errors: int = 0
    total_timeouts: int = 0
    start_time: float = field(default_factory=time.time)
    tokens: List[Dict] = field(default_factory=list)
    lock: Lock = field(default_factory=Lock)
    
    def add_solved(self, token: str, tab_id: int, solve_time: float, sitekey: str):
        with self.lock:
            self.total_solved += 1
            token_data = {
                "token": token,
                "tab_id": tab_id,
                "solve_time": round(solve_time, 2),
                "timestamp": datetime.now().isoformat(),
                "sitekey": sitekey,
                "count": self.total_solved
            }
            self.tokens.append(token_data)
            return self.total_solved
    
    def add_error(self):
        with self.lock:
            self.total_errors += 1
    
    def add_timeout(self):
        with self.lock:
            self.total_timeouts += 1


class TurnstileSolverTab:
    """Solver para uma única aba"""
    
    def __init__(self, tab_id: int, ws_endpoint: str, sitekey: str,
                 proxy_host: str, proxy_port: str, proxy_user: str, proxy_pass: str,
                 stats: SolverStats, max_solve_time: int = 60):
        self.tab_id = tab_id
        self.ws_endpoint = ws_endpoint
        self.sitekey = sitekey
        self.proxy = {
            "server": f"http://{proxy_host}:{proxy_port}",
            "username": proxy_user,
            "password": proxy_pass
        }
        self.stats = stats
        self.max_solve_time = max_solve_time
        self.running = True
        self.solve_count = 0
        
        # HTML com sitekey
        self.page_html = PAGE_HTML_TEMPLATE.format(sitekey=sitekey)
    
    def log(self, msg: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"info": "ℹ️", "ok": "✅", "err": "❌", "warn": "⚠️", "token": "🎟️"}
        print(f"[{ts}] {icons.get(level, '•')} Tab #{self.tab_id}: {msg}")
    
    def route_handler(self, route):
        """Intercepta requisições e serve HTML local"""
        url = route.request.url
        if TARGET_URL.rstrip('/') in url or url == TARGET_URL:
            route.fulfill(body=self.page_html, content_type="text/html", status=200)
        else:
            route.continue_()
    
    def solve_once(self, page: Page) -> Optional[str]:
        """Tenta resolver uma vez"""
        start = time.time()
        click_count = 0
        
        try:
            # Navega (será interceptada)
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=30000)
            
            # Loop para verificar token
            while time.time() - start < self.max_solve_time:
                if not self.running:
                    break
                
                # Verifica token via JS
                token = page.evaluate("window.turnstileToken")
                
                if token and len(str(token)) > 50:
                    solve_time = time.time() - start
                    self.solve_count += 1
                    total = self.stats.add_solved(token, self.tab_id, solve_time, self.sitekey)
                    
                    # Salva em arquivo
                    self.save_token(token, solve_time, total)
                    
                    self.log(f"TOKEN #{self.solve_count} em {solve_time:.1f}s | Total: {total}", "token")
                    self.log(f"   → {token[:60]}...", "ok")
                    
                    return token
                
                # Tenta clicar no iframe
                if click_count < 5:
                    try:
                        iframe = page.query_selector('iframe[src*="challenges.cloudflare.com"]')
                        if iframe:
                            box = iframe.bounding_box()
                            if box and box["width"] > 0:
                                x = box["x"] + box["width"] / 2 + random.randint(-3, 3)
                                y = box["y"] + box["height"] / 2 + random.randint(-3, 3)
                                page.mouse.click(x, y)
                                click_count += 1
                    except:
                        pass
                
                time.sleep(0.5)
            
            self.log("Timeout", "warn")
            self.stats.add_timeout()
            
        except Exception as e:
            self.log(f"Erro: {str(e)[:50]}", "err")
            self.stats.add_error()
        
        return None
    
    def save_token(self, token: str, solve_time: float, count: int):
        """Salva token em arquivo"""
        try:
            data = {
                "token": token,
                "tab": self.tab_id,
                "time": round(solve_time, 2),
                "timestamp": datetime.now().isoformat(),
                "sitekey": self.sitekey,
                "total": count
            }
            
            with open("turnstile_tokens.jsonl", "a") as f:
                f.write(json.dumps(data) + "\n")
        except:
            pass
    
    def run(self):
        """Loop principal da aba"""
        self.log("Iniciando...", "info")
        
        while self.running:
            browser = None
            context = None
            page = None
            
            try:
                with sync_playwright() as p:
                    # Conectar ao Browserless
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        browser = p.chromium.connect_over_cdp(
                            self.ws_endpoint,
                            timeout=60000
                        )
                    
                    self.log("Conectado!", "ok")
                    
                    # Cria contexto com proxy BR
                    context = browser.new_context(
                        proxy=self.proxy,
                        viewport={"width": 380, "height": 320},
                        ignore_https_errors=True
                    )
                    
                    page = context.new_page()
                    
                    # Configura interceptação
                    page.route("**/*", self.route_handler)
                    
                    # Loop de resolução
                    while self.running:
                        token = self.solve_once(page)
                        
                        if token:
                            # Sucesso - recarrega para próximo
                            time.sleep(1)
                            try:
                                page.reload()
                            except:
                                break
                        else:
                            # Timeout - tenta recarregar
                            try:
                                page.reload()
                            except:
                                break
                            time.sleep(2)
                    
            except Exception as e:
                self.log(f"Erro conexão: {str(e)[:40]}", "err")
                time.sleep(3)
            
            finally:
                try:
                    if context:
                        context.close()
                    if browser:
                        browser.close()
                except:
                    pass
            
            if self.running:
                self.log("Reconectando...", "warn")
                time.sleep(2)
    
    def stop(self):
        self.running = False


def run_solver(endpoint: str, num_tabs: int = 5, sitekey: str = DEFAULT_SITEKEY,
               proxy_host: str = PROXY_HOST, proxy_port: str = PROXY_PORT,
               proxy_user: str = PROXY_USER, proxy_pass: str = PROXY_PASS,
               timeout_ms: int = 1800000):
    """Executa o solver com múltiplas abas"""
    
    # Ajusta endpoint - adiciona /chrome e timeout
    if "/chrome" not in endpoint:
        endpoint = endpoint.rstrip("/") + "/chrome"
    
    # Adiciona timeout à URL
    if "timeout=" not in endpoint:
        separator = "&" if "?" in endpoint else "?"
        endpoint = f"{endpoint}{separator}timeout={timeout_ms}"
    
    print("=" * 60)
    print("🚀 TURNSTILE SOLVER FINAL")
    print("=" * 60)
    print(f"Endpoint: {endpoint}")
    print(f"Sitekey: {sitekey}")
    print(f"Tabs: {num_tabs}")
    print(f"Proxy BR: {proxy_user}@{proxy_host}")
    print("=" * 60)
    
    stats = SolverStats()
    tabs: List[TurnstileSolverTab] = []
    
    # Cria abas
    for i in range(num_tabs):
        tab = TurnstileSolverTab(
            tab_id=i + 1,
            ws_endpoint=endpoint,
            sitekey=sitekey,
            proxy_host=proxy_host,
            proxy_port=proxy_port,
            proxy_user=proxy_user,
            proxy_pass=proxy_pass,
            stats=stats
        )
        tabs.append(tab)
    
    # Executa em threads
    threads = []
    try:
        for tab in tabs:
            t = Thread(target=tab.run, daemon=True)
            t.start()
            threads.append(t)
            time.sleep(0.5)  # Delay entre conexões
        
        print(f"\n✅ {num_tabs} abas iniciadas. Pressione Ctrl+C para parar.\n")
        
        # Aguarda threads
        while True:
            time.sleep(5)
            
            # Status
            elapsed = time.time() - stats.start_time
            rate = stats.total_solved / (elapsed / 60) if elapsed > 60 else stats.total_solved
            print(f"📊 Status: {stats.total_solved} tokens | {elapsed/60:.1f} min | {rate:.1f}/min")
            
    except KeyboardInterrupt:
        print("\n\n⏹️ Parando...")
        
        for tab in tabs:
            tab.stop()
        
        # Aguarda threads finalizarem
        for t in threads:
            t.join(timeout=5)
    
    # Stats finais
    elapsed = time.time() - stats.start_time
    rate = stats.total_solved / (elapsed / 60) if elapsed > 60 else stats.total_solved
    
    print("\n" + "=" * 60)
    print("📊 ESTATÍSTICAS FINAIS")
    print("=" * 60)
    print(f"Total resolvidos: {stats.total_solved}")
    print(f"Erros: {stats.total_errors}")
    print(f"Timeouts: {stats.total_timeouts}")
    print(f"Tempo total: {elapsed/60:.1f} minutos")
    print(f"Taxa: {rate:.1f} tokens/minuto")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Turnstile Solver Final")
    parser.add_argument("-e", "--endpoint", required=True, 
                        help="WebSocket endpoint do Browserless (ws://ip:port)")
    parser.add_argument("-t", "--tabs", type=int, default=5,
                        help="Número de abas paralelas (default: 5)")
    parser.add_argument("-s", "--sitekey", default=DEFAULT_SITEKEY,
                        help="Sitekey do Turnstile")
    parser.add_argument("--proxy-host", default=PROXY_HOST)
    parser.add_argument("--proxy-port", default=PROXY_PORT)
    parser.add_argument("--proxy-user", default=PROXY_USER)
    parser.add_argument("--proxy-pass", default=PROXY_PASS)
    
    args = parser.parse_args()
    
    run_solver(
        endpoint=args.endpoint,
        num_tabs=args.tabs,
        sitekey=args.sitekey,
        proxy_host=args.proxy_host,
        proxy_port=args.proxy_port,
        proxy_user=args.proxy_user,
        proxy_pass=args.proxy_pass
    )


if __name__ == "__main__":
    main()

