import requests

PROXY_URL = "http://liderbet1-zone-resi-region-br:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666"

proxies = {
    "http": PROXY_URL,
    "https": PROXY_URL
}

print("=" * 50)
print("TESTE DIRETO DA PROXY (sem Browserless)")
print("=" * 50)
print(f"Proxy: {PROXY_URL[:60]}...")
print()

try:
    print("Conectando via proxy...")
    r = requests.get("https://ipinfo.io/json", proxies=proxies, timeout=30)
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        ip = data.get("ip", "N/A")
        city = data.get("city", "N/A")
        region = data.get("region", "N/A")
        country = data.get("country", "N/A")
        org = data.get("org", "N/A")
        
        print()
        print("=" * 50)
        print(f"IP: {ip}")
        print(f"Cidade: {city}")
        print(f"Regiao: {region}")
        print(f"Pais: {country}")
        print(f"Org: {org}")
        print("=" * 50)
        
        if country == "BR":
            print("SUCESSO! IP DO BRASIL!")
        else:
            print(f"IP nao e do Brasil (pais: {country})")
    else:
        print(f"Erro HTTP: {r.status_code}")
        print(r.text[:200])
        
except Exception as e:
    print(f"ERRO: {e}")
    print()
    print("A proxy nao esta funcionando!")

