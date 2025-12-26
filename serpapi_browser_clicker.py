"""
SerpAPI + Patchright Browser Clicker - MODO ESCALA MÁXIMA
Busca ads via SerpAPI e clica continuamente com múltiplos navegadores
"""

import asyncio
import os
import random
import time
import tempfile
import threading
from datetime import datetime
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import json

from serpapi import GoogleSearch
from patchright.async_api import async_playwright

from dashboard_serpapi import stats_manager, iniciar_dashboard_thread

# =====================================================
# CONFIGURAÇÕES
# =====================================================
SERPAPI_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

PROXY_HOST = "fb29d01db8530b99.shg.na.pyproxy.io"
PROXY_PORT = "16666"
PROXY_USER_BASE = "liderbet1-zone-resi-region-br"
PROXY_PASS = "Aa10203040"

PLUGIN_PATH = r"C:\Users\outros\liderbet\plugin"

NUM_BROWSERS = 8  # Navegadores paralelos
CLIQUES_POR_BROWSER = 50  # Cliques antes de reiniciar browser

LOCS = [
    "Sao Paulo, State of Sao Paulo, Brazil",
    "Rio de Janeiro, State of Rio de Janeiro, Brazil",
    "Curitiba, State of Parana, Brazil",
    "Belo Horizonte, State of Minas Gerais, Brazil",
    "Fortaleza, State of Ceara, Brazil",
    "Porto Alegre, State of Rio Grande do Sul, Brazil",
    "Salvador, State of Bahia, Brazil",
    "Brasilia, Federal District, Brazil",
    "Manaus, State of Amazonas, Brazil",
    "Recife, State of Pernambuco, Brazil",
]

# Armazena tracking links encontrados globalmente
tracking_links_global = []
tracking_links_lock = threading.Lock()

# =====================================================
# FUNÇÕES AUXILIARES
# =====================================================
def carregar_dominios():
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

def extrair_dominio(url):
    try:
        return urlparse(url).netloc.replace("www.", "").lower()
    except:
        return ""

def gerar_proxy_session():
    """Gera uma sessão de proxy única para rotação"""
    session_id = random.randint(100000, 999999)
    return f"{PROXY_USER_BASE}-session-{session_id}-sessTime-1"

# =====================================================
# BUSCA ADS VIA SERPAPI
# =====================================================
def buscar_ads_serpapi(palavra, dominios_permitidos, loc):
    """Busca ads via SerpAPI para uma palavra em uma localização"""
    ads_encontrados = []
    
    try:
        params = {
            "q": palavra,
            "location": loc,
            "hl": "pt-br",
            "gl": "br",
            "google_domain": "google.com.br",
            "api_key": SERPAPI_KEY
        }
        results = GoogleSearch(params).get_dict()
        ads = results.get("ads", [])
        
        cidade = loc.split(",")[0]
        
        for ad in ads:
            link = ad.get("link", "")
            tracking = ad.get("tracking_link", "")
            dominio = extrair_dominio(link)
            
            if dominio in dominios_permitidos and tracking:
                stats_manager.registrar_ad_encontrado(palavra, dominio, tracking, cidade)
                
                ads_encontrados.append({
                    "dominio": dominio,
                    "tracking_link": tracking,
                    "palavra": palavra,
                    "cidade": cidade
                })
                
    except Exception as e:
        pass
    
    return ads_encontrados

def buscar_todos_ads_paralelo(palavras, dominios_permitidos):
    """Busca ads em paralelo para todas as palavras em todas as localizações"""
    global tracking_links_global
    
    todos_ads = []
    tarefas = []
    
    # Cria tarefas para cada combinação palavra + localização
    for palavra in palavras:
        for loc in LOCS:
            tarefas.append((palavra, loc))
    
    print(f"  📋 {len(tarefas)} buscas para executar...")
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = []
        for palavra, loc in tarefas:
            futures.append(executor.submit(buscar_ads_serpapi, palavra, dominios_permitidos, loc))
        
        for future in futures:
            try:
                ads = future.result()
                todos_ads.extend(ads)
            except:
                pass
    
    # Remove duplicatas e atualiza lista global
    vistos = set()
    ads_unicos = []
    for ad in todos_ads:
        key = ad["tracking_link"]
        if key not in vistos:
            vistos.add(key)
            ads_unicos.append(ad)
    
    with tracking_links_lock:
        # Adiciona novos links (evita duplicatas)
        links_existentes = {a["tracking_link"] for a in tracking_links_global}
        for ad in ads_unicos:
            if ad["tracking_link"] not in links_existentes:
                tracking_links_global.append(ad)
    
    return ads_unicos

