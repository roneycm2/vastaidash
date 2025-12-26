"""
Turnstile Solver para Browserless usando Patchright
====================================================
Combina a técnica do Patchright com conexão CDP ao Browserless.

A diferença chave é que:
- LOCAL: usa p.chromium.launch() - abre browser local
- BROWSERLESS: usa p.chromium.connect_over_cdp() - conecta a browser remoto

O Patchright modifica o driver do Playwright para evitar detecção,
mas quando conectamos via CDP a um browser que NÃO foi lançado pelo Patchright,
perdemos as modificações anti-detecção.

SOLUÇÃO: O Browserless precisa ser configurado com flags anti-detecção,
ou usar uma imagem de Browserless com Patchright integrado.

Este script tenta replicar o comportamento do solver local.
"""

import json
import random
import time
import threading
import argparse
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Usa Patchright (modificado anti-detecção) ao invés de Playwright padrão
try:
    from patchright.sync_api import sync_playwright
    USING_PATCHRIGHT = True
except ImportError:
    from playwright.sync_api import sync_playwright
    USING_PATCHRIGHT = False

# Configurações
TOKEN_FILE = "turnstile_token.json"
SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
TARGET_URL = "https://7k.bet.br/"

# Proxy BR
PROXY = {
    "server": "http://fb29d01db8530b99.shg.na.pyproxy.io:16666",
    "username": "liderbet1-zone-mob-region-br",
    "password": "Aa10203040"
}

# Threading
file_lock = threading.Lock()
stats = {"solved": 0, "reloads": 0, "start_time": None}
stats_lock = threading.Lock()
stop_flag = threading.Event()

