"""
Login 7k.bet.br - Debug Completo
Analisa todos os aspectos do login e tenta multiplas abordagens.
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


def resolver_turnstile():
    """Resolve o Turnstile via Anti-Captcha API."""
    print("\n" + "=" * 60)
    print("[ETAPA 1] RESOLVENDO TURNSTILE")
    print("=" * 60)
    print(f"SiteKey: {TURNSTILE_SITEKEY}")
    
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
            token = data["solution"]["token"]
            print(f"\nTOKEN OBTIDO! ({len(token)} chars)")
            return token
    
    raise Exception("Timeout")


def main():
    print("=" * 60)
    print("LOGIN 7k.bet.br - DEBUG COMPLETO")
    print("=" * 60)
    print(f"Email: {EMAIL}")
    print(f"Proxy: {PROXY_CONFIG['server']}")
    print("=" * 60)

    if not EMAIL or not SENHA:
        raise SystemExit("Defina SEVENK_EMAIL e SEVENK_PASSWORD no ambiente.")
    if not ANTICAPTCHA_KEY:
        raise SystemExit("Defina ANTICAPTCHA_KEY no ambiente.")
    if not PROXY_CONFIG["server"]:
        raise SystemExit("Defina SEVENK_PROXY_SERVER (e opcionalmente USERNAME/PASSWORD) no ambiente.")
    
    # Resolver Turnstile primeiro
    captcha_token = resolver_turnstile()
    print(f"Token: {captcha_token[:60]}...")
    
    print("\n" + "=" * 60)
    print("[ETAPA 2] CONECTANDO AO BROWSERLESS")
    print("=" * 60)
    
    # Endpoint do Browserless
    WS_ENDPOINT = "ws://50.217.254.165:40422"
    
    with sync_playwright() as p:
        # Conecta ao Browserless
        print(f"Conectando ao Browserless: {WS_ENDPOINT}")
        try:
            browser = p.chromium.connect_over_cdp(WS_ENDPOINT, timeout=60000)
            print("Conectado ao Browserless!")
        except Exception as e:
            print(f"Erro ao conectar: {e}")
            print("Tentando navegador local sem proxy...")
            browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            proxy=PROXY_CONFIG,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="pt-BR"
        )
        
        page = context.new_page()
        
        # Captura requisicoes de rede
        network_requests = []
        def on_request(request):
            if "api" in request.url or "login" in request.url or "auth" in request.url:
                network_requests.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers)
                })
        
        def on_response(response):
            if "api" in response.url or "login" in response.url or "auth" in response.url:
                print(f"[NET] {response.status} {response.url[:80]}")
        
        page.on("request", on_request)
        page.on("response", on_response)
        
        # Acessa o site
        print("\nAcessando 7k.bet.br...")
        page.goto("https://7k.bet.br", timeout=60000, wait_until="networkidle")
        
        print(f"URL: {page.url}")
        print(f"Titulo: {page.title()}")
        
        # Verifica se passou pelo Cloudflare
        if "Just a moment" in page.title() or "challenge" in page.url.lower():
            print("\n[CLOUDFLARE] Pagina de desafio detectada. Aguardando...")
            time.sleep(10)
            print(f"URL apos espera: {page.url}")
        
        # Captura cookies
        cookies = context.cookies()
        print(f"\n[COOKIES] {len(cookies)} cookies capturados:")
        for c in cookies:
            print(f"  - {c['name']}: {c['value'][:30]}...")
        
        print("\n" + "=" * 60)
        print("[ETAPA 3] TENTATIVA 1 - FETCH NO NAVEGADOR")
        print("=" * 60)
        
        # Tenta login via fetch dentro do navegador
        login_js = f"""
        (async () => {{
            try {{
                console.log("Iniciando fetch de login...");
                
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
                let data;
                try {{
                    data = JSON.parse(text);
                }} catch {{
                    data = text;
                }}
                
                return {{
                    status: response.status,
                    statusText: response.statusText,
                    headers: Object.fromEntries(response.headers.entries()),
                    data: data
                }};
            }} catch (error) {{
                return {{
                    error: error.message,
                    stack: error.stack
                }};
            }}
        }})();
        """
        
        result1 = page.evaluate(login_js)
        print(f"Status: {result1.get('status')} {result1.get('statusText')}")
        print(f"Resposta: {json.dumps(result1.get('data'), indent=2, ensure_ascii=False)}")
        
        if result1.get('status') == 200:
            print("\n[SUCESSO] LOGIN VIA FETCH FUNCIONOU!")
            page.screenshot(path="login_sucesso.png")
            browser.close()
            return
        
        print("\n" + "=" * 60)
        print("[ETAPA 4] TENTATIVA 2 - XMLHttpRequest")
        print("=" * 60)
        
        # Tenta com XMLHttpRequest
        xhr_js = f"""
        new Promise((resolve) => {{
            const xhr = new XMLHttpRequest();
            xhr.open("POST", "https://7k.bet.br/api/auth/login", true);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.setRequestHeader("Accept", "application/json");
            xhr.withCredentials = true;
            
            xhr.onload = function() {{
                resolve({{
                    status: xhr.status,
                    statusText: xhr.statusText,
                    response: xhr.responseText
                }});
            }};
            
            xhr.onerror = function() {{
                resolve({{
                    error: "Network error",
                    status: xhr.status
                }});
            }};
            
            xhr.send(JSON.stringify({{
                login: "{EMAIL}",
                password: "{SENHA}",
                captcha_token: "{captcha_token}"
            }}));
        }});
        """
        
        result2 = page.evaluate(xhr_js)
        print(f"Status: {result2.get('status')} {result2.get('statusText')}")
        print(f"Resposta: {result2.get('response', result2.get('error'))[:500]}")
        
        if result2.get('status') == 200:
            print("\n[SUCESSO] LOGIN VIA XHR FUNCIONOU!")
            browser.close()
            return
        
        print("\n" + "=" * 60)
        print("[ETAPA 5] TENTATIVA 3 - NAVEGAR PARA PAGINA DE LOGIN")
        print("=" * 60)
        
        # Navega para a pagina de login e tenta encontrar o formulario
        page.goto("https://7k.bet.br/login", timeout=30000)
        time.sleep(3)
        print(f"URL: {page.url}")
        
        # Verifica se ha formulario de login
        form_exists = page.evaluate("""
        () => {
            const inputs = document.querySelectorAll('input');
            const buttons = document.querySelectorAll('button');
            return {
                inputs: inputs.length,
                buttons: buttons.length,
                inputTypes: Array.from(inputs).map(i => ({type: i.type, name: i.name, placeholder: i.placeholder})),
                buttonTexts: Array.from(buttons).map(b => b.textContent.trim())
            };
        }
        """)
        print(f"Formulario encontrado: {json.dumps(form_exists, indent=2, ensure_ascii=False)}")
        
        print("\n" + "=" * 60)
        print("[ETAPA 6] TENTATIVA 4 - DIFERENTES PAYLOADS")
        print("=" * 60)
        
        # Tenta diferentes estruturas de payload
        payloads = [
            {"login": EMAIL, "password": SENHA, "captcha_token": captcha_token},
            {"email": EMAIL, "password": SENHA, "captcha_token": captcha_token},
            {"username": EMAIL, "password": SENHA, "captcha_token": captcha_token},
            {"login": EMAIL, "password": SENHA, "cf-turnstile-response": captcha_token},
            {"login": EMAIL, "password": SENHA, "turnstile_token": captcha_token},
        ]
        
        for i, payload in enumerate(payloads):
            print(f"\nPayload {i+1}: {list(payload.keys())}")
            
            test_js = f"""
            (async () => {{
                const response = await fetch("https://7k.bet.br/api/auth/login", {{
                    method: "POST",
                    credentials: "include",
                    headers: {{"content-type": "application/json"}},
                    body: JSON.stringify({json.dumps(payload)})
                }});
                return {{status: response.status, data: await response.text()}};
            }})();
            """
            
            result = page.evaluate(test_js)
            print(f"  Status: {result.get('status')}")
            
            data_str = result.get('data', '')[:200]
            print(f"  Resposta: {data_str}")
            
            if result.get('status') == 200:
                print(f"\n[SUCESSO] PAYLOAD {i+1} FUNCIONOU!")
                browser.close()
                return
        
        print("\n" + "=" * 60)
        print("[ETAPA 7] ANALISE DE HEADERS DA REQUISICAO")
        print("=" * 60)
        
        # Analisa headers que o navegador envia
        headers_analysis = page.evaluate("""
        async () => {
            // Faz uma requisicao de teste para ver os headers
            const testReq = new Request("https://7k.bet.br/api/auth/login", {
                method: "POST",
                credentials: "include",
                headers: {"content-type": "application/json"},
                body: "{}"
            });
            
            return {
                mode: testReq.mode,
                credentials: testReq.credentials,
                headers: Object.fromEntries(testReq.headers.entries())
            };
        }
        """)
        print(f"Headers da requisicao: {json.dumps(headers_analysis, indent=2)}")
        
        print("\n" + "=" * 60)
        print("[ETAPA 8] TENTATIVA 5 - RESOLVER TURNSTILE NO NAVEGADOR")
        print("=" * 60)
        
        # Volta para a pagina principal e tenta resolver Turnstile no navegador
        page.goto("https://7k.bet.br", timeout=30000)
        time.sleep(3)
        
        # Verifica se o Turnstile esta na pagina
        turnstile_check = page.evaluate("""
        () => {
            const turnstileDiv = document.querySelector('.cf-turnstile');
            const turnstileInput = document.querySelector('input[name="cf-turnstile-response"]');
            const turnstileFrame = document.querySelector('iframe[src*="turnstile"]');
            
            return {
                divExists: !!turnstileDiv,
                inputExists: !!turnstileInput,
                frameExists: !!turnstileFrame,
                inputValue: turnstileInput ? turnstileInput.value : null
            };
        }
        """)
        print(f"Turnstile na pagina: {json.dumps(turnstile_check, indent=2)}")
        
        # Se o Turnstile estiver na pagina, injeta o token
        if turnstile_check.get('inputExists') or turnstile_check.get('divExists'):
            print("Injetando token do Turnstile...")
            
            inject_js = f"""
            () => {{
                // Cria/atualiza o input do turnstile
                let input = document.querySelector('input[name="cf-turnstile-response"]');
                if (!input) {{
                    input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = 'cf-turnstile-response';
                    document.body.appendChild(input);
                }}
                input.value = "{captcha_token}";
                
                // Dispara evento de mudanca
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                
                return input.value.length;
            }}
            """
            
            injected = page.evaluate(inject_js)
            print(f"Token injetado: {injected} chars")
        
        print("\n" + "=" * 60)
        print("[ETAPA 9] TENTATIVA 6 - DIFERENTES ENDPOINTS")
        print("=" * 60)
        
        # Tenta outros endpoints possiveis
        endpoints = [
            "https://7k.bet.br/api/auth/login",
            "https://7k.bet.br/api/v1/auth/login",
            "https://7k.bet.br/api/user/login",
            "https://7k.bet.br/api/session",
            "https://7k.bet.br/api/auth/signin",
            "https://www.7k.bet.br/api/auth/login",
        ]
        
        for endpoint in endpoints:
            print(f"\nEndpoint: {endpoint}")
            
            test_js = f"""
            (async () => {{
                try {{
                    const response = await fetch("{endpoint}", {{
                        method: "POST",
                        credentials: "include",
                        headers: {{"content-type": "application/json"}},
                        body: JSON.stringify({{
                            login: "{EMAIL}",
                            password: "{SENHA}",
                            captcha_token: "{captcha_token}"
                        }})
                    }});
                    return {{status: response.status, data: await response.text()}};
                }} catch (e) {{
                    return {{error: e.message}};
                }}
            }})();
            """
            
            result = page.evaluate(test_js)
            status = result.get('status', 'erro')
            print(f"  Status: {status}")
            
            if status == 200:
                print(f"  [SUCESSO] Endpoint correto encontrado!")
                print(f"  Resposta: {result.get('data')}")
                browser.close()
                return
            elif status != 404:
                print(f"  Resposta: {result.get('data', result.get('error'))[:150]}")
        
        print("\n" + "=" * 60)
        print("[ETAPA 10] CAPTURA DE SCREENSHOT E ANALISE FINAL")
        print("=" * 60)
        
        page.screenshot(path="login_debug_final.png", full_page=True)
        print("Screenshot salvo: login_debug_final.png")
        
        # Analise final do HTML
        html_analysis = page.evaluate("""
        () => {
            const html = document.documentElement.outerHTML;
            return {
                length: html.length,
                hasLogin: html.includes('login'),
                hasAuth: html.includes('auth'),
                hasForm: html.includes('<form'),
                title: document.title,
                url: window.location.href
            };
        }
        """)
        print(f"Analise HTML: {json.dumps(html_analysis, indent=2)}")
        
        browser.close()
    
    print("\n" + "=" * 60)
    print("[FIM] RESUMO")
    print("=" * 60)
    print("Nenhuma tentativa foi bem sucedida.")
    print("Possiveis causas:")
    print("  1. Credenciais incorretas")
    print("  2. Token Turnstile expirado")
    print("  3. IP do proxy bloqueado")
    print("  4. Campo de captcha com nome diferente")
    print("  5. Necessidade de headers adicionais")


if __name__ == "__main__":
    main()

