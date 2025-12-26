"""
Teste de Proxy Externa com Browserless - Método Correto
Documentação: https://docs.browserless.io/baas/features/proxies#third-party-proxies
"""
import requests
import json

TOKEN = "2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72"

# Proxy credentials
PROXY_HOST = "fb29d01db8530b99.shg.na.pyproxy.io"
PROXY_PORT = "16666"
PROXY_USER = "liderbet1-zone-resi-region-br"
PROXY_PASS = "Aa10203040"

# URL com --proxy-server na query string
API_URL = f"https://production-sfo.browserless.io/content?token={TOKEN}&--proxy-server=http://{PROXY_HOST}:{PROXY_PORT}"

# Body com authenticate para username/password
payload = {
    "url": "https://ipinfo.io/json",
    "authenticate": {
        "username": PROXY_USER,
        "password": PROXY_PASS
    },
    "waitForTimeout": 15000,
    "gotoOptions": {
        "waitUntil": "domcontentloaded"
    }
}

print("=" * 60)
print("TESTE PROXY EXTERNA - MÉTODO CORRETO")
print("=" * 60)
print(f"Proxy: {PROXY_HOST}:{PROXY_PORT}")
print(f"User: {PROXY_USER}")
print(f"URL: {API_URL[:80]}...")
print("=" * 60)

print("\nEnviando requisição...")

try:
    resp = requests.post(
        API_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=90
    )
    
    print(f"Status HTTP: {resp.status_code}")
    
    if resp.status_code == 200:
        content = resp.text
        print(f"Tamanho resposta: {len(content)} bytes")
        
        # Tentar extrair IP
        import re
        ip_match = re.search(r'"ip":\s*"([^"]+)"', content)
        city_match = re.search(r'"city":\s*"([^"]+)"', content)
        region_match = re.search(r'"region":\s*"([^"]+)"', content)
        country_match = re.search(r'"country":\s*"([^"]+)"', content)
        org_match = re.search(r'"org":\s*"([^"]+)"', content)
        
        ip = ip_match.group(1) if ip_match else "N/A"
        city = city_match.group(1) if city_match else "N/A"
        region = region_match.group(1) if region_match else "N/A"
        country = country_match.group(1) if country_match else "N/A"
        org = org_match.group(1) if org_match else "N/A"
        
        print("\n" + "=" * 60)
        print("RESULTADO:")
        print("=" * 60)
        print(f"🌐 IP: {ip}")
        print(f"🏙️  Cidade: {city}")
        print(f"📍 Região: {region}")
        print(f"🏳️  País: {country}")
        print(f"🏢 Org: {org}")
        
        if country == "BR":
            print("\n" + "=" * 60)
            print("✅ SUCESSO! IP DO BRASIL! 🇧🇷")
            print("=" * 60)
        else:
            print(f"\n⚠️ IP não é do Brasil (país: {country})")
    else:
        print(f"\n❌ Erro HTTP {resp.status_code}")
        print(resp.text[:500])
        
except Exception as e:
    print(f"\n❌ Erro: {e}")

