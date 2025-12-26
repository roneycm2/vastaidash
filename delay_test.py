#!/usr/bin/env python3
"""
Teste de Delay Mínimo - Descobre o limite de rate limit
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

def testar_delay(delay: float, num_requests: int = 15):
    """Testa um delay específico e conta quantas requisições passam"""
    print(f"\n{'='*50}")
    print(f"🧪 Testando delay: {delay:.2f}s")
    print(f"{'='*50}")
    
    session = requests.Session(impersonate="chrome120")
    
    # Aquece a sessão
    try:
        session.get("https://7k.bet.br/", timeout=10)
    except:
        pass
    
    sucessos = 0
    rate_limits = 0
    
    for i in range(1, num_requests + 1):
        cpf = gerar_cpf()
        
        try:
            response = session.post(
                "https://7k.bet.br/api/documents/validate",
                json={"number": cpf, "type": "cpf"},
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://7k.bet.br",
                    "Referer": "https://7k.bet.br/",
                },
                timeout=10
            )
            
            status = response.status_code
            
            if status in [200, 400]:
                print(f"  [{i:2d}] ✅ {status}", end="")
                sucessos += 1
            elif status == 429:
                print(f"  [{i:2d}] ⏳ 429 RATE LIMIT", end="")
                rate_limits += 1
            else:
                print(f"  [{i:2d}] ❓ {status}", end="")
            
            print(f" (delay: {delay:.2f}s)")
            
        except Exception as e:
            print(f"  [{i:2d}] 💥 Erro: {str(e)[:30]}")
        
        if rate_limits >= 2:
            print(f"\n  🛑 2 rate limits - parando teste")
            break
        
        time.sleep(delay)
    
    return sucessos, rate_limits

def main():
    print("="*60)
    print("🔬 TESTE DE DELAY MÍNIMO - Rate Limit Discovery")
    print("="*60)
    
    # Delays para testar (do mais rápido ao mais lento)
    delays_para_testar = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    resultados = []
    
    for delay in delays_para_testar:
        sucessos, rate_limits = testar_delay(delay, num_requests=12)
        resultados.append({
            "delay": delay,
            "sucessos": sucessos,
            "rate_limits": rate_limits
        })
        
        # Se conseguiu passar sem rate limit, encontrou o mínimo
        if rate_limits == 0:
            print(f"\n✅ Delay {delay}s passou sem rate limit!")
            break
        
        # Pausa entre testes
        print(f"\n⏳ Aguardando 5s antes do próximo teste...")
        time.sleep(5)
    
    # Resumo
    print("\n" + "="*60)
    print("📊 RESUMO DOS TESTES")
    print("="*60)
    print(f"{'Delay':<10} {'Sucessos':<12} {'Rate Limits':<12} {'Status'}")
    print("-"*50)
    
    delay_minimo = None
    for r in resultados:
        status = "✅ OK" if r["rate_limits"] == 0 else "❌ Bloqueado"
        print(f"{r['delay']:.2f}s     {r['sucessos']:<12} {r['rate_limits']:<12} {status}")
        
        if r["rate_limits"] == 0 and delay_minimo is None:
            delay_minimo = r["delay"]
    
    print("-"*50)
    if delay_minimo:
        print(f"\n🎯 DELAY MÍNIMO RECOMENDADO: {delay_minimo}s")
    else:
        print(f"\n⚠️  Nenhum delay testado passou sem rate limit")
        print(f"   Tente delays maiores ou use rotação de sessão")
    
    print("="*60)

if __name__ == "__main__":
    main()







