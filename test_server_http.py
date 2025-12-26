"""
Script para testar se o servidor HTTP responde
"""
import requests
import socket

SERVER_IP = "172.219.157.164"
PORT = 18638

print("="*70)
print("🔍 TESTE DE CONECTIVIDADE DO SERVIDOR")
print("="*70)
print(f"📍 Servidor: {SERVER_IP}:{PORT}")
print("="*70)
print()

# Teste 1: Verificar se a porta está aberta
print("1️⃣ Testando se a porta está aberta...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((SERVER_IP, PORT))
    sock.close()
    
    if result == 0:
        print(f"   ✅ Porta {PORT} está ABERTA e acessível!")
    else:
        print(f"   ❌ Porta {PORT} está FECHADA ou bloqueada (código: {result})")
        print("   💡 A porta pode estar bloqueada por firewall ou o servidor não está rodando")
except Exception as e:
    print(f"   ❌ Erro ao testar porta: {e}")

print()

# Teste 2: Tentar conectar via HTTP
print("2️⃣ Testando conexão HTTP...")
http_urls = [
    f"http://{SERVER_IP}:{PORT}",
    f"http://{SERVER_IP}:{PORT}/",
    f"http://{SERVER_IP}:{PORT}/health",
    f"http://{SERVER_IP}:{PORT}/api",
]

for url in http_urls:
    try:
        print(f"   → Testando: {url}")
        response = requests.get(url, timeout=5)
        print(f"      ✅ Respondeu! Status: {response.status_code}")
        print(f"      📄 Headers: {dict(response.headers)}")
        if response.text:
            print(f"      📝 Conteúdo (primeiros 200 chars): {response.text[:200]}")
        break
    except requests.exceptions.Timeout:
        print(f"      ⏱️ Timeout (servidor não respondeu em 5s)")
    except requests.exceptions.ConnectionError:
        print(f"      ❌ Erro de conexão (servidor recusou ou não está acessível)")
    except Exception as e:
        print(f"      ⚠️ Erro: {str(e)[:100]}")

print()

# Teste 3: Verificar WebSocket endpoint
print("3️⃣ Informações sobre WebSocket...")
print(f"   📍 Endpoint WebSocket testado: ws://{SERVER_IP}:{PORT}")
print(f"   📍 Endpoint WebSocket alternativo: ws://{SERVER_IP}:{PORT}/chrome")
print()
print("   💡 Se o servidor Browserless estiver rodando, o endpoint WebSocket")
print("      deve estar disponível. O timeout pode indicar:")
print("      - Servidor não está rodando Browserless")
print("      - Firewall bloqueando conexões WebSocket")
print("      - Endpoint precisa de autenticação/token")
print("      - Porta está mapeada incorretamente")

print()
print("="*70)
print("✅ TESTE CONCLUÍDO")
print("="*70)