# =====================================================
# WORKER DE CLIQUES COM NAVEGADOR
# =====================================================
async def obter_ip(page, browser_id):
    """Obtém IP atual do proxy"""
    try:
        await page.goto('https://ipinfo.io/json', wait_until='networkidle', timeout=15000)
        body = await page.locator('body').inner_text()
        data = json.loads(body)
        ip = data.get('ip', 'N/A')
        cidade = data.get('city', '')
        estado = data.get('region', '')
        stats_manager.registrar_ip(browser_id, ip, cidade, estado)
        return ip, cidade, estado
    except Exception as e:
        return "N/A", "", ""

async def worker_cliques(browser_id, stop_event):
    """Worker que fica em loop clicando nos tracking links"""
    global tracking_links_global
    
    while not stop_event.is_set():
        # Gera nova sessão de proxy para rotação de IP
        proxy_user = gerar_proxy_session()
        current_ip = "N/A"
        
        with tempfile.TemporaryDirectory() as user_data_dir:
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch_persistent_context(
                        user_data_dir,
                        headless=False,
                        proxy={
                            "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                            "username": proxy_user,
                            "password": PROXY_PASS
                        },
                        args=[
                            f'--disable-extensions-except={PLUGIN_PATH}',
                            f'--load-extension={PLUGIN_PATH}',
                        ],
                    )
                    
                    page = await browser.new_page()
                    page.set_default_navigation_timeout(25000)
                    
                    # Obtém IP do proxy
                    current_ip, cidade_ip, estado_ip = await obter_ip(page, browser_id)
                    print(f"  🌐 [{browser_id}] Novo IP: {current_ip} ({cidade_ip}, {estado_ip})")
                    
                    cliques_feitos = 0
                    
                    while cliques_feitos < CLIQUES_POR_BROWSER and not stop_event.is_set():
                        # Pega um tracking link aleatório da lista global
                        with tracking_links_lock:
                            if not tracking_links_global:
                                await asyncio.sleep(2)
                                continue
                            ad = random.choice(tracking_links_global)
                        
                        dominio = ad["dominio"]
                        tracking = ad["tracking_link"]
                        cidade = ad.get("cidade", "")
                        url_retorno = None
                        
                        try:
                            await page.goto(tracking, wait_until="domcontentloaded", timeout=20000)
                            
                            url_retorno = page.url
                            
                            # Simula comportamento humano
                            await asyncio.sleep(random.uniform(1.5, 3))
                            await page.evaluate("window.scrollBy(0, Math.random() * 400)")
                            await asyncio.sleep(random.uniform(0.5, 1.5))
                            
                            # Registra sucesso
                            stats_manager.registrar_clique(
                                dominio, url_retorno,
                                tracking_link=tracking,
                                cidade=cidade,
                                ip=current_ip,
                                sucesso=True
                            )
                            cliques_feitos += 1
                            print(f"  ✅ [{browser_id}] {dominio} ({current_ip[:15]}...) → OK")
                            
                        except Exception as e:
                            stats_manager.registrar_clique(
                                dominio, url_retorno,
                                tracking_link=tracking,
                                cidade=cidade,
                                ip=current_ip,
                                sucesso=False,
                                erro=str(e)
                            )
                            print(f"  ❌ [{browser_id}] {dominio} - {str(e)[:40]}")
                        
                        # Pequena pausa entre cliques
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                    
                    await browser.close()
                    
            except Exception as e:
                print(f"  ⚠️ [{browser_id}] Erro browser: {str(e)[:40]}")
        
        # Pausa antes de reiniciar com novo IP
        if not stop_event.is_set():
            print(f"  🔄 [{browser_id}] Reiniciando com novo IP...")
            await asyncio.sleep(2)

def run_worker(browser_id, stop_event):
    """Executa worker em asyncio"""
    asyncio.run(worker_cliques(browser_id, stop_event))

# =====================================================
# BUSCADOR CONTÍNUO
# =====================================================
def buscador_continuo(palavras, dominios_permitidos, stop_event):
    """Thread que fica buscando novos ads continuamente"""
    while not stop_event.is_set():
        print("\n🔍 Buscando novos ads...")
        stats_manager.incrementar_rodada()
        
        novos = buscar_todos_ads_paralelo(palavras, dominios_permitidos)
        
        with tracking_links_lock:
            total = len(tracking_links_global)
        
        print(f"  📊 {len(novos)} novos ads | Total: {total} tracking links")
        
        # Aguarda antes da próxima busca
        for _ in range(30):  # 30 segundos
            if stop_event.is_set():
                break
            time.sleep(1)

