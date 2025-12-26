import requests
import json

TOKEN = "2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72"
BQL_URL = f"https://production-sfo.browserless.io/stealth/bql?token={TOKEN}"
PROXY = "http://liderbet1-zone-resi-region-br:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666"

query = """
mutation ExternalProxy {
  proxy(server: "%s", url: "*") { time }
  goto(url: "http://ipinfo.io/json", waitUntil: networkIdle) { status }
  body: text(selector: "body") { text }
}
""" % PROXY

print("=" * 60)
print("TESTE BQL COM PROXY BR")
print("=" * 60)

r = requests.post(BQL_URL, json={"query": query}, timeout=90)
print(f"Status HTTP: {r.status_code}")

data = r.json()
print("\nResposta:")
print(json.dumps(data, indent=2))

# Extrair IP se tiver
if "data" in data and "body" in data["data"]:
    body_text = data["data"]["body"].get("text", "")
    if body_text:
        import re
        ip_match = re.search(r'"ip":\s*"([^"]+)"', body_text)
        country_match = re.search(r'"country":\s*"([^"]+)"', body_text)
        city_match = re.search(r'"city":\s*"([^"]+)"', body_text)
        
        print("\n" + "=" * 60)
        print(f"IP: {ip_match.group(1) if ip_match else 'N/A'}")
        print(f"Cidade: {city_match.group(1) if city_match else 'N/A'}")
        print(f"Pais: {country_match.group(1) if country_match else 'N/A'}")
        
        if country_match and country_match.group(1) == "BR":
            print("\n✅ SUCESSO! IP DO BRASIL!")
        else:
            print("\n⚠️ IP nao e do Brasil")

