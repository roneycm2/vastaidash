"""
Teste de proxy alternativo encontrado no projeto.
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import requests

print("=" * 60)
print("TESTE DE PROXIES ALTERNATIVOS")
print("=" * 60)

# Proxy 1 - Original (nao funcionando)
print("\n[PROXY 1] pybpm-ins-hxqlzicm.pyproxy.io:2510")
try:
    proxies = {
        "http": "http://liderbet1-zone-adam-region-br:Aa10203040@pybpm-ins-hxqlzicm.pyproxy.io:2510",
        "https": "http://liderbet1-zone-adam-region-br:Aa10203040@pybpm-ins-hxqlzicm.pyproxy.io:2510"
    }
    resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=15)
    print(f"  IP: {resp.json()['ip']}")
except Exception as e:
    print(f"  Erro: {str(e)[:80]}")

# Proxy 2 - Alternativo (residencial)
print("\n[PROXY 2] fb29d01db8530b99.shg.na.pyproxy.io:16666")
try:
    proxies = {
        "http": "http://liderbet1-zone-resi-region-br:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666",
        "https": "http://liderbet1-zone-resi-region-br:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666"
    }
    resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=15)
    print(f"  IP: {resp.json()['ip']}")
    
    # Testa acesso ao 7k
    print("  Testando 7k.bet.br...")
    resp2 = requests.get("https://7k.bet.br", proxies=proxies, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    print(f"  Status 7k: {resp2.status_code}")
    print(f"  Tamanho: {len(resp2.text)} bytes")
    
except Exception as e:
    print(f"  Erro: {str(e)[:80]}")

# Proxy 3 - Com session
print("\n[PROXY 3] fb29d01db8530b99.shg.na.pyproxy.io:16666 (com session)")
try:
    import random
    session_id = ''.join(random.choices('abcdef0123456789', k=12))
    proxies = {
        "http": f"http://liderbet1-zone-resi-region-br-session-{session_id}-sessTime-1:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666",
        "https": f"http://liderbet1-zone-resi-region-br-session-{session_id}-sessTime-1:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666"
    }
    resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=15)
    print(f"  Session: {session_id}")
    print(f"  IP: {resp.json()['ip']}")
    
except Exception as e:
    print(f"  Erro: {str(e)[:80]}")

print("\n" + "=" * 60)











