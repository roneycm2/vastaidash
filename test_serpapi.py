from serpapi import GoogleSearch
import json

params = {
    "q": "apostas esportivas",
    "location": "Brazil",
    "hl": "pt",
    "gl": "br",
    "api_key": "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"
}

search = GoogleSearch(params)
results = search.get_dict()

print("=" * 60)
print("Chaves disponíveis na resposta:")
print(list(results.keys()))
print("=" * 60)

# Verifica ads
if "ads" in results:
    ads = results["ads"]
    print(f"\n✅ Encontrados {len(ads)} anúncios:")
    for i, ad in enumerate(ads[:5]):
        print(f"\n  [{i+1}] {ad.get('title', 'Sem título')}")
        print(f"      Link: {ad.get('link', 'Sem link')}")
        print(f"      Tracking: {ad.get('tracking_link', 'Sem tracking')}")
else:
    print("\n❌ Nenhum campo 'ads' na resposta")

# Verifica shopping
if "shopping_results" in results:
    shopping = results["shopping_results"]
    print(f"\n🛒 Encontrados {len(shopping)} resultados de shopping")
else:
    print("\n❌ Nenhum campo 'shopping_results' na resposta")

# Verifica se há algum tipo de anúncio em outros campos
for key in results.keys():
    if 'ad' in key.lower() or 'sponsor' in key.lower():
        print(f"\n📢 Campo potencial de anúncio: {key}")
        print(f"   Conteúdo: {results[key][:200] if isinstance(results[key], str) else results[key][:2] if isinstance(results[key], list) else results[key]}")

