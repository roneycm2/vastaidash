"""
Script de teste para a API da Vast.ai
Testa o formato correto baseado no exemplo do curl
"""

import requests
import json

API_KEY = 'eb17d1910d038ebb9d7430697920353562078a2f26ed45b68c50ee7a5fe6ba3b'
API_BASE_URL = 'https://console.vast.ai/api/v0'

url = f"{API_BASE_URL}/bundles/"

# Payload no formato correto (baseado no exemplo do curl)
payload = {
    "dph_total": {"lte": 0.20},
    "verified": {"eq": True},
    "rentable": {"eq": True},
    "rented": {"eq": False}
}

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json'
}

print("=" * 60)
print("Teste da API Vast.ai")
print("=" * 60)
print(f"\nURL: {url}")
print(f"\nHeaders: {json.dumps(headers, indent=2)}")
print(f"\nPayload: {json.dumps(payload, indent=2)}")
print("\n" + "=" * 60)
print("Fazendo requisição...")
print("=" * 60)

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    
    print(f"\nStatus Code: {response.status_code}")
    print(f"Headers da Resposta: {dict(response.headers)}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            print("\n✅ Resposta JSON recebida!")
            print(f"\nTipo da resposta: {type(data)}")
            
            if isinstance(data, dict):
                print(f"Chaves na resposta: {list(data.keys())}")
            
            if isinstance(data, list):
                print(f"\n📊 Total de ofertas encontradas: {len(data)}")
                if len(data) > 0:
                    print("\nPrimeira oferta (exemplo):")
                    print(json.dumps(data[0], indent=2))
            elif isinstance(data, dict):
                # Procura por listas de ofertas
                for key in ['offers', 'bundles', 'results', 'data']:
                    if key in data and isinstance(data[key], list):
                        print(f"\n📊 Total de ofertas encontradas (chave '{key}'): {len(data[key])}")
                        if len(data[key]) > 0:
                            print(f"\nPrimeira oferta (exemplo da chave '{key}'):")
                            print(json.dumps(data[key][0], indent=2))
                        break
                else:
                    print("\n📋 Estrutura completa da resposta:")
                    print(json.dumps(data, indent=2)[:2000])  # Limita a 2000 chars
        except json.JSONDecodeError as e:
            print(f"\n❌ Erro ao decodificar JSON: {e}")
            print(f"\nResposta recebida (primeiros 1000 chars):")
            print(response.text[:1000])
    else:
        print(f"\n❌ Erro HTTP: {response.status_code}")
        print(f"Resposta: {response.text[:500]}")
        
except Exception as e:
    print(f"\n❌ Erro na requisição: {e}")
    import traceback
    traceback.print_exc()

