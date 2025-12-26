"""
Testa diferentes configuracoes de proxy para encontrar a que funciona.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests
from requests.auth import HTTPProxyAuth

# Configuracoes de proxy
PROXY_HOST = "pybpm-ins-hxqlzicm.pyproxy.io"
PROXY_PORT = "2510"
PROXY_USER = "liderbet1-zone-adam-region-br"
PROXY_PASS = "Aa10203040"

print("=" * 60)
print("TESTE DE CONFIGURACOES DE PROXY")
print("=" * 60)

# Teste 1: Proxy com autenticacao na URL
print("\n[TESTE 1] Proxy com auth na URL")
try:
    proxies1 = {
        "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
        "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    }
    resp = requests.get("https://api.ipify.org?format=json", proxies=proxies1, timeout=15)
    print(f"  IP: {resp.json()['ip']}")
except Exception as e:
    print(f"  Erro: {e}")

# Teste 2: Proxy HTTPS
print("\n[TESTE 2] Proxy HTTPS")
try:
    proxies2 = {
        "http": f"https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
        "https": f"https://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    }
    resp = requests.get("https://api.ipify.org?format=json", proxies=proxies2, timeout=15)
    print(f"  IP: {resp.json()['ip']}")
except Exception as e:
    print(f"  Erro: {e}")

# Teste 3: Usando HTTPProxyAuth
print("\n[TESTE 3] Usando HTTPProxyAuth")
try:
    proxies3 = {
        "http": f"http://{PROXY_HOST}:{PROXY_PORT}",
        "https": f"http://{PROXY_HOST}:{PROXY_PORT}"
    }
    auth = HTTPProxyAuth(PROXY_USER, PROXY_PASS)
    resp = requests.get("https://api.ipify.org?format=json", proxies=proxies3, auth=auth, timeout=15)
    print(f"  IP: {resp.json()['ip']}")
except Exception as e:
    print(f"  Erro: {e}")

# Teste 4: Porta diferente (algumas proxies usam portas diferentes para HTTPS)
print("\n[TESTE 4] Outras portas comuns")
for port in ["2510", "2000", "3128", "8080"]:
    try:
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{port}",
            "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{port}"
        }
        resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=10)
        print(f"  Porta {port}: IP = {resp.json()['ip']}")
    except Exception as e:
        print(f"  Porta {port}: Erro - {str(e)[:50]}")

# Teste 5: Acesso ao 7k.bet.br
print("\n[TESTE 5] Acesso ao 7k.bet.br com proxy")
try:
    proxies = {
        "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
        "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    }
    resp = requests.get("https://7k.bet.br", proxies=proxies, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    print(f"  Status: {resp.status_code}")
    print(f"  Titulo: {'7k' in resp.text}")
    print(f"  Tamanho: {len(resp.text)} bytes")
except Exception as e:
    print(f"  Erro: {e}")

# Teste 6: Sem proxy (verificar bloqueio geografico)
print("\n[TESTE 6] Acesso sem proxy (verificar bloqueio)")
try:
    resp = requests.get("https://7k.bet.br", timeout=15, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    print(f"  Status: {resp.status_code}")
    if "disponível" in resp.text.lower() or "região" in resp.text.lower():
        print("  Resultado: BLOQUEADO POR REGIAO")
    else:
        print(f"  Resultado: Acessivel! Tamanho: {len(resp.text)}")
except Exception as e:
    print(f"  Erro: {e}")

print("\n" + "=" * 60)
print("FIM DOS TESTES")
print("=" * 60)











