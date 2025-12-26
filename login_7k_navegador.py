"""
Login 7k.bet.br via Navegador (Browserless/Playwright)
1. Conecta ao Browserless
2. Acessa o site (passa pelo Cloudflare)
3. Resolve Turnstile via Anti-Captcha
4. Faz login via JavaScript no navegador
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
import json
import requests
from playwright.sync_api import sync_playwright

# Configuracoes
ANTICAPTCHA_KEY = os.getenv("ANTICAPTCHA_KEY", "")
TURNSTILE_SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"

PROXY_CONFIG = {
    "server": os.getenv("SEVENK_PROXY_SERVER", ""),
    "username": os.getenv("SEVENK_PROXY_USERNAME", ""),
    "password": os.getenv("SEVENK_PROXY_PASSWORD", "")
}

# Credenciais
EMAIL = os.getenv("SEVENK_EMAIL", "")
SENHA = os.getenv("SEVENK_PASSWORD", "")

# Browserless (ajuste conforme necessario)
WS_ENDPOINT = os.getenv("BROWSERLESS_WS_ENDPOINT", "ws://127.0.0.1:9222")


def resolver_turnstile_anticaptcha():
    """Resolve o Turnstile via Anti-Captcha API."""
    print("\n[1] RESOLVENDO TURNSTILE VIA ANTI-CAPTCHA...")
    print(f"    SiteKey: {TURNSTILE_SITEKEY}")
    
    # Criar tarefa
    resp = requests.post(
        "https://api.anti-captcha.com/createTask",
        json={
            "clientKey": ANTICAPTCHA_KEY,
            "task": {
                "type": "TurnstileTaskProxyless",
                "websiteURL": "https://7k.bet.br",
                "websiteKey": TURNSTILE_SITEKEY
            }
        },
        timeout=30
    )
    
    data = resp.json()
    if data.get("errorId") != 0:
        raise Exception(f"Erro Anti-Captcha: {data.get('errorCode')}")
    
    task_id = data["taskId"]
    print(f"    TaskId: {task_id}")
    print("    Aguardando resolucao...")
    
    # Aguardar resultado
    for i in range(40):
        time.sleep(3)
        print(f"    Verificando... {(i+1)*3}s")
        
        resp = requests.post(
            "https://api.anti-captcha.com/getTaskResult",
            json={
                "clientKey": ANTICAPTCHA_KEY,
                "taskId": task_id
            },
            timeout=30
        )
        
        data = resp.json()
        if data.get("status") == "ready":
            token = data["solution"]["token"]
            print(f"    TOKEN OBTIDO!")
            return token
    
    raise Exception("Timeout ao resolver Turnstile")


def fazer_login_via_navegador(captcha_token):
    """Faz login usando navegador real via Browserless."""
    print("\n[2] FAZENDO LOGIN VIA NAVEGADOR...")
    
    with sync_playwright() as p:
        # Tenta conectar ao Browserless
        print(f"    Conectando ao Browserless: {WS_ENDPOINT}")
        
        try:
            browser = p.chromium.connect_over_cdp(WS_ENDPOINT, timeout=30000)
            print("    Conectado ao Browserless!")
        except Exception as e:
            print(f"    Erro ao conectar ao Browserless: {e}")
            print("    Usando navegador local...")
            browser = p.chromium.launch(headless=False)
        
        # Cria contexto com proxy
        context = browser.new_context(
            proxy=PROXY_CONFIG,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        
        # Listener de console
        def on_console(msg):
            text = msg.text
            if "LOGIN_RESULT" in text:
                print(f"    [JS] {text}")
        
        page.on("console", on_console)
        
        # Acessa o site
        print("    Acessando 7k.bet.br...")
        page.goto("https://7k.bet.br", timeout=60000, wait_until="domcontentloaded")
        
        print(f"    URL: {page.url}")
        print(f"    Titulo: {page.title()}")
        
        # Aguarda o Cloudflare
        print("    Aguardando Cloudflare (5s)...")
        time.sleep(5)
        
        # Faz login via JavaScript
        print("    Executando login via JavaScript...")
        
        login_js = f"""
        (async () => {{
            try {{
                const response = await fetch("https://7k.bet.br/api/auth/login", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{
                        "accept": "application/json",
                        "content-type": "application/json"
                    }},
                    body: JSON.stringify({{
                        login: "{EMAIL}",
                        password: "{SENHA}",
                        captcha_token: "{captcha_token}"
                    }})
                }});
                
                const data = await response.json();
                console.log("LOGIN_RESULT: " + JSON.stringify({{
                    status: response.status,
                    ok: response.ok,
                    data: data
                }}));
                
                return {{
                    status: response.status,
                    ok: response.ok,
                    data: data
                }};
            }} catch (error) {{
                console.log("LOGIN_RESULT: ERROR - " + error.message);
                return {{
                    error: error.message
                }};
            }}
        }})();
        """
        
        result = page.evaluate(login_js)
        
        print(f"\n    Resultado:")
        print(f"    Status: {result.get('status')}")
        print(f"    OK: {result.get('ok')}")
        print(f"    Data: {json.dumps(result.get('data'), indent=2, ensure_ascii=False)}")
        
        if result.get("ok"):
            print("\n    LOGIN BEM SUCEDIDO!")
            
            # Captura screenshot
            page.screenshot(path="login_sucesso.png")
            print("    Screenshot salvo: login_sucesso.png")
        else:
            print("\n    LOGIN FALHOU")
            page.screenshot(path="login_falhou.png")
        
        # Fecha
        browser.close()
        
        return result


def main():
    print("=" * 60)
    print("LOGIN 7k.bet.br - Navegador + Anti-Captcha")
    print("=" * 60)
    print(f"Email: {EMAIL}")
    print("=" * 60)

    if not EMAIL or not SENHA:
        raise SystemExit("Defina SEVENK_EMAIL e SEVENK_PASSWORD no ambiente.")
    if not ANTICAPTCHA_KEY:
        raise SystemExit("Defina ANTICAPTCHA_KEY no ambiente.")
    if not PROXY_CONFIG["server"]:
        raise SystemExit("Defina SEVENK_PROXY_SERVER (e opcionalmente USERNAME/PASSWORD) no ambiente.")
    
    try:
        # 1. Resolver Turnstile
        token = resolver_turnstile_anticaptcha()
        print(f"\n    Token (80 chars): {token[:80]}...")
        
        # 2. Fazer login via navegador
        result = fazer_login_via_navegador(token)
        
    except Exception as e:
        print(f"\nErro: {e}")
    
    print("\n" + "=" * 60)
    print("FIM")
    print("=" * 60)


if __name__ == "__main__":
    main()

