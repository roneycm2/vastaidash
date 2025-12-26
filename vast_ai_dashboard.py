"""
Dashboard Web para Vast.ai - Visualização de Máquinas Disponíveis
VERSÃO OTIMIZADA - Com cache e timeout agressivo testestestetetete 
"""

from flask import Flask, render_template, jsonify, request
import requests
import json
import sys
from datetime import datetime
import threading
import time

app = Flask(__name__)

# =============================================
# CACHE EM MEMÓRIA - Evita chamadas repetidas
# =============================================
cache = {
    'ofertas': {'data': None, 'timestamp': 0, 'ttl': 60},  # Cache de 60 segundos
    'paises': {'data': None, 'timestamp': 0, 'ttl': 300},  # Cache de 5 minutos
    'estatisticas': {'data': None, 'timestamp': 0, 'ttl': 60}
}
cache_lock = threading.Lock()

def get_cache(key):
    """Obtém dados do cache se ainda válidos"""
    with cache_lock:
        if key in cache and cache[key]['data'] is not None:
            if time.time() - cache[key]['timestamp'] < cache[key]['ttl']:
                return cache[key]['data']
    return None

def set_cache(key, data):
    """Armazena dados no cache"""
    with cache_lock:
        if key in cache:
            cache[key]['data'] = data
            cache[key]['timestamp'] = time.time()

# Configuração da API
API_BASE_URL = 'https://console.vast.ai/api/v0'
API_KEY = 'eb17d1910d038ebb9d7430697920353562078a2f26ed45b68c50ee7a5fe6ba3b'


# Mapeamento de países por região
REGIOES_PAISES = {
    'europa': [
        'DE', 'FR', 'GB', 'UK', 'NL', 'PL', 'IT', 'ES', 'BE', 'AT', 'CH', 
        'SE', 'NO', 'DK', 'FI', 'IE', 'PT', 'GR', 'CZ', 'HU', 'RO', 'BG',
        'SK', 'SI', 'HR', 'LT', 'LV', 'EE', 'LU', 'MT', 'CY', 'IS'
    ],
    'america_sul': [
        'BR', 'AR', 'CL', 'CO', 'PE', 'VE', 'EC', 'BO', 'PY', 'UY', 'GY',
        'SR', 'GF', 'FK'
    ],
    'america_norte': [
        'US', 'CA', 'MX', 'GT', 'BZ', 'SV', 'HN', 'NI', 'CR', 'PA', 'CU',
        'JM', 'HT', 'DO', 'PR', 'TT', 'BB', 'BS', 'AG', 'DM', 'GD', 'LC',
        'VC', 'KN'
    ]
}

def extrair_pais_geolocation(geolocation):
    """
    Extrai o país da geolocalização (pode ser string ou dict)
    Retorna o nome do país como string
    
    Exemplos:
    - "California, United States" -> "United States"
    - {"country": "United States"} -> "United States"
    - "Brazil" -> "Brazil"
    """
    if not geolocation:
        return None
    
    if isinstance(geolocation, dict):
        # Se for dict, pode ter 'country' ou 'country_code'
        pais = geolocation.get('country') or geolocation.get('country_code')
        if pais:
            return str(pais).strip()
        return None
    elif isinstance(geolocation, str):
        # Se for string como "California, United States", extrai o último elemento
        geolocation = geolocation.strip()
        if not geolocation:
            return None
        
        # Remove espaços extras
        parts = [p.strip() for p in geolocation.split(',') if p.strip()]
        if len(parts) > 1:
            # Retorna o país (último elemento após vírgula)
            return parts[-1]
        elif len(parts) == 1:
            # Se só tiver um elemento, pode ser o país ou estado/cidade
            # Retorna como está
            return parts[0]
    
    return None


