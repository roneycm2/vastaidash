"""
Script para listar e comprar máquinas na Vast.ai com preço máximo de $0.40/hora
Baseado na documentação: https://docs.vast.ai/documentation/get-started
"""

import requests
import json
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
import sys

console = Console()

# Configuração da API
API_BASE_URL = 'https://console.vast.ai/api/v0'
API_KEY = 'eb17d1910d038ebb9d7430697920353562078a2f26ed45b68c50ee7a5fe6ba3b'


def configurar_api_key():
    """Solicita e configura a chave de API"""
    global API_KEY
    if not API_KEY:
        console.print("\n[bold yellow]⚠️  Chave de API necessária![/bold yellow]")
        console.print("Obtenha sua chave em: https://console.vast.ai/account/")
        API_KEY = Prompt.ask("Digite sua chave de API da Vast.ai", password=True)
    return API_KEY


def buscar_ofertas(preco_maximo: float = None, limite: int = 100, apenas_baratas: bool = True) -> List[Dict]:
    """
    Busca ofertas de máquinas na Vast.ai, priorizando as mais baratas
    
    Args:
        preco_maximo: Preço máximo por hora em dólares (None = sem limite)
        limite: Número máximo de resultados (padrão: 100)
        apenas_baratas: Se True, busca apenas máquinas baratas e disponíveis
    
    Returns:
        Lista de ofertas disponíveis
    """
    if not API_KEY:
        configurar_api_key()
    
    # Endpoint correto baseado no exemplo do curl
    url = f"{API_BASE_URL}/bundles/"
    
    # Constrói o payload no formato correto da API
    # Os filtros vão diretamente no payload, não dentro de um objeto "q"
    payload = {
        "rentable": {"eq": True},
        "rented": {"eq": False}
    }
    
    # Adiciona filtro de preço se especificado
    if preco_maximo is not None:
        payload["dph_total"] = {"lte": preco_maximo}
    
    # Adiciona opções de ordenação e limite
    payload["sort"] = "dph_total"
    payload["order"] = "asc"
    payload["limit"] = limite
    
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        console.print(f"[dim]Fazendo requisição para: {url}[/dim]")
        console.print(f"[dim]Payload: {json.dumps(payload, indent=2)}[/dim]")
        
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        # Debug: mostra status e conteúdo da resposta
        console.print(f"[dim]Status: {response.status_code}[/dim]")
        
        # Verifica se a resposta está vazia
        if not response.text:
            console.print("[bold red]❌ Resposta vazia da API[/bold red]")
            return []
        
        # Tenta fazer parse do JSON
        try:
            data = response.json()
        except json.JSONDecodeError as json_err:
            console.print(f"[bold red]❌ Erro ao decodificar JSON: {json_err}[/bold red]")
            console.print(f"[red]Resposta recebida (primeiros 500 chars):[/red]")
            console.print(f"[dim]{response.text[:500]}[/dim]")
            return []
        
        # Verifica se há erro na resposta
        if 'error' in data:
            console.print(f"[bold red]❌ Erro da API: {data.get('msg', data.get('error', 'Erro desconhecido'))}[/bold red]")
            return []
        
        response.raise_for_status()
        
        # Debug: mostra estrutura da resposta
        console.print(f"[dim]Tipo da resposta: {type(data)}[/dim]")
        if isinstance(data, dict):
            console.print(f"[dim]Chaves na resposta: {list(data.keys())}[/dim]")
        
        # Retorna as ofertas (pode estar em diferentes chaves)
        if isinstance(data, list):
            console.print(f"[green]✅ Encontradas {len(data)} ofertas (formato lista)[/green]")
            return data
        elif 'offers' in data:
            ofertas = data.get('offers', [])
            console.print(f"[green]✅ Encontradas {len(ofertas)} ofertas (chave 'offers')[/green]")
            return ofertas
        elif 'bundles' in data:
            ofertas = data.get('bundles', [])
            console.print(f"[green]✅ Encontradas {len(ofertas)} ofertas (chave 'bundles')[/green]")
            return ofertas
        else:
            # Tenta encontrar qualquer lista de ofertas
            for key in ['results', 'data', 'items', 'machines']:
                if key in data and isinstance(data[key], list):
                    ofertas = data[key]
                    console.print(f"[green]✅ Encontradas {len(ofertas)} ofertas (chave '{key}')[/green]")
                    return ofertas
            
            # Se não encontrou, mostra a estrutura completa para debug
            console.print(f"[yellow]⚠️  Estrutura da resposta não reconhecida. Chaves: {list(data.keys()) if isinstance(data, dict) else 'N/A'}[/yellow]")
            console.print(f"[dim]Resposta completa (primeiros 1000 chars): {str(data)[:1000]}[/dim]")
            return []
    
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]❌ Erro ao buscar ofertas: {e}[/bold red]")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[red]Status: {e.response.status_code}[/red]")
            console.print(f"[red]Resposta: {e.response.text[:500]}[/red]")
        return []
    except Exception as e:
        console.print(f"[bold red]❌ Erro inesperado: {e}[/bold red]")
        return []


