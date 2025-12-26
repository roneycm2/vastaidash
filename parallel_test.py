#!/usr/bin/env python3
"""
Teste Paralelo - 10 requisições simultâneas
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

def fazer_requisicao(session, cpf):
    """Faz uma requisição e retorna o status"""
    try:
        r = session.post(
            "https://7k.bet.br/api/documents/validate",
            json={"number": cpf, "type": "cpf"},
            headers={"Content-Type": "application/json", "Origin": "https://7k.bet.br"},
            timeout=10
        )
        return r.status_code, cpf
    except Exception as e:
        return -1, cpf

def teste_paralelo(num_paralelo=10):
    """Faz N requisições em paralelo"""
    print(f"\n🚀 Enviando {num_paralelo} requisições em PARALELO...")
    
    session = requests.Session(impersonate="chrome120")
    
    # Gera CPFs
    cpfs = [gerar_cpf() for _ in range(num_paralelo)]
    
    inicio = time.time()
    
    # Executa em paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_paralelo) as executor:
        futures = [executor.submit(fazer_requisicao, session, cpf) for cpf in cpfs]
        resultados = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    tempo = time.time() - inicio
    
    # Conta resultados
    ok = sum(1 for s, _ in resultados if s in [200, 400])
    rate_limit = sum(1 for s, _ in resultados if s == 429)
    erros = sum(1 for s, _ in resultados if s == -1)
    validos = [(s, cpf) for s, cpf in resultados if s == 200]
    
    print(f"\n📊 Resultado ({tempo:.2f}s):")
    print(f"   ✅ OK: {ok}")
    print(f"   ⏳ Rate Limit: {rate_limit}")
    print(f"   💥 Erros: {erros}")
    
    if validos:
        print(f"\n   🎯 CPFs Válidos encontrados: {len(validos)}")
    
    return ok, rate_limit

def main():
    print("="*50)
    print("🔬 TESTE DE REQUISIÇÕES PARALELAS")
    print("="*50)
    
    # Testa com diferentes quantidades
    for num in [5, 10, 15, 20]:
        print(f"\n{'='*40}")
        print(f"📦 Teste com {num} requisições paralelas")
        
        ok, rate_limit = teste_paralelo(num)
        
        if rate_limit > 0:
            print(f"\n⚠️  Rate limit detectado com {num} paralelas")
        else:
            print(f"\n✅ {num} paralelas OK!")
        
        time.sleep(3)
    
    print("\n" + "="*50)
    print("✅ Teste concluído!")

if __name__ == "__main__":
    main()