def buscar_ofertas(preco_maximo=None, limite=1000, apenas_verificadas=False, regioes=None, paises=None, usar_paginacao=True):
    """
    Busca ofertas de máquinas na Vast.ai com suporte a paginação e mais resultados
    
    Args:
        preco_maximo: Preço máximo por hora em dólares (None = sem limite)
        limite: Número máximo de resultados (padrão: 1000, pode ser aumentado)
        apenas_verificadas: Se True, busca apenas máquinas verificadas (padrão: False para mais resultados)
        regioes: Lista de regiões para filtrar ['europa', 'america_sul', 'america_norte']
                 Se None, não filtra por região
        paises: Lista de nomes de países para filtrar (ex: ['United States', 'Brazil'])
                Se None, não filtra por país
        usar_paginacao: Se True, faz múltiplas requisições para obter mais resultados
    
    Returns:
        Lista de ofertas disponíveis
    """
    url = f"{API_BASE_URL}/bundles/"
    
    # Limite máximo por requisição da API (testado empiricamente)
    # A API pode retornar até 1000+ resultados em uma única requisição
    LIMITE_POR_REQUISICAO = 5000
    
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    todas_ofertas = []
    
    try:
        # Primeiro, tenta uma requisição única com limite alto
        # A API da Vast.ai geralmente retorna muitos resultados em uma única chamada
        payload = {
            "rentable": {"eq": True},
            "rented": {"eq": False}
        }
        
        if preco_maximo is not None:
            payload["dph_total"] = {"lte": preco_maximo}
        
        if apenas_verificadas:
            payload["verified"] = {"eq": True}
        
        # Adiciona parâmetros de ordenação na API (formato correto: lista de listas)
        # Conforme documentação: [['campo', 'direcao']]
        payload["order"] = [["dph_total", "asc"]]
        # Tenta buscar o máximo possível em uma única requisição
        payload["limit"] = min(limite, LIMITE_POR_REQUISICAO)
        
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        if response.status_code == 200:
            data = response.json()
            todas_ofertas = data.get('offers', [])
            
            # Se a API retornou menos que o solicitado e ainda queremos mais,
            # e a paginação está habilitada, podemos tentar fazer requisições adicionais
            # com diferentes critérios ou simplesmente retornar o que temos
            if usar_paginacao and len(todas_ofertas) < limite and len(todas_ofertas) > 0:
                # Se retornou exatamente o limite da requisição, pode haver mais resultados
                # Mas como a API pode não suportar offset tradicional, vamos retornar o que temos
                # A maioria dos casos a API retorna todos os resultados disponíveis
                pass
        else:
            print(f"Erro ao buscar ofertas: HTTP {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return []
        
        # Aplica filtros de país/região após obter os resultados
        if paises:
            paises_set = {p.strip().lower() for p in paises if p}
            ofertas_filtradas = []
            for oferta in todas_ofertas:
                geolocation = oferta.get('geolocation', '')
                pais = extrair_pais_geolocation(geolocation)
                
                if pais and pais.lower() in paises_set:
                    ofertas_filtradas.append(oferta)
            
            todas_ofertas = ofertas_filtradas
        elif regioes:
            paises_permitidos = set()
            for regiao in regioes:
                if regiao.lower() in REGIOES_PAISES:
                    paises_permitidos.update(REGIOES_PAISES[regiao.lower()])
            
            if paises_permitidos:
                ofertas_filtradas = []
                for oferta in todas_ofertas:
                    geolocation = oferta.get('geolocation', '')
                    pais = extrair_pais_geolocation(geolocation)
                    
                    if pais:
                        pais_upper = pais.upper()
                        if pais_upper in paises_permitidos:
                            ofertas_filtradas.append(oferta)
                
                todas_ofertas = ofertas_filtradas
        
        # Garante que está ordenado por preço (mais baratas primeiro)
        todas_ofertas = sorted(
            todas_ofertas, 
            key=lambda x: x.get('dph_total', float('inf'))
        )
        
        # Aplica o limite final
        return todas_ofertas[:limite]
        
    except Exception as e:
        print(f"Erro ao buscar ofertas: {e}")
        import traceback
        traceback.print_exc()
        return []


def formatar_dados_oferta(oferta):
    """Formata os dados de uma oferta para exibição"""
    preco = oferta.get('dph_total', 0)
    ram_gb = oferta.get('cpu_ram', 0) / 1024 if oferta.get('cpu_ram') else 0
    vram_gb = oferta.get('gpu_ram', 0) / 1024 if oferta.get('gpu_ram') else 0
    
    geolocation = oferta.get('geolocation', 'N/A')
    if isinstance(geolocation, dict):
        localizacao = geolocation.get('country', 'N/A')
    else:
        localizacao = geolocation if geolocation else 'N/A'
    
    verificacao = (
        oferta.get('verification') == 'verified' or 
        oferta.get('verified', False) or 
        oferta.get('vericode', 0) == 1
    )
    
    return {
        'id': oferta.get('id', 'N/A'),
        'gpu_name': oferta.get('gpu_name', 'N/A'),
        'gpu_ram': f"{vram_gb:.1f} GB",
        'cpu_name': oferta.get('cpu_name', 'N/A'),
        'cpu_cores': oferta.get('cpu_cores', 0),
        'cpu_ram': f"{ram_gb:.1f} GB",
        'disk_space': f"{oferta.get('disk_space', 0):.1f} GB",
        'disk_name': oferta.get('disk_name', 'N/A'),
        'preco': preco,
        'preco_formatado': f"${preco:.4f}",
        'inet_up': oferta.get('inet_up', 0),
        'inet_down': oferta.get('inet_down', 0),
        'localizacao': localizacao,
        'verificado': verificacao,
        'rentable': oferta.get('rentable', False),
        'reliability': oferta.get('reliability', 0) * 100,
        'num_gpus': oferta.get('num_gpus', 1),
        'dlperf': oferta.get('dlperf', 0),
        'flops': oferta.get('total_flops', 0)
    }


@app.route('/')
def index():
    """Página principal do dashboard"""
    return render_template('dashboard.html')


@app.route('/api/paises')
def api_paises():
    """Endpoint para buscar países disponíveis nas ofertas"""
    try:
        # Limite reduzido para melhor performance
        limite = request.args.get('limite', default=500, type=int)
        limite = min(limite, 1000)
        ofertas = buscar_ofertas(limite=limite, apenas_verificadas=False, usar_paginacao=True)
        
        # Extrair países únicos
        paises_set = set()
        for oferta in ofertas:
            geolocation = oferta.get('geolocation', '')
            pais = extrair_pais_geolocation(geolocation)
            if pais:
                paises_set.add(pais.strip())
        
        # Ordenar países alfabeticamente
        paises_ordenados = sorted(list(paises_set))
        
        return jsonify({
            'success': True,
            'total': len(paises_ordenados),
            'paises': paises_ordenados
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/ofertas')
def api_ofertas():
    """Endpoint da API para buscar ofertas com suporte a grandes volumes e CACHE"""
    try:
        preco_max = request.args.get('preco_max', type=float)
        # Limite padrão reduzido para 50, máximo de 2000
        limite = request.args.get('limite', default=50, type=int)
        limite = min(limite, 2000)  # Limita para evitar sobrecarga
        # Muda o padrão para False para retornar mais máquinas (não apenas verificadas)
        apenas_verificadas = request.args.get('verificadas', default='false', type=str).lower() == 'true'
        # Permite desabilitar paginação se necessário
        usar_paginacao = request.args.get('paginacao', default='true', type=str).lower() == 'true'
        # Usar cache?
        usar_cache = request.args.get('cache', default='true', type=str).lower() == 'true'
        
        # Obter países do parâmetro (pode ser múltiplos separados por vírgula)
        paises_param = request.args.get('paises', type=str)
        paises = None
        if paises_param:
            paises = [p.strip() for p in paises_param.split(',') if p.strip()]
        
        # Obter regiões do parâmetro (pode ser múltiplas separadas por vírgula)
        regioes_param = request.args.get('regioes', type=str)
        regioes = None
        if regioes_param:
            regioes = [r.strip().lower() for r in regioes_param.split(',') if r.strip()]
        
        # Tenta usar cache para requisições simples (sem filtros específicos)
        cache_key = f"ofertas_{limite}_{apenas_verificadas}"
        ofertas = None
        from_cache = False
        
        if usar_cache and not paises and not regioes and not preco_max:
            ofertas = get_cache(cache_key)
            if ofertas:
                from_cache = True
        
        if not ofertas:
            ofertas = buscar_ofertas(
                preco_maximo=preco_max,
                limite=limite,
                apenas_verificadas=apenas_verificadas,
                regioes=regioes,
                paises=paises,
                usar_paginacao=usar_paginacao
            )
            # Salva no cache se não tiver filtros específicos
            if usar_cache and not paises and not regioes and not preco_max:
                set_cache(cache_key, ofertas)
        
        ofertas_formatadas = [formatar_dados_oferta(o) for o in ofertas]
        
        return jsonify({
            'success': True,
            'total': len(ofertas_formatadas),
            'ofertas': ofertas_formatadas,
            'paises_filtrados': paises if paises else None,
            'regioes_filtradas': regioes if regioes else None,
            'apenas_verificadas': apenas_verificadas,
            'from_cache': from_cache,
            'timestamp': datetime.now().isoformat()
        })
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Timeout ao conectar com Vast.ai. Tente novamente com um limite menor.'
        }), 504
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/instancias')
def api_instancias():
    """Endpoint para listar todas as instâncias do usuário conforme documentação da API"""
    try:
        url = f"{API_BASE_URL}/instances/"
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            instances = data.get('instances', []) or []
            instances_found = data.get('instances_found', len(instances))
            
            # Formata as instâncias com todos os campos disponíveis
            instancias_formatadas = []
            for instance in instances:
                # Status atual (prioridade: actual_status > cur_state > status)
                status = (
                    instance.get('actual_status') or 
                    instance.get('cur_state') or 
                    instance.get('status') or 
                    'unknown'
                )
                
                # IP público
                ip = (
                    instance.get('public_ipaddr') or 
                    instance.get('public_ip') or 
                    instance.get('ipaddr') or
                    instance.get('inet_addr') or
                    'Aguardando atribuição'
                )
                
                # SSH info
                ssh_host = instance.get('ssh_host') or ip
                ssh_port = instance.get('ssh_port') or '22'
                
                # Datas
                start_date = instance.get('start_date')
                end_date = instance.get('end_date')
                
                # Formata datas
                start_date_str = 'N/A'
                if start_date:
                    try:
                        from datetime import datetime
                        start_date_str = datetime.fromtimestamp(start_date).strftime('%d/%m/%Y %H:%M:%S')
                    except:
                        start_date_str = str(start_date)
                
                time_remaining = instance.get('time_remaining', 'N/A')
                
                # Template e imagem
                template_name = instance.get('template_name') or 'N/A'
                image_uuid = instance.get('image_uuid') or 'N/A'
                
                # Status message
                status_msg = instance.get('status_msg', '')
                
                # Processa portas abertas
                ports_data = instance.get('ports', {})
                port_3000 = None
                port_3000_host = None
                outras_portas = []
                
                if ports_data and isinstance(ports_data, dict):
                    # Procura pela porta 3000 especificamente
                    for port_key, port_mappings in ports_data.items():
                        if isinstance(port_mappings, list) and len(port_mappings) > 0:
                            # Extrai o número da porta da chave (ex: "3000/tcp" -> 3000)
                            try:
                                port_num = int(port_key.split('/')[0])
                                host_port = port_mappings[0].get('HostPort')
                                host_ip = port_mappings[0].get('HostIp', '0.0.0.0')
                                
                                if port_num == 3000:
                                    port_3000 = host_port
                                    port_3000_host = host_ip
                                else:
                                    outras_portas.append({
                                        'porta': port_num,
                                        'host_port': host_port,
                                        'host_ip': host_ip,
                                        'protocolo': port_key.split('/')[1] if '/' in port_key else 'tcp'
                                    })
                            except (ValueError, AttributeError, IndexError):
                                continue
                
                # Função auxiliar para garantir que valores numéricos sejam números ou None
                def safe_number(value, default=0):
                    """Converte valores None/null para default, mantém números"""
                    if value is None:
                        return default
                    try:
                        return float(value) if value != '' else default
                    except (ValueError, TypeError):
                        return default
                
                instancias_formatadas.append({
                    'id': instance.get('id'),
                    'offer_id': instance.get('ask_id') or instance.get('offer_id') or instance.get('machine_id'),
                    'ip': ip,
                    'status': status,
                    'status_msg': status_msg,
                    'intended_status': instance.get('intended_status', 'N/A'),
                    'next_state': instance.get('next_state', 'N/A'),
                    'gpu_name': instance.get('gpu_name', 'N/A'),
                    'gpu_ram': safe_number(instance.get('gpu_ram')),
                    'gpu_totalram': safe_number(instance.get('gpu_totalram')),
                    'gpu_util': safe_number(instance.get('gpu_util')),
                    'cpu_name': instance.get('cpu_name', 'N/A'),
                    'cpu_cores': safe_number(instance.get('cpu_cores')),
                    'cpu_ram': safe_number(instance.get('cpu_ram')),
                    'cpu_util': safe_number(instance.get('cpu_util')),
                    'disk_space': safe_number(instance.get('disk_space')),
                    'ssh_port': ssh_port,
                    'ssh_host': ssh_host,
                    'ssh_idx': instance.get('ssh_idx', 'N/A'),
                    'template_name': template_name,
                    'template_id': instance.get('template_id'),
                    'image_uuid': image_uuid,
                    'label': instance.get('label', ''),
                    'start_date': start_date_str,
                    'time_remaining': time_remaining,
                    'dph_total': safe_number(instance.get('dph_total')),
                    'geolocation': instance.get('geolocation', 'N/A'),
                    'verification': instance.get('verification', 'N/A'),
                    'reliability2': safe_number(instance.get('reliability2')),
                    'machine_id': instance.get('machine_id'),
                    'ports': instance.get('ports', {}),
                    'port_3000': port_3000,
                    'port_3000_host': port_3000_host,
                    'outras_portas': outras_portas,
                    'local_ipaddrs': instance.get('local_ipaddrs', ''),
                    'jupyter_token': instance.get('jupyter_token'),
                    'is_ready': status.lower() in ['running', 'started'] and ip != 'Aguardando atribuição'
                })
            
            return jsonify({
                'success': True,
                'total': instances_found,
                'instancias': instancias_formatadas
            })
        else:
            error_text = response.text[:500] if response.text else 'Sem detalhes'
            return jsonify({
                'success': False,
                'error': f'Erro HTTP {response.status_code}: {error_text}'
            }), response.status_code
            
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar instâncias: {e}")
        error_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f" - Resposta: {e.response.text[:200]}"
        return jsonify({'success': False, 'error': error_msg}), 500
    except Exception as e:
        import traceback
        print(f"Erro inesperado ao buscar instâncias: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/estatisticas')
def api_estatisticas():
    """Endpoint para estatísticas gerais"""
    try:
        # Obter regiões do parâmetro (pode ser múltiplas separadas por vírgula)
        regioes_param = request.args.get('regioes', type=str)
        regioes = None
        if regioes_param:
            regioes = [r.strip().lower() for r in regioes_param.split(',') if r.strip()]
        
        # Limite reduzido para melhor performance
        limite = request.args.get('limite', default=500, type=int)
        limite = min(limite, 1000)
        apenas_verificadas = request.args.get('verificadas', default='false', type=str).lower() == 'true'
        ofertas = buscar_ofertas(limite=limite, regioes=regioes, apenas_verificadas=apenas_verificadas)
        
        if not ofertas:
            return jsonify({
                'success': True,
                'total': 0,
                'preco_minimo': 0,
                'preco_maximo': 0,
                'preco_medio': 0,
                'total_gpus': 0,
                'regioes_filtradas': regioes if regioes else 'todas'
            })
        
        precos = [o.get('dph_total', 0) for o in ofertas if o.get('dph_total')]
        total_gpus = sum(o.get('num_gpus', 1) for o in ofertas)
        
        return jsonify({
            'success': True,
            'total': len(ofertas),
            'preco_minimo': min(precos) if precos else 0,
            'preco_maximo': max(precos) if precos else 0,
            'preco_medio': sum(precos) / len(precos) if precos else 0,
            'total_gpus': total_gpus,
            'regioes_filtradas': regioes if regioes else 'todas'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/comprar-lote', methods=['POST'])
def api_comprar_lote():
    """
    Endpoint para compra em LOTE - processa todas as máquinas em PARALELO
    para aparecer mais rápido no sistema
    
    Usa template_id: 319260 que já contém as credenciais Docker configuradas
    para o repositório privado adminbetsofc/exodia-machine
    """
    import concurrent.futures
    import threading
    
    try:
        data = request.get_json()
        oferta_ids = data.get('ids', [])
        # Template ID com credenciais Docker já configuradas
        template_id = data.get('template_id', 319260)
        disk_size = data.get('disk', 20)
        
        if not oferta_ids:
            return jsonify({
                'success': False,
                'error': 'Nenhuma máquina selecionada'
            }), 400
        
        resultados = []
        resultados_lock = threading.Lock()
        
        def comprar_uma_maquina(oferta_id):
            """Função para comprar uma única máquina - será executada em paralelo"""
            try:
                url = f"{API_BASE_URL}/asks/{oferta_id}/"
                
                # Usa template_id que já contém credenciais Docker
                payload = {
                    "template_id": template_id,
                    "disk": disk_size
                }
                
                headers = {
                    'Authorization': f'Bearer {API_KEY}',
                    'Content-Type': 'application/json'
                }
                
                print(f"[LOTE] Comprando máquina {oferta_id} com template {template_id}...")
                response = requests.put(url, json=payload, headers=headers, timeout=30)
                
                try:
                    result_data = response.json()
                except:
                    result_data = {'error': response.text[:500] if response.text else 'Resposta vazia'}
                
                resultado = None
                if response.status_code == 200:
                    if result_data.get('success') or 'new_contract' in result_data or 'id' in result_data:
                        resultado = {
                            'id': oferta_id,
                            'success': True,
                            'message': 'Máquina comprada com sucesso',
                            'instance_id': result_data.get('id', 'N/A')
                        }
                        print(f"[LOTE] ✅ Máquina {oferta_id} comprada!")
                    else:
                        error_msg = (
                            result_data.get('msg') or 
                            result_data.get('error') or 
                            result_data.get('message') or
                            result_data.get('detail') or
                            json.dumps(result_data) if result_data else 'Erro desconhecido'
                        )
                        resultado = {
                            'id': oferta_id,
                            'success': False,
                            'message': f'Erro: {error_msg}'
                        }
                        print(f"[LOTE] ❌ Erro na máquina {oferta_id}: {error_msg}")
                else:
                    error_msg = (
                        result_data.get('msg') or 
                        result_data.get('error') or 
                        result_data.get('message') or
                        result_data.get('detail') or
                        response.text[:500] if response.text else f'Erro HTTP {response.status_code}'
                    )
                    resultado = {
                        'id': oferta_id,
                        'success': False,
                        'message': f'Erro HTTP {response.status_code}: {error_msg}'
                    }
                    print(f"[LOTE] ❌ Erro HTTP na máquina {oferta_id}: {error_msg}")
                
                with resultados_lock:
                    resultados.append(resultado)
                    
            except Exception as e:
                resultado = {
                    'id': oferta_id,
                    'success': False,
                    'message': f'Erro: {str(e)}'
                }
                with resultados_lock:
                    resultados.append(resultado)
                print(f"[LOTE] ❌ Exceção na máquina {oferta_id}: {e}")
        
        # Executa TODAS as compras em PARALELO usando ThreadPoolExecutor
        # Usa max_workers igual ao número de máquinas (até 50) para máxima velocidade
        max_workers = min(len(oferta_ids), 50)
        
        print(f"\n{'='*60}")
        print(f"[LOTE] 🚀 Iniciando compra em LOTE de {len(oferta_ids)} máquinas")
        print(f"[LOTE] Workers paralelos: {max_workers}")
        print(f"[LOTE] Template ID: {template_id}")
        print(f"[LOTE] Disk: {disk_size} GB")
        print(f"{'='*60}\n")
        
        import time
        inicio = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submete todas as compras de uma vez
            futures = [executor.submit(comprar_uma_maquina, oferta_id) for oferta_id in oferta_ids]
            # Aguarda todas completarem
            concurrent.futures.wait(futures)
        
        tempo_total = time.time() - inicio
        
        # Conta sucessos e falhas
        sucessos = sum(1 for r in resultados if r.get('success'))
        falhas = len(resultados) - sucessos
        
        print(f"\n{'='*60}")
        print(f"[LOTE] ✅ Compra em lote finalizada!")
        print(f"[LOTE] Tempo total: {tempo_total:.2f} segundos")
        print(f"[LOTE] Sucessos: {sucessos}, Falhas: {falhas}")
        print(f"{'='*60}\n")
        
        return jsonify({
            'success': True,
            'resultados': resultados,
            'tempo_total': tempo_total,
            'sucessos': sucessos,
            'falhas': falhas
        })
        
    except Exception as e:
        import traceback
        print(f"[LOTE] Erro geral: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/comprar', methods=['POST'])
def api_comprar():
    """
    Endpoint para comprar/alugar máquinas.
    
    Usa template_id: 319260 que já contém as credenciais Docker configuradas
    para o repositório privado adminbetsofc/exodia-machine
    """
    try:
        data = request.get_json()
        oferta_ids = data.get('ids', [])
        # Template ID com credenciais Docker já configuradas
        template_id = data.get('template_id', 319260)
        disk_size = data.get('disk', 20)
        
        if not oferta_ids:
            return jsonify({
                'success': False,
                'error': 'Nenhuma máquina selecionada'
            }), 400
        
        resultados = []
        
        for oferta_id in oferta_ids:
            try:
                # Endpoint correto conforme documentação: PUT /asks/{id}/
                url = f"{API_BASE_URL}/asks/{oferta_id}/"
                
                # Payload usando template_id que já contém credenciais Docker
                payload = {
                    "template_id": template_id,
                    "disk": disk_size
                }
                
                headers = {
                    'Authorization': f'Bearer {API_KEY}',
                    'Content-Type': 'application/json'
                }
                
                # Log do payload antes de enviar
                print(f"\n{'='*60}")
                print(f"Tentando comprar máquina ID: {oferta_id}")
                print(f"URL: {url}")
                print(f"Template ID: {template_id}")
                print(f"Disk: {disk_size} GB")
                print(f"Payload: {json.dumps(payload, indent=2)}")
                print(f"{'='*60}\n")
                
                response = requests.put(url, json=payload, headers=headers, timeout=30)
                
                # Log da resposta
                print(f"Status HTTP: {response.status_code}")
                print(f"Response Body (primeiros 1000 chars): {response.text[:1000]}")
                
                # Tenta fazer parse da resposta
                try:
                    result_data = response.json()
                    print(f"Response JSON: {json.dumps(result_data, indent=2)}")
                except Exception as json_err:
                    print(f"⚠️ Erro ao fazer parse JSON: {json_err}")
                    print(f"Response text completo: {response.text}")
                    result_data = {
                        'error': response.text[:500] if response.text else 'Resposta vazia',
                        'raw_response': response.text
                    }
                
                # Processa a resposta
                if response.status_code == 200:
                    # A API pode retornar success=True ou apenas os dados da instância
                    if result_data.get('success') or 'new_contract' in result_data or 'id' in result_data:
                        # Buscar informações da instância criada, incluindo IP
                        instance_info = obter_info_instancia(oferta_id)
                        
                        resultados.append({
                            'id': oferta_id,
                            'success': True,
                            'message': 'Máquina comprada com sucesso',
                            'ip': instance_info.get('ip', 'N/A'),
                            'instance_id': instance_info.get('instance_id', result_data.get('id', 'N/A'))
                        })
                    else:
                        # Extrai mensagem de erro de várias possíveis chaves
                        error_msg = (
                            result_data.get('msg') or 
                            result_data.get('error') or 
                            result_data.get('message') or
                            result_data.get('detail') or
                            json.dumps(result_data) if result_data else 'Erro desconhecido'
                        )
                        print(f"❌ Erro na resposta: {error_msg}")
                        resultados.append({
                            'id': oferta_id,
                            'success': False,
                            'message': f'Erro: {error_msg}',
                            'response_data': result_data
                        })
                else:
                    # Erro HTTP (não 200)
                    error_msg = (
                        result_data.get('msg') or 
                        result_data.get('error') or 
                        result_data.get('message') or
                        result_data.get('detail') or
                        response.text[:500] if response.text else f'Erro HTTP {response.status_code}'
                    )
                    print(f"❌ Erro HTTP {response.status_code}: {error_msg}")
                    resultados.append({
                        'id': oferta_id,
                        'success': False,
                        'message': f'Erro HTTP {response.status_code}: {error_msg}',
                        'response_text': response.text[:1000] if response.text else None,
                        'response_data': result_data if isinstance(result_data, dict) else None
                    })
                    
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"Erro ao comprar máquina {oferta_id}: {error_details}")
                resultados.append({
                    'id': oferta_id,
                    'success': False,
                    'message': f'Erro: {str(e)}'
                })
        
        return jsonify({
            'success': True,
            'resultados': resultados
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/destruir', methods=['DELETE', 'POST'])
def api_destruir():
    """
    Endpoint para destruir instâncias EM PARALELO.
    Aceita DELETE ou POST.
    
    Body JSON:
    - ids: Lista de IDs de instâncias para destruir, ou ['all'] para destruir todas
    
    Processa TODAS as destruições em paralelo para máxima velocidade!
    """
    import concurrent.futures
    import threading
    import time
    
    try:
        data = request.get_json() or {}
        instance_ids = data.get('ids', [])
        
        if not instance_ids:
            return jsonify({
                'success': False,
                'error': 'Nenhuma instância especificada. Use {"ids": [123]} ou {"ids": ["all"]}'
            }), 400
        
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Se for "all", buscar todas as instâncias primeiro
        if 'all' in [str(id).lower() for id in instance_ids]:
            url_list = f"{API_BASE_URL}/instances/"
            response_list = requests.get(url_list, headers=headers, timeout=30)
            
            if response_list.status_code == 200:
                data_list = response_list.json()
                instances = data_list.get('instances', []) or []
                instance_ids = [inst.get('id') for inst in instances if inst.get('id')]
            else:
                return jsonify({
                    'success': False,
                    'error': f'Erro ao buscar instâncias: HTTP {response_list.status_code}'
                }), response_list.status_code
        
        # Filtra IDs válidos
        instance_ids = [id for id in instance_ids if id]
        
        if not instance_ids:
            return jsonify({
                'success': True,
                'total': 0,
                'sucessos': 0,
                'falhas': 0,
                'resultados': [],
                'message': 'Nenhuma instância para destruir'
            })
        
        resultados = []
        resultados_lock = threading.Lock()
        
        def destruir_uma_instancia(instance_id):
            """Função para destruir uma única instância - executada em paralelo"""
            try:
                url = f"{API_BASE_URL}/instances/{instance_id}/"
                
                print(f"[DESTRUIR] 🗑️ Destruindo instância {instance_id}...")
                
                response = requests.delete(url, headers=headers, timeout=30)
                
                resultado = None
                if response.status_code == 200:
                    try:
                        result_data = response.json()
                    except:
                        result_data = {'success': True}
                    
                    resultado = {
                        'instance_id': instance_id,
                        'success': True,
                        'message': 'Instância destruída com sucesso'
                    }
                    print(f"[DESTRUIR] ✅ Instância {instance_id} destruída!")
                else:
                    try:
                        error_data = response.json()
                        error_msg = (
                            error_data.get('msg') or 
                            error_data.get('error') or 
                            error_data.get('message') or
                            error_data.get('detail') or
                            response.text[:500] if response.text else f'Erro HTTP {response.status_code}'
                        )
                    except:
                        error_msg = response.text[:500] if response.text else f'Erro HTTP {response.status_code}'
                    
                    resultado = {
                        'instance_id': instance_id,
                        'success': False,
                        'message': f'Erro ao destruir: {error_msg}',
                        'status_code': response.status_code
                    }
                    print(f"[DESTRUIR] ❌ Erro na instância {instance_id}: {error_msg}")
                
                with resultados_lock:
                    resultados.append(resultado)
                    
            except Exception as e:
                resultado = {
                    'instance_id': instance_id,
                    'success': False,
                    'message': f'Erro: {str(e)}'
                }
                with resultados_lock:
                    resultados.append(resultado)
                print(f"[DESTRUIR] ❌ Exceção na instância {instance_id}: {e}")
        
        # Executa TODAS as destruições em PARALELO
        max_workers = min(len(instance_ids), 50)
        
        print(f"\n{'='*60}")
        print(f"[DESTRUIR] 🚀 Iniciando destruição em PARALELO de {len(instance_ids)} instâncias")
        print(f"[DESTRUIR] Workers paralelos: {max_workers}")
        print(f"{'='*60}\n")
        
        inicio = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(destruir_uma_instancia, instance_id) for instance_id in instance_ids]
            concurrent.futures.wait(futures)
        
        tempo_total = time.time() - inicio
        
        # Contar sucessos e falhas
        sucessos = sum(1 for r in resultados if r.get('success'))
        falhas = len(resultados) - sucessos
        
        print(f"\n{'='*60}")
        print(f"[DESTRUIR] ✅ Destruição em paralelo finalizada!")
        print(f"[DESTRUIR] Tempo total: {tempo_total:.2f} segundos")
        print(f"[DESTRUIR] Sucessos: {sucessos}, Falhas: {falhas}")
        print(f"{'='*60}\n")
        
        return jsonify({
            'success': True,
            'total': len(resultados),
            'sucessos': sucessos,
            'falhas': falhas,
            'tempo_total': tempo_total,
            'resultados': resultados
        })
        
    except Exception as e:
        import traceback
        print(f"[DESTRUIR] Erro geral: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def obter_info_instancia(offer_id):
    """Obtém informações da instância criada, incluindo IP"""
    import time
    time.sleep(2)  # Aguarda um pouco para a instância ser criada
    
    try:
        # Buscar instâncias do usuário
        url = f"{API_BASE_URL}/instances/"
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        
        print("Response: ", response.text)

        if response.status_code == 200:
            data = response.json()
            instances = data.get('instances', []) or []
            
            # Procurar a instância mais recente que corresponde ao offer_id
            for instance in instances:
                ask_id = instance.get('ask_id') or instance.get('offer_id')
                if ask_id == offer_id:
                    ip = (
                        instance.get('public_ipaddr') or 
                        instance.get('public_ip') or 
                        instance.get('ipaddr') or
                        instance.get('inet_addr') or
                        'Aguardando atribuição'
                    )
                    return {
                        'instance_id': instance.get('id'),
                        'ip': ip,
                        'status': instance.get('status', 'N/A')
                    }
        
        # Se não encontrou nas instâncias, tenta buscar na oferta original
        url_offer = f"{API_BASE_URL}/offers/{offer_id}/"
        response = requests.get(url_offer, headers=headers, timeout=30)
        
        if response.status_code == 200:
            offer_data = response.json()
            ip = (
                offer_data.get('public_ipaddr') or 
                offer_data.get('public_ip') or 
                'Aguardando atribuição'
            )
            return {'ip': ip}
            
    except Exception as e:
        print(f"Erro ao obter info da instância: {e}")
    
    return {'ip': 'Aguardando atribuição'}


if __name__ == '__main__':
    PORT = 5012  # Porta alterada para evitar conflitos
    print("=" * 60)
    print("🚀 Dashboard Vast.ai iniciando...")
    print("=" * 60)
    print(f"📊 Acesse: http://localhost:{PORT}")
    print("💡 DICA: Use limite=50 para carregamento rápido")
    print("=" * 60)
    # Usa threaded=True para não bloquear o servidor durante requisições lentas
    # Desabilita debug e reloader para melhor estabilidade no Windows
    app.run(
        debug=False,  # Desabilitado para melhor performance
        host='0.0.0.0', 
        port=PORT, 
        threaded=True,  # Importante: permite múltiplas requisições simultâneas
        use_reloader=False
    )

