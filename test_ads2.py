from serpapi import GoogleSearch
import time

API_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

print("=" * 60)
print("Testando diferentes localizações do Brasil...")
print("=" * 60)

localizacoes = [
    "Sao Paulo, State of Sao Paulo, Brazil",
    "Rio de Janeiro, State of Rio de Janeiro, Brazil", 
    "Belo Horizonte, State of Minas Gerais, Brazil",
    "Brasilia, Federal District, Brazil",
    "Curitiba, State of Parana, Brazil"
]

palavra = "apostas esportivas"

for loc in localizacoes:
    params = {
        "q": palavra,
        "location": loc,
        "hl": "pt",
        "gl": "br",
        "device": "desktop",
        "api_key": API_KEY
    }
    
    results = GoogleSearch(params).get_dict()
    ads = results.get("ads", [])
    
    print(f"\n📍 {loc.split(',')[0]}:")
    print(f"   Ads: {len(ads)}")
    for ad in ads[:3]:
        print(f"   → {ad.get('displayed_link', 'N/A')}")
    
    time.sleep(0.3)

print("\n" + "=" * 60)
print("Testando mesma palavra várias vezes (pode variar)...")
print("=" * 60)

for i in range(5):
    params = {
        "q": "bet futebol",
        "location": "Sao Paulo, State of Sao Paulo, Brazil",
        "hl": "pt",
        "gl": "br",
        "device": "desktop",
        "api_key": API_KEY
    }
    
    results = GoogleSearch(params).get_dict()
    ads = results.get("ads", [])
    print(f"Tentativa {i+1}: {len(ads)} ads")
    time.sleep(1)

print("\n" + "=" * 60)
print("Testando sem location (apenas gl=br)...")
print("=" * 60)

params = {
    "q": "apostas esportivas",
    "hl": "pt",
    "gl": "br",
    "google_domain": "google.com.br",
    "device": "desktop",
    "api_key": API_KEY
}

results = GoogleSearch(params).get_dict()
ads = results.get("ads", [])
print(f"Ads: {len(ads)}")
for ad in ads:
    print(f"   → {ad.get('displayed_link', 'N/A')}")





