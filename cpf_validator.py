#!/usr/bin/env python3
"""
Script para gerar CPFs válidos e testar validação na API da 7k.bet.br
"""
import requests
import random
import time
import json

def gerar_cpf():
    """Gera um CPF matematicamente válido"""
    # Gera os 9 primeiros dígitos
    cpf = [random.randint(0, 9) for _ in range(9)]
    
    # Calcula o primeiro dígito verificador
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    
    # Calcula o segundo dígito verificador
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    
    return ''.join(map(str, cpf))

def formatar_cpf(cpf):
    """Formata CPF no padrão XXX.XXX.XXX-XX"""
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"

def validar_cpf_api(cpf, session):
    """Faz requisição para validar CPF na API"""
    url = "https://7k.bet.br/api/documents/validate"
    
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://7k.bet.br",
        "Referer": "https://7k.bet.br/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Payload com o CPF (campo correto é "number")
    payload = {
        "number": cpf,
        "type": "cpf"
    }
    
    try:
        response = session.post(url, json=payload, headers=headers, timeout=10)
        return {
            "status_code": response.status_code,
            "response": response.text,
            "headers": dict(response.headers)
        }
    except Exception as e:
        return {
            "status_code": -1,
            "error": str(e)
        }

def main():
    print("=" * 60)
    print("🔍 Testador de CPF - 7k.bet.br")
    print("=" * 60)
    
    session = requests.Session()
    
    # Primeiro, faz uma requisição à página principal para pegar cookies
    print("\n📡 Obtendo cookies da página principal...")
    try:
        home_response = session.get("https://7k.bet.br/", timeout=10)
        print(f"   Status: {home_response.status_code}")
        print(f"   Cookies: {dict(session.cookies)}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    print("\n" + "=" * 60)
    print("🔄 Iniciando testes de CPF...")
    print("=" * 60)
    
    tentativas = 0
    captcha_detectado = False
    
    while not captcha_detectado and tentativas < 50:
        tentativas += 1
        cpf = gerar_cpf()
        cpf_formatado = formatar_cpf(cpf)
        
        print(f"\n[{tentativas}] Testando CPF: {cpf_formatado}")
        
        resultado = validar_cpf_api(cpf, session)
        
        status = resultado.get("status_code")
        response_text = resultado.get("response", "")
        
        print(f"    Status: {status}")
        
        if status == 200:
            print(f"    ✅ CPF VÁLIDO! Resposta: {response_text[:200]}")
        elif status == 400:
            print(f"    ❌ CPF inválido/não existe na Receita Federal")
        elif status == 403:
            print(f"    🚫 BLOQUEADO! Possível CAPTCHA/Turnstile")
            print(f"    Headers: {resultado.get('headers', {})}")
            captcha_detectado = True
        elif status == 429:
            print(f"    ⏳ RATE LIMIT! Muitas requisições")
            captcha_detectado = True
        else:
            print(f"    ⚠️ Resposta inesperada: {response_text[:200]}")
            
        # Verifica se há indicadores de CAPTCHA na resposta
        if "captcha" in response_text.lower() or "challenge" in response_text.lower():
            print(f"    🔐 CAPTCHA detectado na resposta!")
            captcha_detectado = True
            
        # Pequeno delay entre requisições
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print(f"📊 Resumo: {tentativas} tentativas realizadas")
    if captcha_detectado:
        print("🔐 CAPTCHA/Bloqueio detectado!")
    else:
        print("✅ Nenhum CAPTCHA visual detectado após todas as tentativas")
    print("=" * 60)

if __name__ == "__main__":
    main()

