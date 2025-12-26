from serpapi import GoogleSearch
import json

API_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

# Palavras que DEVEM ter anúncios
palavras_teste = [
    "apostas esportivas",
    "cassino online",
    "bet futebol",
    "casa de apostas",
    "7k bet"
]

print("=" * 70)
print("🔍 DEBUG: Testando diferentes configurações da SerpApi")
print("=" * 70)

for palavra in palavras_teste:
    print(f"\n📌 Buscando: '{palavra}'")
    print("-" * 50)
    
    # Configuração atual
    params = {
        "q": palavra,
        "location": "Sao Paulo, State of Sao Paulo, Brazil",
        "hl": "pt",
        "gl": "br",
        "api_key": API_KEY
    }
    
    search = GoogleSearch(params)
    results = search.get_dict()
    
    # Verifica todas as possíveis chaves de anúncios
    ads = results.get("ads", [])
    ads_bottom = results.get("ads_bottom", [])
    shopping = results.get("shopping_results", [])
    inline_shopping = results.get("inline_shopping", [])
    local_ads = results.get("local_ads", [])
    
    print(f"   ads: {len(ads)}")
    print(f"   ads_bottom: {len(ads_bottom)}")
    print(f"   shopping_results: {len(shopping)}")
    print(f"   inline_shopping: {len(inline_shopping)}")
    print(f"   local_ads: {len(local_ads)}")
    
    # Mostra os primeiros anúncios encontrados
    if ads:
        print(f"\n   🎯 Anúncios encontrados:")
        for i, ad in enumerate(ads[:3]):
            link = ad.get("link", "N/A")
            title = ad.get("title", "N/A")
            print(f"      [{i+1}] {title[:50]}")
            print(f"          Link: {link[:60]}...")
    
    # Mostra todas as chaves disponíveis
    print(f"\n   📋 Chaves na resposta: {list(results.keys())}")

print("\n" + "=" * 70)
print("🔧 Testando com parâmetros alternativos...")
print("=" * 70)

# Teste com device=desktop
params_desktop = {
    "q": "apostas esportivas",
    "location": "Sao Paulo, State of Sao Paulo, Brazil",
    "hl": "pt",
    "gl": "br",
    "device": "desktop",
    "api_key": API_KEY
}

search = GoogleSearch(params_desktop)
results = search.get_dict()
print(f"\n📱 Com device=desktop:")
print(f"   ads: {len(results.get('ads', []))}")

# Teste com google_domain
params_domain = {
    "q": "apostas esportivas",
    "google_domain": "google.com.br",
    "hl": "pt",
    "gl": "br",
    "api_key": API_KEY
}

search = GoogleSearch(params_domain)
results = search.get_dict()
print(f"\n🌐 Com google_domain=google.com.br:")
print(f"   ads: {len(results.get('ads', []))}")

# Teste combinado
params_combined = {
    "q": "apostas esportivas",
    "location": "Sao Paulo, State of Sao Paulo, Brazil",
    "google_domain": "google.com.br",
    "hl": "pt",
    "gl": "br",
    "device": "desktop",
    "api_key": API_KEY
}

search = GoogleSearch(params_combined)
results = search.get_dict()
print(f"\n🔄 Combinado (location + google_domain + device):")
print(f"   ads: {len(results.get('ads', []))}")
if results.get('ads'):
    for ad in results['ads'][:3]:
        print(f"      - {ad.get('displayed_link', 'N/A')}")





