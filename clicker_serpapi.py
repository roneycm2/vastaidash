"""
Google Ads Clicker - SerpApi Google Ads API + Patchright
Usa a API oficial do SerpApi para buscar anúncios e Patchright para clicar
"""

import asyncio
import random
import time
import json
import tempfile
import threading
from urllib.parse import urlparse

from serpapi import GoogleSearch
from patchright.async_api import async_playwright

from stats_serpapi import stats_manager
from dashboard_serpapi import iniciar_dashboard_thread

# =====================================================
# CONFIGURAÇÕES
# =====================================================
SERPAPI_KEY = "bc8250eea3f0d6305d9adb605a1b10d5378fde18f805c3b48b6bbcd1e48da1b9"

PROXY_HOST = "fb29d01db8530b99.shg.na.pyproxy.io"
PROXY_PORT = "16666"
PROXY_USER = "liderbet1-zone-resi-region-br-session-85deaca4d5ea-sessTime-1"
PROXY_PASS = "Aa10203040"

PALAVRAS_ARQUIVO = "palavras_chave.txt"
DOMINIOS_PERMITIDOS_ARQUIVO = "dominios_permitidos.txt"

NUM_WORKERS = 15
DELAY_MIN = 2.0
DELAY_MAX = 5.0

# =====================================================
# VARIÁVEIS GLOBAIS
# =====================================================
DOMINIOS_PERMITIDOS = []
DOMINIOS_CLICADOS_GLOBAL = set()
DOMINIOS_CLICADOS_LOCK = threading.Lock()
ANUNCIOS_QUEUE = []
ANUNCIOS_QUEUE_LOCK = threading.Lock()


def carregar_palavras_chave(arquivo: str) -> list[str]:
    """Carrega palavras-chave do arquivo."""
    palavras = []
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#"):
                    palavras.append(linha)
    except FileNotFoundError:
        print(f"❌ Arquivo '{arquivo}' não encontrado!")
    return palavras


def carregar_dominios_permitidos(arquivo: str) -> list[str]:
    """Carrega domínios permitidos do arquivo."""
    dominios = []
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#"):
                    dominios.append(linha.lower())
    except FileNotFoundError:
        pass
    return dominios


def extrair_dominio(url: str) -> str:
    """Extrai domínio de uma URL."""
    try:
        return urlparse(url).netloc.lower()
    except:
        return ""


def verificar_dominio_valido(href: str) -> tuple[bool, str]:
    """Verifica se domínio é válido para clicar."""
    global DOMINIOS_CLICADOS_GLOBAL
    
    dominio = extrair_dominio(href)
    if not dominio:
        return False, ""
    
    # Verifica se é permitido
    if DOMINIOS_PERMITIDOS:
        if not any(p in dominio for p in DOMINIOS_PERMITIDOS):
            return False, dominio
    
    # Verifica se já foi clicado (thread-safe)
    with DOMINIOS_CLICADOS_LOCK:
        if dominio in DOMINIOS_CLICADOS_GLOBAL:
            return False, dominio
    
    return True, dominio


def marcar_dominio_clicado(dominio: str):
    """Marca domínio como clicado (thread-safe)."""
    with DOMINIOS_CLICADOS_LOCK:
        DOMINIOS_CLICADOS_GLOBAL.add(dominio)


