"""
Login 7k.bet.br - Usando Selenium-Wire (que ja funciona com proxy)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
import json
import requests
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuracoes
ANTICAPTCHA_KEY = os.getenv("ANTICAPTCHA_KEY", "")
TURNSTILE_SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"

# Proxy
PROXY_HOST = os.getenv("SEVENK_PROXY_HOST", "")
PROXY_PORT = os.getenv("SEVENK_PROXY_PORT", "")
PROXY_USER = os.getenv("SEVENK_PROXY_USER", "")
PROXY_PASS = os.getenv("SEVENK_PROXY_PASS", "")

SELENIUMWIRE_OPTIONS = {
    'proxy': {
        'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
        'https': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
        'no_proxy': 'localhost,127.0.0.1'
    }
}

# Credenciais
EMAIL = os.getenv("SEVENK_EMAIL", "")
SENHA = os.getenv("SEVENK_PASSWORD", "")


def resolver_turnstile():
    """Resolve o Turnstile via Anti-Captcha API."""
    print("\n" + "=" * 60)
    print("[ETAPA 1] RESOLVENDO TURNSTILE")
    print("=" * 60)
    
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
        raise Exception(f"Erro: {data.get('errorCode')}")
    
    task_id = data["taskId"]
    print(f"TaskId: {task_id}")
    
    for i in range(40):
        time.sleep(3)
        print(f"Aguardando... {(i+1)*3}s", end="\r")
        
        resp = requests.post(
            "https://api.anti-captcha.com/getTaskResult",
            json={"clientKey": ANTICAPTCHA_KEY, "taskId": task_id},
            timeout=30
        )
        
        data = resp.json()
        if data.get("status") == "ready":
            print(f"\nTOKEN OBTIDO!")
            return data["solution"]["token"]
    
    raise Exception("Timeout")


def criar_browser():
    """Cria o browser Chrome com proxy."""
    options = Options()
    options.page_load_strategy = 'eager'
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1366,768')
    options.add_argument('--lang=pt-BR')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Headless para rodar sem interface
    options.add_argument('--headless=new')
    
    browser = webdriver.Chrome(
        options=options,
        seleniumwire_options=SELENIUMWIRE_OPTIONS
    )
    return browser


def main():
    print("=" * 60)
    print("LOGIN 7k.bet.br - SELENIUM-WIRE")
    print("=" * 60)
    print(f"Email: {EMAIL}")
    print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}")
    print("=" * 60)

    if not EMAIL or not SENHA:
        raise SystemExit("Defina SEVENK_EMAIL e SEVENK_PASSWORD no ambiente.")
    if not ANTICAPTCHA_KEY:
        raise SystemExit("Defina ANTICAPTCHA_KEY no ambiente.")
    if not (PROXY_HOST and PROXY_PORT and PROXY_USER and PROXY_PASS):
        raise SystemExit("Defina SEVENK_PROXY_HOST/PORT/USER/PASS no ambiente (ou ajuste o script).")
    
    # 1. Resolver Turnstile
    captcha_token = resolver_turnstile()
    print(f"Token: {captcha_token[:60]}...")
    
    print("\n" + "=" * 60)
    print("[ETAPA 2] ABRINDO NAVEGADOR COM PROXY")
    print("=" * 60)
    
    browser = criar_browser()
    
    try:
        # Acessa o site
        print("Acessando 7k.bet.br...")
        browser.get("https://7k.bet.br")
        
        # Aguarda carregar
        time.sleep(5)
        
        print(f"URL: {browser.current_url}")
        print(f"Titulo: {browser.title}")
        
        # Verifica cookies
        cookies = browser.get_cookies()
        print(f"\nCookies ({len(cookies)}):")
        for c in cookies:
            print(f"  - {c['name']}: {c['value'][:30]}...")
        
        print("\n" + "=" * 60)
        print("[ETAPA 3] FAZENDO LOGIN VIA JAVASCRIPT")
        print("=" * 60)
        
        # Faz login via JavaScript
        login_js = f"""
        return (async () => {{
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
                
                const text = await response.text();
                return {{
                    status: response.status,
                    statusText: response.statusText,
                    data: text
                }};
            }} catch (error) {{
                return {{
                    error: error.message
                }};
            }}
        }})();
        """
        
        result = browser.execute_script(login_js)
        
        print(f"Status: {result.get('status')} {result.get('statusText')}")
        
        data_str = result.get('data', '')
        print(f"Resposta: {data_str[:500]}")
        
        # Tenta parsear como JSON
        try:
            data = json.loads(data_str)
            print(f"\nJSON: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            if result.get('status') == 200:
                print("\n[SUCESSO] LOGIN FUNCIONOU!")
            elif "captcha" in data_str.lower():
                print("\n[ERRO] Problema com captcha")
            elif "password" in data_str.lower() or "senha" in data_str.lower():
                print("\n[ERRO] Senha incorreta")
            else:
                print("\n[ERRO] Verifique a resposta acima")
                
        except:
            pass
        
        # Se falhou, tenta outras abordagens
        if result.get('status') != 200:
            print("\n" + "=" * 60)
            print("[ETAPA 4] TENTANDO OUTRAS ABORDAGENS")
            print("=" * 60)
            
            # Tenta com cf-turnstile-response
            print("\nTentativa 2: cf-turnstile-response")
            login_js2 = f"""
            return (async () => {{
                const response = await fetch("https://7k.bet.br/api/auth/login", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{"content-type": "application/json"}},
                    body: JSON.stringify({{
                        login: "{EMAIL}",
                        password: "{SENHA}",
                        "cf-turnstile-response": "{captcha_token}"
                    }})
                }});
                return {{status: response.status, data: await response.text()}};
            }})();
            """
            
            result2 = browser.execute_script(login_js2)
            print(f"  Status: {result2.get('status')}")
            print(f"  Resposta: {result2.get('data')[:200]}")
            
            # Tenta com turnstile_token
            print("\nTentativa 3: turnstile_token")
            login_js3 = f"""
            return (async () => {{
                const response = await fetch("https://7k.bet.br/api/auth/login", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{"content-type": "application/json"}},
                    body: JSON.stringify({{
                        login: "{EMAIL}",
                        password: "{SENHA}",
                        turnstile_token: "{captcha_token}"
                    }})
                }});
                return {{status: response.status, data: await response.text()}};
            }})();
            """
            
            result3 = browser.execute_script(login_js3)
            print(f"  Status: {result3.get('status')}")
            print(f"  Resposta: {result3.get('data')[:200]}")
            
            # Tenta sem captcha
            print("\nTentativa 4: Sem captcha")
            login_js4 = f"""
            return (async () => {{
                const response = await fetch("https://7k.bet.br/api/auth/login", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{"content-type": "application/json"}},
                    body: JSON.stringify({{
                        login: "{EMAIL}",
                        password: "{SENHA}"
                    }})
                }});
                return {{status: response.status, data: await response.text()}};
            }})();
            """
            
            result4 = browser.execute_script(login_js4)
            print(f"  Status: {result4.get('status')}")
            print(f"  Resposta: {result4.get('data')[:200]}")
        
        # Captura screenshot
        browser.save_screenshot("login_selenium_result.png")
        print("\nScreenshot: login_selenium_result.png")
        
        # Analisa requisicoes de rede
        print("\n" + "=" * 60)
        print("[ANALISE DE REDE]")
        print("=" * 60)
        
        for req in browser.requests:
            if "api" in req.url and "auth" in req.url:
                print(f"\n{req.method} {req.url}")
                print(f"  Status: {req.response.status_code if req.response else 'N/A'}")
                if req.response:
                    print(f"  Headers: {dict(req.response.headers)}")
                    if req.response.body:
                        print(f"  Body: {req.response.body[:300]}")
        
    finally:
        browser.quit()
    
    print("\n" + "=" * 60)
    print("[FIM]")
    print("=" * 60)


if __name__ == "__main__":
    main()

