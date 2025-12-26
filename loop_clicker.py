from serpapi import GoogleSearch
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from urllib.parse import urlparse
import time
from datetime import datetime
import random

API_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

LOCS = [
    "Sao Paulo, State of Sao Paulo, Brazil",
    "Rio de Janeiro, State of Rio de Janeiro, Brazil",
    "Curitiba, State of Parana, Brazil",
    "Belo Horizonte, State of Minas Gerais, Brazil",
    "Fortaleza, State of Ceara, Brazil",
    "Porto Alegre, State of Rio Grande do Sul, Brazil",
    "Salvador, State of Bahia, Brazil",
    "Brasilia, Federal District, Brazil",
]

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edge/120.0.0.0"},
    {"User-Agent": "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"},
]

# Estatísticas globais
stats = {
    "total_cliques": 0,
    "cliques_sucesso": 0,
    "cliques_falha": 0,
    "por_dominio": {},
    "inicio": None,
    "rodadas": 0
}

def carregar_dominios_permitidos():
    dominios = set()
    with open("dominios_permitidos.txt", "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                dominios.add(linha.lower())
    return dominios

def carregar_palavras():
    palavras = []
    with open("palavras_chave.txt", "r", encoding="utf-8") as f:
        for linha in f:
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                palavras.append(linha)
    return palavras

def buscar_ads(palavra, loc):
    try:
        r = GoogleSearch({
            "q": palavra, 
            "location": loc, 
            "hl": "pt-br", 
            "gl": "br", 
            "google_domain": "google.com.br", 
            "api_key": API_KEY
        }).get_dict()
        return r.get("ads", [])
    except:
        return []

def extrair_dominio(url):
    try:
        return urlparse(url).netloc.replace("www.", "").lower()
    except:
        return ""

def clicar(tracking_link, dominio):
    global stats
    try:
        headers = random.choice(HEADERS_LIST)
        r = requests.get(tracking_link, headers=headers, timeout=8, allow_redirects=True)
        stats["total_cliques"] += 1
        stats["cliques_sucesso"] += 1
        stats["por_dominio"][dominio] = stats["por_dominio"].get(dominio, 0) + 1
        return True
    except:
        stats["total_cliques"] += 1
        stats["cliques_falha"] += 1
        return False

def buscar_e_clicar(args):
    palavra, loc, dominios_permitidos = args
    ads = buscar_ads(palavra, loc)
    cliques = 0
    
    for ad in ads:
        link = ad.get("link", "")
        dominio = extrair_dominio(link)
        tracking = ad.get("tracking_link", "")
        
        if dominio in dominios_permitidos and tracking:
            if clicar(tracking, dominio):
                cliques += 1
    
    return cliques

def exibir_stats():
    global stats
    elapsed = time.time() - stats["inicio"] if stats["inicio"] else 0
    mins = int(elapsed // 60)
    secs = int(elapsed % 60)
    
    print(f"\r⚡ Rodada {stats['rodadas']} | "
          f"✅ {stats['cliques_sucesso']} OK | "
          f"❌ {stats['cliques_falha']} FAIL | "
          f"⏱️ {mins}m{secs}s | "
          f"📊 {stats['cliques_sucesso']/(elapsed/60):.1f}/min" if elapsed > 0 else "", end="", flush=True)

def salvar_relatorio():
    global stats
    elapsed = time.time() - stats["inicio"] if stats["inicio"] else 0
    
    with open("relatorio_cliques.txt", "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("📊 RELATÓRIO DE CLIQUES EM MASSA\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
        f.write(f"⏱️ Tempo total: {int(elapsed//60)}m {int(elapsed%60)}s\n")
        f.write(f"🔄 Rodadas: {stats['rodadas']}\n\n")
        f.write("-" * 40 + "\n")
        f.write(f"✅ Cliques com sucesso: {stats['cliques_sucesso']}\n")
        f.write(f"❌ Cliques com falha: {stats['cliques_falha']}\n")
        f.write(f"📈 Total de cliques: {stats['total_cliques']}\n")
        f.write(f"⚡ Média: {stats['cliques_sucesso']/(elapsed/60):.1f} cliques/min\n\n" if elapsed > 60 else "\n")
        f.write("-" * 40 + "\n")
        f.write("📊 CLIQUES POR DOMÍNIO:\n")
        f.write("-" * 40 + "\n")
        for dom, qtd in sorted(stats["por_dominio"].items(), key=lambda x: -x[1]):
            f.write(f"   {dom}: {qtd} cliques\n")
    
    print(f"\n💾 Relatório salvo em relatorio_cliques.txt")

def main():
    global stats
    
    dominios_permitidos = carregar_dominios_permitidos()
    palavras = carregar_palavras()
    
    print("=" * 60)
    print("🚀 LOOP CLICKER - MODO ESCALA")
    print("=" * 60)
    print(f"🎯 Domínios permitidos: {', '.join(dominios_permitidos)}")
    print(f"📋 Palavras-chave: {len(palavras)}")
    print(f"📍 Localizações: {len(LOCS)}")
    print("-" * 60)
    print("⚠️  Pressione Ctrl+C para parar e gerar relatório")
    print("=" * 60 + "\n")
    
    stats["inicio"] = time.time()
    
    try:
        while True:
            stats["rodadas"] += 1
            
            # Criar lista de tarefas (palavra + localização)
            tarefas = []
            for palavra in palavras:
                loc = random.choice(LOCS)
                tarefas.append((palavra, loc, dominios_permitidos))
            
            # Executar em paralelo (15 workers)
            with ThreadPoolExecutor(max_workers=15) as executor:
                list(executor.map(buscar_e_clicar, tarefas))
            
            exibir_stats()
            
            # Pequena pausa entre rodadas
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Parando...")
        salvar_relatorio()
        
        print("\n" + "=" * 60)
        print("📊 RESULTADO FINAL")
        print("=" * 60)
        print(f"✅ Cliques com sucesso: {stats['cliques_sucesso']}")
        print(f"❌ Cliques com falha: {stats['cliques_falha']}")
        print(f"🔄 Rodadas completas: {stats['rodadas']}")
        print("\n📊 Por domínio:")
        for dom, qtd in sorted(stats["por_dominio"].items(), key=lambda x: -x[1]):
            print(f"   🔗 {dom}: {qtd} cliques")

if __name__ == "__main__":
    main()

