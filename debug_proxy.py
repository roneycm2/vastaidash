"""Debug - verificar URL da proxy"""
import requests

BROWSERLESS_REST_URL = 'https://production-sfo.browserless.io'
BROWSERLESS_API_KEY = '2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72'
PROXY_CONFIG = {
    'host': 'fb29d01db8530b99.shg.na.pyproxy.io',
    'port': 16666,
    'username': 'liderbet1-zone-resi-region-br',
    'password': 'Aa10203040'
}

proxy_server = f"http://{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}"
api_url = f"{BROWSERLESS_REST_URL}/content?token={BROWSERLESS_API_KEY}&--proxy-server={proxy_server}"

print("=" * 60)
print("URL construída:")
print(api_url)
print("=" * 60)

# Testar
payload = {
    "url": "https://ipinfo.io/json",
    "authenticate": {
        "username": PROXY_CONFIG["username"],
        "password": PROXY_CONFIG["password"]
    },
    "waitForTimeout": 15000
}

print("\nTestando...")
resp = requests.post(api_url, json=payload, timeout=60)
print(f"Status: {resp.status_code}")

import re
content = resp.text
ip_match = re.search(r'"ip":\s*"([^"]+)"', content)
country_match = re.search(r'"country":\s*"([^"]+)"', content)
city_match = re.search(r'"city":\s*"([^"]+)"', content)

print(f"IP: {ip_match.group(1) if ip_match else 'N/A'}")
print(f"Cidade: {city_match.group(1) if city_match else 'N/A'}")
print(f"País: {country_match.group(1) if country_match else 'N/A'}")

if country_match and country_match.group(1) == "BR":
    print("\n✅ PROXY BR FUNCIONANDO!")

