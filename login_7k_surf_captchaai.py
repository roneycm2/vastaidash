#!/usr/bin/env python3
"""
LOGIN 7k.bet.br - CURL_CFFI + CAPTCHAAI
"""

import os
import sys
import time
import re
from curl_cffi import requests

# Configuracoes
API_BASE = "https://ocr.captchaai.com"
API_KEY = os.getenv("CAPTCHAAI_API_KEY", "")
TARGET_URL = "https://7k.bet.br"
LOGIN_API = "https://7k.bet.br/api/auth/login"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def parse_proxy_string(proxy_str: str) -> tuple[str, str, str, str]:
    """Parse proxy string format: user:pass@host:port"""
    host, port, user, password = "", "", "", ""
    
    if "@" in proxy_str:
        parts = proxy_str.split("@")
        if len(parts) == 2:
            user_pass = parts[0].split(":", 1)
            host_port = parts[1].split(":")
            if len(user_pass) >= 2 and len(host_port) >= 2:
                user = user_pass[0]
                password = user_pass[1]
                host = host_port[0]
                port = host_port[1]
    
    return host, port, user, password


def extrair_sitekey(html: str) -> str | None:
    """Extrai sitekey do Turnstile do HTML"""
    patterns = [
        r'turnstileSiteKey["\s]*:["\s]*["\']?(0x[0-9a-zA-Z_-]+)["\']?',
        r'"turnstileSiteKey"\s*:\s*"(0x[0-9a-zA-Z_-]+)"',
        r'turnstileSiteKey\s*:\s*"(0x[0-9a-zA-Z_-]+)"',
        r'data-sitekey="(0x[0-9a-zA-Z_-]+)"',
        r'cf-turnstile[^>]*data-sitekey="(0x[0-9a-zA-Z_-]+)"',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, html)
        if match and match.group(1).startswith("0x"):
            return match.group(1)
    
    return None


