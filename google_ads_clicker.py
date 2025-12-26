"""
Script para buscar palavras-chave no Google e clicar em links patrocinados.
Usa Selenium-Wire com Anti-Captcha API para resolver captchas.
"""

import os
import re
import random
import time
import pathlib
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from anticaptchaofficial.recaptchav2enterpriseproxyless import recaptchaV2EnterpriseProxyless


# Configurações do Proxy (Brasil)
PROXY_HOST = "fb29d01db8530b99.shg.na.pyproxy.io"
PROXY_PORT = "16666"
PROXY_USER = "liderbet1-zone-resi-region-br"
PROXY_PASS = "Aa10203040"

# Configuração do proxy para selenium-wire
SELENIUMWIRE_OPTIONS = {
    'proxy': {
        'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
        'https': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
        'no_proxy': 'localhost,127.0.0.1'
    }
}

# Chave API do Anti-Captcha
ANTICAPTCHA_KEY = "a1bc79d96d6f26b1b232a400b3727113"

# Arquivo com palavras-chave
PALAVRAS_ARQUIVO = "palavras_chave.txt"

# Tempo de espera entre ações (segundos)
DELAY_MIN = 2
DELAY_MAX = 5

# Timeout para esperar captcha ser resolvido (segundos)
CAPTCHA_TIMEOUT = 180

# Arquivo com domínios permitidos
DOMINIOS_PERMITIDOS_ARQUIVO = "dominios_permitidos.txt"

# Set global para armazenar domínios já clicados (não repete)
DOMINIOS_CLICADOS = set()

# Lista de padrões de domínios permitidos (carregada do arquivo)
DOMINIOS_PERMITIDOS = []


def carregar_dominios_permitidos(arquivo: str) -> list[str]:
    """Carrega os domínios permitidos do arquivo."""
    dominios = []
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#"):
                    dominios.append(linha.lower())
        print(f"  ✅ {len(dominios)} padrões de domínio carregados: {dominios}")
    except FileNotFoundError:
        print(f"  ⚠️ Arquivo '{arquivo}' não encontrado. Permitindo todos os domínios.")
        return []
    return dominios


def extrair_dominio(url: str) -> str:
    """Extrai o domínio de uma URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except:
        return ""


def verificar_dominio_valido(href: str) -> tuple[bool, str]:
    """
    Verifica se o domínio é válido para clicar.
    Retorna (é_válido, domínio)
    
    Regras:
    - Deve conter um dos padrões do arquivo dominios_permitidos.txt
    - Não pode ter sido clicado antes
    """
    dominio = extrair_dominio(href)
    
    if not dominio:
        return False, ""
    
    # Se não há domínios permitidos configurados, permite todos
    if not DOMINIOS_PERMITIDOS:
        if dominio in DOMINIOS_CLICADOS:
            return False, dominio
        return True, dominio
    
    # Verifica se contém algum dos padrões permitidos
    dominio_permitido = False
    for padrao in DOMINIOS_PERMITIDOS:
        if padrao in dominio:
            dominio_permitido = True
            break
    
    if not dominio_permitido:
        return False, dominio
    
    # Verifica se já foi clicado
    if dominio in DOMINIOS_CLICADOS:
        return False, dominio
    
    return True, dominio


def carregar_palavras_chave(arquivo: str) -> list[str]:
    palavras = []
    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#"):
                    palavras.append(linha)
    except FileNotFoundError:
        print(f"❌ Arquivo '{arquivo}' não encontrado!")
        return []
    return palavras


def delay_aleatorio():
    tempo = random.uniform(DELAY_MIN, DELAY_MAX)
    time.sleep(tempo)


def criar_extensao_proxy(proxy_host: str, proxy_port: str, proxy_user: str, proxy_pass: str) -> str:
    """
    Cria uma extensão Chrome para autenticação de proxy.
    Chrome não suporta proxy autenticado nativamente, precisa desta extensão.
    Usa Manifest V2 com webRequestBlocking (ainda suportado para extensões locais).
    """
    current_dir = str(pathlib.Path(__file__).parent.resolve())
    proxy_plugin_dir = os.path.join(current_dir, 'proxy_extension')
    
    # Cria diretório da extensão
    if os.path.exists(proxy_plugin_dir):
        import shutil
        shutil.rmtree(proxy_plugin_dir)
    os.makedirs(proxy_plugin_dir)
    
    manifest_json = """{
    "version": "1.0.0",
    "manifest_version": 2,
    "name": "Proxy Auth Extension",
    "permissions": [
        "proxy",
        "tabs",
        "unlimitedStorage",
        "storage",
        "<all_urls>",
        "webRequest",
        "webRequestBlocking"
    ],
    "background": {
        "scripts": ["background.js"]
    },
    "minimum_chrome_version": "76.0.0"
}"""

    background_js = """