def buscar_anuncios_serpapi(palavra_chave: str, debug: bool = False) -> list[dict]:
    """
    Busca anúncios usando SerpApi Google Ads API.
    Retorna lista de anúncios com link, título e tracking_link.
    """
    anuncios = []
    
    try:
        # Parâmetros usando o formato oficial do SerpApi
        params = {
            "q": palavra_chave,
            "location": "Sao Paulo, State of Sao Paulo, Brazil",
            "hl": "pt",
            "gl": "br",
            "api_key": SERPAPI_KEY
        }
        
        # Realiza a busca usando a biblioteca oficial
        search = GoogleSearch(params)
        results = search.get_dict()
        
        # Debug: mostra se há erro na API
        if "error" in results:
            print(f"      ❌ Erro API: {results['error']}")
            return []
        
        # Debug: mostra quantos anúncios a API retornou
        if debug:
            ads_count = len(results.get("ads", []))
            ads_bottom_count = len(results.get("ads_bottom", []))
            shopping_count = len(results.get("shopping_results", []))
            print(f"      📊 API retornou: {ads_count} ads, {ads_bottom_count} ads_bottom, {shopping_count} shopping")
        
        # Extrai anúncios do topo (ads) - Google Ads Results
        if "ads" in results:
            for ad in results["ads"]:
                # Link principal do anúncio
                link = ad.get("link", "")
                # Link de rastreamento (clique real do Google Ads)
                tracking_link = ad.get("tracking_link", link)
                titulo = ad.get("title", "")
                descricao = ad.get("description", "")
                displayed_link = ad.get("displayed_link", "")
                
                if link:
                    anuncios.append({
                        "link": link,
                        "tracking_link": tracking_link,
                        "titulo": titulo,
                        "descricao": descricao,
                        "displayed_link": displayed_link,
                        "palavra_chave": palavra_chave,
                        "tipo": "ads"
                    })
        
        # Extrai anúncios do rodapé (ads_bottom)
        if "ads_bottom" in results:
            for ad in results["ads_bottom"]:
                link = ad.get("link", "")
                tracking_link = ad.get("tracking_link", link)
                titulo = ad.get("title", "")
                
                if link:
                    anuncios.append({
                        "link": link,
                        "tracking_link": tracking_link,
                        "titulo": titulo,
                        "descricao": ad.get("description", ""),
                        "displayed_link": ad.get("displayed_link", ""),
                        "palavra_chave": palavra_chave,
                        "tipo": "ads_bottom"
                    })
        
        # Extrai anúncios de shopping
        if "shopping_results" in results:
            for item in results["shopping_results"][:5]:
                link = item.get("link", "")
                if link:
                    anuncios.append({
                        "link": link,
                        "tracking_link": link,
                        "titulo": item.get("title", ""),
                        "descricao": f"Preço: {item.get('price', 'N/A')}",
                        "displayed_link": item.get("source", ""),
                        "palavra_chave": palavra_chave,
                        "tipo": "shopping"
                    })
        
        # Extrai anúncios inline shopping
        if "inline_shopping" in results:
            for item in results["inline_shopping"][:3]:
                link = item.get("link", "")
                if link:
                    anuncios.append({
                        "link": link,
                        "tracking_link": link,
                        "titulo": item.get("title", ""),
                        "descricao": f"Preço: {item.get('price', 'N/A')}",
                        "displayed_link": item.get("source", ""),
                        "palavra_chave": palavra_chave,
                        "tipo": "inline_shopping"
                    })
        
    except Exception as e:
        print(f"❌ Erro SerpApi para '{palavra_chave}': {e}")
    
    return anuncios


def coletar_todos_anuncios(palavras: list[str]) -> list[dict]:
    """Coleta todos os anúncios de todas as palavras-chave usando SerpApi."""
    todos_anuncios = []
    
    # Registra início da coleta no stats
    stats_manager.add_log(f"🔍 Iniciando busca de anúncios para {len(palavras)} palavras-chave")
    
    print(f"\n🔍 Buscando anúncios via SerpApi Google Ads API...")
    print(f"   {len(palavras)} palavras-chave para processar\n")
    
    for i, palavra in enumerate(palavras):
        print(f"  [{i+1}/{len(palavras)}] Buscando: {palavra[:50]}...")
        
        # Ativa debug nas primeiras 3 buscas
        anuncios = buscar_anuncios_serpapi(palavra, debug=(i < 3))
        
        # Registra busca no stats
        anuncios_validos_count = 0
        anuncios_total_count = 0
        
        # Filtra apenas domínios válidos
        for anuncio in anuncios:
            dominio = extrair_dominio(anuncio["link"])
            anuncios_total_count += 1
            
            # Mostra todos os domínios encontrados (para debug)
            if i < 3:  # Debug nas primeiras 3 buscas
                tipo = anuncio.get("tipo", "ads")
                print(f"      🔍 [{tipo}] {dominio}")
            
            valido, dominio = verificar_dominio_valido(anuncio["link"])
            if valido and dominio:
                anuncio["dominio"] = dominio
                todos_anuncios.append(anuncio)
                anuncios_validos_count += 1
                tipo = anuncio.get("tipo", "ads")
                print(f"      ✅ [{tipo}] {dominio} (PERMITIDO)")
        
        # Registra busca no SerpApi
        stats_manager.registrar_busca_serpapi(palavra, anuncios_validos_count)
        
        # Pequeno delay entre requisições
        time.sleep(0.3)
    
    # Remove duplicatas por domínio
    dominios_vistos = set()
    anuncios_unicos = []
    for anuncio in todos_anuncios:
        if anuncio["dominio"] not in dominios_vistos:
            dominios_vistos.add(anuncio["dominio"])
            anuncios_unicos.append(anuncio)
    
    print(f"\n📊 Resumo:")
    print(f"   Total de anúncios encontrados: {len(todos_anuncios)}")
    print(f"   Anúncios únicos (sem duplicatas): {len(anuncios_unicos)}")
    
    # Registra conclusão no stats
    stats_manager.add_log(f"✅ Busca concluída: {len(anuncios_unicos)} anúncios únicos encontrados")
    
    return anuncios_unicos