# HTML da página
PAGE_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Tab {tab_id}</title>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<style>
body {{ background: #0f0f1a; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: system-ui; }}
.box {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 25px 35px; border-radius: 16px; text-align: center; color: #fff; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }}
h2 {{ margin: 0 0 5px; color: #4ade80; font-size: 28px; }}
.count {{ font-size: 14px; color: #888; margin-bottom: 15px; }}
</style>
</head><body>
<div class="box">
<h2>Tab #{tab_id}</h2>
<div class="count">Resolvendo...</div>
<div class="cf-turnstile" data-sitekey="{sitekey}"></div>
</div>
</body></html>"""


def save_token(token: str, tab_id: int, processing_time: float, sitekey: str, solve_count: int):
    """Salva token"""
    entry = {
        "token": token,
        "url": TARGET_URL,
        "sitekey": sitekey,
        "tab_id": tab_id,
        "solve_number": solve_count,
        "timestamp": datetime.now().isoformat(),
        "processing_time_seconds": round(processing_time, 2)
    }
    
    with file_lock:
        tokens = []
        path = Path(TOKEN_FILE)
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    tokens = data if isinstance(data, list) else [data]
            except:
                pass
        tokens.append(entry)
        with open(TOKEN_FILE, 'w') as f:
            json.dump(tokens, f, indent=2)


def log(tab_id: int, msg: str, level: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"info": "ℹ️", "ok": "✅", "err": "❌", "warn": "⚠️", "token": "🎟️"}
    print(f"[{ts}] {icons.get(level, '•')} Tab #{tab_id}: {msg}")


def browserless_worker(tab_id: int, ws_endpoint: str, use_proxy: bool = True):
    """
    Worker que conecta ao Browserless e resolve Turnstile.
    Usa Patchright se disponível.
    """
    solve_count = 0
    
    log(tab_id, "Iniciando...")
    
    while not stop_flag.is_set():
        try:
            with sync_playwright() as p:
                # Conecta ao Browserless via CDP
                log(tab_id, f"Conectando a {ws_endpoint[:50]}...")
                browser = p.chromium.connect_over_cdp(ws_endpoint, timeout=60000)
                
                log(tab_id, "Conectado!", "ok")
                
                # Cria contexto com proxy
                context_opts = {
                    "viewport": {"width": 380, "height": 320},
                    "ignore_https_errors": True
                }
                if use_proxy:
                    context_opts["proxy"] = PROXY
                
                context = browser.new_context(**context_opts)
                page = context.new_page()
                
                # Intercepta URL para servir HTML
                page_html = PAGE_HTML.format(tab_id=tab_id, sitekey=SITEKEY)
                page.route(TARGET_URL + "**", lambda route: route.fulfill(
                    body=page_html, status=200, content_type="text/html"
                ))
                
                # Navega
                page.goto(TARGET_URL)
                log(tab_id, "Página pronta")
                
                # Loop de resolução
                while not stop_flag.is_set():
                    start_time = time.time()
                    click_count = 0
                    resolved = False
                    max_time = 60
                    
                    while time.time() - start_time < max_time and not stop_flag.is_set():
                        # Verifica token
                        try:
                            elem = page.query_selector("[name=cf-turnstile-response]")
                            if elem:
                                token = elem.get_attribute("value")
                                if token and len(token) > 50:
                                    processing_time = time.time() - start_time
                                    solve_count += 1
                                    
                                    save_token(token, tab_id, processing_time, SITEKEY, solve_count)
                                    
                                    with stats_lock:
                                        stats["solved"] += 1
                                        total = stats["solved"]
                                    
                                    log(tab_id, f"TOKEN #{solve_count} em {processing_time:.1f}s (Total: {total})", "token")
                                    resolved = True
                                    break
                        except:
                            pass
                        
                        # Clica no checkbox
                        if click_count < 5:
                            try:
                                iframe = page.query_selector("iframe")
                                if iframe:
                                    box = iframe.bounding_box()
                                    if box and box["width"] > 0:
                                        frame = iframe.content_frame()
                                        if frame:
                                            checkbox = frame.query_selector("input")
                                            if checkbox:
                                                cbox = checkbox.bounding_box()
                                                if cbox:
                                                    x = cbox["x"] + cbox["width"]/2 + random.randint(-3, 3)
                                                    y = cbox["y"] + cbox["height"]/2 + random.randint(-3, 3)
                                                    page.mouse.click(x, y)
                                                    click_count += 1
                                            elif click_count < 2:
                                                x = box["x"] + box["width"]/2
                                                y = box["y"] + box["height"]/2
                                                page.mouse.click(x, y)
                                                click_count += 1
                            except:
                                pass
                        
                        time.sleep(0.1)
                    
                    if not resolved and not stop_flag.is_set():
                        with stats_lock:
                            stats["reloads"] += 1
                        log(tab_id, "Timeout - recarregando...", "warn")
                    
                    # Reload para próxima tentativa
                    if not stop_flag.is_set():
                        try:
                            page.reload()
                            time.sleep(0.5)
                        except:
                            break
                
                context.close()
                browser.close()
                
        except Exception as e:
            log(tab_id, f"Erro: {str(e)[:40]}", "err")
            time.sleep(3)
        
        if not stop_flag.is_set():
            log(tab_id, "Reconectando...", "warn")
            time.sleep(2)


def run_browserless_solver(ws_endpoint: str, num_tabs: int = 5, use_proxy: bool = True):
    """Executa solver com múltiplas tabs no Browserless"""
    
    # Remove trailing slash
    ws_endpoint = ws_endpoint.rstrip("/")
    
    # Adiciona /chrome antes de qualquer query param
    if "/chrome" not in ws_endpoint:
        # Se já tem query params, insere /chrome antes deles
        if "?" in ws_endpoint:
            base, params = ws_endpoint.split("?", 1)
            ws_endpoint = f"{base}/chrome?{params}"
        else:
            ws_endpoint = f"{ws_endpoint}/chrome"
    
    # Adiciona timeout se não tiver
    if "timeout=" not in ws_endpoint:
        sep = "&" if "?" in ws_endpoint else "?"
        ws_endpoint = f"{ws_endpoint}{sep}timeout=1800000"
    
    print("=" * 70)
    print("🚀 TURNSTILE BROWSERLESS SOLVER")
    print("=" * 70)
    print(f"Usando: {'Patchright' if USING_PATCHRIGHT else 'Playwright padrão'}")
    print(f"Endpoint: {ws_endpoint}")
    print(f"Tabs: {num_tabs}")
    print(f"Proxy: {'Sim' if use_proxy else 'Não'}")
    print("=" * 70)
    print()
    
    stats["start_time"] = time.time()
    
    with ThreadPoolExecutor(max_workers=num_tabs) as executor:
        futures = [
            executor.submit(browserless_worker, i+1, ws_endpoint, use_proxy)
            for i in range(num_tabs)
        ]
        
        try:
            while True:
                time.sleep(10)
                elapsed = time.time() - stats["start_time"]
                rate = stats["solved"] / (elapsed / 60) if elapsed > 0 else 0
                print(f"\n📊 Status: {stats['solved']} tokens | {stats['reloads']} reloads | {rate:.1f}/min | {elapsed/60:.1f} min\n")
                
        except KeyboardInterrupt:
            print("\n[!] Finalizando...")
            stop_flag.set()
    
    elapsed = time.time() - stats["start_time"]
    print()
    print("=" * 70)
    print(f"📊 Total: {stats['solved']} tokens em {elapsed/60:.1f} min")
    print("=" * 70)


def run_local_solver(num_tabs: int = 5, use_proxy: bool = True):
    """Executa solver local (sem Browserless) - usa browser local"""
    
    print("=" * 70)
    print("🚀 TURNSTILE LOCAL SOLVER")
    print("=" * 70)
    print(f"Usando: {'Patchright' if USING_PATCHRIGHT else 'Playwright padrão'}")
    print(f"Tabs: {num_tabs}")
    print(f"Proxy: {'Sim' if use_proxy else 'Não'}")
    print("=" * 70)
    print()
    
    def local_worker(tab_id: int):
        solve_count = 0
        log(tab_id, "Iniciando browser local...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            
            context_opts = {"viewport": {"width": 380, "height": 320}}
            if use_proxy:
                context_opts["proxy"] = PROXY
            
            context = browser.new_context(**context_opts)
            page = context.new_page()
            
            page_html = PAGE_HTML.format(tab_id=tab_id, sitekey=SITEKEY)
            page.route(TARGET_URL + "**", lambda route: route.fulfill(
                body=page_html, status=200, content_type="text/html"
            ))
            
            page.goto(TARGET_URL)
            log(tab_id, "Pronta", "ok")
            
            while not stop_flag.is_set():
                start_time = time.time()
                click_count = 0
                resolved = False
                
                while time.time() - start_time < 60 and not stop_flag.is_set():
                    try:
                        elem = page.query_selector("[name=cf-turnstile-response]")
                        if elem:
                            token = elem.get_attribute("value")
                            if token and len(token) > 50:
                                solve_count += 1
                                with stats_lock:
                                    stats["solved"] += 1
                                log(tab_id, f"TOKEN #{solve_count} em {time.time()-start_time:.1f}s (Total: {stats['solved']})", "token")
                                save_token(token, tab_id, time.time()-start_time, SITEKEY, solve_count)
                                resolved = True
                                break
                    except:
                        pass
                    
                    if click_count < 5:
                        try:
                            iframe = page.query_selector("iframe")
                            if iframe:
                                box = iframe.bounding_box()
                                if box and box["width"] > 0:
                                    frame = iframe.content_frame()
                                    if frame:
                                        checkbox = frame.query_selector("input")
                                        if checkbox:
                                            cbox = checkbox.bounding_box()
                                            if cbox:
                                                page.mouse.click(cbox["x"]+cbox["width"]/2, cbox["y"]+cbox["height"]/2)
                                                click_count += 1
                        except:
                            pass
                    
                    time.sleep(0.1)
                
                if not resolved:
                    with stats_lock:
                        stats["reloads"] += 1
                
                if not stop_flag.is_set():
                    page.reload()
                    time.sleep(0.5)
            
            context.close()
            browser.close()
    
    stats["start_time"] = time.time()
    
    with ThreadPoolExecutor(max_workers=num_tabs) as executor:
        futures = [executor.submit(local_worker, i+1) for i in range(num_tabs)]
        
        try:
            while True:
                time.sleep(10)
                elapsed = time.time() - stats["start_time"]
                rate = stats["solved"] / (elapsed / 60) if elapsed > 0 else 0
                print(f"\n📊 Status: {stats['solved']} tokens | {rate:.1f}/min | {elapsed/60:.1f} min\n")
        except KeyboardInterrupt:
            stop_flag.set()
    
    elapsed = time.time() - stats["start_time"]
    print(f"\n📊 Total: {stats['solved']} tokens em {elapsed/60:.1f} min")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Turnstile Solver - Local ou Browserless")
    parser.add_argument("-e", "--endpoint", help="WebSocket endpoint do Browserless (omita para rodar local)")
    parser.add_argument("-t", "--tabs", type=int, default=5, help="Número de tabs")
    parser.add_argument("--no-proxy", action="store_true", help="Sem proxy")
    
    args = parser.parse_args()
    
    if args.endpoint:
        run_browserless_solver(args.endpoint, args.tabs, not args.no_proxy)
    else:
        run_local_solver(args.tabs, not args.no_proxy)

