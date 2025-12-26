#!/usr/bin/env python3
"""
Teste de Delay Rápido - 10 requisições por teste
"""
import random
import time
from curl_cffi import requests

def gerar_cpf():
    cpf = [random.randint(0, 9) for _ in range(9)]
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    return ''.join(map(str, cpf))

def testar_delay(delay: float):
    """Testa 10 requisições com delay específico"""
    print(f"\n🧪 Delay: {delay:.1f}s | ", end="", flush=True)
    
    session = requests.Session(impersonate="chrome120")
    
    sucessos = 0
    rate_limits = 0
    
    for i in range(10):
        cpf = gerar_cpf()
        
        try:
            r = session.post(
                "https://7k.bet.br/api/documents/validate",
                json={"number": cpf, "type": "cpf"},
                headers={"Content-Type": "application/json", "Origin": "https://7k.bet.br"},
                timeout=8
            )
            
            if r.status_code in [200, 400]:
                print("✓", end="", flush=True)
                sucessos += 1
            elif r.status_code == 429:
                print("⏳", end="", flush=True)
                rate_limits += 1
            else:
                print("?", end="", flush=True)
                
        except:
            print("x", end="", flush=True)
        
        if delay > 0:
            time.sleep(delay)
    
    status = "✅ OK" if rate_limits == 0 else f"❌ {rate_limits} bloq"
    print(f" | {sucessos}/10 ok | {status}")
    
    return rate_limits == 0

def main():
    print("="*50)
    print("🔬 TESTE DE DELAY MÍNIMO")
    print("="*50)
    
    # Testa delays de 0 a 1 segundo
    delays = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    for delay in delays:
        passou = testar_delay(delay)
        
        if passou:
            print(f"\n🎯 DELAY MÍNIMO: {delay}s")
            break
        
        time.sleep(3)  # Pausa entre testes

if __name__ == "__main__":
    main()