def obter_proximo_anuncio(total_anuncios: int) -> dict | None:
    """Obtém próximo anúncio da fila (thread-safe)."""
    with ANUNCIOS_QUEUE_LOCK:
        if ANUNCIOS_QUEUE:
            anuncio = ANUNCIOS_QUEUE.pop(0)
            # Atualiza estatísticas da fila
            stats_manager.atualizar_fila(total_anuncios, len(ANUNCIOS_QUEUE))
            return anuncio
    return None


async def verificar_proxy(page, worker_id: int) -> bool:
    """Verifica se o proxy está funcionando."""
    try:
        await page.goto('https://ipinfo.io/json', wait_until='networkidle')
        
        body = await page.locator('body').inner_text()
        data = json.loads(body)
        
        ip = data.get('ip', '')
        cidade = data.get('city', '')
        estado = data.get('region', '')
        pais = data.get('country', '')
        
        stats_manager.atualizar_ip(worker_id, ip, cidade, estado)
        print(f"  [Worker {worker_id}] IP: {ip} ({cidade}, {estado}, {pais})")
        
        return pais == 'BR'
    except Exception as e:
        print(f"  [Worker {worker_id}] Erro ao verificar proxy: {e}")
        return False


async def clicar_anuncio(page, worker_id: int, anuncio: dict) -> bool:
    """
    Clica em um anúncio usando o tracking_link para simular clique real.
    """
    # Usa tracking_link se disponível (clique real do Google Ads)
    link = anuncio.get("tracking_link", anuncio["link"])
    dominio = anuncio["dominio"]
    palavra = anuncio.get("palavra_chave", "")
    tipo = anuncio.get("tipo", "ads")
    
    try:
        stats_manager.atualizar_status(worker_id, f"clicando: {dominio[:20]}")
        stats_manager.atualizar_palavra(worker_id, f"[{tipo}] {palavra[:30]}")
        
        print(f"  [Worker {worker_id}] 🖱️ [{tipo}] Navegando para: {dominio}")
        
        # Navega para o link do anúncio (tracking_link)
        try:
            await page.goto(link, wait_until='domcontentloaded', timeout=30000)
        except Exception as e:
            # Timeout é comum, continuamos mesmo assim
            pass
        
        # Simula tempo de leitura na página (comportamento humano)
        tempo_leitura = random.uniform(8, 20)
        await asyncio.sleep(tempo_leitura)
        
        # Simula interações humanas
        try:
            # Scroll para baixo
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
            await asyncio.sleep(random.uniform(1, 2))
            
            # Scroll mais
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.6)")
            await asyncio.sleep(random.uniform(1, 2))
            
            # Move mouse aleatoriamente
            await page.mouse.move(
                random.randint(100, 800),
                random.randint(100, 600)
            )
        except:
            pass
        
        # Registra clique
        marcar_dominio_clicado(dominio)
        stats_manager.registrar_clique(worker_id, dominio, tempo_leitura)
        
        print(f"  [Worker {worker_id}] ✅ Clique registrado: {dominio} (tempo: {tempo_leitura:.1f}s)")
        
        return True
        
    except Exception as e:
        print(f"  [Worker {worker_id}] ❌ Erro ao clicar em {dominio}: {e}")
        stats_manager.registrar_erro(worker_id, str(e))
        return False


