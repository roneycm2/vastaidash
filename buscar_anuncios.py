from serpapi import GoogleSearch
import time

API_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

# Principais cidades/regiões do Brasil
LOCALIZACOES = [
    "Sao Paulo, State of Sao Paulo, Brazil",
    "Rio de Janeiro, State of Rio de Janeiro, Brazil",
    "Curitiba, State of Parana, Brazil",
    "Belo Horizonte, State of Minas Gerais, Brazil",
    "Porto Alegre, State of Rio Grande do Sul, Brazil",
    "Salvador, State of Bahia, Brazil",
    "Brasilia, Federal District, Brazil",
    "Fortaleza, State of Ceara, Brazil",
    "Recife, State of Pernambuco, Brazil",
    "Manaus, State of Amazonas, Brazil",
]

# Ler palavras-chave do arquivo
def carregar_palavras_chave():
    palavras = []
    with open("palavras_chave.txt", "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            # Ignorar comentários e linhas vazias
            if linha and not linha.startswith("#"):
                palavras.append(linha)
    return palavras

def buscar_anuncios(palavra, localizacao):
    """Busca anúncios para uma palavra-chave em uma localização"""
    params = {
        "q": palavra,
        "location": localizacao,
        "hl": "pt-br",
        "gl": "br",
        "google_domain": "google.com.br",
        "api_key": API_KEY
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return results.get("ads", [])
    except Exception as e:
        print(f"  Erro: {e}")
        return []

def extrair_dominio(url):
    """Extrai o domínio de uma URL"""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace("www.", "")
    except:
        return url

def main():
    palavras = carregar_palavras_chave()
    print(f"📋 {len(palavras)} palavras-chave carregadas")
    print(f"📍 {len(LOCALIZACOES)} localizações para testar")
    print("=" * 60)
    
    # Dicionário para armazenar resultados
    # {dominio: {palavra: [localizacoes]}}
    dominios_encontrados = {}
    anuncios_por_palavra = {}
    
    total_buscas = len(palavras) * len(LOCALIZACOES)
    busca_atual = 0
    
    for palavra in palavras:
        print(f"\n🔍 Buscando: '{palavra}'")
        encontrou = False
        
        for loc in LOCALIZACOES:
            busca_atual += 1
            cidade = loc.split(",")[0]
            
            ads = buscar_anuncios(palavra, loc)
            
            if ads:
                encontrou = True
                print(f"  ✅ {cidade}: {len(ads)} anúncio(s)")
                
                for ad in ads:
                    link = ad.get("link", "")
                    dominio = extrair_dominio(link)
                    titulo = ad.get("title", "")[:50]
                    
                    # Registrar domínio
                    if dominio not in dominios_encontrados:
                        dominios_encontrados[dominio] = {}
                    if palavra not in dominios_encontrados[dominio]:
                        dominios_encontrados[dominio][palavra] = []
                    if cidade not in dominios_encontrados[dominio][palavra]:
                        dominios_encontrados[dominio][palavra].append(cidade)
                    
                    # Registrar por palavra
                    if palavra not in anuncios_por_palavra:
                        anuncios_por_palavra[palavra] = set()
                    anuncios_por_palavra[palavra].add(dominio)
            
            # Pequena pausa para não sobrecarregar a API
            time.sleep(0.3)
        
        if not encontrou:
            print(f"  ❌ Nenhum anúncio encontrado")
    
    # Relatório final
    print("\n" + "=" * 60)
    print("📊 RELATÓRIO FINAL")
    print("=" * 60)
    
    print(f"\n🌐 DOMÍNIOS ENCONTRADOS ({len(dominios_encontrados)}):")
    print("-" * 40)
    for dominio in sorted(dominios_encontrados.keys()):
        palavras_dom = dominios_encontrados[dominio]
        total_palavras = len(palavras_dom)
        print(f"\n  🔗 {dominio}")
        print(f"     Aparece em {total_palavras} palavra(s)-chave")
        for p, locs in list(palavras_dom.items())[:3]:
            print(f"       - '{p}' em: {', '.join(locs[:3])}")
        if total_palavras > 3:
            print(f"       ... e mais {total_palavras - 3} palavras")
    
    print(f"\n\n📝 PALAVRAS COM ANÚNCIOS ({len(anuncios_por_palavra)}/{len(palavras)}):")
    print("-" * 40)
    for palavra, doms in sorted(anuncios_por_palavra.items()):
        print(f"  '{palavra}': {', '.join(doms)}")
    
    # Salvar lista de domínios para clicar
    print("\n\n💾 Salvando lista de domínios em 'dominios_anuncios.txt'...")
    with open("dominios_anuncios.txt", "w", encoding="utf-8") as f:
        f.write("# Domínios encontrados nos anúncios\n")
        f.write("# Gerado automaticamente\n\n")
        for dominio in sorted(dominios_encontrados.keys()):
            f.write(f"{dominio}\n")
    
    print(f"\n✅ Concluído! {len(dominios_encontrados)} domínios salvos.")
    
    return dominios_encontrados

if __name__ == "__main__":
    main()