def formatar_preco(preco: float) -> str:
    """Formata o preço em dólares"""
    return f"${preco:.4f}"


def formatar_velocidade(mbps: float) -> str:
    """Formata velocidade de internet"""
    if mbps >= 1000:
        return f"{mbps/1000:.2f} Gbps"
    return f"{mbps:.2f} Mbps"


def criar_tabela_ofertas(ofertas: List[Dict]) -> Table:
    """Cria uma tabela formatada com as ofertas"""
    table = Table(
        title="[bold cyan]Máquinas Disponíveis - Vast.ai[/bold cyan]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        title_style="bold cyan"
    )
    
    table.add_column("ID", style="dim", width=8)
    table.add_column("GPU", style="bold yellow", width=20)
    table.add_column("Preço/h", style="bold green", width=10)
    table.add_column("CPU", style="cyan", width=8)
    table.add_column("RAM", style="blue", width=8)
    table.add_column("Disk", style="magenta", width=8)
    table.add_column("Upload", style="dim", width=10)
    table.add_column("Download", style="dim", width=10)
    table.add_column("Localização", style="dim", width=12)
    
    for oferta in ofertas:
        # Usa dph_total como preço principal, com fallback para outros campos
        preco = oferta.get('dph_total') or oferta.get('dph') or oferta.get('price_gpu', 0)
        
        # Geolocation pode ser string ou dict
        geolocation = oferta.get('geolocation', 'N/A')
        if isinstance(geolocation, dict):
            localizacao = geolocation.get('country', 'N/A')
        else:
            localizacao = geolocation if geolocation else 'N/A'
        
        table.add_row(
            str(oferta.get('id', 'N/A')),
            oferta.get('gpu_name', 'N/A'),
            formatar_preco(preco),
            f"{oferta.get('cpu_cores', 0)} cores",
            f"{oferta.get('cpu_ram', 0) / 1024:.1f} GB" if oferta.get('cpu_ram') else "N/A",
            f"{oferta.get('disk_space', 0):.1f} GB" if oferta.get('disk_space') else "N/A",
            formatar_velocidade(oferta.get('inet_up', 0)),
            formatar_velocidade(oferta.get('inet_down', 0)),
            localizacao
        )
    
    return table


