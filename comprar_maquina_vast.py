"""
Script para comprar uma máquina na Vast.ai usando o template exodia-machine

IMPORTANTE: Usa template_id: 319260 que já contém as credenciais Docker
configuradas para o repositório privado adminbetsofc/exodia-machine
"""

import requests
import json
import sys

# Configuração da API
API_BASE_URL = 'https://console.vast.ai/api/v0'
API_KEY = 'eb17d1910d038ebb9d7430697920353562078a2f26ed45b68c50ee7a5fe6ba3b'

# Template ID com credenciais Docker já configuradas
TEMPLATE_ID = 319260
DISK_SIZE = 20  # GB

HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}


def buscar_ofertas(limite=10, preco_maximo=None):
    """Busca ofertas disponíveis ordenadas por preço"""
    url = f"{API_BASE_URL}/bundles/"
    
    payload = {
        "rentable": {"eq": True},
        "rented": {"eq": False},
        "order": [["dph_total", "asc"]],
        "limit": limite
    }
    
    if preco_maximo:
        payload["dph_total"] = {"lte": preco_maximo}
    
    response = requests.post(url, json=payload, headers=HEADERS, timeout=60)
    
    if response.status_code == 200:
        data = response.json()
        return data.get('offers', [])
    else:
        print(f"❌ Erro ao buscar ofertas: HTTP {response.status_code}")
        print(response.text[:500])
        return []


def comprar_maquina(offer_id):
    """
    Compra uma máquina usando o template exodia-machine
    
    IMPORTANTE: Usa template_id que já contém credenciais Docker configuradas
    
    Args:
        offer_id: ID da oferta (ask_id) para aceitar
    
    Returns:
        dict com resultado da operação
    """
    url = f"{API_BASE_URL}/asks/{offer_id}/"
    
    # Payload usando template_id que já contém credenciais Docker
    payload = {
        "template_id": TEMPLATE_ID,
        "disk": DISK_SIZE
    }
    
    print(f"\n{'='*60}")
    print(f"🚀 Comprando máquina com offer_id: {offer_id}")
    print(f"URL: {url}")
    print(f"Template ID: {TEMPLATE_ID}")
    print(f"Disk: {DISK_SIZE} GB")
    print(f"{'='*60}\n")
    
    response = requests.put(url, json=payload, headers=HEADERS, timeout=30)
    
    print(f"📡 Status HTTP: {response.status_code}")
    
    try:
        result = response.json()
        print(f"📋 Resposta: {json.dumps(result, indent=2)}")
    except:
        result = {"raw": response.text[:500]}
        print(f"📋 Resposta (raw): {response.text[:500]}")
    
    if response.status_code == 200:
        if result.get('success') or 'new_contract' in result:
            print(f"\n✅ SUCESSO! Máquina comprada!")
            print(f"   Contract ID: {result.get('new_contract', 'N/A')}")
            return {"success": True, "data": result}
        else:
            print(f"\n⚠️ Resposta recebida mas sem confirmação de sucesso")
            return {"success": False, "data": result}
    else:
        print(f"\n❌ Erro HTTP {response.status_code}")
        return {"success": False, "error": result}


def listar_e_comprar_interativo():
    """Modo interativo: lista ofertas e permite escolher qual comprar"""
    print("\n" + "="*60)
    print("🔍 Buscando ofertas disponíveis...")
    print("="*60)
    
    ofertas = buscar_ofertas(limite=10)
    
    if not ofertas:
        print("❌ Nenhuma oferta encontrada!")
        return
    
    print(f"\n📋 {len(ofertas)} ofertas encontradas (ordenadas por preço):\n")
    print(f"{'#':<4} {'ID':<12} {'GPU':<25} {'RAM GPU':<10} {'Preço/h':<12} {'Local'}")
    print("-" * 90)
    
    for i, oferta in enumerate(ofertas):
        gpu_name = oferta.get('gpu_name', 'N/A')[:24]
        gpu_ram = oferta.get('gpu_ram', 0) / 1024 if oferta.get('gpu_ram') else 0
        preco = oferta.get('dph_total', 0)
        geo = oferta.get('geolocation', 'N/A')
        if isinstance(geo, dict):
            geo = geo.get('country', 'N/A')
        
        print(f"{i+1:<4} {oferta.get('id', 'N/A'):<12} {gpu_name:<25} {gpu_ram:.1f} GB    ${preco:.4f}/h    {geo}")
    
    print("\n" + "-" * 90)
    escolha = input("\n👉 Digite o número da oferta para comprar (ou 'q' para sair): ").strip()
    
    if escolha.lower() == 'q':
        print("👋 Saindo...")
        return
    
    try:
        idx = int(escolha) - 1
        if 0 <= idx < len(ofertas):
            oferta_escolhida = ofertas[idx]
            offer_id = oferta_escolhida.get('id')
            
            confirma = input(f"\n⚠️ Confirma compra da máquina {offer_id} por ${oferta_escolhida.get('dph_total', 0):.4f}/h? (s/n): ").strip().lower()
            
            if confirma == 's':
                comprar_maquina(offer_id)
            else:
                print("❌ Compra cancelada.")
        else:
            print("❌ Número inválido!")
    except ValueError:
        print("❌ Entrada inválida!")


def comprar_mais_barata():
    """Compra automaticamente a máquina mais barata disponível"""
    print("\n" + "="*60)
    print("🔍 Buscando a máquina mais barata disponível...")
    print("="*60)
    
    ofertas = buscar_ofertas(limite=1)
    
    if not ofertas:
        print("❌ Nenhuma oferta encontrada!")
        return None
    
    oferta = ofertas[0]
    offer_id = oferta.get('id')
    preco = oferta.get('dph_total', 0)
    gpu = oferta.get('gpu_name', 'N/A')
    
    print(f"\n📌 Máquina mais barata encontrada:")
    print(f"   ID: {offer_id}")
    print(f"   GPU: {gpu}")
    print(f"   Preço: ${preco:.4f}/hora")
    
    return comprar_maquina(offer_id)


def comprar_por_id(offer_id):
    """Compra uma máquina específica pelo ID"""
    return comprar_maquina(offer_id)


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🖥️  VAST.AI - Comprar Máquina com Template Exodia")
    print("="*60)
    
    if len(sys.argv) > 1:
        # Se passou um ID como argumento, compra diretamente
        offer_id = sys.argv[1]
        
        if offer_id == '--auto' or offer_id == '-a':
            # Modo automático: compra a mais barata
            comprar_mais_barata()
        elif offer_id == '--list' or offer_id == '-l':
            # Modo interativo: lista e deixa escolher
            listar_e_comprar_interativo()
        else:
            # Compra pelo ID especificado
            try:
                offer_id = int(offer_id)
                comprar_por_id(offer_id)
            except ValueError:
                print(f"❌ ID inválido: {offer_id}")
                print("\nUso:")
                print("  python comprar_maquina_vast.py <offer_id>  - Compra máquina específica")
                print("  python comprar_maquina_vast.py --auto     - Compra a mais barata")
                print("  python comprar_maquina_vast.py --list     - Lista e escolhe interativamente")
    else:
        # Sem argumentos: modo interativo
        listar_e_comprar_interativo()

