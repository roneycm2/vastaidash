"""
Script de teste simplificado para conexão Browserless
Versão com melhor tratamento de erros
"""
import sys
import warnings
from playwright.sync_api import sync_playwright
import time

# Suprimir todos os warnings
warnings.filterwarnings('ignore')

# Handler para suprimir erros do Playwright
def suppress_playwright_error(exctype, value, traceback):
    if exctype == KeyError and 'error' in str(value):
        # Apenas ignorar, não imprimir
        return
    sys.__excepthook__(exctype, value, traceback)

# Configurar handler
sys.excepthook = suppress_playwright_error

# Endpoints para testar
ENDPOINTS = [
    "ws://172.219.157.164:18638",
    "ws://172.219.157.164:18638/chrome",
]

def test_endpoint(endpoint):
    """Testa um endpoint específico."""
    print(f"\n{'='*70}")
    print(f"🧪 TESTANDO: {endpoint}")
    print(f"{'='*70}\n")
    
    browser = None
    
    try:
        with sync_playwright() as p:
            print("1. Conectando...")
            
            # Tentar Chromium com timeout curto
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    browser = p.chromium.connect(endpoint, timeout=10000)
                    print("   ✅ Conectado com Chromium!")
            except Exception as e:
                error_str = str(e)
                if "timeout" in error_str.lower():
                    print(f"   ⏱️ Timeout ao conectar (servidor pode estar lento)")
                elif "KeyError" in error_str or "KeyError" in type(e).__name__:
                    print(f"   ⚠️ Erro interno do Playwright (mas pode funcionar)")
                else:
                    print(f"   ❌ Erro: {error_str[:100]}")
                
                # Tentar Firefox
                try:
                    print("   → Tentando Firefox...")
                    browser = p.firefox.connect(endpoint, timeout=10000)
                    print("   ✅ Conectado com Firefox!")
                except Exception as e2:
                    print(f"   ❌ Firefox também falhou: {str(e2)[:100]}")
                    return False
            
            if not browser:
                return False
            
            print("\n2. Criando contexto...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    context = browser.new_context(ignore_https_errors=True)
                    print("   ✅ Contexto criado!")
            except Exception as e:
                print(f"   ❌ Erro ao criar contexto: {str(e)[:100]}")
                return False
            
            print("\n3. Criando página...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    page = context.new_page()
                    print("   ✅ Página criada!")
            except Exception as e:
                print(f"   ❌ Erro ao criar página: {str(e)[:100]}")
                return False
            
            print("\n4. Navegando para URL de teste...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        response = page.goto("https://api.ipify.org?format=json", 
                                            timeout=15000, 
                                            wait_until="domcontentloaded")
                        print(f"   ✅ Navegação OK! Status: {response.status if response else 'N/A'}")
                    except KeyError:
                        print("   ⚠️ KeyError durante navegação (erro interno, mas continuando...)")
            except Exception as e:
                error_str = str(e)
                if "KeyError" not in error_str and "KeyError" not in type(e).__name__:
                    print(f"   ❌ Erro na navegação: {error_str[:100]}")
                    return False
                else:
                    print("   ⚠️ Erro interno do Playwright (continuando...)")
            
            print("\n5. Obtendo conteúdo...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        content = page.content()
                        print(f"   ✅ Conteúdo obtido! ({len(content)} bytes)")
                        
                        # Tentar extrair IP
                        import re
                        ip_match = re.search(r'"ip":\s*"([^"]+)"', content)
                        if ip_match:
                            print(f"   🌐 IP extraído: {ip_match.group(1)}")
                        
                        return True
                    except KeyError:
                        print("   ⚠️ KeyError ao obter conteúdo (erro interno)")
                        return False
            except Exception as e:
                print(f"   ❌ Erro ao obter conteúdo: {str(e)[:100]}")
                return False
                
    except Exception as e:
        error_str = str(e)
        if "KeyError" not in error_str and "KeyError" not in type(e).__name__:
            print(f"\n❌ Erro geral: {error_str[:100]}")
        return False
    finally:
        try:
            if browser:
                browser.close()
        except:
            pass

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🔬 TESTE DE CONEXÃO BROWSERLESS - VERSÃO SIMPLIFICADA")
    print("="*70)
    
    success_count = 0
    
    for endpoint in ENDPOINTS:
        if test_endpoint(endpoint):
            success_count += 1
            print(f"\n✅✅✅ ENDPOINT FUNCIONOU: {endpoint} ✅✅✅")
            break
    
    print("\n" + "="*70)
    print("📊 RESULTADO FINAL")
    print("="*70)
    
    if success_count > 0:
        print("✅ SUCESSO! Pelo menos um endpoint funcionou!")
    else:
        print("❌ Nenhum endpoint funcionou.")
        print("\n💡 Possíveis causas:")
        print("   1. Servidor Browserless não está rodando")
        print("   2. Porta não está acessível ou bloqueada por firewall")
        print("   3. Endpoint precisa de autenticação")
        print("   4. Formato do endpoint está incorreto")
        print("\n🔍 Verificações:")
        print("   - Teste se o servidor responde: curl http://172.219.157.164:18638")
        print("   - Verifique se a porta está aberta")
        print("   - Confirme se o Browserless está configurado corretamente")
    
    print("="*70 + "\n")





