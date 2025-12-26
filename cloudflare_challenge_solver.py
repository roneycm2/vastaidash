"""
Cloudflare Challenge Solver - Abas Persistentes
================================================
Resolve o Cloudflare managed challenge usando abas persistentes.
Usa o HTML real do Cloudflare challenge.

Uso:
    python cloudflare_challenge_solver.py --tabs 5
    python cloudflare_challenge_solver.py --tabs 10
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
TOKEN_FILE = "cloudflare_token.json"

# Nova Proxy
PROXY = {
    "server": "http://pybpm-ins-hxqlzicm.pyproxy.io:2510",
    "username": "liderbet1-zone-adam-region-br-session-dc5736626334-sessTime-15",
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

# Arquivo HTML do Cloudflare Challenge
CHALLENGE_HTML_FILE = "index.html"

def load_challenge_html():
    """Carrega o HTML do arquivo index.html"""
    html_path = Path(__file__).parent / CHALLENGE_HTML_FILE
    if html_path.exists():
        with open(html_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise FileNotFoundError(f"Arquivo {CHALLENGE_HTML_FILE} não encontrado!")


def save_token(token: str, tab_id: int, processing_time: float, solve_count: int, cookies: list = None):
    """Salva token/cookies com lock para thread-safety"""
    entry = {
        "token": token,
        "url": "https://7k.bet.br",
        "tab_id": tab_id,
        "solve_number": solve_count,
        "timestamp": datetime.now().isoformat(),
        "expires_in": 300,
        "processing_time_seconds": round(processing_time, 2),
        "cookies": cookies or [],
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


def persistent_tab_worker(tab_id: int, use_proxy: bool = True):
    """
    Worker que mantém uma aba aberta indefinidamente.
    Navega para a página real do 7k.bet.br e deixa o Cloudflare servir o challenge.
    Após resolver ou timeout, recarrega e tenta novamente.
    """
    solve_count = 0
    url = "https://7k.bet.br/"
    
    # Carrega o HTML do arquivo index.html
    challenge_html = load_challenge_html()
    
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
            "viewport": {"width": 450, "height": 400},
            "user_agent": real_user_agent
        }
        if use_proxy:
            context_opts["proxy"] = PROXY
        
        context = browser.new_context(**context_opts)
        page = context.new_page()
        
        # Whitelist - URLs que passam direto para o servidor real
        WHITELIST = [
            "/cdn-cgi/",            # Scripts do Cloudflare
            "/challenge-platform/", # Challenge platform
            "/api/documents",       # Endpoint de documentos (7k.bet.br/api/documents)
            "/api/documents/validate",  # Endpoint de validação do Cloudflare
            ".js",                  # JavaScript files
            ".css",                 # CSS files
            ".png",                 # Imagens
            ".jpg",
            ".svg",
            ".woff",                # Fontes
            ".woff2",
            ".ttf",
        ]
        
        # Intercepta requisições - whitelist passa direto
        def handle_route(route):
            request_url = route.request.url
            
            # Verifica se está na whitelist
            for pattern in WHITELIST:
                if pattern in request_url:
                    # Deixa passar para o servidor real
                    route.continue_()
                    return
            
            # Se for a página principal, serve nosso HTML
            if request_url.rstrip('/') == url.rstrip('/') or request_url == url:
                route.fulfill(
                    body=challenge_html,
                    status=200,
                    content_type="text/html; charset=UTF-8"
                )
            else:
                # Outras requisições passam para o servidor real
                route.continue_()
        
        page.route("**/*", handle_route)
        
        # Primeira navegação
        try:
            page.goto(url, timeout=30000)
            print(f"    [Tab {tab_id}] Pronta - Challenge carregado")
        except Exception as e:
            print(f"    [Tab {tab_id}] Erro ao carregar: {e}")
        
        # Loop infinito até stop_flag
        while not stop_flag.is_set():
            start_time = time.time()
            click_count = 0
            resolved = False
            max_time = 120  # Timeout por tentativa (2 min para challenge)
            
            # Loop de resolução
            while time.time() - start_time < max_time and not stop_flag.is_set():
                try:
                    # Verifica se o challenge foi resolvido
                    # O Cloudflare normalmente redireciona ou muda a página após resolver
                    
                    # Verifica se não está mais na página "Just a moment..."
                    title = page.title()
                    if "Just a moment" not in title and title != "":
                        processing_time = time.time() - start_time
                        solve_count += 1
                        
                        # Pega cookies do contexto
                        cookies = context.cookies()
                        cf_clearance = None
                        for cookie in cookies:
                            if cookie.get("name") == "cf_clearance":
                                cf_clearance = cookie.get("value")
                                break
                        
                        if cf_clearance:
                            # Salva o cf_clearance como token
                            save_token(cf_clearance, tab_id, processing_time, solve_count, cookies)
                            
                            # Stats
                            with stats_lock:
                                stats["solved"] += 1
                            
                            print(f"    ✓ [Tab {tab_id}] #{solve_count} RESOLVIDO em {processing_time:.1f}s (Total: {stats['solved']})")
                            resolved = True
                            break
                    
                    # Verifica cf-turnstile-response (pode aparecer em alguns challenges)
                    elem = page.query_selector("[name=cf-turnstile-response]")
                    if elem:
                        token = elem.get_attribute("value")
                        if token and len(token) > 50:
                            processing_time = time.time() - start_time
                            solve_count += 1
                            
                            cookies = context.cookies()
                            save_token(token, tab_id, processing_time, solve_count, cookies)
                            
                            with stats_lock:
                                stats["solved"] += 1
                            
                            print(f"    ✓ [Tab {tab_id}] #{solve_count} TURNSTILE em {processing_time:.1f}s (Total: {stats['solved']})")
                            resolved = True
                            break
                    
                    # Tenta clicar em elementos do challenge
                    if click_count < 5:
                        try:
                            # Procura iframe do Cloudflare
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
                
                except Exception as e:
                    pass
                
                time.sleep(0.2)
            
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


def run_challenge_solver(num_tabs: int = 5, use_proxy: bool = True):
    """
    Executa o solver de Cloudflare challenge com abas persistentes.
    As abas nunca fecham - apenas recarregam após cada resolução.
    """
    print("=" * 70)
    print("🛡️  CLOUDFLARE CHALLENGE SOLVER")
    print("=" * 70)
    print()
    print(f"[*] Tabs persistentes: {num_tabs}")
    print(f"[*] Proxy: {'Sim' if use_proxy else 'Não'}")
    if use_proxy:
        print(f"    Server: {PROXY['server']}")
        print(f"    User: {PROXY['username'][:40]}...")
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
            executor.submit(persistent_tab_worker, i+1, use_proxy)
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
    
    parser = argparse.ArgumentParser(description="Cloudflare Challenge Solver")
    parser.add_argument("--tabs", type=int, default=5, help="Número de tabs persistentes")
    parser.add_argument("--no-proxy", action="store_true", help="Sem proxy")
    
    args = parser.parse_args()
    
    run_challenge_solver(
        num_tabs=args.tabs,
        use_proxy=not args.no_proxy
    )

