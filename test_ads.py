from serpapi import GoogleSearch

API_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

palavras = [
    "apostas esportivas",
    "bet online", 
    "cassino",
    "apostas futebol",
    "casa de apostas online",
    "site de apostas",
    "melhor bet",
    "apostar online",
    "jogos de azar",
    "slots online"
]

print("Testando com device=desktop...\n")

total_ads = 0
todos_dominios = []

for palavra in palavras:
    params = {
        "q": palavra,
        "location": "Sao Paulo, State of Sao Paulo, Brazil",
        "hl": "pt",
        "gl": "br",
        "device": "desktop",
        "api_key": API_KEY
    }
    
    results = GoogleSearch(params).get_dict()
    ads = results.get("ads", [])
    
    print(f"'{palavra}': {len(ads)} ads")
    
    for ad in ads:
        link = ad.get("displayed_link", ad.get("link", ""))
        if link:
            todos_dominios.append(link)
            print(f"   → {link}")
    
    total_ads += len(ads)

print(f"\n{'='*50}")
print(f"Total de anúncios encontrados: {total_ads}")
print(f"Domínios únicos: {len(set(todos_dominios))}")





