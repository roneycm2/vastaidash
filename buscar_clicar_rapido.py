from serpapi import GoogleSearch
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import time
from datetime import datetime

API_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

# Principais cidades do Brasil
LOCALIZACOES = [
    "Sao Paulo, State of Sao Paulo, Brazil",
    "Rio de Janeiro, State of Rio de Janeiro, Brazil",
    "Curitiba, State of Parana, Brazil",
    "Belo Horizonte, State of Minas Gerais, Brazil",
    "Porto Alegre, State of Rio Grande do Sul, Brazil",
    "Salvador, State of Bahia, Brazil",
    "Brasilia, Federal District, Brazil",
    "Fortaleza, State of Ceara, Brazil",
]

# Headers para simular navegador
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

def carregar_palavras_chave():
    palavras = []
    with open("palavras_chave.txt", "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                palavras.append(linha)
    return palavras

def extrair_dominio(url):
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except:
        return url

def buscar_primeiro_anuncio(palavra):
    """Busca em várias localizações até encontrar um anúncio"""
    for loc in LOCALIZACOES:
        cidade = loc.split(",")[0]
        try:
            params = {
                "q": palavra,
                "location": loc,
                "hl": "pt-br",
                "gl": "br",
                "google_domain": "google.com.br",
                "api_key": API_KEY
            }
            search = GoogleSearch(params)
            results = search.get_dict()
            ads = results.get("ads", [])
            
            if ads:
                return {
                    "palavra": palavra,
                    "cidade": cidade,
                    "ads": ads,
                    "sucesso": True
                }
        except Exception as e:
            continue
    
    return {"palavra": palavra, "sucesso": False, "ads": []}

def clicar_anuncio(ad_info):
    """Clica no tracking link do anúncio"""
    tracking_link = ad_info.get("tracking_link", "")
    link = ad_info.get("link", "")
    dominio = extrair_dominio(link)
    titulo = ad_info.get("title", "")[:60]
    
    if not tracking_link:
        return {
            "dominio": dominio,
            "titulo": titulo,
            "clicado": False,
            "erro": "Sem tracking link"
        }
    
    try:
        response = requests.get(tracking_link, headers=HEADERS, timeout=15, allow_redirects=True)
        return {
            "dominio": dominio,
            "titulo": titulo,
            "clicado": True,
            "status": response.status_code,
            "url_final": response.url[:80]
        }
    except Exception as e:
        return {
            "dominio": dominio,
            "titulo": titulo,
            "clicado": False,
            "erro": str(e)[:50]
        }

def main():
    print("=" * 70)
    print("🚀 BUSCA E CLIQUE PARALELO EM ANÚNCIOS")
    print("=" * 70)
    
    palavras = carregar_palavras_chave()
    print(f"📋 {len(palavras)} palavras-chave")
    print(f"📍 {len(LOCALIZACOES)} localizações")
    print("-" * 70)
    
    # Fase 1: Buscar anúncios em paralelo
    print("\n🔍 FASE 1: Buscando anúncios (paralelo)...\n")
    
    anuncios_encontrados = []
    dominios_unicos = set()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(buscar_primeiro_anuncio, p): p for p in palavras}
        
        for future in as_completed(futures):
            resultado = future.result()
            palavra = resultado["palavra"]
            
            if resultado["sucesso"]:
                cidade = resultado["cidade"]
                qtd = len(resultado["ads"])
                print(f"  ✅ '{palavra}' → {qtd} ad(s) em {cidade}")
                
                for ad in resultado["ads"]:
                    dominio = extrair_dominio(ad.get("link", ""))
                    if dominio not in dominios_unicos:
                        dominios_unicos.add(dominio)
                        anuncios_encontrados.append({
                            "palavra": palavra,
                            "cidade": cidade,
                            "ad": ad
                        })
            else:
                print(f"  ❌ '{palavra}' → sem anúncios")
    
    print(f"\n📊 Encontrados {len(anuncios_encontrados)} anúncios únicos de {len(dominios_unicos)} domínios")
    
    if not anuncios_encontrados:
        print("⚠️ Nenhum anúncio encontrado!")
        return
    
    # Fase 2: Clicar nos anúncios em paralelo
    print("\n" + "-" * 70)
    print("🖱️ FASE 2: Clicando nos anúncios (paralelo)...\n")
    
    resultados_cliques = []
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(clicar_anuncio, item["ad"]): item for item in anuncios_encontrados}
        
        for future in as_completed(futures):
            item = futures[future]
            resultado = future.result()
            resultado["palavra"] = item["palavra"]
            resultado["cidade"] = item["cidade"]
            resultados_cliques.append(resultado)
            
            if resultado["clicado"]:
                print(f"  ✅ {resultado['dominio']} ← '{item['palavra']}'")
            else:
                print(f"  ❌ {resultado['dominio']} - {resultado.get('erro', 'erro')}")
    
    # Relatório Final
    print("\n" + "=" * 70)
    print("📊 RELATÓRIO FINAL")
    print("=" * 70)
    
    cliques_sucesso = [r for r in resultados_cliques if r["clicado"]]
    cliques_falha = [r for r in resultados_cliques if not r["clicado"]]
    
    print(f"\n✅ CLIQUES COM SUCESSO ({len(cliques_sucesso)}):")
    print("-" * 50)
    for r in cliques_sucesso:
        print(f"  🔗 {r['dominio']}")
        print(f"     Palavra: '{r['palavra']}' | Cidade: {r['cidade']}")
        print(f"     Título: {r['titulo']}")
        print(f"     Status: {r['status']} | URL: {r['url_final']}")
        print()
    
    if cliques_falha:
        print(f"\n❌ CLIQUES COM FALHA ({len(cliques_falha)}):")
        print("-" * 50)
        for r in cliques_falha:
            print(f"  ⚠️ {r['dominio']} - {r.get('erro', 'erro desconhecido')}")
    
    # Salvar relatório
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    relatorio_file = f"relatorio_cliques_{timestamp}.txt"
    
    with open(relatorio_file, "w", encoding="utf-8") as f:
        f.write("RELATÓRIO DE CLIQUES EM ANÚNCIOS\n")
        f.write(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write("=" * 50 + "\n\n")
        
        f.write(f"Total de palavras: {len(palavras)}\n")
        f.write(f"Anúncios encontrados: {len(anuncios_encontrados)}\n")
        f.write(f"Cliques com sucesso: {len(cliques_sucesso)}\n")
        f.write(f"Cliques com falha: {len(cliques_falha)}\n\n")
        
        f.write("DOMÍNIOS CLICADOS COM SUCESSO:\n")
        f.write("-" * 30 + "\n")
        for r in cliques_sucesso:
            f.write(f"- {r['dominio']} ('{r['palavra']}' em {r['cidade']})\n")
        
        if cliques_falha:
            f.write("\nDOMÍNIOS COM FALHA:\n")
            f.write("-" * 30 + "\n")
            for r in cliques_falha:
                f.write(f"- {r['dominio']}: {r.get('erro', 'erro')}\n")
    
    print(f"\n💾 Relatório salvo em: {relatorio_file}")
    print(f"\n🏁 Concluído! {len(cliques_sucesso)}/{len(anuncios_encontrados)} cliques realizados.")

if __name__ == "__main__":
    main()

