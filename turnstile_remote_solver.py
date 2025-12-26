#!/usr/bin/env python3
"""
Turnstile Remote Solver - Auto-instalador para máquinas remotas
================================================================
Este script:
1. Verifica e instala dependências automaticamente
2. Baixa e instala Patchright se necessário
3. Roda o solver de Turnstile
4. Envia logs via HTTP ou salva localmente

Uso em máquinas remotas:
    curl -O https://raw.githubusercontent.com/.../turnstile_remote_solver.py
    python3 turnstile_remote_solver.py --tabs 5
    
Ou via SSH:
    ssh user@host "python3 -c \"$(cat turnstile_remote_solver.py)\""
"""

import subprocess
import sys
import os
import json
import time
import random
import threading
import argparse
import socket
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# ============================================================
# AUTO-INSTALAÇÃO DE DEPENDÊNCIAS
# ============================================================

def install_package(package):
    """Instala um pacote via pip"""
    print(f"[SETUP] Instalando {package}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package])

def check_and_install_deps():
    """Verifica e instala dependências necessárias"""
    print("=" * 60)
    print("🔧 VERIFICANDO DEPENDÊNCIAS")
    print("=" * 60)
    
    # Lista de dependências
    deps = {
        "patchright": "patchright",
    }
    
    for module, package in deps.items():
        try:
            __import__(module)
            print(f"[OK] {module} já instalado")
        except ImportError:
            print(f"[!] {module} não encontrado, instalando...")
            try:
                install_package(package)
                print(f"[OK] {package} instalado com sucesso")
            except Exception as e:
                print(f"[ERRO] Falha ao instalar {package}: {e}")
                return False
    
    # Instala browsers do Patchright
    print("[SETUP] Verificando browsers...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "patchright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            print("[OK] Chromium instalado/verificado")
        else:
            print(f"[WARN] Problema ao instalar chromium: {result.stderr[:100]}")
    except Exception as e:
        print(f"[WARN] Erro ao verificar chromium: {e}")
    
    print("=" * 60)
    return True


# ============================================================
# CONFIGURAÇÕES
# ============================================================

TOKEN_FILE = "turnstile_tokens.jsonl"
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
stats = {"solved": 0, "reloads": 0, "errors": 0, "start_time": None}
stats_lock = threading.Lock()
stop_flag = threading.Event()

# HTML template
PAGE_HTML = """<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Tab {tab_id}</title>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<style>
body {{ background: #0f0f1a; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: system-ui; }}
.box {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 25px 35px; border-radius: 16px; text-align: center; color: #fff; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }}
h2 {{ margin: 0 0 5px; color: #4ade80; font-size: 28px; }}
.info {{ font-size: 12px; color: #888; margin-bottom: 15px; }}
</style>
</head><body>
<div class="box">
<h2>🔐 Tab #{tab_id}</h2>
<div class="info">{hostname}</div>
<div class="cf-turnstile" data-sitekey="{sitekey}"></div>
</div>
</body></html>"""


def get_hostname():
    """Retorna hostname da máquina"""
    try:
        return socket.gethostname()
    except:
        return "unknown"


def log(msg: str, level: str = "info"):
    """Log formatado com timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"info": "ℹ️", "ok": "✅", "err": "❌", "warn": "⚠️", "token": "🎟️"}
    icon = icons.get(level, "•")
    hostname = get_hostname()
    print(f"[{ts}] [{hostname}] {icon} {msg}")


def save_token(token: str, tab_id: int, processing_time: float):
    """Salva token em arquivo JSONL"""
    entry = {
        "token": token,
        "hostname": get_hostname(),
        "tab_id": tab_id,
        "timestamp": datetime.now().isoformat(),
        "processing_time": round(processing_time, 2),
        "sitekey": SITEKEY
    }
    
    with file_lock:
        with open(TOKEN_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    return entry


def worker(tab_id: int, use_proxy: bool = True, headless: bool = True):
    """Worker que resolve Turnstile continuamente"""
    from patchright.sync_api import sync_playwright
    
    solve_count = 0
    hostname = get_hostname()
    
    log(f"Tab #{tab_id}: Iniciando browser...")
    
    while not stop_flag.is_set():
        try:
            with sync_playwright() as p:
                # Lança browser
                browser = p.chromium.launch(headless=headless)
                
                # Contexto com proxy
                context_opts = {"viewport": {"width": 380, "height": 320}}
                if use_proxy:
                    context_opts["proxy"] = PROXY
                
                context = browser.new_context(**context_opts)
                page = context.new_page()
                
                # HTML personalizado
                page_html = PAGE_HTML.format(
                    tab_id=tab_id, 
                    sitekey=SITEKEY,
                    hostname=hostname
                )
                
                # Intercepta URL
                page.route(TARGET_URL + "**", lambda route: route.fulfill(
                    body=page_html, status=200, content_type="text/html"
                ))
                
                # Navega
                page.goto(TARGET_URL)
                log(f"Tab #{tab_id}: Pronta", "ok")
                
                # Loop de resolução
                while not stop_flag.is_set():
                    start_time = time.time()
                    click_count = 0
                    resolved = False
                    
                    while time.time() - start_time < 60 and not stop_flag.is_set():
                        # Verifica token
                        try:
                            elem = page.query_selector("[name=cf-turnstile-response]")
                            if elem:
                                token = elem.get_attribute("value")
                                if token and len(token) > 50:
                                    solve_time = time.time() - start_time
                                    solve_count += 1
                                    
                                    # Salva
                                    save_token(token, tab_id, solve_time)
                                    
                                    with stats_lock:
                                        stats["solved"] += 1
                                        total = stats["solved"]
                                    
                                    log(f"Tab #{tab_id}: TOKEN #{solve_count} em {solve_time:.1f}s (Total: {total})", "token")
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
                    
                    if not resolved:
                        with stats_lock:
                            stats["reloads"] += 1
                        log(f"Tab #{tab_id}: Timeout - recarregando...", "warn")
                    
                    # Reload
                    if not stop_flag.is_set():
                        try:
                            page.reload()
                            time.sleep(0.5)
                        except:
                            break
                
                context.close()
                browser.close()
                
        except Exception as e:
            with stats_lock:
                stats["errors"] += 1
            log(f"Tab #{tab_id}: Erro: {str(e)[:50]}", "err")
            time.sleep(3)
        
        if not stop_flag.is_set():
            log(f"Tab #{tab_id}: Reiniciando...", "warn")
            time.sleep(2)


def run_solver(num_tabs: int = 5, use_proxy: bool = True, headless: bool = True):
    """Executa o solver com múltiplas tabs"""
    
    hostname = get_hostname()
    
    print()
    print("=" * 60)
    print("🚀 TURNSTILE REMOTE SOLVER")
    print("=" * 60)
    print(f"Hostname: {hostname}")
    print(f"Tabs: {num_tabs}")
    print(f"Proxy BR: {'Sim' if use_proxy else 'Não'}")
    print(f"Headless: {'Sim' if headless else 'Não'}")
    print(f"Sitekey: {SITEKEY}")
    print(f"Tokens: {TOKEN_FILE}")
    print("=" * 60)
    print()
    print("Pressione Ctrl+C para parar")
    print()
    
    stats["start_time"] = time.time()
    
    with ThreadPoolExecutor(max_workers=num_tabs) as executor:
        futures = [
            executor.submit(worker, i+1, use_proxy, headless)
            for i in range(num_tabs)
        ]
        
        try:
            while True:
                time.sleep(10)
                elapsed = time.time() - stats["start_time"]
                rate = stats["solved"] / (elapsed / 60) if elapsed > 0 else 0
                
                print()
                log(f"📊 {stats['solved']} tokens | {stats['reloads']} reloads | {stats['errors']} erros | {rate:.1f}/min | {elapsed/60:.1f} min")
                print()
                
        except KeyboardInterrupt:
            print()
            log("Finalizando...", "warn")
            stop_flag.set()
    
    # Resumo
    elapsed = time.time() - stats["start_time"]
    
    print()
    print("=" * 60)
    print("📊 RESUMO FINAL")
    print("=" * 60)
    print(f"Hostname: {hostname}")
    print(f"Tokens: {stats['solved']}")
    print(f"Reloads: {stats['reloads']}")
    print(f"Erros: {stats['errors']}")
    print(f"Tempo: {elapsed/60:.1f} min")
    if elapsed > 0:
        print(f"Taxa: {stats['solved']/(elapsed/60):.1f} tokens/min")
    print(f"Arquivo: {TOKEN_FILE}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Turnstile Remote Solver")
    parser.add_argument("--tabs", "-t", type=int, default=5, help="Número de tabs (default: 5)")
    parser.add_argument("--no-proxy", action="store_true", help="Não usar proxy")
    parser.add_argument("--visible", action="store_true", help="Mostrar browser (não headless)")
    parser.add_argument("--skip-install", action="store_true", help="Pular instalação de deps")
    
    args = parser.parse_args()
    
    # Verifica deps (a menos que --skip-install)
    if not args.skip_install:
        if not check_and_install_deps():
            print("[ERRO] Falha ao instalar dependências")
            sys.exit(1)
    
    # Roda solver
    run_solver(
        num_tabs=args.tabs,
        use_proxy=not args.no_proxy,
        headless=not args.visible
    )


if __name__ == "__main__":
    main()










