"""
Dashboard de Abas - Abre 1 janela Chrome com múltiplas guias
============================================================
Simples: abre um navegador e cria várias abas na mesma janela.

Uso:
    python dashboard_abas.py [num_abas] [url]
    
Exemplos:
    python dashboard_abas.py           # 5 abas em 7k.bet.br
    python dashboard_abas.py 10        # 10 abas em 7k.bet.br
    python dashboard_abas.py 3 https://google.com  # 3 abas no Google
"""

from patchright.sync_api import sync_playwright
import sys
import time

# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Proxy rotacional
PROXY = {
    "server": "http://fb29d01db8530b99.shg.na.pyproxy.io:16666",
    "username": "liderbet1-zone-mob-region-br",
    "password": "Aa10203040"
}

# URL padrão
DEFAULT_URL = "https://7k.bet.br/"

# Número padrão de abas
DEFAULT_TABS = 5


def obter_ip(page):
    """Obtém o IP público"""
    try:
        page.goto("https://api.ipify.org?format=text", timeout=10000)
        ip = page.inner_text("body").strip()
        return ip
    except:
        return "Erro"


def abrir_navegador_com_abas(num_abas: int, url: str, usar_proxy: bool = True):
    """
    Abre 1 janela do Chrome com múltiplas guias.
    
    Args:
        num_abas: Quantas abas abrir
        url: URL para navegar em cada aba
        usar_proxy: Se deve usar o proxy rotacional
    """
    print("=" * 60)
    print(f"🌐 Abrindo 1 janela com {num_abas} guias")
    print(f"📎 URL: {url}")
    print(f"🔒 Proxy: {'Sim' if usar_proxy else 'Não'}")
    print("=" * 60)
    print()
    
    with sync_playwright() as p:
        # Lança o navegador (1 janela)
        print("[1/3] Iniciando Chrome...")
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--start-maximized'
            ]
        )
        
        # Cria contexto (com ou sem proxy)
        context_opts = {
            "viewport": None,  # Usa tamanho da janela
            "no_viewport": True
        }
        if usar_proxy:
            context_opts["proxy"] = PROXY
        
        context = browser.new_context(**context_opts)
        print("[2/3] Navegador iniciado!")
        
        # Cria a primeira aba e verifica IP
        abas = []
        primeira_aba = context.new_page()
        abas.append(primeira_aba)
        
        if usar_proxy:
            print("[2/3] Verificando IP do proxy...")
            ip = obter_ip(primeira_aba)
            print(f"      ✓ IP: {ip}")
        
        # Navega primeira aba para URL
        print(f"\n[3/3] Abrindo {num_abas} guias...")
        try:
            primeira_aba.goto(url, timeout=30000)
            print(f"      ✓ Guia 1: {url[:50]}...")
        except Exception as e:
            print(f"      ✗ Guia 1: Erro - {e}")
        
        # Cria as demais guias
        for i in range(2, num_abas + 1):
            nova_aba = context.new_page()
            abas.append(nova_aba)
            
            try:
                nova_aba.goto(url, timeout=30000)
                print(f"      ✓ Guia {i}: {url[:50]}...")
            except Exception as e:
                print(f"      ✗ Guia {i}: Erro - {e}")
            
            time.sleep(0.5)  # Pequeno delay entre abas
        
        print()
        print("=" * 60)
        print(f"✅ {num_abas} guias abertas com sucesso!")
        print()
        print("Pressione ENTER para fechar o navegador...")
        print("=" * 60)
        
        # Mantém aberto até o usuário pressionar Enter
        input()
        
        # Fecha tudo
        print("\nFechando navegador...")
        context.close()
        browser.close()
        print("Pronto!")


if __name__ == '__main__':
    # Argumentos da linha de comando
    num_abas = DEFAULT_TABS
    url = DEFAULT_URL
    
    if len(sys.argv) >= 2:
        try:
            num_abas = int(sys.argv[1])
        except:
            print(f"Número de abas inválido: {sys.argv[1]}")
            sys.exit(1)
    
    if len(sys.argv) >= 3:
        url = sys.argv[2]
    
    # Limita entre 1 e 20 abas
    num_abas = max(1, min(20, num_abas))
    
    abrir_navegador_com_abas(num_abas, url, usar_proxy=True)