def mostrar_detalhes_oferta(oferta: Dict):
    """Mostra detalhes completos de uma oferta"""
    # Usa dph_total como preço principal, com fallback para outros campos
    preco = oferta.get('dph_total') or oferta.get('dph') or oferta.get('price_gpu', 0)
    # Geolocation pode ser string ou dict
    geolocation = oferta.get('geolocation', 'N/A')
    if isinstance(geolocation, dict):
        localizacao = geolocation.get('country', 'N/A')
    else:
        localizacao = geolocation if geolocation else 'N/A'
    
    # Verificação pode ser string "verified" ou booleano
    verificacao = oferta.get('verification') == 'verified' or oferta.get('verified', False) or oferta.get('vericode', 0) == 1
    
    # RAM em GB (vem em MB)
    ram_gb = oferta.get('cpu_ram', 0) / 1024 if oferta.get('cpu_ram') else 0
    
    info = f"""
[bold]ID da Oferta:[/bold] {oferta.get('id', 'N/A')}
[bold]GPU:[/bold] {oferta.get('gpu_name', 'N/A')} ({oferta.get('gpu_ram', 0) / 1024:.1f} GB VRAM)
[bold]Preço por hora:[/bold] {formatar_preco(preco)}
[bold]CPU:[/bold] {oferta.get('cpu_name', 'N/A')} - {oferta.get('cpu_cores', 0)} cores
[bold]RAM:[/bold] {ram_gb:.1f} GB
[bold]Armazenamento:[/bold] {oferta.get('disk_space', 0):.1f} GB ({oferta.get('disk_name', 'N/A')})
[bold]Upload:[/bold] {formatar_velocidade(oferta.get('inet_up', 0))}
[bold]Download:[/bold] {formatar_velocidade(oferta.get('inet_down', 0))}
[bold]Localização:[/bold] {localizacao}
[bold]Verificado:[/bold] {'✅ Sim' if verificacao else '❌ Não'}
[bold]Disponível:[/bold] {'✅ Sim' if oferta.get('rentable', False) else '❌ Não'}
[bold]Confiabilidade:[/bold] {oferta.get('reliability', 0) * 100:.2f}%
"""
    
    console.print(Panel(info, title="[bold green]Detalhes da Oferta[/bold green]", border_style="green"))


def alugar_maquina(oferta_id: int, quantidade: int = 1) -> bool:
    """
    Aluga uma máquina na Vast.ai
    
    Args:
        oferta_id: ID da oferta a ser alugada
        quantidade: Quantidade de instâncias (padrão: 1)
    
    Returns:
        True se o aluguel foi bem-sucedido, False caso contrário
    """
    if not API_KEY:
        configurar_api_key()
    
    url = f"{API_BASE_URL}/asks/{oferta_id}/"
    
    payload = {
        "client_id": "me",
        "quantity": quantidade
    }
    
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.put(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if data.get('success'):
            console.print(f"[bold green]✅ Máquina {oferta_id} alugada com sucesso![/bold green]")
            return True
        else:
            console.print(f"[bold red]❌ Erro ao alugar máquina: {data.get('msg', 'Erro desconhecido')}[/bold red]")
            return False
    
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]❌ Erro ao alugar máquina: {e}[/bold red]")
        if hasattr(e, 'response') and e.response is not None:
            console.print(f"[red]Resposta: {e.response.text}[/red]")
        return False


