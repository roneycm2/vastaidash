"""
Script para testar login no 7k.bet.br via API com proxy.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import requests
import json

# Configuracao do Proxy
PROXY_CONFIG = {
    "http": os.getenv("SEVENK_PROXY_HTTP", ""),
    "https": os.getenv("SEVENK_PROXY_HTTPS", "")
}

# Headers padrao
HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "origin": "https://7k.bet.br",
    "referer": "https://7k.bet.br/"
}

# Credenciais de teste
EMAIL = os.getenv("SEVENK_EMAIL", "")
SENHA = os.getenv("SEVENK_PASSWORD", "")

print("=" * 60)
print("[TESTE DE LOGIN - 7k.bet.br]")
print("=" * 60)
if not EMAIL or not SENHA:
    print("ERRO: defina SEVENK_EMAIL e SEVENK_PASSWORD no ambiente.")
    sys.exit(2)
if not PROXY_CONFIG["http"] or not PROXY_CONFIG["https"]:
    print("ERRO: defina SEVENK_PROXY_HTTP e SEVENK_PROXY_HTTPS no ambiente.")
    print("Ex: set SEVENK_PROXY_HTTP=http://user:pass@host:port")
    sys.exit(2)

# 1. Testa IP
print("\n[1] Verificando IP via proxy...")
try:
    resp = requests.get("https://api.ipify.org?format=json", proxies=PROXY_CONFIG, timeout=15)
    print(f"    IP: {resp.json()['ip']}")
except Exception as e:
    print(f"    Erro: {e}")
    sys.exit(1)

# 2. Cria sessao e acessa o site
print("\n[2] Acessando 7k.bet.br para cookies...")
session = requests.Session()
try:
    resp = session.get("https://7k.bet.br", proxies=PROXY_CONFIG, headers=HEADERS, timeout=15)
    print(f"    Status: {resp.status_code}")
    print(f"    Cookies: {list(session.cookies.keys())}")
except Exception as e:
    print(f"    Erro: {e}")

# 3. Testa endpoints de login mais comuns
print("\n[3] Testando endpoints de login...")

endpoints = [
    "/api/auth/login",
    "/api/login", 
    "/api/v1/auth/login",
    "/api/sessions",
    "/api/user/login",
]

payload = {
    "email": EMAIL,
    "password": SENHA,
    "captcha_token": ""
}

for endpoint in endpoints:
    url = f"https://7k.bet.br{endpoint}"
    try:
        resp = session.post(url, json=payload, headers=HEADERS, proxies=PROXY_CONFIG, timeout=10)
        print(f"\n    {endpoint}")
        print(f"    Status: {resp.status_code}")
        if resp.status_code != 404:
            try:
                data = resp.json()
                print(f"    Resposta: {json.dumps(data, ensure_ascii=False)[:300]}")
            except:
                print(f"    Resposta: {resp.text[:200]}")
    except Exception as e:
        print(f"\n    {endpoint}")
        print(f"    Erro: {str(e)[:100]}")

# 4. Tenta variacao com username
print("\n[4] Testando com 'username' ao inves de 'email'...")
payload2 = {
    "username": EMAIL,
    "password": SENHA,
    "captcha_token": ""
}

for endpoint in ["/api/auth/login", "/api/login"]:
    url = f"https://7k.bet.br{endpoint}"
    try:
        resp = session.post(url, json=payload2, headers=HEADERS, proxies=PROXY_CONFIG, timeout=10)
        if resp.status_code != 404:
            print(f"\n    {endpoint} (username)")
            print(f"    Status: {resp.status_code}")
            try:
                print(f"    Resposta: {resp.json()}")
            except:
                print(f"    Resposta: {resp.text[:200]}")
    except:
        pass

print("\n" + "=" * 60)
print("[FIM DO TESTE]")
