import requests
import re

# Configuração da proxy
proxy_str = "liderbet1-zone-adam-region-br:Aa10203040@pybpm-ins-hxqlzicm.pyproxy.io:2510"
parts = proxy_str.split("@")
user_pass = parts[0].split(":", 1)
host_port = parts[1].split(":")

proxy_url = f"http://{user_pass[0]}:{user_pass[1]}@{host_port[0]}:{host_port[1]}"

proxies = {
    "http": proxy_url,
    "https": proxy_url
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}

print("=" * 70)
print("INVESTIGANDO TURNSTILE NO 7K.BET.BR")
print("=" * 70)

print(f"\n[1] Acessando site via proxy...")
print(f"    Proxy: {host_port[0]}:{host_port[1]}")

try:
    resp = requests.get("https://7k.bet.br", proxies=proxies, headers=headers, timeout=30)
    print(f"    Status: {resp.status_code}")
    print(f"    Tamanho HTML: {len(resp.text)} bytes")
    
    html = resp.text
    
    # Salvar HTML completo
    with open("debug_7k_html.txt", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n    HTML salvo em: debug_7k_html.txt")
    
    print("\n" + "=" * 70)
    print("[2] BUSCANDO TURNSTILE NO HTML")
    print("=" * 70)
    
    # Procurar por cf-turnstile
    cf_turnstile = re.findall(r'cf-turnstile[^>]*', html, re.IGNORECASE)
    if cf_turnstile:
        print(f"\n✓ ENCONTRADO cf-turnstile:")
        for match in cf_turnstile:
            print(f"    {match}")
    else:
        print("\n✗ Nenhum cf-turnstile encontrado diretamente")
    
    # Procurar data-sitekey
    sitekeys = re.findall(r'data-sitekey=["\']([^"\']+)["\']', html)
    if sitekeys:
        print(f"\n✓ SITEKEYS ENCONTRADOS:")
        for sk in sitekeys:
            print(f"    {sk}")
    else:
        print("\n✗ Nenhum data-sitekey encontrado")
    
    # Procurar por qualquer menção a turnstile
    turnstile_mentions = re.findall(r'turnstile[^\s<>"\']*', html, re.IGNORECASE)
    if turnstile_mentions:
        print(f"\n✓ MENÇÕES A TURNSTILE:")
        for tm in set(turnstile_mentions):
            print(f"    {tm}")
    else:
        print("\n✗ Nenhuma menção a turnstile")
    
    # Procurar por Cloudflare
    cloudflare = re.findall(r'cloudflare[^\s<>"\']*', html, re.IGNORECASE)
    if cloudflare:
        print(f"\n✓ MENÇÕES A CLOUDFLARE:")
        for cf in set(cloudflare):
            print(f"    {cf}")
    
    # Procurar scripts externos
    scripts = re.findall(r'<script[^>]*src=["\']([^"\']+)["\']', html)
    print(f"\n[3] SCRIPTS EXTERNOS ({len(scripts)}):")
    for s in scripts:
        if "turnstile" in s.lower() or "cloudflare" in s.lower() or "challenge" in s.lower():
            print(f"    ★ {s}")
        else:
            print(f"      {s}")
    
    # Verificar se é uma página de challenge
    if "challenge" in html.lower() or "Just a moment" in html:
        print("\n⚠ PÁGINA DE CHALLENGE DETECTADA!")
        print("    O site pode estar mostrando um desafio Cloudflare antes de carregar")
    
    # Verificar se tem formulário de login
    login_form = re.findall(r'<form[^>]*login[^>]*|<input[^>]*password[^>]*', html, re.IGNORECASE)
    if login_form:
        print(f"\n✓ FORMULÁRIO DE LOGIN DETECTADO")
    else:
        print(f"\n✗ Nenhum formulário de login na página principal")
    
    # Mostrar primeiros 2000 caracteres
    print("\n" + "=" * 70)
    print("[4] PRIMEIROS 2000 CARACTERES DO HTML:")
    print("=" * 70)
    print(html[:2000])
    
    print("\n" + "=" * 70)
    print("[5] VERIFICANDO PÁGINA DE LOGIN ESPECÍFICA")
    print("=" * 70)
    
    # Tentar acessar /login ou /auth
    for login_path in ["/login", "/auth/login", "/?login=true"]:
        try:
            resp2 = requests.get(f"https://7k.bet.br{login_path}", proxies=proxies, headers=headers, timeout=15)
            print(f"\n    {login_path}: Status {resp2.status_code} ({len(resp2.text)} bytes)")
            
            # Procurar turnstile nessa página
            sk = re.findall(r'data-sitekey=["\']([^"\']+)["\']', resp2.text)
            if sk:
                print(f"        ★ SITEKEY: {sk}")
            
            cf = re.findall(r'cf-turnstile[^>]*', resp2.text)
            if cf:
                print(f"        ★ CF-TURNSTILE: {cf}")
                
        except Exception as e:
            print(f"\n    {login_path}: ERRO - {e}")
            
except Exception as e:
    print(f"\n✗ ERRO: {e}")
    import traceback
    traceback.print_exc()

