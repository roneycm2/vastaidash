import requests

proxy_str = "liderbet1-zone-adam-region-br:Aa10203040@pybpm-ins-hxqlzicm.pyproxy.io:2510"
parts = proxy_str.split("@")
user_pass = parts[0].split(":", 1)
host_port = parts[1].split(":")

proxy_url = f"http://{user_pass[0]}:{user_pass[1]}@{host_port[0]}:{host_port[1]}"

proxies = {
    "http": proxy_url,
    "https": proxy_url
}

print("=" * 60)
print("TESTANDO IP DA PROXY")
print("=" * 60)

# Testar IP
try:
    resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=15)
    ip_info = resp.json()
    print(f"IP da Proxy: {ip_info.get('ip', 'N/A')}")
except Exception as e:
    print(f"Erro ao obter IP: {e}")

# Testar info completa
try:
    resp = requests.get("https://ipapi.co/json/", proxies=proxies, timeout=15)
    data = resp.json()
    print(f"Pais: {data.get('country_name', 'N/A')} ({data.get('country_code', 'N/A')})")
    print(f"Cidade: {data.get('city', 'N/A')}")
    print(f"Regiao: {data.get('region', 'N/A')}")
    print(f"ISP: {data.get('org', 'N/A')}")
    print(f"ASN: {data.get('asn', 'N/A')}")
except Exception as e:
    print(f"Erro ao obter info: {e}")

# Verificar se o site 7k esta acessivel
print("\n" + "=" * 60)
print("TESTANDO ACESSO AO 7K.BET.BR")
print("=" * 60)

try:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get("https://7k.bet.br", proxies=proxies, headers=headers, timeout=20)
    print(f"Status: {resp.status_code}")
    print(f"Tamanho: {len(resp.text)} bytes")
    
    # Verificar se tem bloqueio
    if "Ops, sorry" in resp.text or "nao disponivel" in resp.text.lower():
        print("AVISO: Site mostrando pagina de bloqueio!")
    elif "7k.bet.br" in resp.text and "Bet7K" in resp.text:
        print("OK: Site carregou normalmente!")
except Exception as e:
    print(f"Erro: {e}")

