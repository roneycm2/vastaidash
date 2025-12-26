#!/usr/bin/env python3
"""
Script para adicionar IP à whitelist de proxy rotativa
Uso: python PYSW41pquLUjQkAQZXwXTrtC.py <IP_ADDRESS>
"""

import sys
import requests
import argparse
import re

# Chaves de autenticação
API_KEY = "PYSW41pquLUjQkAQZXwXTrtC"
SECRET_KEY = "wlwramfVCecNFfqVcXqXl20tmxkH1eGs"

# URL base da API (ajustar conforme necessário)
BASE_API_URL = "https://api.pyproxy.io"  # Ajuste conforme a documentação do seu provedor


def validar_ip(ip: str) -> bool:
    """Valida se o endereço IP tem formato válido"""
    pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if not re.match(pattern, ip):
        return False
    
    partes = ip.split('.')
    for parte in partes:
        num = int(parte)
        if num < 0 or num > 255:
            return False
    return True


def adicionar_ip_whitelist(ip: str) -> dict:
    """
    Adiciona um IP à whitelist da proxy rotativa
    
    Args:
        ip: Endereço IP a ser adicionado
        
    Returns:
        dict: Resposta da API com status e mensagem
    """
    if not validar_ip(ip):
        return {
            "success": False,
            "error": f"IP inválido: {ip}. Use o formato XXX.XXX.XXX.XXX"
        }
    
    # Tentar diferentes endpoints comuns para whitelist
    endpoints = [
        f"{BASE_API_URL}/api/v1/whitelist/add",
        f"{BASE_API_URL}/whitelist/add",
        f"{BASE_API_URL}/api/whitelist",
    ]
    
    # Dados para enviar
    payload = {
        "ip": ip,
        "ip_address": ip
    }
    
    # Headers com autenticação (tentar diferentes formatos)
    headers_list = [
        # Formato 1: API Key + Secret Key
        {
            "X-API-Key": API_KEY,
            "X-Secret-Key": SECRET_KEY,
            "Content-Type": "application/json"
        },
        # Formato 2: Bearer Token
        {
            "Authorization": f"Bearer {API_KEY}",
            "X-Secret-Key": SECRET_KEY,
            "Content-Type": "application/json"
        },
        # Formato 3: Basic Auth
        {
            "Authorization": f"Basic {API_KEY}:{SECRET_KEY}",
            "Content-Type": "application/json"
        },
        # Formato 4: Query params + headers
        {
            "X-API-Key": API_KEY,
            "X-API-Secret": SECRET_KEY,
            "Content-Type": "application/json"
        }
    ]
    
    # Tentar cada combinação de endpoint e header
    for endpoint in endpoints:
        for headers in headers_list:
            try:
                print(f"[*] Tentando: {endpoint}")
                print(f"[*] Headers: {list(headers.keys())}")
                
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                
                print(f"[*] Status Code: {response.status_code}")
                
                if response.status_code == 200 or response.status_code == 201:
                    try:
                        result = response.json()
                        return {
                            "success": True,
                            "message": f"IP {ip} adicionado à whitelist com sucesso!",
                            "data": result
                        }
                    except:
                        return {
                            "success": True,
                            "message": f"IP {ip} adicionado à whitelist com sucesso!",
                            "data": response.text
                        }
                
                # Se recebeu resposta 401/403, as credenciais podem estar erradas
                if response.status_code in [401, 403]:
                    print(f"[!] Erro de autenticação (401/403). Tentando próximo formato...")
                    continue
                
                # Se recebeu 404, endpoint não existe
                if response.status_code == 404:
                    print(f"[!] Endpoint não encontrado (404). Tentando próximo...")
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"[!] Timeout ao conectar em {endpoint}")
                continue
            except requests.exceptions.ConnectionError as e:
                print(f"[!] Erro de conexão: {e}")
                continue
            except Exception as e:
                print(f"[!] Erro: {e}")
                continue
    
    # Se nenhum endpoint funcionou, tentar método alternativo usando GET com query params
    print("\n[*] Tentando método alternativo (GET com query params)...")
    try:
        alt_endpoint = f"{BASE_API_URL}/whitelist"
        params = {
            "action": "add",
            "ip": ip,
            "api_key": API_KEY,
            "secret_key": SECRET_KEY
        }
        
        response = requests.get(alt_endpoint, params=params, timeout=30)
        if response.status_code == 200:
            try:
                result = response.json()
                return {
                    "success": True,
                    "message": f"IP {ip} adicionado à whitelist com sucesso!",
                    "data": result
                }
            except:
                return {
                    "success": True,
                    "message": f"IP {ip} adicionado à whitelist com sucesso!",
                    "data": response.text
                }
    except Exception as e:
        pass
    
    return {
        "success": False,
        "error": "Não foi possível adicionar o IP. Verifique:\n"
                 "1. As chaves de API estão corretas\n"
                 "2. O endpoint da API está correto (use --api-url para especificar)\n"
                 "3. Você tem permissão para adicionar IPs à whitelist\n"
                 "4. A documentação da API para o formato correto\n\n"
                 "NOTA: Se você souber o endpoint correto da API, edite a variável BASE_API_URL no script."
    }


