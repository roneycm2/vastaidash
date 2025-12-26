from serpapi import GoogleSearch
import json

# Teste 1: Com google_domain brasileiro
print("=== TESTE 1: google.com.br ===")
params = {
    "q": "bet7k",
    "location": "Brazil",
    "hl": "pt-br",
    "gl": "br",
    "google_domain": "google.com.br",
    "device": "desktop",
    "api_key": "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"
}
search = GoogleSearch(params)
results = search.get_dict()
print("Chaves:", list(results.keys()))
print("TEM ADS!" if "ads" in results else "SEM ADS")

# Teste 2: Mobile
print("\n=== TESTE 2: Mobile ===")
params["device"] = "mobile"
search = GoogleSearch(params)
results = search.get_dict()
print("TEM ADS!" if "ads" in results else "SEM ADS")

# Teste 3: Cidade específica
print("\n=== TESTE 3: Rio de Janeiro ===")
params["location"] = "Rio de Janeiro, State of Rio de Janeiro, Brazil"
params["device"] = "desktop"
search = GoogleSearch(params)
results = search.get_dict()
print("TEM ADS!" if "ads" in results else "SEM ADS")

# Mostrar resultados orgânicos para confirmar que a busca está funcionando
print("\n=== Resultados Orgânicos (confirmação) ===")
for i, org in enumerate(results.get("organic_results", [])[:3], 1):
    print(f"{i}. {org.get('title')}")
    print(f"   {org.get('link')}")

# Se tiver ads, mostrar
if "ads" in results:
    print("\n=== ANÚNCIOS ENCONTRADOS ===")
    print(json.dumps(results["ads"], indent=2, ensure_ascii=False))

