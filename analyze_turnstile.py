"""
Analise completa do Turnstile no site 7k.bet.br
Busca por parametros adicionais: action, data, cData, etc.
"""
import requests
import re
import json

# Configuracao da proxy
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
}

print("=" * 70)
print("ANALISE COMPLETA DO TURNSTILE - 7K.BET.BR")
print("=" * 70)

try:
    resp = requests.get("https://7k.bet.br", proxies=proxies, headers=headers, timeout=30)
    html = resp.text
    
    print(f"\nStatus: {resp.status_code}")
    print(f"Tamanho: {len(html)} bytes")
    
    # Buscar configuracao do captcha
    print("\n[1] CONFIGURACAO DO CAPTCHA NO NUXT CONFIG:")
    captcha_match = re.search(r'captcha:\s*\{([^}]+)\}', html)
    if captcha_match:
        captcha_config = captcha_match.group(1)
        print(f"    {captcha_config}")
        
        # Extrair valores
        sitekey = re.search(r'turnstileSiteKey["\s:]+["\'](0x[^"\']+)["\']', captcha_config)
        always_show = re.search(r'turnstileAlwaysShow["\s:]+(\w+)', captcha_config)
        
        if sitekey:
            print(f"\n    turnstileSiteKey: {sitekey.group(1)}")
        if always_show:
            print(f"    turnstileAlwaysShow: {always_show.group(1)}")
    
    # Buscar referencias a action no Turnstile
    print("\n[2] BUSCANDO 'action' DO TURNSTILE:")
    action_patterns = [
        r'data-action=["\']([^"\']+)["\']',
        r'action["\s:]+["\']([^"\']+)["\']',
        r'"action"\s*:\s*"([^"]+)"',
        r'turnstile[^}]*action["\s:]+["\']([^"\']+)["\']',
    ]
    
    found_actions = []
    for pattern in action_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            if m not in found_actions and "login" in m.lower() or "auth" in m.lower() or "captcha" in m.lower():
                found_actions.append(m)
                print(f"    Encontrado: {m}")
    
    if not found_actions:
        print("    Nenhum 'action' especifico encontrado")
    
    # Buscar data-cdata
    print("\n[3] BUSCANDO 'cData' DO TURNSTILE:")
    cdata_patterns = [
        r'data-cdata=["\']([^"\']+)["\']',
        r'cData["\s:]+["\']([^"\']+)["\']',
        r'"cData"\s*:\s*"([^"]+)"',
    ]
    
    for pattern in cdata_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        for m in matches:
            print(f"    Encontrado: {m}")
    
    # Buscar URLs relacionadas ao Turnstile/Cloudflare
    print("\n[4] SCRIPTS DO CLOUDFLARE/TURNSTILE:")
    turnstile_scripts = re.findall(r'(https?://[^\s"\'<>]*(?:turnstile|cloudflare|challenge)[^\s"\'<>]*)', html, re.IGNORECASE)
    for script in set(turnstile_scripts):
        print(f"    {script}")
    
    # Verificar se ha invisible turnstile
    print("\n[5] TIPO DE TURNSTILE:")
    if 'invisible' in html.lower():
        print("    Tipo: INVISIBLE (pode requerer parametros extras)")
    elif 'managed' in html.lower():
        print("    Tipo: MANAGED")
    else:
        print("    Tipo: NORMAL/VISIBLE")
    
    # Extrair todo o config do NUXT
    print("\n[6] CONFIGURACAO COMPLETA NUXT (captcha section):")
    nuxt_config = re.search(r'window\.__NUXT__\s*=\s*\{[^;]+\};', html)
    if nuxt_config:
        config_text = nuxt_config.group(0)
        # Extrair apenas a parte do captcha
        captcha_section = re.search(r'captcha:\{[^}]+\}', config_text)
        if captcha_section:
            print(f"    {captcha_section.group(0)}")
    
    # Verificar se ha algum parametro extra no HTML
    print("\n[7] PARAMETROS EXTRAS DO TURNSTILE:")
    extra_params = re.findall(r'data-([a-z]+)=["\']([^"\']+)["\']', html, re.IGNORECASE)
    turnstile_params = [p for p in extra_params if 'turnstile' in p[0].lower() or 'cf-' in p[0].lower()]
    for param in turnstile_params:
        print(f"    data-{param[0]}: {param[1]}")
    
    if not turnstile_params:
        print("    Nenhum parametro extra encontrado no HTML estatico")
        print("    (O Turnstile e renderizado via JavaScript)")

except Exception as e:
    print(f"ERRO: {e}")
    import traceback
    traceback.print_exc()