# =====================================================
# MAIN
# =====================================================
def main():
    print("=" * 70)
    print("🚀 SERPAPI BROWSER CLICKER - MODO ESCALA MÁXIMA")
    print("=" * 70)
    
    if not os.path.exists(PLUGIN_PATH):
        print(f"❌ Plugin não encontrado: {PLUGIN_PATH}")
        return
    
    dominios = carregar_dominios()
    palavras = carregar_palavras()
    
    print(f"🎯 Domínios: {', '.join(dominios)}")
    print(f"📋 Palavras: {len(palavras)}")
    print(f"📍 Regiões: {len(LOCS)}")
    print(f"🌐 Browsers paralelos: {NUM_BROWSERS}")
    print(f"🔄 Cliques por browser: {CLIQUES_POR_BROWSER}")
    
    # Inicia dashboard
    print("\n🌐 Iniciando Dashboard...")
    iniciar_dashboard_thread(5000)
    print("✅ Dashboard: http://localhost:5000")
    
    print("-" * 70)
    print("⚠️  Pressione Ctrl+C para parar")
    print("=" * 70)
    
    stats_manager.iniciar()
    stop_event = threading.Event()
    
    # Primeira busca de ads
    print("\n🔍 Busca inicial de ads...")
    buscar_todos_ads_paralelo(palavras, dominios)
    
    with tracking_links_lock:
        total_links = len(tracking_links_global)
    
    print(f"  ✅ {total_links} tracking links encontrados!")
    
    if total_links == 0:
        print("❌ Nenhum tracking link encontrado. Verifique os domínios permitidos.")
        return
    
    try:
        # Inicia thread de busca contínua
        buscador_thread = threading.Thread(
            target=buscador_continuo,
            args=(palavras, dominios, stop_event),
            daemon=True
        )
        buscador_thread.start()
        
        # Inicia workers de clique
        print(f"\n🖱️ Iniciando {NUM_BROWSERS} workers de clique...")
        workers = []
        
        for i in range(NUM_BROWSERS):
            t = threading.Thread(
                target=run_worker,
                args=(i + 1, stop_event),
                daemon=True
            )
            workers.append(t)
            t.start()
            time.sleep(1)  # Intervalo entre inicializações
        
        print("✅ Todos os workers iniciados!")
        print("\n📊 Acompanhe em: http://localhost:5000\n")
        
        # Loop de monitoramento
        while True:
            time.sleep(10)
            s = stats_manager.get_stats()
            print(f"\r📊 ✅ {s['cliques_sucesso']} OK | ❌ {s['cliques_falha']} FAIL | ⚡ {s['cliques_por_minuto']}/min | 🔗 {len(tracking_links_global)} links", end="", flush=True)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Parando...")
        stop_event.set()
        
        # Aguarda workers finalizarem
        time.sleep(3)
        
        # Salva relatório
        s = stats_manager.get_stats()
        
        with open("relatorio_cliques.txt", "w", encoding="utf-8") as f:
            f.write("=" * 70 + "\n")
            f.write("📊 RELATÓRIO FINAL - MODO ESCALA MÁXIMA\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"📅 Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f.write(f"⏱️ Tempo: {s['tempo_execucao']}\n")
            f.write(f"🔄 Rodadas de busca: {s['rodadas']}\n\n")
            f.write("-" * 50 + "\n")
            f.write(f"🔍 Ads Encontrados: {s['ads_encontrados']}\n")
            f.write(f"🔗 Tracking Links: {len(tracking_links_global)}\n")
            f.write(f"✅ Cliques OK: {s['cliques_sucesso']}\n")
            f.write(f"❌ Cliques FAIL: {s['cliques_falha']}\n")
            f.write(f"📈 Taxa de Sucesso: {s['taxa_sucesso']}%\n")
            f.write(f"⚡ Média: {s['cliques_por_minuto']}/min\n\n")
            f.write("-" * 50 + "\n")
            f.write("📊 POR DOMÍNIO:\n")
            for dom, qtd in sorted(s["por_dominio"].items(), key=lambda x: -x[1]):
                f.write(f"   {dom}: {qtd} cliques\n")
            f.write("\n" + "-" * 50 + "\n")
            f.write("📍 POR REGIÃO:\n")
            for reg, qtd in sorted(s.get("por_regiao", {}).items(), key=lambda x: -x[1]):
                f.write(f"   {reg}: {qtd} cliques\n")
        
        print(f"\n💾 Relatório salvo em relatorio_cliques.txt")
        print("\n" + "=" * 70)
        print("📊 RESULTADO FINAL")
        print("=" * 70)
        print(f"🔍 Ads Encontrados: {s['ads_encontrados']}")
        print(f"🔗 Tracking Links: {len(tracking_links_global)}")
        print(f"✅ Cliques OK: {s['cliques_sucesso']}")
        print(f"❌ Cliques FAIL: {s['cliques_falha']}")
        print(f"📈 Taxa de Sucesso: {s['taxa_sucesso']}%")
        print(f"⚡ Média: {s['cliques_por_minuto']} cliques/min")

if __name__ == "__main__":
    main()