def obter_ip_publico() -> str:
    """
    Obtém o IP público do terminal atual
    
    Returns:
        str: Endereço IP público ou None em caso de erro
    """
    servicos = [
        "https://api.ipify.org?format=json",
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]
    
    for servico in servicos:
        try:
            response = requests.get(servico, timeout=10)
            if response.status_code == 200:
                if servico.endswith("format=json"):
                    return response.json().get("ip", "").strip()
                else:
                    return response.text.strip()
        except Exception as e:
            print(f"[!] Erro ao obter IP de {servico}: {e}")
            continue
    
    return None


def main():
    """Função principal"""
    parser = argparse.ArgumentParser(
        description="Adiciona um IP à whitelist de proxy rotativa",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python PYSW41pquLUjQkAQZXwXTrtC.py 192.168.1.100
  python PYSW41pquLUjQkAQZXwXTrtC.py 203.0.113.45
  python PYSW41pquLUjQkAQZXwXTrtC.py --auto    # Usa o IP público atual
        """
    )
    
    parser.add_argument(
        "ip",
        nargs="?",
        help="Endereço IP a ser adicionado à whitelist"
    )
    
    parser.add_argument(
        "--api-url",
        default=BASE_API_URL,
        help=f"URL base da API (padrão: {BASE_API_URL})"
    )
    
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Obtém automaticamente o IP público e adiciona à whitelist"
    )
    
    args = parser.parse_args()
    
    # Se --auto, obter IP público
    if args.auto:
        print("[*] Obtendo IP público...")
        ip = obter_ip_publico()
        if not ip:
            print("❌ Erro: Não foi possível obter o IP público automaticamente")
            sys.exit(1)
        print(f"[*] IP público detectado: {ip}")
    # Se IP foi fornecido como argumento
    elif args.ip:
        ip = args.ip.strip()
    # Se não foi fornecido, pedir ao usuário
    else:
        print("\nOpções:")
        print("  1. Digite um IP manualmente")
        print("  2. Pressione Enter para usar o IP público atual")
        escolha = input("\nEscolha (1/Enter para auto): ").strip()
        
        if escolha == "" or escolha.lower() == "2":
            print("[*] Obtendo IP público...")
            ip = obter_ip_publico()
            if not ip:
                print("❌ Erro: Não foi possível obter o IP público")
                ip = input("Digite o endereço IP manualmente: ").strip()
        else:
            ip = input("Digite o endereço IP: ").strip()
        
        if not ip:
            print("❌ Erro: IP não fornecido")
            sys.exit(1)
    
    # Atualizar URL base se fornecida
    global BASE_API_URL
    if args.api_url != BASE_API_URL:
        BASE_API_URL = args.api_url
    
    print("=" * 60)
    print("🔒 Adicionando IP à Whitelist de Proxy Rotativa")
    print("=" * 60)
    print(f"IP: {ip}")
    print(f"API Key: {API_KEY[:10]}...")
    print(f"Base URL: {BASE_API_URL}")
    print("=" * 60)
    print()
    
    # Adicionar IP à whitelist
    resultado = adicionar_ip_whitelist(ip)
    
    print()
    print("=" * 60)
    if resultado["success"]:
        print("✅ SUCESSO")
        print("=" * 60)
        print(resultado["message"])
        if "data" in resultado:
            print(f"\nResposta da API: {resultado['data']}")
        sys.exit(0)
    else:
        print("❌ ERRO")
        print("=" * 60)
        print(resultado["error"])
        sys.exit(1)


if __name__ == "__main__":
    main()

