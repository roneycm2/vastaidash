"""
Teste da API CaptchaAI - Verificar saldo e testar Turnstile
Documentacao: https://captchaai.com/api-docs.php
"""
import os
import requests
import time
import json

CAPTCHAAI_KEY = os.getenv("CAPTCHAAI_API_KEY", "")
CAPTCHAAI_IN_URL = "https://ocr.captchaai.com/in.php"
CAPTCHAAI_RES_URL = "https://ocr.captchaai.com/res.php"

# Configuracoes do site
SITEKEY = "0x4AAAAAAAykd8yJm3kQzNJc"
PAGEURL = "https://7k.bet.br"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Proxy (opcional)
PROXY_CONFIG = os.getenv("SEVENK_PROXY", "user:pass@host:port")

print("=" * 70)
print("TESTE CAPTCHAAI - CLOUDFLARE TURNSTILE")
print("=" * 70)
if not CAPTCHAAI_KEY:
    print("ERRO: defina CAPTCHAAI_API_KEY no ambiente.")
    raise SystemExit(2)

# 1. Verificar saldo
print("\n[1] VERIFICANDO SALDO...")
try:
    balance_url = f"{CAPTCHAAI_RES_URL}?key={CAPTCHAAI_KEY}&action=getbalance"
    resp = requests.get(balance_url, timeout=10)
    print(f"    Resposta: {resp.text}")
except Exception as e:
    print(f"    ERRO: {e}")

# 2. Enviar Turnstile para resolver
print("\n[2] ENVIANDO TURNSTILE PARA RESOLVER...")

# Dados conforme documentacao
data = {
    "key": CAPTCHAAI_KEY,
    "method": "turnstile",
    "sitekey": SITEKEY,
    "pageurl": PAGEURL,
    "userAgent": USER_AGENT,
    "json": "1"
}

# Adicionar proxy se quiser testar com proxy
USE_PROXY = False  # Mudar para True para testar com proxy
if USE_PROXY:
    data["proxy"] = PROXY_CONFIG
    data["proxytype"] = "HTTP"
    print(f"    Proxy: {PROXY_CONFIG}")
else:
    print("    Proxy: NAO ENVIADA (CaptchaAI usara proprio IP)")

print(f"    Sitekey: {SITEKEY}")
print(f"    PageURL: {PAGEURL}")
print(f"    UserAgent: {USER_AGENT[:50]}...")

try:
    resp = requests.post(CAPTCHAAI_IN_URL, data=data, timeout=30)
    print(f"    Resposta: {resp.text}")
    
    result = resp.json() if resp.text.startswith("{") else {"request": resp.text}
    
    if result.get("status") == 1 or "OK" in resp.text:
        task_id = result.get("request") or resp.text.split("|")[-1]
        print(f"    Task ID: {task_id}")
        
        # 3. Aguardar resolucao
        print("\n[3] AGUARDANDO RESOLUCAO...")
        print("    Aguardando 20 segundos inicial...")
        time.sleep(20)
        
        for i in range(20):
            try:
                res_url = f"{CAPTCHAAI_RES_URL}?key={CAPTCHAAI_KEY}&action=get&id={task_id}&json=1"
                res_resp = requests.get(res_url, timeout=10)
                print(f"    [{20 + (i+1)*5}s] {res_resp.text}")
                
                res_data = res_resp.json() if res_resp.text.startswith("{") else {}
                
                if res_data.get("status") == 1:
                    token = res_data.get("request", "")
                    print("\n" + "=" * 70)
                    print("TOKEN RESOLVIDO!")
                    print("=" * 70)
                    print(f"Token: {token[:100]}..." if len(token) > 100 else f"Token: {token}")
                    print(f"Tamanho: {len(token)} caracteres")
                    break
                elif "CAPCHA_NOT_READY" not in res_resp.text:
                    print(f"    ERRO: {res_resp.text}")
                    break
                    
                time.sleep(5)
            except Exception as e:
                print(f"    ERRO: {e}")
                time.sleep(5)
    else:
        print(f"    ERRO na submissao: {result}")
        
except Exception as e:
    print(f"    ERRO: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("TESTE FINALIZADO")
print("=" * 70)