var config = {
    mode: "fixed_servers",
    rules: {
        singleProxy: {
            scheme: "http",
            host: "%s",
            port: %s
        },
        bypassList: ["localhost", "127.0.0.1"]
    }
};

chrome.proxy.settings.set({value: config, scope: "regular"}, function() {
    console.log("Proxy configurado: %s:%s");
});

chrome.webRequest.onAuthRequired.addListener(
    function(details) {
        console.log("Auth required for: " + details.url);
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    },
    {urls: ["<all_urls>"]},
    ["blocking"]
);

console.log("Proxy extension loaded!");
""" % (proxy_host, proxy_port, proxy_host, proxy_port, proxy_user, proxy_pass)

    # Escreve os arquivos
    with open(os.path.join(proxy_plugin_dir, 'manifest.json'), 'w') as f:
        f.write(manifest_json)
    
    with open(os.path.join(proxy_plugin_dir, 'background.js'), 'w') as f:
        f.write(background_js)
    
    print(f"  🌐 Extensão de proxy criada: {proxy_plugin_dir}")
    return proxy_plugin_dir


def criar_browser() -> webdriver.Chrome:
    """
    Cria o browser Chrome com proxy Brasil via selenium-wire.
    """
    options = Options()
    
    # Estratégia de carregamento
    options.page_load_strategy = 'eager'
    
    # Configurações do Chrome
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--window-size=1366,768')
    options.add_argument('--lang=pt-BR')
    options.add_argument('--ignore-certificate-errors')
    
    # Permite modo não-automação
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    
    # User Agent
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Cria o browser com selenium-wire (suporta proxy autenticado)
    print("  🚀 Iniciando Chrome com Proxy Brasil...")
    print(f"  🌐 Proxy: {PROXY_HOST}:{PROXY_PORT}")
    print(f"  👤 Usuário: {PROXY_USER}")
    
    browser = webdriver.Chrome(
        options=options,
        seleniumwire_options=SELENIUMWIRE_OPTIONS
    )
    
    return browser


def resolver_captcha_api(site_key: str, page_url: str, data_s: str = None) -> str | None:
    """
    Resolve o captcha via API do Anti-Captcha (reCAPTCHA Enterprise).
    """
    print("  🔐 Enviando captcha para Anti-Captcha API...")
    print(f"     Site Key: {site_key[:20]}...")
    print(f"     Data-S: {'Presente' if data_s else 'Ausente'}")
    
    solver = recaptchaV2EnterpriseProxyless()
    solver.set_verbose(0)
    solver.set_key(ANTICAPTCHA_KEY)
    solver.set_website_url(page_url)
    solver.set_website_key(site_key)
    
    # IMPORTANTE: O data-s é obrigatório para Google /sorry/
    if data_s:
        solver.set_enterprise_payload({"s": data_s})
    
    token = solver.solve_and_return_solution()
    
    if token and token != 0:
        print(f"  ✅ Captcha resolvido! Token: {len(token)} chars")
        return token
    else:
        print(f"  ❌ Erro ao resolver: {solver.error_code}")
        return None


def extrair_dados_captcha(browser) -> tuple[str | None, str | None]:
    """
    Extrai site_key e data-s da página de captcha do Google.
    """
    try:
        # Busca o div do recaptcha
        recaptcha_div = browser.find_elements(By.CSS_SELECTOR, '[data-sitekey]')
        if recaptcha_div:
            site_key = recaptcha_div[0].get_attribute('data-sitekey')
            data_s = recaptcha_div[0].get_attribute('data-s')
            if site_key:
                print(f"  🔑 Site key encontrada")
                if data_s:
                    print(f"  🔑 Data-S encontrado")
                return site_key, data_s
        
        # Fallback via HTML
        content = browser.page_source
        match = re.search(r'data-sitekey=["\']([^"\']+)["\']', content)
        site_key = match.group(1) if match else None
        
        match_s = re.search(r'data-s=["\']([^"\']+)["\']', content)
        data_s = match_s.group(1) if match_s else None
        
        return site_key, data_s
    except Exception as e:
        print(f"  ❌ Erro ao extrair dados: {e}")
        return None, None


def verificar_proxy(browser) -> bool:
    """
    Verifica se o proxy está funcionando acessando um site que mostra o IP.
    Retorna True se o IP for brasileiro.
    """
    print("\n🔍 Verificando proxy...")
    
    try:
        # Acessa site que mostra IP e localização
        browser.get('https://api.ipify.org?format=json')
        time.sleep(3)
        
        # Pega o IP
        try:
            page_text = browser.find_element(By.TAG_NAME, 'body').text
            print(f"  📡 Resposta: {page_text}")
        except:
            page_text = browser.page_source
        
        # Agora verifica a localização do IP
        browser.get('https://ipinfo.io/json')
        time.sleep(3)
        
        try:
            page_text = browser.find_element(By.TAG_NAME, 'body').text
            print(f"  🌍 Info do IP: {page_text}")
            
            # Verifica se é do Brasil
            if '"country": "BR"' in page_text or '"BR"' in page_text:
                print("  ✅ PROXY FUNCIONANDO! IP é do BRASIL 🇧🇷")
                return True
            else:
                print("  ⚠️ Proxy pode não estar funcionando - IP não é do Brasil")
                return False
                
        except Exception as e:
            print(f"  ⚠️ Não foi possível verificar localização: {e}")
            return False
            
    except Exception as e:
        print(f"  ❌ Erro ao verificar proxy: {e}")
        return False


def verificar_pagina_captcha(browser) -> bool:
    """Verifica se estamos na página de captcha do Google."""
    try:
        url = browser.current_url.lower()
        return '/sorry/' in url
    except:
        return False


def resolver_captcha_google(browser) -> bool:
    """
    Resolve o captcha do Google /sorry/ via API Anti-Captcha.
    """
    if not verificar_pagina_captcha(browser):
        return True
    
    print("  🚨 CAPTCHA DETECTADO!")
    print(f"  📍 URL: {browser.current_url}")
    
    # Salva debug
    try:
        browser.save_screenshot("captcha_antes.png")
        with open("captcha_antes.html", "w", encoding="utf-8") as f:
            f.write(browser.page_source)
    except:
        pass
    
    # Extrai dados do captcha
    page_url = browser.current_url
    site_key, data_s = extrair_dados_captcha(browser)
    
    if not site_key:
        print("  ❌ Site key não encontrada!")
        return False
    
    if not data_s:
        print("  ⚠️ Data-S não encontrado - pode falhar!")
    
    # Resolve via API
    print("  ⏳ Resolvendo captcha via API...")
    token = resolver_captcha_api(site_key, page_url, data_s)
    
    if not token:
        print("  ❌ Falha ao obter token")
        return False
    
    # Injeta o token e submete o formulário
    print("  🔄 Injetando token...")
    try:
        result = browser.execute_script(f'''
            const token = `{token}`;
            
            // Preenche o textarea
            const textarea = document.getElementById('g-recaptcha-response');
            if (textarea) {{
                textarea.value = token;
                textarea.innerHTML = token;
            }}
            
            // Preenche por name também
            const byName = document.querySelectorAll('[name="g-recaptcha-response"]');
            byName.forEach(el => {{
                el.value = token;
                if (el.tagName === 'TEXTAREA') el.innerHTML = token;
            }});
            
            // Chama o callback submitCallback
            if (typeof submitCallback === 'function') {{
                submitCallback(token);
                return 'callback_called';
            }}
            
            // Fallback: submit do form
            const form = document.getElementById('captcha-form');
            if (form) {{
                form.submit();
                return 'form_submitted';
            }}
            
            return 'no_action';
        ''')
        print(f"  ✅ Resultado: {result}")
    except Exception as e:
        print(f"  ❌ Erro ao injetar token: {e}")
        return False
    
    # Aguarda navegação
    time.sleep(5)
    
    if '/sorry/' not in browser.current_url:
        print("  ✅ CAPTCHA RESOLVIDO COM SUCESSO!")
        browser.save_screenshot("captcha_sucesso.png")
        return True
    
    print("  ❌ Ainda na página /sorry/")
    return False


def buscar_e_clicar_patrocinados(browser, palavra_chave: str) -> int:
    """
    Busca uma palavra-chave no Google e clica nos anúncios patrocinados.
    """
    cliques = 0
    max_tentativas = 3
    
    print(f"\n🔍 Buscando: '{palavra_chave}'")
    
    try:
        # Acessa o Google
        browser.get("https://www.google.com.br")
        time.sleep(3)
        
        # Aguarda página carregar
        try:
            WebDriverWait(browser, 30).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except:
            pass
        
        # Verifica e resolve captcha
        for t in range(max_tentativas):
            if resolver_captcha_google(browser):
                break
            print(f"  🔄 Tentativa {t+1}/{max_tentativas}...")
            time.sleep(3)
        
        if '/sorry/' in browser.current_url:
            print("  ❌ Não conseguiu resolver captcha")
            return 0
        
        delay_aleatorio()
        
        # Aceita cookies se aparecer
        try:
            accept_selectors = [
                "button#L2AGLb",
                "button[aria-label*='Aceitar']",
                "button:contains('Aceitar')"
            ]
            for sel in accept_selectors:
                try:
                    btn = browser.find_element(By.CSS_SELECTOR, sel)
                    btn.click()
                    time.sleep(1)
                    break
                except:
                    continue
        except:
            pass
        
        # Encontra o campo de busca
        search_box = None
        search_selectors = ['textarea[name="q"]', 'input[name="q"]']
        
        for sel in search_selectors:
            try:
                search_box = WebDriverWait(browser, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                )
                break
            except:
                continue
        
        if not search_box:
            print("  ❌ Campo de busca não encontrado")
            return 0
        
        # Digita a busca
        search_box.clear()
        search_box.send_keys(palavra_chave)
        delay_aleatorio()
        search_box.send_keys(Keys.RETURN)
        
        print("  ⏳ Aguardando resultados...")
        time.sleep(5)
        
        # Aguarda página carregar
        try:
            WebDriverWait(browser, 30).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
        except:
            pass
        
        # Verifica captcha pós-busca
        for t in range(max_tentativas):
            if resolver_captcha_google(browser):
                break
            time.sleep(3)
        
        delay_aleatorio()
        
        # Procura anúncios patrocinados
        seletores_anuncios = [
            '#tads a[data-ved]',
            '#tads .sVXRqc',
            '#tadsb a[data-ved]',
            'div[data-text-ad="1"] a',
            '.uEierd a[data-ved]',
            'a[data-rw]',
        ]
        
        links_clicados = set()
        janela_principal = browser.current_window_handle
        
        print(f"  🎯 Filtro: somente domínios permitidos: {DOMINIOS_PERMITIDOS}")
        print(f"  🚫 Domínios já clicados: {len(DOMINIOS_CLICADOS)}")
        
        for sel in seletores_anuncios:
            try:
                links = browser.find_elements(By.CSS_SELECTOR, sel)
                
                if links:
                    print(f"  📢 {len(links)} anúncios: {sel[:30]}")
                    
                    for link in links:  # Verifica todos os links
                        try:
                            href = link.get_attribute("href")
                            
                            if not href or not href.startswith("http"):
                                continue
                            
                            # Verifica se é um domínio válido (.bet.br e não repetido)
                            valido, dominio = verificar_dominio_valido(href)
                            
                            if not valido:
                                if dominio:
                                    if not any(p in dominio for p in DOMINIOS_PERMITIDOS):
                                        print(f"  ⏭️ Ignorando (não permitido): {dominio}")
                                    elif dominio in DOMINIOS_CLICADOS:
                                        print(f"  ⏭️ Ignorando (já clicado): {dominio}")
                                continue
                            
                            if href in links_clicados:
                                continue
                            
                            # Abre em nova aba
                            print(f"  🔗 Abrindo: {dominio}")
                            link.send_keys(Keys.CONTROL + Keys.RETURN)
                            time.sleep(2)
                            
                            # Muda para nova aba
                            for handle in browser.window_handles:
                                if handle != janela_principal:
                                    browser.switch_to.window(handle)
                                    
                                    # Aguarda carregar
                                    time.sleep(random.randint(3, 7))
                                    
                                    # Verifica captcha na nova página
                                    resolver_captcha_google(browser)
                                    
                                    # Marca como clicado (domínio e href)
                                    links_clicados.add(href)
                                    DOMINIOS_CLICADOS.add(dominio)
                                    cliques += 1
                                    print(f"  ✅ Clicou: {dominio}")
                                    
                                    # Fecha a aba
                                    browser.close()
                                    browser.switch_to.window(janela_principal)
                                    break
                            
                            delay_aleatorio()
                        except Exception as e:
                            # Volta para janela principal se der erro
                            try:
                                browser.switch_to.window(janela_principal)
                            except:
                                pass
                            continue
            except:
                continue
        
        # Busca por texto "Patrocinado" se não encontrou anúncios .bet.br
        if cliques == 0:
            try:
                # Procura elementos com texto "Patrocinado"
                patrocinados = browser.find_elements(By.XPATH, "//*[contains(text(), 'Patrocinado')]")
                
                if patrocinados:
                    print(f"  📢 {len(patrocinados)} elementos 'Patrocinado'")
                    
                    for el in patrocinados:
                        try:
                            # Encontra link pai
                            parent = el.find_element(By.XPATH, "./ancestor::div[.//a[@href]][1]")
                            link = parent.find_element(By.CSS_SELECTOR, "a[href^='http']")
                            href = link.get_attribute("href")
                            
                            if not href:
                                continue
                            
                            # Verifica se é um domínio válido (.bet.br e não repetido)
                            valido, dominio = verificar_dominio_valido(href)
                            
                            if not valido:
                                if dominio and not any(p in dominio for p in DOMINIOS_PERMITIDOS):
                                    print(f"  ⏭️ Ignorando (não permitido): {dominio}")
                                continue
                            
                            if href in links_clicados:
                                continue
                            
                            print(f"  🔗 Abrindo: {dominio}")
                            link.send_keys(Keys.CONTROL + Keys.RETURN)
                            time.sleep(2)
                            
                            for handle in browser.window_handles:
                                if handle != janela_principal:
                                    browser.switch_to.window(handle)
                                    time.sleep(random.randint(3, 7))
                                    resolver_captcha_google(browser)
                                    
                                    links_clicados.add(href)
                                    DOMINIOS_CLICADOS.add(dominio)
                                    cliques += 1
                                    print(f"  ✅ Clicou: {dominio}")
                                    
                                    browser.close()
                                    browser.switch_to.window(janela_principal)
                                    break
                            
                            delay_aleatorio()
                        except:
                            try:
                                browser.switch_to.window(janela_principal)
                            except:
                                pass
                            continue
            except:
                pass
        
        if cliques == 0:
            print(f"  ⚠️ Nenhum anúncio de domínios permitidos encontrado")
            print(f"  ➡️ Passando para próxima palavra-chave...")
        else:
            print(f"  📊 {cliques} cliques em domínios permitidos")
            
    except TimeoutException:
        print(f"  ❌ Timeout")
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    
    return cliques


def main():
    global DOMINIOS_PERMITIDOS
    
    print("=" * 60)
    print("🎯 Google Ads Clicker + Anti-Captcha API")
    print("=" * 60)
    
    palavras = carregar_palavras_chave(PALAVRAS_ARQUIVO)
    
    if not palavras:
        print("❌ Nenhuma palavra-chave encontrada.")
        return
    
    print(f"\n📋 {len(palavras)} palavras-chave")
    
    # Carrega domínios permitidos
    print("\n🎯 Carregando domínios permitidos...")
    DOMINIOS_PERMITIDOS = carregar_dominios_permitidos(DOMINIOS_PERMITIDOS_ARQUIVO)
    
    total_cliques = 0
    browser = None
    
    try:
        # Cria o browser com Proxy via selenium-wire
        print("\n🚀 Iniciando navegador...")
        browser = criar_browser()
        
        # Verifica se o proxy está funcionando
        proxy_ok = verificar_proxy(browser)
        if not proxy_ok:
            print("\n⚠️ ATENÇÃO: Proxy pode não estar funcionando!")
            print("   Deseja continuar mesmo assim? (aguardando 5s para cancelar...)")
            time.sleep(5)
        
        # Embaralha palavras
        random.shuffle(palavras)
        
        for i, palavra in enumerate(palavras, 1):
            print(f"\n{'─' * 50}")
            print(f"📌 [{i}/{len(palavras)}] {palavra}")
            
            cliques = buscar_e_clicar_patrocinados(browser, palavra)
            total_cliques += cliques
            
            if i < len(palavras):
                # Se não encontrou cliques, espera menos antes da próxima busca
                if cliques == 0:
                    espera = random.randint(2, 5)
                    print(f"⏳ Próxima busca em {espera}s...")
                else:
                    espera = random.randint(5, 15)
                    print(f"⏳ Aguardando {espera}s...")
                time.sleep(espera)
        
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        if browser:
            print("\n🔒 Fechando navegador...")
            browser.quit()
    
    print("\n" + "=" * 60)
    print(f"✅ Finalizado! {total_cliques} cliques")
    print("=" * 60)


if __name__ == "__main__":
    main()
