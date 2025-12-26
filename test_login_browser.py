"""
Script para testar login no 7k.bet.br via navegador com Playwright.
Usa o Browserless para contornar a protecao Cloudflare.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import time
from playwright.sync_api import sync_playwright

# Configuracao do Proxy
PROXY_CONFIG = {
    "server": os.getenv("SEVENK_PROXY_SERVER", ""),
    "username": os.getenv("SEVENK_PROXY_USERNAME", ""),
    "password": os.getenv("SEVENK_PROXY_PASSWORD", "")
}

# Credenciais
EMAIL = os.getenv("SEVENK_EMAIL", "")
SENHA = os.getenv("SEVENK_PASSWORD", "")

# Endpoint do Browserless (ajuste conforme seu servidor)
WS_ENDPOINT = os.getenv("BROWSERLESS_WS_ENDPOINT", "ws://127.0.0.1:9222")


def fazer_login_via_fetch(page, email, senha):
    """
    Faz login via fetch JavaScript dentro do navegador.
    Isso contorna o Cloudflare pois o navegador ja passou pela verificacao.
    """
    js_code = f"""
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
                    email: "{email}",
                    password: "{senha}",
                    captcha_token: ""
                }})
            }});
            
            const data = await response.json();
            return {{
                status: response.status,
                ok: response.ok,
                data: data
            }};
        }} catch (error) {{
            return {{
                status: 0,
                ok: false,
                error: error.message
            }};
        }}
    }})();
    """
    
    result = page.evaluate(js_code)
    return result


def main():
    print("=" * 60)
    print("[LOGIN 7k.bet.br via NAVEGADOR]")
    print("=" * 60)
    print(f"Email: {EMAIL}")
    print(f"Senha: {'*' * len(SENHA)}")
    print(f"Endpoint: {WS_ENDPOINT}")
    print("=" * 60)

    if not EMAIL or not SENHA:
        raise SystemExit("Defina SEVENK_EMAIL e SEVENK_PASSWORD no ambiente.")
    if not PROXY_CONFIG["server"]:
        raise SystemExit("Defina SEVENK_PROXY_SERVER (e opcionalmente USERNAME/PASSWORD) no ambiente.")
    
    with sync_playwright() as p:
        print("\n[1] Conectando ao Browserless...")
        try:
            browser = p.chromium.connect_over_cdp(
                WS_ENDPOINT,
                timeout=60000
            )
            print("    Conectado!")
        except Exception as e:
            print(f"    Erro ao conectar: {e}")
            print("\n    Tentando com navegador local...")
            browser = p.chromium.launch(headless=False)
        
        print("\n[2] Criando contexto com proxy...")
        context = browser.new_context(
            proxy=PROXY_CONFIG,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = context.new_page()
        
        # Listener para console
        def on_console(msg):
            print(f"    [Console] {msg.text}")
        page.on("console", on_console)
        
        print("\n[3] Navegando para 7k.bet.br...")
        try:
            page.goto("https://7k.bet.br", timeout=60000, wait_until="domcontentloaded")
            print(f"    URL: {page.url}")
            print(f"    Titulo: {page.title()}")
        except Exception as e:
            print(f"    Erro: {e}")
        
        # Aguarda um pouco para o Cloudflare processar
        print("\n[4] Aguardando Cloudflare (5s)...")
        time.sleep(5)
        print(f"    URL atual: {page.url}")
        
        print("\n[5] Tentando login via fetch...")
        try:
            result = fazer_login_via_fetch(page, EMAIL, SENHA)
            print(f"    Status: {result.get('status')}")
            print(f"    OK: {result.get('ok')}")
            print(f"    Resposta: {result.get('data') or result.get('error')}")
            
            if result.get('ok'):
                print("\n[SUCCESS] LOGIN BEM SUCEDIDO!")
            else:
                print("\n[FALHOU] Login nao funcionou")
                
                # Tenta outras estruturas de payload
                print("\n[6] Tentando outras estruturas...")
                
                # Tenta com 'username' ao inves de 'email'
                js_code2 = f"""
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
                                username: "{EMAIL}",
                                password: "{SENHA}",
                                captcha_token: ""
                            }})
                        }});
                        
                        return {{
                            status: response.status,
                            data: await response.json()
                        }};
                    }} catch (error) {{
                        return {{ error: error.message }};
                    }}
                }})();
                """
                result2 = page.evaluate(js_code2)
                print(f"    Tentativa 2 (username): {result2}")
                
                # Tenta com 'login' ao inves de 'email'
                js_code3 = f"""
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
                                password: "{SENHA}"
                            }})
                        }});
                        
                        return {{
                            status: response.status,
                            data: await response.json()
                        }};
                    }} catch (error) {{
                        return {{ error: error.message }};
                    }}
                }})();
                """
                result3 = page.evaluate(js_code3)
                print(f"    Tentativa 3 (login): {result3}")
                
        except Exception as e:
            print(f"    Erro: {e}")
        
        print("\n[7] Capturando screenshot...")
        try:
            page.screenshot(path="login_7k_resultado.png")
            print("    Screenshot salvo: login_7k_resultado.png")
        except:
            pass
        
        print("\n[8] Fechando navegador...")
        browser.close()
        
    print("\n" + "=" * 60)
    print("[FIM]")


if __name__ == "__main__":
    main()

