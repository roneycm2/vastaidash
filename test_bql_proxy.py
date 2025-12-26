import requests

TOKEN = "2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72"

BQL_ENDPOINT = f"https://production-sfo.browserless.io/stealth/bql?token={TOKEN}"

query = """
mutation ExternalProxy {
  # Usa sua proxy externa para TODAS as requisições
  proxy(
    server: "http://liderbet1-zone-resi-region-br:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666"
    url: "*"
  ) {
    time
  }
  goto(url: "https://ipinfo.io/json", waitUntil: networkIdle) {
    status
  }
  ipData: text(selector: "body") {
    text
  }
}
"""

payload = {"query": query}

print("=" * 60)
print("🔍 TESTE BQL COM PROXY EXTERNA BR")
print("=" * 60)

response = requests.post(
    BQL_ENDPOINT,
    json=payload,
    headers={"Content-Type": "application/json"},
    timeout=120
)

print(f"Status HTTP: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print("\n📋 Resposta:")
    
    import json
    print(json.dumps(data, indent=2))
    
    # Extrair IP
    if "data" in data and "ipData" in data["data"]:
        ip_text = data["data"]["ipData"].get("text", "")
        if ip_text:
            import re
            ip_match = re.search(r'"ip":\s*"([^"]+)"', ip_text)
            country_match = re.search(r'"country":\s*"([^"]+)"', ip_text)
            city_match = re.search(r'"city":\s*"([^"]+)"', ip_text)
            
            ip = ip_match.group(1) if ip_match else "N/A"
            country = country_match.group(1) if country_match else "N/A"
            city = city_match.group(1) if city_match else "N/A"
            
            print("\n" + "=" * 60)
            print(f"🌐 IP: {ip}")
            print(f"🏙️  Cidade: {city}")
            print(f"🏳️  País: {country}")
            
            if country == "BR":
                print("\n✅ SUCESSO! IP DO BRASIL!")
            else:
                print(f"\n⚠️ IP não é do Brasil")
else:
    print(f"❌ Erro: {response.text}")

print("=" * 60)