def create_turnstile_task(sitekey: str, pageurl: str, action: str | None = None,
                          proxy: str | None = None, proxytype: str | None = None) -> str:
    """
    Sends a Turnstile task to in.php and returns the captcha ID.
    """
    payload = {
        "method": "turnstile",
        "key": API_KEY,
        "sitekey": sitekey,
        "pageurl": pageurl,
        "json": 1,
    }

    if action:
        payload["action"] = action
    if proxy:
        payload["proxy"] = proxy
    if proxytype:
        payload["proxytype"] = proxytype

    resp = requests.post(f"{API_BASE}/in.php", data=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != 1:
        raise RuntimeError(f"Failed to create captcha: {data}")

    return str(data["request"])


def get_turnstile_result(captcha_id: str, poll_interval: int = 5, timeout: int = 180) -> str:
    """
    Polls res.php until the Turnstile is solved.
    """
    start = time.time()
    params = {
        "key": API_KEY,
        "action": "get",
        "id": captcha_id,
        "json": 1,
    }

    while True:
        elapsed = int(time.time() - start)
        
        if elapsed > timeout:
            raise TimeoutError("Timed out waiting for Turnstile solution")

        resp = requests.get(f"{API_BASE}/res.php", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == 1:
            print(f"  [{elapsed}s] [+] RESOLVIDO!")
            return data["request"]

        if data.get("request") != "CAPCHA_NOT_READY":
            raise RuntimeError(f"Error from res.php: {data}")

        print(f"  [{elapsed}s] Aguardando... ({data})")
        time.sleep(poll_interval)


def fazer_login(proxy_url: str, email: str, senha: str, captcha_token: str) -> bool:
    """Faz login na API com o token do captcha"""
    payload = {
        "login": email,
        "password": senha,
        "captcha_token": captcha_token,
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://7k.bet.br",
        "Referer": "https://7k.bet.br/",
        "User-Agent": DEFAULT_USER_AGENT,
    }
    
    resp = requests.post(
        LOGIN_API, 
        json=payload, 
        headers=headers, 
        proxies={"http": proxy_url, "https": proxy_url},
        timeout=30,
        impersonate="chrome120"
    )
    
    print(f"  [+] Status HTTP: {resp.status_code}")
    print(f"  [+] Resposta: {resp.text}")
    
    if resp.status_code == 200:
        resp_json = resp.json()
        print(f"\n  [+++] LOGIN BEM SUCEDIDO! [+++]")
        if "token" in resp_json:
            print(f"  JWT Token: {resp_json['token'][:50]}...")
        return True
    else:
        print(f"\n  [X] Login falhou: {resp.text}")
        return False


def main():
    print("=" * 64)
    print("     LOGIN 7k.bet.br - CURL_CFFI + CAPTCHAAI")
    print("=" * 64)
    
    # Configuracoes
    if len(sys.argv) < 2:
        proxy_config = os.getenv("SEVENK_PROXY", "user:pass@host:port")
    else:
        proxy_config = sys.argv[1]
    
    email_login = os.getenv("SEVENK_EMAIL", "")
    senha_login = os.getenv("SEVENK_PASSWORD", "")
    if not API_KEY:
        print("\n[!] ERRO: defina CAPTCHAAI_API_KEY no ambiente.")
        print("    Ex: set CAPTCHAAI_API_KEY=SEU_TOKEN")
        return
    if not email_login or not senha_login:
        print("\n[!] ERRO: defina SEVENK_EMAIL e SEVENK_PASSWORD no ambiente.")
        print("    Ex: set SEVENK_EMAIL=seu@email.com")
        print("        set SEVENK_PASSWORD=sua_senha")
        return
    
    host, port, user, password = parse_proxy_string(proxy_config)
    proxy_url = f"http://{user}:{password}@{host}:{port}"
    
    print(f"\n[*] Proxy: {host}:{port} (user: {user})")
    print(f"[*] Email: {email_login}")
    print(f"[*] Site: {TARGET_URL}")
    
    # PASSO 1: ACESSAR SITE COM PROXY
    print("\n" + "-" * 64)
    print(" PASSO 1: ACESSANDO SITE COM PROXY (curl_cffi)")
    print("-" * 64)
    
    print(f"  [>] Fazendo GET em {TARGET_URL}...")
    resp = requests.get(
        TARGET_URL, 
        proxies={"http": proxy_url, "https": proxy_url},
        timeout=30,
        impersonate="chrome120"
    )
    print(f"  [+] Status: {resp.status_code} | Tamanho: {len(resp.text)} bytes")
    
    sitekey = extrair_sitekey(resp.text)
    if not sitekey:
        print("  [!] ERRO: Nao foi possivel extrair sitekey!")
        return
    
    print(f"  [+] SITEKEY: {sitekey}")
    
    # PASSO 2: ENVIAR PARA CAPTCHAAI
    print("\n" + "-" * 64)
    print(" PASSO 2: ENVIANDO TURNSTILE PARA CAPTCHAAI")
    print("-" * 64)
    
    use_proxy = os.environ.get("CAPTCHA_USE_PROXY") == "1"
    proxy_for_api = None
    proxytype = None
    
    if use_proxy:
        proxy_for_api = f"{user}:{password}@{host}:{port}"
        proxytype = "HTTP"
        print(f"  [>] Usando proxy: {proxy_for_api}")
    else:
        print(f"  [>] Sem proxy (CaptchaAI usara proprio IP)")
    
    print(f"  [>] Criando task...")
    captcha_id = create_turnstile_task(sitekey, TARGET_URL, proxy=proxy_for_api, proxytype=proxytype)
    print(f"  [+] TASK ID: {captcha_id}")
    
    # PASSO 3: AGUARDAR RESOLUCAO
    print("\n" + "-" * 64)
    print(" PASSO 3: AGUARDANDO CAPTCHAAI RESOLVER")
    print("-" * 64)
    
    print(f"  [>] Aguardando solucao...")
    captcha_token = get_turnstile_result(captcha_id)
    
    # PASSO 4: MOSTRAR TOKEN
    print("\n" + "-" * 64)
    print(" PASSO 4: TOKEN RESOLVIDO")
    print("-" * 64)
    print(f"  Token: {captcha_token[:60]}...")
    print(f"  Tamanho: {len(captcha_token)} chars")
    
    # PASSO 5: FAZER LOGIN
    print("\n" + "-" * 64)
    print(" PASSO 5: FAZENDO LOGIN")
    print("-" * 64)
    
    fazer_login(proxy_url, email_login, senha_login, captcha_token)
    
    print("\n" + "=" * 64)
    print("     PROCESSO FINALIZADO")
    print("=" * 64)


if __name__ == "__main__":
    main()
