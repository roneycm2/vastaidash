"""
Turnstile Persistent Solver - Abas Persistentes
================================================
Mantém as abas abertas e recicla após cada resolução.
Não fecha os browsers - apenas recarrega a página.
Máxima eficiência!

Uso:
    python turnstile_persistent_solver.py --tabs 5
    python turnstile_persistent_solver.py --tabs 10
    Ctrl+C para parar
"""

import json
import random
import time
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from patchright.sync_api import sync_playwright

# Configurações
TOKEN_FILE = "turnstile_token.json"
SITEKEY_FILE = "turnstile_sitekey.json"

# Proxy
PROXY = {
    "server": "http://fb29d01db8530b99.shg.na.pyproxy.io:16666",
    "username": "liderbet1-zone-mob-region-br",
    "password": "Aa10203040"
}

# Lock para escrita
file_lock = threading.Lock()

# Stats globais
stats = {
    "solved": 0,
    "reloads": 0,
    "start_time": None
}
stats_lock = threading.Lock()

# Flag para parar
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


def load_sitekey() -> str:
    try:
        with open(SITEKEY_FILE, 'r') as f:
            return json.load(f).get("sitekey", "0x4AAAAAAAykd8yJm3kQzNJc")
    except:
        return "0x4AAAAAAAykd8yJm3kQzNJc"


def save_token(token: str, tab_id: int, processing_time: float, sitekey: str, solve_count: int):
    """Salva token com lock para thread-safety"""
    entry = {
        "token": token,
        "url": "https://7k.bet.br",
        "sitekey": sitekey,
        "tab_id": tab_id,
        "solve_number": solve_count,
        "timestamp": datetime.now().isoformat(),
        "expires_in": 300,
        "processing_time_seconds": round(processing_time, 2),
        "valid": True
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
            json.dump(tokens, f, indent=2, ensure_ascii=False)


def persistent_tab_worker(tab_id: int, sitekey: str, use_proxy: bool = True):
    """
    Worker que mantém uma aba aberta indefinidamente.
    Após resolver ou timeout, recarrega e tenta novamente.
    """
    solve_count = 0
    url = "https://7k.bet.br/"
    
    print(f"    [Tab {tab_id}] Iniciando browser...")
    
    with sync_playwright() as p:
        # Lança browser (fica aberto até Ctrl+C)
        browser = p.chromium.launch(headless=False)
        
        # Pega user agent real do browser
        temp_page = browser.new_page()
        real_user_agent = temp_page.evaluate("navigator.userAgent")
        temp_page.close()
        
        print(f"    [Tab {tab_id}] User-Agent: {real_user_agent[:70]}...")
        
        context_opts = {
            "viewport": {"width": 380, "height": 320},
            "user_agent": real_user_agent
        }
        if use_proxy:
            context_opts["proxy"] = PROXY
        
        context = browser.new_context(**context_opts)
        page = context.new_page()
        
        # Intercepta requisições para servir nossa página
        page_html = PAGE_HTML.format(tab_id=tab_id, sitekey=sitekey)
        page.route(url + "**", lambda route: route.fulfill(
            body=page_html, status=200, content_type="text/html"
        ))
        
        # Primeira navegação
        page.goto(url)
        print(f"    [Tab {tab_id}] Pronta")
        
        # Loop infinito até stop_flag
        while not stop_flag.is_set():
            start_time = time.time()
            click_count = 0
            resolved = False
            max_time = 60  # Timeout por tentativa
            
            # Loop de resolução
            while time.time() - start_time < max_time and not stop_flag.is_set():
                # Verifica token
                try:
                    elem = page.query_selector("[name=cf-turnstile-response]")
                    if elem:
                        token = elem.get_attribute("value")
                        if token and len(token) > 50:
                            processing_time = time.time() - start_time
                            solve_count += 1
                            
                            # Salva
                            save_token(token, tab_id, processing_time, sitekey, solve_count)
                            
                            # Stats
                            with stats_lock:
                                stats["solved"] += 1
                            
                            print(f"    ✓ [Tab {tab_id}] #{solve_count} RESOLVIDO em {processing_time:.1f}s (Total: {stats['solved']})")
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
            
            # Se não resolveu (timeout), registra
            if not resolved and not stop_flag.is_set():
                with stats_lock:
                    stats["reloads"] += 1
                print(f"    ⟳ [Tab {tab_id}] Timeout - recarregando...")
            
            # Recarrega a página para próxima tentativa
            if not stop_flag.is_set():
                try:
                    page.reload()
                    time.sleep(0.5)  # Pequena pausa após reload
                except:
                    # Se falhar reload, tenta goto
                    try:
                        page.goto(url)
                    except:
                        pass
        
        # Cleanup quando stop_flag é setada
        print(f"    [Tab {tab_id}] Fechando (Ctrl+C detectado)...")
        context.close()
        browser.close()


def run_persistent_solver(num_tabs: int = 5, use_proxy: bool = True):
    """
    Executa o solver com abas persistentes.
    As abas nunca fecham - apenas recarregam após cada resolução.
    """
    sitekey = load_sitekey()
    
    print("=" * 70)
    print("🚀 TURNSTILE PERSISTENT SOLVER")
    print("=" * 70)
    print()
    print(f"[*] Tabs persistentes: {num_tabs}")
    print(f"[*] Sitekey: {sitekey}")
    print(f"[*] Proxy: {'Sim' if use_proxy else 'Não'}")
    print()
    print("[*] Pressione Ctrl+C para parar")
    print()
    print("=" * 70)
    print()
    
    stats["start_time"] = time.time()
    
    # Inicia threads
    print(f"[*] Iniciando {num_tabs} tabs persistentes...")
    print()
    
    with ThreadPoolExecutor(max_workers=num_tabs) as executor:
        futures = [
            executor.submit(persistent_tab_worker, i+1, sitekey, use_proxy)
            for i in range(num_tabs)
        ]
        
        try:
            # Aguarda indefinidamente (até Ctrl+C)
            while True:
                time.sleep(10)
                
                # Status periódico
                elapsed = time.time() - stats["start_time"]
                rate = stats["solved"] / (elapsed / 60) if elapsed > 0 else 0
                
                print()
                print(f"    📊 Status: {stats['solved']} tokens | {stats['reloads']} reloads | {rate:.1f} tokens/min | {elapsed/60:.1f} min")
                print()
        
        except KeyboardInterrupt:
            print()
            print()
            print("[!] Ctrl+C detectado - finalizando...")
            stop_flag.set()
    
    # Resumo final
    elapsed = time.time() - stats["start_time"]
    
    print()
    print("=" * 70)
    print("📊 RESUMO FINAL")
    print("=" * 70)
    print(f"Tempo total: {elapsed/60:.1f} minutos")
    print(f"Tokens resolvidos: {stats['solved']}")
    print(f"Reloads (timeouts): {stats['reloads']}")
    if elapsed > 0:
        print(f"Taxa: {stats['solved']/(elapsed/60):.1f} tokens/minuto")
    print(f"Arquivo: {TOKEN_FILE}")
    print()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Turnstile Persistent Solver")
    parser.add_argument("--tabs", type=int, default=5, help="Número de tabs persistentes")
    parser.add_argument("--no-proxy", action="store_true", help="Sem proxy")
    
    args = parser.parse_args()
    
    run_persistent_solver(
        num_tabs=args.tabs,
        use_proxy=not args.no_proxy
    )




