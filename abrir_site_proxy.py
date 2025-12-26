"""
Script para abrir um site usando Selenium com proxy.
Uso: python abrir_site_proxy.py <site>
Exemplo: python abrir_site_proxy.py 7k.bet.br
"""

import sys
import time
import random
import threading
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException

#liderbet1-zone-adam-region-br:Aa10203040@pybpm-ins-hxqlzicm.pyproxy.io:2510

# Configurações do Proxy
PROXY_HOST = "pybpm-ins-hxqlzicm.pyproxy.io"
PROXY_PORT = "2510"
PROXY_USER = "liderbet1-zone-adam-region-br"
PROXY_PASS = "Aa10203040"

# Configuração do proxy para selenium-wire
SELENIUMWIRE_OPTIONS = {
    'proxy': {
        'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
        'https': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
        'no_proxy': 'localhost,127.0.0.1'
    }
}


def criar_browser():
    """
    Cria o browser Chrome com proxy configurado.
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
    print("🚀 Iniciando Chrome com Proxy...")
    print(f"🌐 Proxy: {PROXY_HOST}:{PROXY_PORT}")
    print(f"👤 Usuário: {PROXY_USER}")
    
    try:
        browser = webdriver.Chrome(
            options=options,
            seleniumwire_options=SELENIUMWIRE_OPTIONS
        )
        return browser
    except WebDriverException as e:
        print(f"❌ Erro ao iniciar o navegador: {e}")
        sys.exit(1)


def clicar_maior_18(browser, timeout=30):
    """
    Procura e clica no botão de confirmação de maior de 18 anos.
    """
    wait = WebDriverWait(browser, timeout)
    
    # Lista de possíveis textos para o botão de maior de 18
    textos_possiveis = [
        "sim tenho maior de 18 anos",
        "sim, tenho maior de 18 anos",
        "tenho maior de 18 anos",
        "sim, sou maior de 18",
        "sou maior de 18",
        "maior de 18",
        "confirmar",
        "aceitar",
        "entrar",
        "continuar"
    ]
    
    print("🔍 Procurando botão de confirmação de maior de 18 anos...")
    
    # XPath exato do botão fornecido pelo usuário (primeira tentativa)
    xpath_exato = "/html/body/div[14]/div[1]/div[2]/div[2]/button[2]"
    
    try:
        print(f"🎯 Tentando usar XPath exato: {xpath_exato}")
        elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_exato)))
        print(f"✅ Botão encontrado pelo XPath exato!")
        print(f"📝 Texto do botão: '{elemento.text}'")
        print("🖱️  Clicando no botão...")
        elemento.click()
        print("✅ Clique realizado com sucesso!")
        time.sleep(2)  # Aguarda um pouco após o clique
        return True
    except (TimeoutException, NoSuchElementException) as e:
        print(f"⚠️  XPath exato não funcionou, tentando outras estratégias...")
    except Exception as e:
        print(f"⚠️  Erro ao usar XPath exato: {e}")
    
    # Estratégias de busca alternativas (fallback)
    estrategias = [
        # Busca por XPath contendo o texto (case insensitive)
        lambda: browser.find_element(By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '18') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'maior')]"),
        
        # Busca por botões
        lambda: browser.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '18')]"),
        lambda: browser.find_element(By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'maior')]"),
        
        # Busca por links
        lambda: browser.find_element(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '18')]"),
        lambda: browser.find_element(By.XPATH, "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'maior')]"),
        
        # Busca por div clicável
        lambda: browser.find_element(By.XPATH, "//div[contains(@class, 'button') or contains(@class, 'btn')][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '18')]"),
    ]
    
    # Tenta encontrar e clicar no elemento
    for estrategia in estrategias:
        try:
            elemento = wait.until(EC.element_to_be_clickable(estrategia()))
            texto_elemento = elemento.text.lower() if elemento.text else ""
            
            # Verifica se o texto contém alguma palavra-chave relevante
            if any(palavra in texto_elemento for palavra in ["18", "maior", "confirmar", "aceitar", "entrar", "sim"]):
                print(f"✅ Botão encontrado: '{elemento.text}'")
                print("🖱️  Clicando no botão...")
                elemento.click()
                print("✅ Clique realizado com sucesso!")
                time.sleep(2)  # Aguarda um pouco após o clique
                return True
        except (TimeoutException, NoSuchElementException):
            continue
        except Exception as e:
            print(f"⚠️  Erro ao tentar estratégia: {e}")
            continue
    
    # Se não encontrou, tenta buscar por ID ou classe comum
    ids_comuns = ["age-confirm", "age-confirm-btn", "confirm-age", "enter-btn", "continue-btn"]
    classes_comuns = ["age-confirm", "confirm-button", "enter-button", "continue-button"]
    
    for id_elem in ids_comuns:
        try:
            elemento = wait.until(EC.element_to_be_clickable((By.ID, id_elem)))
            print(f"✅ Botão encontrado por ID: {id_elem}")
            elemento.click()
            print("✅ Clique realizado com sucesso!")
            time.sleep(2)
            return True
        except (TimeoutException, NoSuchElementException):
            continue
    
    for class_elem in classes_comuns:
        try:
            elemento = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, class_elem)))
            print(f"✅ Botão encontrado por classe: {class_elem}")
            elemento.click()
            print("✅ Clique realizado com sucesso!")
            time.sleep(2)
            return True
        except (TimeoutException, NoSuchElementException):
            continue
    
    print("⚠️  Não foi possível encontrar o botão de confirmação automaticamente.")
    return False


def gerar_cpf():
    """
    Gera um CPF brasileiro válido aleatório.
    """
    def calcular_digito(cpf_parcial, multiplicadores):
        soma = sum(int(cpf_parcial[i]) * multiplicadores[i] for i in range(len(cpf_parcial)))
        resto = soma % 11
        return '0' if resto < 2 else str(11 - resto)
    
    # Gera os 9 primeiros dígitos aleatórios
    cpf = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    
    # Calcula o primeiro dígito verificador
    multiplicadores_1 = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    cpf += calcular_digito(cpf, multiplicadores_1)
    
    # Calcula o segundo dígito verificador
    multiplicadores_2 = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
    cpf += calcular_digito(cpf, multiplicadores_2)
    
    return cpf


def verificar_cpf_existente(browser, wait_time=3):
    """
    Verifica se há mensagens de erro indicando que o CPF já existe.
    Retorna True se o CPF já existe, False caso contrário.
    """
    try:
        time.sleep(wait_time)  # Aguarda um pouco para o servidor responder
        
        # Textos que indicam que o CPF já existe
        textos_erro_cpf = [
            "já existe",
            "já cadastrado",
            "já está cadastrado",
            "cpf já existe",
            "cpf já cadastrado",
            "usuário já existe",
            "já está em uso",
            "cpf inválido",
            "cpf já utilizado"
        ]
        
        # Busca por mensagens de erro na página
        page_text = browser.find_element(By.TAG_NAME, "body").text.lower()
        
        # Verifica se há algum texto de erro relacionado a CPF
        for texto_erro in textos_erro_cpf:
            if texto_erro in page_text:
                # Tenta encontrar o elemento de erro específico
                try:
                    elementos_erro = browser.find_elements(
                        By.XPATH, 
                        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{texto_erro}')]"
                    )
                    if elementos_erro:
                        print(f"⚠️  Mensagem de erro encontrada: '{elementos_erro[0].text}'")
                        return True
                except:
                    pass
        
        # Verifica também por classes comuns de mensagens de erro
        try:
            erros = browser.find_elements(By.XPATH, 
                "//*[contains(@class, 'error') or contains(@class, 'alert') or contains(@class, 'warning') or contains(@class, 'danger')]")
            for erro in erros:
                texto_erro_elem = erro.text.lower()
                if any(texto in texto_erro_elem for texto in textos_erro_cpf):
                    print(f"⚠️  Erro encontrado: '{erro.text}'")
                    return True
        except:
            pass
        
        # Se não encontrou mensagens de erro, considera que o CPF está OK
        return False
        
    except Exception as e:
        print(f"⚠️  Erro ao verificar CPF: {e}")
        # Em caso de erro na verificação, assume que pode ter dado certo
        return False


def preencher_cpf(browser, timeout=30, max_tentativas=10):
    """
    Aguarda o formulário aparecer e preenche o campo CPF com um CPF aleatório válido.
    Tenta novamente se o CPF já existir.
    """
    wait = WebDriverWait(browser, timeout)
    
    # XPath do label fornecido - vamos tentar encontrar o input relacionado
    xpath_label = '/html/body/div[13]/div/div/div/div/div/div/div[2]/div[1]/section/div/div/div[1]/div[1]/div/div[1]/label'
    
    try:
        print("\n⏳ Aguardando formulário aparecer...")
        time.sleep(3)  # Aguarda um pouco para o formulário aparecer
        
        # Primeiro, tenta encontrar o input diretamente próximo ao label
        # Estratégia 1: Tenta encontrar input após o label
        input_cpf = None
        try:
            print("🔍 Procurando campo CPF...")
            # Tenta encontrar input que venha depois do label ou seja filho do mesmo container
            input_cpf = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//input[@type="text" and (contains(@name, "cpf") or contains(@id, "cpf") or contains(@placeholder, "CPF") or contains(@class, "cpf"))]')
            ))
            print("✅ Campo CPF encontrado por atributos!")
        except TimeoutException:
            # Estratégia 2: Tenta encontrar input no mesmo container do label
            try:
                input_cpf = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '/html/body/div[13]/div/div/div/div/div/div/div[2]/div[1]/section/div/div/div[1]/div[1]/div/div[1]//input')
                ))
                print("✅ Campo CPF encontrado próximo ao label!")
            except TimeoutException:
                # Estratégia 3: Busca qualquer input de texto no formulário
                try:
                    input_cpf = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, '//input[@type="text"]')
                    ))
                    print("✅ Campo de texto encontrado no formulário!")
                except TimeoutException:
                    raise TimeoutException("Nenhum campo de input foi encontrado")
        
        # Loop para tentar CPFs até encontrar um válido
        tentativa = 0
        while tentativa < max_tentativas:
            tentativa += 1
            print(f"\n🔄 Tentativa {tentativa}/{max_tentativas}")
            
            # Gera CPF aleatório
            cpf = gerar_cpf()
            print(f"📝 CPF gerado: {cpf}")
            
            # Limpa o campo e preenche com o CPF
            input_cpf.click()
            time.sleep(0.5)
            input_cpf.clear()
            time.sleep(0.3)
            
            # Digita o CPF caracter por caracter (mais natural)
            for char in cpf:
                input_cpf.send_keys(char)
                time.sleep(0.1)  # Pequeno delay entre caracteres
            
            print(f"✅ CPF inserido: {cpf}")
            
            # Simula perda de foco do campo para disparar validação (se necessário)
            try:
                input_cpf.send_keys(Keys.TAB)
            except:
                pass
            
            # Aguarda e verifica se o CPF já existe
            print("⏳ Aguardando validação do CPF...")
            cpf_existe = verificar_cpf_existente(browser, wait_time=3)
            
            if not cpf_existe:
                print(f"✅ CPF válido e não cadastrado: {cpf}")
                return True
            else:
                print(f"❌ CPF já cadastrado, tentando outro...")
                # Aguarda um pouco antes de tentar novamente
                time.sleep(1)
        
        print(f"⚠️  Limite de tentativas ({max_tentativas}) atingido. Não foi possível encontrar um CPF válido.")
        return False
        
    except TimeoutException:
        print("⚠️  Timeout: Formulário ou campo CPF não apareceu dentro do tempo limite.")
        return False
    except Exception as e:
        print(f"⚠️  Erro ao preencher CPF: {e}")
        return False


def injetar_js_validacao_cpf(browser):
    """
    Injeta o JavaScript na página para gerar e validar CPFs via API.
    """
    js_code = """
    function gerarCPF() {
      // gera os 9 primeiros dígitos
      let n = Array.from({ length: 9 }, () => Math.floor(Math.random() * 10));
      
      // evita CPFs com todos os dígitos iguais
      while (n.every(d => d === n[0])) {
        n = Array.from({ length: 9 }, () => Math.floor(Math.random() * 10));
      }
      
      const calcDV = (base) => {
        let soma = 0;
        for (let i = 0; i < base.length; i++) {
          soma += base[i] * ((base.length + 1) - i);
        }
        const resto = soma % 11;
        return resto < 2 ? 0 : 11 - resto;
      };
      
      const dv1 = calcDV(n);
      const dv2 = calcDV([...n, dv1]);
      
      return [...n, dv1, dv2].join("");
    }
    
    async function enviarPayload(number) {
      const response = await fetch("https://7k.bet.br/api/documents/validate", {
        method: "POST",
        credentials: "include",
        headers: {
          "accept": "application/json",
          "content-type": "application/json"
        },
        body: JSON.stringify({
          number,
          captcha_token: ""
        })
      });
      
      // Verifica se recebeu erro 429 (Too Many Requests)
      if (response.status === 429) {
        console.log("⚠️  Erro 429 detectado! Recarregando página...");
        // Remove o marcador de script ativo (Python vai detectar e reinjetar)
        localStorage.removeItem("cpf_script_ativo");
        // Recarrega a página
        window.location.reload();
        return null;
      }
      
      return response.json();
    }
    
    // Expõe as funções globalmente
    window.gerarCPF = gerarCPF;
    window.enviarPayload = enviarPayload;
    
    // Função para iniciar o loop de validação
    async function iniciarLoop() {
      // Limpa intervalos anteriores se existirem
      if (window.cpfIntervals) {
        window.cpfIntervals.forEach(interval => clearInterval(interval));
      }
      window.cpfIntervals = [];
      
      // Loop que envia requisições em lotes de 5
      while (true) {
        try {
          // Gera 5 CPFs
          const cpfs = [];
          for (let i = 0; i < 5; i++) {
            cpfs.push(gerarCPF());
          }
          
          console.log(`📦 Enviando lote de 5 CPFs: ${cpfs.join(", ")}`);
          
          // Envia todas as 5 requisições em paralelo
          const promessas = cpfs.map(cpf => enviarPayload(cpf));
          
          // Aguarda todas as respostas
          const resultados = await Promise.all(promessas);
          
          // Verifica se alguma requisição retornou null (429 - reload)
          const tem429 = resultados.some(res => res === null);
          
          if (tem429) {
            console.log("⚠️  Erro 429 detectado no lote! Recarregando página...");
            // Remove o marcador de script ativo
            localStorage.removeItem("cpf_script_ativo");
            // Recarrega a página
            window.location.reload();
            // Para o loop - Python vai reinjetar depois
            break;
          }
          
          // Se não teve 429, mostra os resultados
          resultados.forEach((res, index) => {
            if (res !== null) {
              console.log(cpfs[index], res);
            }
          });
          
        } catch (error) {
          // Se der erro, pode ser 429 também
          console.error("Erro ao processar lote:", error);
          // Tenta recarregar como precaução
          localStorage.removeItem("cpf_script_ativo");
          window.location.reload();
          break;
        }
      }
    }
    
    // Inicia o loop normalmente
    iniciarLoop();
    
    // Marca que o script foi injetado (para o Python verificar)
    localStorage.setItem("cpf_script_ativo", "true");
    """
    
    try:
        print("💉 Injetando JavaScript de validação de CPF na página...")
        browser.execute_script(js_code)
        print("✅ JavaScript injetado com sucesso!")
        print("🔄 Loop de validação de CPF iniciado em background...")
        return True
    except Exception as e:
        print(f"⚠️  Erro ao injetar JavaScript: {e}")
        return False


def clicar_botao_cadastrar(browser, timeout=30):
    """
    Aguarda e clica no botão "Cadastrar" após a confirmação de maior de 18 anos.
    """
    wait = WebDriverWait(browser, timeout)
    
    # XPath exato do botão Cadastrar fornecido pelo usuário
    xpath_cadastrar = '//*[@id="divPageLayout"]/div[1]/header/div[2]/div/button[1]/span'
    
    try:
        print("\n🔍 Aguardando botão 'Cadastrar' aparecer...")
        print(f"🎯 Tentando usar XPath: {xpath_cadastrar}")
        
        # Aguarda o elemento aparecer e ficar clicável
        elemento = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_cadastrar)))
        print(f"✅ Botão 'Cadastrar' encontrado!")
        print(f"📝 Texto do botão: '{elemento.text}'")
        print("🖱️  Clicando no botão 'Cadastrar'...")
        elemento.click()
        print("✅ Clique no botão 'Cadastrar' realizado com sucesso!")
        time.sleep(2)  # Aguarda um pouco após o clique
        return True
        
    except TimeoutException:
        print("⚠️  Timeout: Botão 'Cadastrar' não apareceu dentro do tempo limite.")
        # Tenta alternativas
        try:
            # Tenta buscar por texto "Cadastrar" ou "Cadastre-se"
            elemento = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cadastrar')]")
            ))
            print(f"✅ Botão 'Cadastrar' encontrado por texto alternativo!")
            elemento.click()
            print("✅ Clique realizado com sucesso!")
            time.sleep(2)
            return True
        except (TimeoutException, NoSuchElementException):
            print("⚠️  Não foi possível encontrar o botão 'Cadastrar'.")
            return False
    except Exception as e:
        print(f"⚠️  Erro ao clicar no botão 'Cadastrar': {e}")
        return False


def abrir_site(site: str):
    """
    Abre o site, injeta JS e monitora reloads para reinjetar.
    """
    # Adiciona https:// se não tiver protocolo
    if not site.startswith(('http://', 'https://')):
        url = f'https://{site}'
    else:
        url = site
    
    browser = None
    try:
        browser = criar_browser()
        print(f"\n🌍 Abrindo site: {url}")
        browser.get(url)
        
        # Aguarda a página carregar completamente (100%)
        print("⏳ Aguardando página carregar 100%...")
        WebDriverWait(browser, 30).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)  # Aguarda mais um pouco para garantir 100%
        print("✅ Página carregada 100%!")
        
        # Injeta o JavaScript na página
        injetar_js_validacao_cpf(browser)
        
        # Monitora reloads da página e reinjeta o JavaScript quando necessário
        def monitorar_e_reinjetar():
            """Monitora se a página recarregou e reinjeta o JavaScript imediatamente"""
            while True:
                try:
                    time.sleep(1)  # Verifica a cada 1 segundo (mais frequente)
                    
                    # Verifica se o script ainda está ativo
                    try:
                        script_ativo = browser.execute_script(
                            "return localStorage.getItem('cpf_script_ativo') === 'true'"
                        )
                        
                        # Se o script não está ativo, significa que a página recarregou
                        if not script_ativo:
                            print("🔄 Detectado reload da página. Aguardando 100%...")
                            
                            # Aguarda o readyState estar completo (100%)
                            try:
                                WebDriverWait(browser, 30).until(
                                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                                )
                                time.sleep(1)  # Aguarda mais um pouco
                                print("✅ Página carregada 100%! Reinjetando JavaScript...")
                                
                                # Reinjeta o JavaScript IMEDIATAMENTE
                                injetar_js_validacao_cpf(browser)
                                print("✅ JavaScript reinjetado com sucesso!")
                            except Exception as e:
                                print(f"⚠️  Erro ao aguardar carregamento: {e}")
                                # Tenta reinjetar mesmo assim após um tempo
                                time.sleep(3)
                                try:
                                    injetar_js_validacao_cpf(browser)
                                    print("✅ JavaScript reinjetado após retry!")
                                except:
                                    pass
                    except Exception as e:
                        # Se der erro ao verificar, pode ser que a página recarregou
                        # Tenta reinjetar como precaução
                        try:
                            print("⚠️  Erro ao verificar script. Aguardando página carregar 100%...")
                            time.sleep(2)
                            WebDriverWait(browser, 30).until(
                                lambda driver: driver.execute_script("return document.readyState") == "complete"
                            )
                            time.sleep(1)
                            print("✅ Página carregada 100%! Reinjetando JavaScript...")
                            injetar_js_validacao_cpf(browser)
                            print("✅ JavaScript reinjetado após erro de verificação!")
                        except:
                            pass
                            
                except Exception as e:
                    # Continua monitorando mesmo se houver erro
                    continue
        
        # Inicia thread de monitoramento em background
        monitor_thread = threading.Thread(target=monitorar_e_reinjetar, daemon=True)
        monitor_thread.start()
        print("👁️  Monitoramento ativado (reinjeta JS após reload)")
        
        print(f"\n📍 URL atual: {browser.current_url}")
        print("\n⏸️  Pressione Ctrl+C para fechar o navegador...")
        
        # Mantém o navegador aberto
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n👋 Fechando navegador...")
    except Exception as e:
        print(f"\n❌ Erro ao abrir o site: {e}")
    finally:
        if browser:
            browser.quit()
            print("✅ Navegador fechado.")


def main():
    """
    Função principal que recebe o site como parâmetro.
    """
    if len(sys.argv) < 2:
        print("❌ Uso: python abrir_site_proxy.py <site>")
        print("Exemplo: python abrir_site_proxy.py 7k.bet.br")
        sys.exit(1)
    
    site = sys.argv[1]
    abrir_site(site)


if __name__ == "__main__":
    main()