def menu_principal():
    """Menu principal interativo"""
    while True:
        console.print("\n" + "="*60)
        console.print("[bold cyan]🤖 Vast.ai - Gerenciador de Máquinas[/bold cyan]")
        console.print("="*60)
        
        console.print("\n[bold]Opções:[/bold]")
        console.print("1. Buscar máquinas mais baratas (sem limite de preço)")
        console.print("2. Buscar máquinas com preço máximo")
        console.print("3. Configurar chave de API")
        console.print("4. Sair")
        
        opcao = Prompt.ask("\nEscolha uma opção", choices=["1", "2", "3", "4"], default="1")
        
        if opcao == "1":
            # Busca as máquinas mais baratas disponíveis
            console.print("\n[bold yellow]🔍 Buscando as máquinas mais baratas disponíveis...[/bold yellow]")
            ofertas = buscar_ofertas(preco_maximo=None, limite=100, apenas_baratas=True)
            
        elif opcao == "2":
            preco_max = Prompt.ask("Preço máximo por hora (USD)", default="0.40")
            try:
                preco_max = float(preco_max)
            except ValueError:
                console.print("[red]Preço inválido! Usando $0.40 como padrão.[/red]")
                preco_max = 0.40
            
            console.print("\n[bold yellow]🔍 Buscando máquinas...[/bold yellow]")
            ofertas = buscar_ofertas(preco_maximo=preco_max, limite=100)
        
        if opcao in ["1", "2"]:
            
            if not ofertas:
                console.print("[bold red]❌ Nenhuma máquina encontrada com os critérios especificados.[/bold red]")
                continue
            
            if ofertas:
                # Ordena por preço para garantir que as mais baratas aparecem primeiro
                ofertas_ordenadas = sorted(ofertas, key=lambda x: x.get('dph_total') or x.get('dph') or x.get('price_gpu', float('inf')))
                console.print(f"\n[bold green]✅ Encontradas {len(ofertas_ordenadas)} máquinas disponíveis![/bold green]")
                console.print(f"[dim]💰 Preço mais barato: ${min(o.get('dph_total') or o.get('dph') or o.get('price_gpu', float('inf')) for o in ofertas_ordenadas):.4f}/hora[/dim]\n")
                console.print(criar_tabela_ofertas(ofertas_ordenadas))
            
            # Opção de ver detalhes e alugar
            console.print("\n[bold]Ações disponíveis:[/bold]")
            console.print("1. Ver detalhes de uma máquina")
            console.print("2. Alugar uma máquina")
            console.print("3. Voltar ao menu principal")
            
            acao = Prompt.ask("Escolha uma ação", choices=["1", "2", "3"], default="3")
            
            if acao == "1":
                oferta_id = Prompt.ask("Digite o ID da máquina")
                try:
                    oferta_id = int(oferta_id)
                    oferta = next((o for o in ofertas if o.get('id') == oferta_id), None)
                    if oferta:
                        mostrar_detalhes_oferta(oferta)
                    else:
                        console.print("[red]Máquina não encontrada na lista![/red]")
                except ValueError:
                    console.print("[red]ID inválido![/red]")
            
            elif acao == "2":
                oferta_id = Prompt.ask("Digite o ID da máquina para alugar")
                try:
                    oferta_id = int(oferta_id)
                    oferta = next((o for o in ofertas if o.get('id') == oferta_id), None)
                    if oferta:
                        mostrar_detalhes_oferta(oferta)
                        if Confirm.ask("\n[bold yellow]Deseja realmente alugar esta máquina?[/bold yellow]"):
                            quantidade = Prompt.ask("Quantidade de instâncias", default="1")
                            try:
                                quantidade = int(quantidade)
                                alugar_maquina(oferta_id, quantidade)
                            except ValueError:
                                console.print("[red]Quantidade inválida![/red]")
                        else:
                            console.print("[yellow]Operação cancelada.[/yellow]")
                    else:
                        console.print("[red]Máquina não encontrada na lista![/red]")
                except ValueError:
                    console.print("[red]ID inválido![/red]")
        
        elif opcao == "3":
            configurar_api_key()
            console.print("[green]✅ Chave de API configurada![/green]")
        
        elif opcao == "4":
            console.print("\n[bold yellow]👋 Até logo![/bold yellow]")
            sys.exit(0)


def main():
    """Função principal"""
    try:
        # Tenta carregar a chave de API de um arquivo de configuração
        try:
            with open('vast_ai_config.json', 'r') as f:
                config = json.load(f)
                global API_KEY
                API_KEY = config.get('api_key')
        except FileNotFoundError:
            pass
        
        menu_principal()
    
    except KeyboardInterrupt:
        console.print("\n\n[bold yellow]👋 Operação cancelada pelo usuário. Até logo![/bold yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]❌ Erro inesperado: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()

