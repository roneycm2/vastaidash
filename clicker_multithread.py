"""
Google Ads Clicker - Patchright + AntiCaptcha Plugin
Baseado no script funcional de resolução de captcha
"""

import asyncio
import os
import random
import time
import json
import tempfile
import threading
from urllib.parse import urlparse

from patchright.async_api import async_playwright

from stats import stats_manager
from dashboard import iniciar_dashboard_thread

# =====================================================
# CONFIGURAÇÕES
# =====================================================
ANTICAPTCHA_KEY = "f80abc2cefe60bfec5c97f16294a1452"

PROXY_HOST = "fb29d01db8530b99.shg.na.pyproxy.io"
PROXY_PORT = "16666"
PROXY_USER = "liderbet1-zone-resi-region-br-session-85deaca4d5ea-sessTime-1"
PROXY_PASS = "Aa10203040"

# Caminho do plugin AntiCaptcha
PLUGIN_PATH = r"C:\Users\outros\liderbet\plugin"

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


async def resolver_captcha(page, worker_id: int, timeout: int = 120) -> bool:
    """
    Aguarda o plugin AntiCaptcha resolver o captcha automaticamente.
    Usa o seletor '.antigate_solver.solved' conforme documentação.
    """
    try:
        print(f"  [Worker {worker_id}] 🔐 Aguardando plugin resolver captcha...")
        stats_manager.atualizar_status(worker_id, "aguardando captcha")
        
        # Aguarda o plugin resolver (classe .antigate_solver.solved aparece)
        await page.wait_for_selector('.antigate_solver.solved', timeout=timeout * 1000)
        
        print(f"  [Worker {worker_id}] ✅ Captcha resolvido!")
        stats_manager.registrar_captcha(worker_id, True)
        return True
        
    except Exception as e:
        # Verifica se já saiu da página de captcha
        current_url = page.url
        if '/sorry/' not in current_url.lower():
            return True
        
        print(f"  [Worker {worker_id}] ❌ Timeout captcha: {e}")
        stats_manager.registrar_captcha(worker_id, False)
        return False


async def buscar_e_clicar(page, worker_id: int, palavra_chave: str) -> int:
    """Busca palavra-chave no Google e clica em anúncios patrocinados."""
    cliques = 0
    
    try:
        stats_manager.atualizar_status(worker_id, f"buscando: {palavra_chave[:20]}")
        
        # Navega para Google
        try:
            await page.goto("https://www.google.com.br", wait_until='networkidle')
        except Exception as e:
            print(f"  [Worker {worker_id}] Erro ao carregar Google: {e}")
        
        await asyncio.sleep(random.uniform(1, 2))
        
        # Verifica se tem captcha
        if '/sorry/' in page.url.lower():
            if not await resolver_captcha(page, worker_id):
                return 0
            await page.goto("https://www.google.com.br", wait_until='networkidle')
        
        # Digita a busca
        search_box = page.locator('textarea[name="q"], input[name="q"]').first
        await search_box.fill(palavra_chave)
        await asyncio.sleep(random.uniform(0.3, 0.8))
        await page.keyboard.press('Enter')
        
        # Aguarda resultados
        await asyncio.sleep(random.uniform(2, 4))
        
        # Verifica captcha novamente
        if '/sorry/' in page.url.lower():
            if not await resolver_captcha(page, worker_id):
                return 0
        
        stats_manager.atualizar_status(worker_id, "procurando anúncios")
        
        # Procura links patrocinados
        # Seletores para anúncios do Google
        anuncios = await page.locator('div[data-text-ad] a, div[data-hveid] a[data-ved]').all()
        
        anuncios_validos = []
        for anuncio in anuncios:
            try:
                href = await anuncio.get_attribute('href')
                if href and 'google' not in href.lower() and href.startswith('http'):
                    valido, dominio = verificar_dominio_valido(href)
                    if valido and dominio:
                        anuncios_validos.append((anuncio, href, dominio))
            except:
                continue
        
        if not anuncios_validos:
            if DOMINIOS_PERMITIDOS:
                print(f"  [Worker {worker_id}] ⏭️ Nenhum domínio permitido em: {palavra_chave}")
            return 0
        
        # Clica nos anúncios válidos (máximo 2 por busca)
        for anuncio, href, dominio in anuncios_validos[:2]:
            try:
                stats_manager.atualizar_status(worker_id, f"clicando: {dominio[:20]}")
                
                # Abre em nova aba (Ctrl+Click)
                new_page = None
                async with page.context.expect_page() as new_page_info:
                    await anuncio.click(modifiers=['Control'])
                
                try:
                    new_page = await new_page_info.value
                    await asyncio.sleep(random.uniform(3, 6))
                except:
                    pass
                
                # Registra clique
                marcar_dominio_clicado(dominio)
                stats_manager.registrar_clique(worker_id, dominio)
                cliques += 1
                
                print(f"  [Worker {worker_id}] ✅ Clique: {dominio}")
                
                # Fecha nova aba
                if new_page:
                    try:
                        await new_page.close()
                    except:
                        pass
                
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
                
            except Exception as e:
                print(f"  [Worker {worker_id}] Erro ao clicar: {e}")
                continue
        
        return cliques
        
    except Exception as e:
        print(f"  [Worker {worker_id}] Erro na busca: {e}")
        return 0


