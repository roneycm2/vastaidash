"""
Script de teste para conexão Browserless
Testa conexão WebSocket e executa operações básicas
"""
import sys
import warnings
from playwright.sync_api import sync_playwright
import time

# Suprimir warnings
warnings.filterwarnings('ignore')

# Endpoint para testar - testar diferentes formatos
WS_ENDPOINTS = [
    "ws://172.219.157.164:18638",
    "ws://172.219.157.164:18638/chrome",
    "ws://172.219.157.164:18638/browserless",
]

def test_connection(ws_endpoint):
    """Testa conexão com o Browserless."""
    print("=" * 60)
    print("🧪 TESTE DE CONEXÃO BROWSERLESS")
    print("=" * 60)
    print(f"📍 Endpoint: {ws_endpoint}")
    print("=" * 60)
    print()
    
    browser = None
    context = None
    page = None
    
    try:
        with sync_playwright() as p:
            print("1️⃣ Tentando conectar ao WebSocket...")
            try:
                # Tentar Chromium primeiro
                try:
                    print("   → Tentando Chromium...")
                    browser = p.chromium.connect(ws_endpoint, timeout=15000)
                    print("   ✅ Conectado com Chromium!")
                except Exception as chrom_err:
                    print(f"   ❌ Chromium falhou: {chrom_err}")
                    print("   → Tentando Firefox...")
                    browser = p.firefox.connect(ws_endpoint, timeout=15000)
                    print("   ✅ Conectado com Firefox!")
            except KeyError as key_err:
                print(f"   ❌ KeyError do Playwright: {key_err}")
                print("   ⚠️ Erro interno do Playwright - endpoint pode estar incorreto")
                return False
            except Exception as conn_err:
                print(f"   ❌ Erro de conexão: {conn_err}")
                return False
            
            print()
            print("2️⃣ Criando contexto do navegador...")
            try:
                context = browser.new_context(ignore_https_errors=True)
                print("   ✅ Contexto criado!")
            except Exception as ctx_err:
                print(f"   ❌ Erro ao criar contexto: {ctx_err}")
                return False
            
            print()
            print("3️⃣ Criando nova página...")
            try:
                page = context.new_page()
                print("   ✅ Página criada!")
            except Exception as page_err:
                print(f"   ❌ Erro ao criar página: {page_err}")
                return False
            
            print()
            print("4️⃣ Navegando para https://api.ipify.org?format=json...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    response = page.goto("https://api.ipify.org?format=json", timeout=20000, wait_until="domcontentloaded")
                    print(f"   ✅ Navegação concluída! Status: {response.status if response else 'N/A'}")
            except KeyError:
                print("   ⚠️ KeyError durante navegação (erro interno do Playwright)")
                print("   → Continuando mesmo assim...")
            except Exception as nav_err:
                print(f"   ❌ Erro na navegação: {nav_err}")
                return False
            
            print()
            print("5️⃣ Obtendo conteúdo da página...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    content = page.content()
                    print(f"   ✅ Conteúdo obtido! Tamanho: {len(content)} bytes")
                    
                    # Tentar extrair IP
                    import re
                    ip_match = re.search(r'"ip":\s*"([^"]+)"', content)
                    if ip_match:
                        ip = ip_match.group(1)
                        print(f"   🌐 IP detectado: {ip}")
                    else:
                        print("   ⚠️ Não foi possível extrair IP do conteúdo")
                        print(f"   📄 Primeiros 200 chars: {content[:200]}")
            except KeyError:
                print("   ⚠️ KeyError ao obter conteúdo (erro interno do Playwright)")
            except Exception as content_err:
                print(f"   ❌ Erro ao obter conteúdo: {content_err}")
                return False
            
            print()
            print("6️⃣ Testando navegação para outra URL...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    page.goto("https://www.google.com", timeout=20000, wait_until="domcontentloaded")
                    title = page.title()
                    print(f"   ✅ Navegação concluída! Título: {title}")
            except KeyError:
                print("   ⚠️ KeyError durante segunda navegação (erro interno do Playwright)")
            except Exception as nav2_err:
                print(f"   ❌ Erro na segunda navegação: {nav2_err}")
            
            print()
            print("=" * 60)
            print("✅ TESTE CONCLUÍDO COM SUCESSO!")
            print("=" * 60)
            return True
            
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ ERRO GERAL")
        print("=" * 60)
        print(f"Erro: {e}")
        print(f"Tipo: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print()
        print("🧹 Limpando recursos...")
        try:
            if page:
                try:
                    page.close()
                    print("   ✅ Página fechada")
                except:
                    pass
        except:
            pass
        
        try:
            if context:
                try:
                    context.close()
                    print("   ✅ Contexto fechado")
                except:
                    pass
        except:
            pass
        
        try:
            if browser:
                try:
                    browser.close()
                    print("   ✅ Browser fechado")
                except:
                    pass
        except:
            pass
        
        print("   ✅ Limpeza concluída!")


def test_with_chrome_path(ws_endpoint):
    """Testa usando connect_over_cdp (método alternativo)."""
    print()
    print("=" * 60)
    print("🧪 TESTE ALTERNATIVO - connect_over_cdp")
    print("=" * 60)
    print(f"📍 Endpoint: {ws_endpoint}")
    print("=" * 60)
    print()
    
    # Converter ws:// para http:// para CDP
    if ws_endpoint.startswith("ws://"):
        cdp_url = ws_endpoint.replace("ws://", "http://")
        # Remover /chrome se existir
        cdp_url = cdp_url.replace("/chrome", "")
        cdp_url = cdp_url.replace("/browserless", "")
    else:
        cdp_url = ws_endpoint
    
    print(f"🔄 Tentando CDP URL: {cdp_url}")
    
    browser = None
    context = None
    page = None
    
    try:
        with sync_playwright() as p:
            print("1️⃣ Tentando conectar via CDP...")
            try:
                browser = p.chromium.connect_over_cdp(cdp_url, timeout=15000)
                print("   ✅ Conectado via CDP!")
            except Exception as conn_err:
                print(f"   ❌ Erro de conexão CDP: {conn_err}")
                return False
            
            print()
            print("2️⃣ Criando contexto...")
            try:
                context = browser.new_context(ignore_https_errors=True)
                print("   ✅ Contexto criado!")
            except Exception as ctx_err:
                print(f"   ❌ Erro ao criar contexto: {ctx_err}")
                return False
            
            print()
            print("3️⃣ Criando página e testando navegação...")
            try:
                page = context.new_page()
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    page.goto("https://api.ipify.org?format=json", timeout=20000)
                    content = page.content()
                    print(f"   ✅ Teste concluído! Conteúdo: {len(content)} bytes")
                    return True
            except Exception as test_err:
                print(f"   ❌ Erro no teste: {test_err}")
                return False
                
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        return False
    finally:
        try:
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
        except:
            pass


if __name__ == "__main__":
    print("\n")
    
    results = []
    
    # Testar cada formato de endpoint
    for endpoint in WS_ENDPOINTS:
        print(f"\n{'='*60}")
        print(f"🔍 TESTANDO: {endpoint}")
        print(f"{'='*60}\n")
        
        # Teste 1: Conexão direta WebSocket
        success1 = test_connection(endpoint)
        
        # Teste 2: Método alternativo CDP
        success2 = test_with_chrome_path(endpoint)
        
        results.append({
            "endpoint": endpoint,
            "websocket": success1,
            "cdp": success2,
            "success": success1 or success2
        })
        
        if success1 or success2:
            print(f"\n✅ Endpoint {endpoint} FUNCIONOU!")
            break
    
    print()
    print("=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    for result in results:
        status = "✅ PASSOU" if result["success"] else "❌ FALHOU"
        print(f"\nEndpoint: {result['endpoint']}")
        print(f"  WebSocket: {'✅' if result['websocket'] else '❌'}")
        print(f"  CDP: {'✅' if result['cdp'] else '❌'}")
        print(f"  Status geral: {status}")
    
    print("=" * 60)
    print()
    
    working_endpoints = [r for r in results if r["success"]]
    
    if working_endpoints:
        print("✅ Endpoint(s) que funcionaram:")
        for result in working_endpoints:
            print(f"   → {result['endpoint']}")
    else:
        print("❌ Nenhum endpoint funcionou. Verifique:")
        print("   1. O servidor Browserless está rodando?")
        print("   2. A porta está acessível e aberta?")
        print("   3. O formato do endpoint está correto?")
        print("   4. O servidor aceita conexões WebSocket?")
        print("\n💡 Dica: Tente verificar se o Browserless está rodando com:")
        print("   - docker ps (se estiver usando Docker)")
        print("   - netstat -an | findstr 18638 (Windows)")
        print("   - curl http://172.219.157.164:18638 (testar HTTP)")

