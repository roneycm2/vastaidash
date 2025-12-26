from serpapi import GoogleSearch
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from urllib.parse import urlparse

API_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

LOCS = [
    "Sao Paulo, State of Sao Paulo, Brazil",
    "Rio de Janeiro, State of Rio de Janeiro, Brazil", 
    "Curitiba, State of Parana, Brazil",
    "Belo Horizonte, State of Minas Gerais, Brazil",
    "Fortaleza, State of Ceara, Brazil",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}

def buscar(palavra):
    for loc in LOCS:
        try:
            r = GoogleSearch({"q": palavra, "location": loc, "hl": "pt-br", "gl": "br", "google_domain": "google.com.br", "api_key": API_KEY}).get_dict()
            if "ads" in r and r["ads"]:
                return [(a.get("tracking_link"), urlparse(a.get("link","")).netloc.replace("www.",""), palavra) for a in r["ads"] if a.get("tracking_link")]
        except: pass
    return []

def clicar(info):
    link, dom, palavra = info
    try:
        r = requests.get(link, headers=HEADERS, timeout=10, allow_redirects=True)
        return (dom, palavra, True, r.status_code)
    except Exception as e:
        return (dom, palavra, False, str(e)[:30])

# Carregar palavras
palavras = [l.strip() for l in open("palavras_chave.txt", encoding="utf-8") if l.strip() and not l.startswith("#")]
print(f"⚡ TURBO MODE - {len(palavras)} palavras\n")

# FASE 1: Buscar (10 paralelos)
print("🔍 Buscando...")
todos_ads = []
doms_vistos = set()

with ThreadPoolExecutor(max_workers=10) as ex:
    for ads in ex.map(buscar, palavras):
        for ad in ads:
            if ad[1] not in doms_vistos:
                doms_vistos.add(ad[1])
                todos_ads.append(ad)
                print(f"  ✅ {ad[1]} ← '{ad[2]}'")

print(f"\n📊 {len(todos_ads)} anúncios únicos\n")

# FASE 2: Clicar (8 paralelos)
print("🖱️ Clicando...")
sucesso = []
falha = []

with ThreadPoolExecutor(max_workers=8) as ex:
    for r in ex.map(clicar, todos_ads):
        if r[2]:
            sucesso.append(r)
            print(f"  ✅ {r[0]} ({r[3]})")
        else:
            falha.append(r)
            print(f"  ❌ {r[0]}")

# Relatório
print(f"\n{'='*50}")
print(f"📊 RESULTADO: {len(sucesso)}/{len(todos_ads)} cliques OK")
print(f"{'='*50}")
print("\n✅ DOMÍNIOS CLICADOS:")
for r in sucesso:
    print(f"   {r[0]}")
if falha:
    print(f"\n❌ FALHAS: {len(falha)}")