async def worker_async(worker_id: int, palavras: list[str]):
    """
    Worker assíncrono usando patchright - baseado no captcha_solver.py
    """
    stats_manager.registrar_worker(worker_id)
    stats_manager.atualizar_status(worker_id, "iniciando")
    
    print(f"  [Worker {worker_id}] Iniciando browser...")
    
    # Cria diretório temporário que será excluído automaticamente ao sair
    with tempfile.TemporaryDirectory() as user_data_dir:
        print(f"  [Worker {worker_id}] 📁 Diretório temporário: {user_data_dir}")
        
        async with async_playwright() as p:
            # Lança browser persistente com extensão - EXATAMENTE como no captcha_solver.py
            browser = await p.chromium.launch_persistent_context(
                user_data_dir,
                headless=False,
                proxy={
                    "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                    "username": PROXY_USER,
                    "password": PROXY_PASS
                },
                args=[
                    f'--disable-extensions-except={PLUGIN_PATH}',
                    f'--load-extension={PLUGIN_PATH}',
                ],
            )
            
            print(f"  [Worker {worker_id}] ✅ Browser iniciado com plugin!")
            
            # Cria nova página - como no captcha_solver.py
            page = await browser.new_page()
            
            # Desabilita timeout de navegação - como no captcha_solver.py
            page.set_default_navigation_timeout(0)
            
            # Aguarda plugin carregar
            await asyncio.sleep(2)
            
            # Verifica proxy
            stats_manager.atualizar_status(worker_id, "verificando proxy")
            proxy_ok = await verificar_proxy(page, worker_id)
            print(f"  [Worker {worker_id}] Proxy BR: {proxy_ok}")
            
            # Processa palavras-chave
            for palavra in palavras:
                stats_manager.atualizar_palavra(worker_id, palavra)
                
                cliques = await buscar_e_clicar(page, worker_id, palavra)
                
                if cliques > 0:
                    print(f"  [Worker {worker_id}] {cliques} clique(s) em: {palavra}")
                
                await asyncio.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            
            stats_manager.atualizar_status(worker_id, "finalizado")
            
            # Fecha browser - como no captcha_solver.py
            await browser.close()
        
        print(f"  [Worker {worker_id}] 🗑️ Diretório temporário excluído!")
    
    print(f"  [Worker {worker_id}] ✅ Finalizado!")


def worker_thread(worker_id: int, palavras: list[str]):
    """Thread wrapper para worker assíncrono."""
    asyncio.run(worker_async(worker_id, palavras))


def main():
    global DOMINIOS_PERMITIDOS
    
    print("=" * 60)
    print("🎯 Google Ads Clicker - Patchright + AntiCaptcha")
    print("   Anti-detecção + Resolução automática de captcha")
    print("=" * 60)
    
    # Verifica plugin
    if not os.path.exists(PLUGIN_PATH):
        print(f"❌ Plugin não encontrado: {PLUGIN_PATH}")
        return
    
    print(f"✅ Plugin: {PLUGIN_PATH}")
    
    # Carrega configurações
    palavras = carregar_palavras_chave(PALAVRAS_ARQUIVO)
    if not palavras:
        print("❌ Nenhuma palavra-chave encontrada!")
        return
    
    DOMINIOS_PERMITIDOS = carregar_dominios_permitidos(DOMINIOS_PERMITIDOS_ARQUIVO)
    
    print(f"\n📋 {len(palavras)} palavras-chave")
    print(f"🎯 {len(DOMINIOS_PERMITIDOS)} domínios permitidos")
    print(f"👥 {NUM_WORKERS} workers paralelos")
    print(f"🌐 Proxy: {PROXY_HOST}:{PROXY_PORT}")
    
    # Inicia dashboard
    print("\n🌐 Iniciando dashboard...")
    iniciar_dashboard_thread()
    print("✅ Dashboard: http://localhost:5000")
    
    # Divide palavras entre workers
    palavras_por_worker = [[] for _ in range(NUM_WORKERS)]
    for i, palavra in enumerate(palavras):
        palavras_por_worker[i % NUM_WORKERS].append(palavra)
    
    # Inicia workers
    print(f"\n🚀 Iniciando {NUM_WORKERS} workers...")
    threads = []
    
    for i in range(NUM_WORKERS):
        t = threading.Thread(
            target=worker_thread,
            args=(i + 1, palavras_por_worker[i]),
            daemon=True
        )
        threads.append(t)
        t.start()
        time.sleep(2)  # Intervalo entre inicializações
    
    print("\n✅ Todos os workers iniciados!")
    print("📊 Acompanhe o progresso em: http://localhost:5000")
    print("\nPressione Ctrl+C para parar...\n")
    
    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        print("\n⏹️ Parando...")
    
    print("\n" + "=" * 60)
    print("✅ Finalizado!")
    print("=" * 60)


if __name__ == "__main__":
    main()