async def worker_async(worker_id: int, total_anuncios: int):
    """
    Worker assíncrono que processa anúncios da fila.
    """
    stats_manager.registrar_worker(worker_id)
    stats_manager.atualizar_status(worker_id, "iniciando")
    
    print(f"  [Worker {worker_id}] Iniciando browser...")
    
    # Cria diretório temporário que será excluído automaticamente ao sair
    with tempfile.TemporaryDirectory() as user_data_dir:
        print(f"  [Worker {worker_id}] 📁 Diretório temporário criado")
        
        async with async_playwright() as p:
            # Lança browser com proxy
            browser = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                proxy={
                    "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                    "username": PROXY_USER,
                    "password": PROXY_PASS
                },
                args=[
                    '--no-sandbox',
                    '--disable-blink-features=AutomationControlled',
                ],
                viewport={"width": 1366, "height": 768},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            
            print(f"  [Worker {worker_id}] ✅ Browser iniciado!")
            
            # Cria nova página
            page = await browser.new_page()
            
            # Desabilita timeout de navegação
            page.set_default_navigation_timeout(0)
            
            # Verifica proxy
            stats_manager.atualizar_status(worker_id, "verificando proxy")
            proxy_ok = await verificar_proxy(page, worker_id)
            print(f"  [Worker {worker_id}] Proxy BR: {proxy_ok}")
            
            # Processa anúncios da fila
            cliques = 0
            while True:
                anuncio = obter_proximo_anuncio(total_anuncios)
                
                if anuncio is None:
                    print(f"  [Worker {worker_id}] 📭 Fila vazia, finalizando...")
                    break
                
                sucesso = await clicar_anuncio(page, worker_id, anuncio)
                
                if sucesso:
                    cliques += 1
                
                # Delay entre cliques
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            
            stats_manager.atualizar_status(worker_id, f"finalizado ({cliques} cliques)")
            
            # Fecha browser
            await browser.close()
        
        print(f"  [Worker {worker_id}] 🗑️ Diretório temporário excluído!")
    
    print(f"  [Worker {worker_id}] ✅ Finalizado com {cliques} cliques!")


def worker_thread(worker_id: int, total_anuncios: int):
    """Thread wrapper para worker assíncrono."""
    asyncio.run(worker_async(worker_id, total_anuncios))


def main():
    global DOMINIOS_PERMITIDOS, ANUNCIOS_QUEUE
    
    print("=" * 65)
    print("🎯 Google Ads Clicker - SerpApi Google Ads API + Patchright")
    print("   Busca anúncios via API oficial + Cliques via browser")
    print("=" * 65)
    
    # Carrega configurações
    palavras = carregar_palavras_chave(PALAVRAS_ARQUIVO)
    if not palavras:
        print("❌ Nenhuma palavra-chave encontrada!")
        return
    
    DOMINIOS_PERMITIDOS = carregar_dominios_permitidos(DOMINIOS_PERMITIDOS_ARQUIVO)
    
    print(f"\n📋 Configurações:")
    print(f"   Palavras-chave: {len(palavras)}")
    print(f"   Domínios permitidos: {len(DOMINIOS_PERMITIDOS)}")
    print(f"   Workers paralelos: {NUM_WORKERS}")
    print(f"   Proxy: {PROXY_HOST}:{PROXY_PORT}")
    print(f"   SerpApi Key: {SERPAPI_KEY[:20]}...")
    
    # Inicia dashboard ANTES de coletar anúncios
    print("\n🌐 Iniciando dashboard...")
    iniciar_dashboard_thread()
    print("✅ Dashboard: http://localhost:5000")
    time.sleep(1)  # Aguarda dashboard iniciar
    
    # Coleta todos os anúncios via SerpApi
    anuncios = coletar_todos_anuncios(palavras)
    
    if not anuncios:
        print("❌ Nenhum anúncio encontrado!")
        return
    
    # Preenche a fila de anúncios
    ANUNCIOS_QUEUE = anuncios.copy()
    total_anuncios = len(anuncios)
    
    # Atualiza estatísticas iniciais da fila
    stats_manager.atualizar_fila(total_anuncios, total_anuncios)
    
    # Ajusta número de workers se tiver poucos anúncios
    num_workers_efetivo = min(NUM_WORKERS, len(anuncios))
    
    # Inicia workers
    print(f"\n🚀 Iniciando {num_workers_efetivo} workers para {len(anuncios)} anúncios...")
    threads = []
    
    for i in range(num_workers_efetivo):
        t = threading.Thread(
            target=worker_thread,
            args=(i + 1, total_anuncios),
            daemon=True
        )
        threads.append(t)
        t.start()
        time.sleep(1)  # Intervalo entre inicializações
    
    print("\n✅ Todos os workers iniciados!")
    print("📊 Acompanhe o progresso em: http://localhost:5000")
    print("\nPressione Ctrl+C para parar...\n")
    
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n⏹️ Parando...")
    
    print("\n" + "=" * 65)
    print("✅ Finalizado!")
    print("=" * 65)


if __name__ == "__main__":
    main()
