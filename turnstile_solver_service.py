"""
Serviço de Resolução de Cloudflare Turnstile
Usa Playwright para resolver automaticamente o captcha.

Endpoints:
  POST /solve - Resolve um Turnstile e retorna o token
  GET /health - Verifica se o serviço está funcionando

Uso:
  python turnstile_solver_service.py

Requisição:
  POST http://localhost:5099/solve
  {
    "sitekey": "0x4AAAAAAAykd8yJm3kQzNJc",
    "url": "https://7k.bet.br"
  }

Resposta:
  {
    "success": true,
    "token": "0.AbCdEf123...",
    "time_taken": 5.2
  }
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import time
import json
import threading
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Configuracao do Proxy
PROXY_CONFIG = {
    "server": "http://pybpm-ins-hxqlzicm.pyproxy.io:2510",
    "username": "liderbet1-zone-adam-region-br",
    "password": "Aa10203040"
}

# Pool de browsers para reutilizacao
browser_pool = []
pool_lock = threading.Lock()


def criar_pagina_turnstile(sitekey: str, page_url: str) -> str:
    """
    Cria uma pagina HTML com o Turnstile embutido para resolver.
    """
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Turnstile Solver</title>
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
    </head>
    <body>
        <h1>Resolvendo Turnstile...</h1>
        <div id="status">Aguardando...</div>
        
        <!-- Widget do Turnstile -->
        <div class="cf-turnstile" 
             data-sitekey="{sitekey}"
             data-callback="onSuccess"
             data-error-callback="onError">
        </div>
        
        <div id="token" style="display:none;"></div>
        
        <script>
            function onSuccess(token) {{
                document.getElementById('status').textContent = 'Resolvido!';
                document.getElementById('token').textContent = token;
                document.getElementById('token').style.display = 'block';
                console.log('TURNSTILE_TOKEN:' + token);
            }}
            
            function onError(error) {{
                document.getElementById('status').textContent = 'Erro: ' + error;
                console.log('TURNSTILE_ERROR:' + error);
            }}
        </script>
    </body>
    </html>
    '''


def resolver_turnstile_navegador(sitekey: str, page_url: str, timeout: int = 60) -> dict:
    """
    Resolve o Turnstile usando um navegador real.
    """
    start_time = time.time()
    result = {
        "success": False,
        "token": None,
        "error": None,
        "time_taken": 0
    }
    
    with sync_playwright() as p:
        # Lanca navegador com configuracoes anti-deteccao
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        
        context = browser.new_context(
            proxy=PROXY_CONFIG,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="pt-BR"
        )
        
        page = context.new_page()
        
        # Variavel para capturar o token
        token_capturado = {"token": None}
        
        # Listener para capturar o token do console
        def on_console(msg):
            text = msg.text
            if text.startswith("TURNSTILE_TOKEN:"):
                token_capturado["token"] = text.replace("TURNSTILE_TOKEN:", "")
            elif text.startswith("TURNSTILE_ERROR:"):
                result["error"] = text.replace("TURNSTILE_ERROR:", "")
        
        page.on("console", on_console)
        
        try:
            # Metodo 1: Acessar diretamente a pagina do site
            print(f"[Solver] Acessando {page_url}...")
            page.goto(page_url, timeout=30000, wait_until="domcontentloaded")
            
            # Aguarda o Turnstile carregar e resolver
            print("[Solver] Aguardando Turnstile...")
            
            for i in range(timeout):
                time.sleep(1)
                
                # Tenta capturar o token do input hidden do Turnstile
                try:
                    # Busca o input com o token
                    token = page.evaluate("""
                        () => {
                            // Tenta varios seletores possiveis
                            const selectors = [
                                'input[name="cf-turnstile-response"]',
                                'input[name="cf_turnstile_response"]',
                                '[data-turnstile-response]',
                                '.cf-turnstile input[type="hidden"]'
                            ];
                            
                            for (const sel of selectors) {
                                const el = document.querySelector(sel);
                                if (el && el.value) {
                                    return el.value;
                                }
                            }
                            
                            // Tenta pegar do window
                            if (window.turnstile && window.turnstile.getResponse) {
                                return window.turnstile.getResponse();
                            }
                            
                            return null;
                        }
                    """)
                    
                    if token:
                        result["success"] = True
                        result["token"] = token
                        result["time_taken"] = round(time.time() - start_time, 2)
                        print(f"[Solver] Token capturado em {result['time_taken']}s")
                        break
                        
                except Exception as e:
                    pass
                
                # Verifica token do console
                if token_capturado["token"]:
                    result["success"] = True
                    result["token"] = token_capturado["token"]
                    result["time_taken"] = round(time.time() - start_time, 2)
                    print(f"[Solver] Token do console em {result['time_taken']}s")
                    break
                
                if i % 10 == 0:
                    print(f"[Solver] Aguardando... {i}s")
            
            if not result["success"]:
                result["error"] = "Timeout ao resolver Turnstile"
                
        except Exception as e:
            result["error"] = str(e)
            print(f"[Solver] Erro: {e}")
        
        finally:
            browser.close()
    
    return result


def resolver_turnstile_via_api(sitekey: str, page_url: str) -> dict:
    """
    Metodo alternativo: Resolve acessando a API do site diretamente.
    Alguns sites aceitam requests sem captcha se vier de um navegador valido.
    """
    start_time = time.time()
    result = {
        "success": False,
        "token": None,
        "error": None,
        "time_taken": 0
    }
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        context = browser.new_context(
            proxy=PROXY_CONFIG,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        page = context.new_page()
        
        try:
            # Acessa o site para pegar cookies
            page.goto(page_url, timeout=30000)
            time.sleep(3)
            
            # Executa JavaScript para obter token do Turnstile
            token = page.evaluate(f"""
                async () => {{
                    return new Promise((resolve, reject) => {{
                        // Carrega o script do Turnstile
                        const script = document.createElement('script');
                        script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js';
                        script.onload = () => {{
                            // Renderiza o widget
                            turnstile.render('#turnstile-container', {{
                                sitekey: '{sitekey}',
                                callback: (token) => resolve(token),
                                'error-callback': (err) => reject(err)
                            }});
                        }};
                        
                        // Cria container
                        const container = document.createElement('div');
                        container.id = 'turnstile-container';
                        document.body.appendChild(container);
                        document.head.appendChild(script);
                        
                        // Timeout
                        setTimeout(() => reject('Timeout'), 60000);
                    }});
                }}
            """)
            
            if token:
                result["success"] = True
                result["token"] = token
                result["time_taken"] = round(time.time() - start_time, 2)
                
        except Exception as e:
            result["error"] = str(e)
        
        finally:
            browser.close()
    
    return result


# ============================================================
# ENDPOINTS DA API
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Turnstile Solver"})


@app.route("/solve", methods=["POST"])
def solve():
    """
    Resolve um Cloudflare Turnstile.
    
    Request:
        {
            "sitekey": "0x4AAAAAAAykd8yJm3kQzNJc",
            "url": "https://7k.bet.br",
            "timeout": 60  (opcional)
        }
    
    Response:
        {
            "success": true,
            "token": "0.AbCdEf123...",
            "time_taken": 5.2
        }
    """
    try:
        data = request.get_json()
        
        sitekey = data.get("sitekey")
        page_url = data.get("url")
        timeout = data.get("timeout", 60)
        
        if not sitekey or not page_url:
            return jsonify({
                "success": False,
                "error": "sitekey e url sao obrigatorios"
            }), 400
        
        print(f"\n[API] Resolvendo Turnstile para {page_url}")
        print(f"[API] SiteKey: {sitekey}")
        
        result = resolver_turnstile_navegador(sitekey, page_url, timeout)
        
        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/solve-and-login", methods=["POST"])
def solve_and_login():
    """
    Resolve o Turnstile e faz login no 7k.bet.br.
    
    Request:
        {
            "email": "user@email.com",
            "password": "senha123"
        }
    
    Response:
        {
            "success": true,
            "user": {...},
            "cookies": [...]
        }
    """
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")
        
        if not email or not password:
            return jsonify({
                "success": False,
                "error": "email e password sao obrigatorios"
            }), 400
        
        print(f"\n[API] Login para {email}")
        
        # Resolve o Turnstile
        turnstile_result = resolver_turnstile_navegador(
            "0x4AAAAAAAykd8yJm3kQzNJc",
            "https://7k.bet.br",
            60
        )
        
        if not turnstile_result["success"]:
            return jsonify({
                "success": False,
                "error": "Falha ao resolver Turnstile",
                "details": turnstile_result["error"]
            }), 500
        
        # Faz login com o token
        import requests as req
        
        login_resp = req.post(
            "https://7k.bet.br/api/auth/login",
            json={
                "login": email,
                "password": password,
                "captcha_token": turnstile_result["token"]
            },
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Origin": "https://7k.bet.br",
                "Referer": "https://7k.bet.br/"
            },
            proxies={
                "http": f"http://{PROXY_CONFIG['username']}:{PROXY_CONFIG['password']}@pybpm-ins-hxqlzicm.pyproxy.io:2510",
                "https": f"http://{PROXY_CONFIG['username']}:{PROXY_CONFIG['password']}@pybpm-ins-hxqlzicm.pyproxy.io:2510"
            },
            timeout=30
        )
        
        return jsonify({
            "success": login_resp.status_code == 200,
            "status_code": login_resp.status_code,
            "response": login_resp.json() if login_resp.headers.get("content-type", "").startswith("application/json") else login_resp.text,
            "cookies": dict(login_resp.cookies),
            "turnstile_time": turnstile_result["time_taken"]
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    print("=" * 60)
    print("TURNSTILE SOLVER SERVICE")
    print("=" * 60)
    print("Endpoints:")
    print("  GET  /health        - Status do servico")
    print("  POST /solve         - Resolve um Turnstile")
    print("  POST /solve-and-login - Resolve e faz login no 7k")
    print("=" * 60)
    print("Iniciando em http://localhost:5099")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=5099, debug=False, threaded=True)

