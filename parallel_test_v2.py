#!/usr/bin/env python3
"""
Teste Paralelo v2 - 10 requisições simultâneas com sessões separadas
"""
import random
import time
import concurrent.futures
from curl_cffi import requests

def gerar_cpf():
    cpf = [random.randint(0, 9) for _ in range(9)]
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, cpf))

def fazer_requisicao(cpf, thread_id):
    """Cada thread cria sua própria sessão"""
    session = requests.Session(impersonate="chrome120")
    try:
        r = session.post(
            "https://7k.bet.br/api/documents/validate",
            json={"number": cpf, "type": "cpf"},
            headers={"Content-Type": "application/json", "Origin": "https://7k.bet.br"},
            timeout=10
        )
        return r.status_code, cpf, thread_id
    except Exception as e:
        return -1, cpf, thread_id

def teste_paralelo(num_paralelo=10):
    """Faz N requisições em paralelo"""
    print(f"\n🚀 Enviando {num_paralelo} requisições PARALELAS...")
    
    cpfs = [(gerar_cpf(), i) for i in range(num_paralelo)]
    
    inicio = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_paralelo) as executor:
        futures = [executor.submit(fazer_requisicao, cpf, tid) for cpf, tid in cpfs]
        resultados = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    tempo = time.time() - inicio
    
    # Mostra cada resultado
    print(f"\n   Resultados ({tempo:.2f}s):")
    for status, cpf, tid in sorted(resultados, key=lambda x: x[2]):
        if status == 200:
            print(f"   [{tid+1:2d}] ✅ 200 VÁLIDO - {cpf[:3]}.{cpf[3:6]}...")
        elif status == 400:
            print(f"   [{tid+1:2d}] ❌ 400")
        elif status == 429:
            print(f"   [{tid+1:2d}] ⏳ 429 RATE LIMIT")
        elif status == 403:
            print(f"   [{tid+1:2d}] 🚫 403 BLOCKED")
        else:
            print(f"   [{tid+1:2d}] ❓ {status}")
    
    ok = sum(1 for s, _, _ in resultados if s in [200, 400])
    rate_limit = sum(1 for s, _, _ in resultados if s == 429)
    blocked = sum(1 for s, _, _ in resultados if s == 403)
    validos = sum(1 for s, _, _ in resultados if s == 200)
    
    print(f"\n   📊 Resumo: {ok} ok | {validos} válidos | {rate_limit} rate limit | {blocked} blocked")
    
    return ok, rate_limit, blocked

def main():
    print("="*50)
    print("🔬 TESTE PARALELO v2 - Sessões Separadas")
    print("="*50)
    
    for num in [5, 10, 20, 30]:
        print(f"\n{'='*40}")
        ok, rate_limit, blocked = teste_paralelo(num)
        time.sleep(2)

if __name__ == "__main__":
    main()







