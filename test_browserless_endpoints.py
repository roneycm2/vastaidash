"""
Script para testar diferentes endpoints WebSocket do Browserless
"""
import sys
import warnings
from playwright.sync_api import sync_playwright
import time

warnings.filterwarnings('ignore')

# Handler para suprimir erros
def suppress_error(exctype, value, traceback):
    if exctype == KeyError:
        return
    sys.__excepthook__(exctype, value, traceback)

sys.excepthook = suppress_error

BASE_IP = "172.219.157.164"
BASE_PORT = 18638

# Diferentes formatos de endpoint para testar
ENDPOINTS = [
    f"ws://{BASE_IP}:{BASE_PORT}",
    f"ws://{BASE_IP}:{BASE_PORT}/",
    f"ws://{BASE_IP}:{BASE_PORT}/chrome",
    f"ws://{BASE_IP}:{BASE_PORT}/browserless",
    f"ws://{BASE_IP}:{BASE_PORT}/playwright",
    f"ws://{BASE_IP}:{BASE_PORT}/cdp",
    f"ws://{BASE_IP}:{BASE_PORT}/v1/browser",
]

def quick_test(endpoint):
    """Teste rápido de conexão."""
    try:
        with sync_playwright() as p:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                try:
                    browser = p.chromium.connect(endpoint, timeout=8000)
                    # Se chegou aqui, conectou!
                    browser.close()
                    return True
                except:
                    return False
    except:
        return False

print("="*70)
print("🔬 TESTE DE ENDPOINTS WEBSOCKET BROWSERLESS")
print("="*70)
print()

working_endpoints = []

for endpoint in ENDPOINTS:
    print(f"Testando: {endpoint:50}", end=" ... ")
    sys.stdout.flush()
    
    if quick_test(endpoint):
        print("✅ FUNCIONOU!")
        working_endpoints.append(endpoint)
    else:
        print("❌")

print()
print("="*70)
print("📊 RESULTADO")
print("="*70)

if working_endpoints:
    print(f"\n✅ {len(working_endpoints)} endpoint(s) funcionaram:")
    for ep in working_endpoints:
        print(f"   → {ep}")
    print("\n💡 Use este endpoint no dashboard!")
else:
    print("\n❌ Nenhum endpoint WebSocket funcionou.")
    print("\n💡 Possíveis problemas:")
    print("   1. Browserless não está configurado para WebSocket nesta porta")
    print("   2. WebSocket está em outra porta")
    print("   3. Precisa de autenticação/token")
    print("   4. Browserless não está rodando (apenas servidor HTTP)")
    print("\n🔍 Próximos passos:")
    print("   - Verifique a documentação do Browserless na instância")
    print("   - Confirme se o Browserless está realmente rodando")
    print("   - Verifique se precisa de token de autenticação")

print("="*70)





