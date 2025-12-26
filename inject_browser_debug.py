#!/usr/bin/env python3
"""
Debug - Verifica o que está acontecendo com as requisições
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
    print("🔍 DEBUG - Investigando requisições")
    print("="*60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        # Captura mensagens do console
        page.on("console", lambda msg: print(f"   [Console] {msg.type}: {msg.text[:100]}"))
        
        print("\n🌐 Acessando site...")
        page.goto("https://7k.bet.br/")
        page.wait_for_timeout(5000)
        
        print("\n📡 Testando 1 requisição manual...")
        
        cpf = gerar_cpf()
        print(f"   CPF: {cpf}")
        
        # Faz uma requisição de teste
        resultado = page.evaluate("""async (cpf) => {
            try {
                console.log('Iniciando fetch para CPF:', cpf);
                
                const response = await fetch('/api/documents/validate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                    },
                    body: JSON.stringify({number: cpf, type: 'cpf'})
                });
                
                console.log('Status:', response.status);
                
                const text = await response.text();
                console.log('Response (primeiros 200 chars):', text.substring(0, 200));
                
                return {
                    status: response.status,
                    statusText: response.statusText,
                    body: text.substring(0, 500)
                };
            } catch (e) {
                console.log('Erro:', e.message);
                return {error: e.message};
            }
        }""", cpf)
        
        print(f"\n📊 Resultado:")
        print(f"   Status: {resultado.get('status', 'N/A')}")
        print(f"   StatusText: {resultado.get('statusText', 'N/A')}")
        print(f"   Body: {resultado.get('body', resultado.get('error', 'N/A'))[:300]}")
        
        print("\n⏳ Aguardando 10s para você ver...")
        time.sleep(10)
        browser.close()

if __name__ == "__main__":
    main()







