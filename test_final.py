from serpapi import GoogleSearch

API_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

# Testa várias palavras comerciais
palavras = [
    "seguro auto cotação",
    "empréstimo pessoal",
    "cartão de crédito",
    "hospedagem site",
    "advogado trabalhista"
]

print("Testando palavras comerciais genéricas (devem ter anúncios):\n")

for p in palavras:
    params = {
        "q": p,
        "location": "Sao Paulo, State of Sao Paulo, Brazil",
        "hl": "pt",
        "gl": "br",
        "api_key": API_KEY
    }
    
    r = GoogleSearch(params).get_dict()
    ads = r.get("ads", [])
    print(f"'{p}': {len(ads)} ads")
    for ad in ads[:2]:
        print(f"   → {ad.get('displayed_link', 'N/A')}")

print("\n" + "=" * 50)
print("Verificando HTML direto da SerpApi para 'apostas'...")

params = {
    "q": "apostas online",
    "location": "Sao Paulo, State of Sao Paulo, Brazil", 
    "hl": "pt",
    "gl": "br",
    "api_key": API_KEY
}

r = GoogleSearch(params).get_dict()
print(f"\nChaves: {list(r.keys())}")
print(f"Ads: {len(r.get('ads', []))}")
print(f"Google URL usado: {r.get('search_metadata', {}).get('google_url', 'N/A')}")





