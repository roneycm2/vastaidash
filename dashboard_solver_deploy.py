"""
Dashboard Solver Deploy - Controle Completo de Solvers via Vast.ai
====================================================================

Este dashboard permite:
1. Sincronizar máquinas da Vast.ai
2. Transformar solver local em executável e fazer deploy
3. Monitorar logs em tempo real
4. Verificar o que necessita para rodar
5. Matar processos em todas as máquinas conectadas
6. Baixar tokens gerados

Uso:
    python dashboard_solver_deploy.py

Acesse: http://localhost:5020
"""

import json
import os
import sys
import time
import subprocess
import threading
import requests
import shutil
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, Response
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÕES DA API VAST.AI
# ============================================================

VAST_API_URL = "https://console.vast.ai/api/v0"
VAST_API_KEY = "eb17d1910d038ebb9d7430697920353562078a2f26ed45b68c50ee7a5fe6ba3b"

# Arquivos do solver (ordem de prioridade)
SOLVER_FILES = [
    "turnstile_persistent_solver.py",  # Solver principal com abas persistentes
    "turnstile_solver_service.py",
    "turnstile_remote_solver.py",
]

# Arquivo de configuração
CONFIG_FILE = "solver_deploy_config.json"

# ============================================================
# ESTADO GLOBAL
# ============================================================

machines = []
machines_lock = threading.Lock()

logs = []
logs_lock = threading.Lock()

stats = {
    "total_tokens": 0,
    "running_machines": 0,
    "total_machines": 0,
    "start_time": None
}
stats_lock = threading.Lock()

should_stop = False


# ============================================================
# LOGGING
# ============================================================

def log_add(msg: str, level: str = "info"):
    """Adiciona uma mensagem ao log"""
    with logs_lock:
        logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "msg": msg,
            "level": level
        })
        # Mantém últimos 500 logs
        if len(logs) > 500:
            logs.pop(0)
    
    # Print no console também
    icons = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {icons.get(level, '•')} {msg}")


# ============================================================
# CONFIGURAÇÃO
# ============================================================

def get_config():
    """Carrega configuração do arquivo"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        log_add(f"Erro ao carregar config: {e}", "warning")
    
    return {
        "tabs_per_machine": 5,
        "use_proxy": True,
        "headless": False,  # Rodar com navegador visível
        "solver_file": "turnstile_persistent_solver.py"  # Solver principal
    }


def save_config(config):
    """Salva configuração no arquivo"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        log_add(f"Erro ao salvar config: {e}", "error")


# ============================================================
# VAST.AI API
# ============================================================

def fetch_vast_instances():
    """Busca todas as instâncias na Vast.ai"""
    global machines
    
    log_add("🔄 Sincronizando com Vast.ai...")
    
    try:
        headers = {
            "Authorization": f"Bearer {VAST_API_KEY}",
            "Content-Type": "application/json"
        }
        
        url = f"{VAST_API_URL}/instances/"
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            log_add(f"Erro API Vast.ai: HTTP {response.status_code}", "error")
            return []
        
        data = response.json()
        instances = data.get("instances", [])
        
        log_add(f"📋 Total de instâncias: {len(instances)}", "info")
        
        # Filtra apenas as running
        running = [i for i in instances if i.get("actual_status") == "running"]
        log_add(f"🟢 Instâncias rodando: {len(running)}", "success")
        
        result = []
        for inst in running:
            instance_id = inst.get("id")
            ssh_host = inst.get("ssh_host")
            ssh_port = inst.get("ssh_port")
            public_ip = inst.get("public_ipaddr")
            
            if ssh_host and ssh_port:
                result.append({
                    "id": instance_id,
                    "host": ssh_host,
                    "port": ssh_port,
                    "public_ip": public_ip or "N/A",
                    "gpu": inst.get("gpu_name", "Unknown"),
                    "gpu_ram": round(inst.get("gpu_ram", 0) / 1024, 1) if inst.get("gpu_ram") else 0,
                    "cpu_ram": round(inst.get("cpu_ram", 0) / 1024, 1) if inst.get("cpu_ram") else 0,
                    "status": "unknown",
                    "tokens": 0,
                    "processes": 0,
                    "last_log": ""
                })
                log_add(f"   [{instance_id}] {ssh_host}:{ssh_port} | GPU: {inst.get('gpu_name', 'N/A')}", "info")
            else:
                log_add(f"   [{instance_id}] Sem SSH configurado", "warning")
        
        with machines_lock:
            machines = result
        
        with stats_lock:
            stats["total_machines"] = len(result)
        
        log_add(f"✅ {len(result)} máquinas prontas para conexão SSH", "success")
        return result
        
    except requests.exceptions.RequestException as e:
        log_add(f"❌ Erro de conexão com Vast.ai: {e}", "error")
        return []
    except Exception as e:
        log_add(f"❌ Erro inesperado: {e}", "error")
        import traceback
        traceback.print_exc()
        return []


# ============================================================
# SSH COMMANDS
# ============================================================

def run_ssh_command(machine: dict, command: str, timeout: int = 30):
    """Executa comando SSH em uma máquina"""
    host = machine["host"]
    port = machine["port"]
    
    # Caminho da chave SSH
    ssh_key = os.path.expanduser("~/.ssh/id_rsa")
    
    try:
        ssh_cmd = [
            "ssh",
            "-i", ssh_key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=15",
            "-o", "ServerAliveInterval=10",
            "-o", "BatchMode=yes",
            "-o", "LogLevel=ERROR",
            "-p", str(port),
            f"root@{host}",
            command
        ]
        
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return result.returncode == 0, result.stdout + result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "Timeout na conexão SSH"
    except Exception as e:
        return False, str(e)


def scp_file(machine: dict, local_file: str, remote_path: str, timeout: int = 120):
    """Copia arquivo via SCP para máquina remota"""
    host = machine["host"]
    port = machine["port"]
    
    # Caminho da chave SSH
    ssh_key = os.path.expanduser("~/.ssh/id_rsa")
    
    try:
        scp_cmd = [
            "scp",
            "-i", ssh_key,
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=15",
            "-o", "BatchMode=yes",
            "-o", "LogLevel=ERROR",
            "-P", str(port),
            local_file,
            f"root@{host}:{remote_path}"
        ]
        
        result = subprocess.run(
            scp_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return result.returncode == 0, result.stdout + result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "Timeout no SCP"
    except Exception as e:
        return False, str(e)


def check_ssh_connection(machine: dict):
    """Verifica se SSH está acessível"""
    success, output = run_ssh_command(machine, "echo 'SSH_OK'", timeout=20)
    return success and "SSH_OK" in output


def verify_all_connections():
    """Verifica conexão SSH de todas as máquinas em paralelo"""
    global machines
    
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        log_add("Nenhuma máquina para verificar", "warning")
        return
    
    log_add(f"🔍 Verificando {len(current_machines)} conexões SSH...", "info")
    
    connected = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_ssh_connection, m): m for m in current_machines}
        
        for future in as_completed(futures):
            machine = futures[future]
            try:
                is_connected = future.result()
                
                with machines_lock:
                    for m in machines:
                        if m["id"] == machine["id"]:
                            m["status"] = "connected" if is_connected else "offline"
                            break
                
                if is_connected:
                    connected += 1
                    log_add(f"🟢 [{machine['id']}] {machine['host']}:{machine['port']} - Conectado", "success")
                else:
                    log_add(f"🔴 [{machine['id']}] {machine['host']}:{machine['port']} - Offline", "error")
                    
            except Exception as e:
                log_add(f"⚠️ [{machine['id']}] Erro: {e}", "warning")
    
    log_add(f"✅ Verificação completa: {connected}/{len(current_machines)} conectadas", "success")


def check_machine_requirements(machine: dict):
    """Verifica o que precisa instalar na máquina"""
    host = machine["host"]
    requirements = {
        "python": False,
        "pip": False,
        "playwright": False,
        "chromium": False,
        "patchright": False
    }
    
    # Verifica Python
    success, output = run_ssh_command(machine, "python3 --version", timeout=10)
    requirements["python"] = success and "Python" in output
    
    # Verifica pip
    success, output = run_ssh_command(machine, "pip3 --version", timeout=10)
    requirements["pip"] = success and "pip" in output
    
    # Verifica Playwright
    success, output = run_ssh_command(machine, "python3 -c 'import playwright' 2>&1", timeout=10)
    requirements["playwright"] = success and "Error" not in output
    
    # Verifica Patchright
    success, output = run_ssh_command(machine, "python3 -c 'import patchright' 2>&1", timeout=10)
    requirements["patchright"] = success and "Error" not in output
    
    return requirements


def install_requirements(machine: dict):
    """Instala dependências necessárias na máquina"""
    host = machine["host"]
    log_add(f"📦 [{host}] Instalando dependências...", "info")
    
    # Comando mais tolerante a falhas de repositório:
    # - apt-get update pode falhar mas continuamos (|| true)
    # - Tenta instalar pacotes mesmo se update falhar (muitas vezes já estão instalados)
    # - Foca nos pacotes Python que são essenciais
    commands = (
        "apt-get update -qq 2>/dev/null || true; "
        "apt-get install -y -qq python3 python3-pip wget curl unzip 2>/dev/null || true; "
        "pip3 install --quiet --break-system-packages flask requests patchright playwright 2>/dev/null || "
        "pip3 install --quiet flask requests patchright playwright; "
        "python3 -m patchright install chromium 2>/dev/null || python3 -m playwright install chromium 2>/dev/null || true; "
        "echo 'DEPS_INSTALLED'"
    )
    
    success, output = run_ssh_command(machine, commands, timeout=300)
    
    if success and "DEPS_INSTALLED" in output:
        log_add(f"✅ [{host}] Dependências instaladas", "success")
        return True
    else:
        log_add(f"❌ [{host}] Erro ao instalar: {output[:100]}", "error")
        return False


# ============================================================
# DEPLOY
# ============================================================

def get_solver_content():
    """Lê o conteúdo do solver local"""
    config = get_config()
    solver_file = config.get("solver_file", "turnstile_persistent_solver.py")
    
    # Prioriza o arquivo da configuração primeiro
    files_to_check = [solver_file] + SOLVER_FILES
    
    for possible_file in files_to_check:
        path = os.path.join(os.path.dirname(__file__), possible_file)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read(), possible_file
    
    return None, None


def send_file_to_machine(machine: dict):
    """
    Envia apenas o arquivo turnstile_persistent_solver.py para a máquina.
    Não instala dependências nem executa.
    """
    host = machine["host"]
    port = machine["port"]
    
    log_add(f"📤 [{host}] Enviando arquivo...", "info")
    
    try:
        ssh_key = os.path.expanduser("~/.ssh/id_rsa")
        
        # Lê o solver local
        solver_path = os.path.join(os.path.dirname(__file__), "turnstile_persistent_solver.py")
        if not os.path.exists(solver_path):
            log_add(f"❌ [{host}] Arquivo solver não encontrado!", "error")
            return False
        
        with open(solver_path, "r", encoding="utf-8") as f:
            solver_content = f.read()
        
        # Converte para formato Unix
        solver_content_unix = solver_content.replace('\r\n', '\n').replace('\r', '')
        
        # Salva temporariamente
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8', newline='\n') as f:
            f.write(solver_content_unix)
            temp_path = f.name
        
        try:
            # Envia via SCP
            scp_cmd = [
                "scp",
                "-i", ssh_key,
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=30",
                "-o", "LogLevel=ERROR",
                "-P", str(port),
                temp_path,
                f"root@{host}:/tmp/turnstile_persistent_solver.py"
            ]
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=120)
            output = result.stdout + result.stderr
            
            # Verifica erros
            error_keywords = ["Permission denied", "Connection refused", "Connection timed out", 
                            "Host key verification failed", "lost connection", "Connection reset"]
            
            if any(err.lower() in output.lower() for err in error_keywords):
                log_add(f"❌ [{host}] Erro SCP: {output[:80]}", "error")
                return False
            
            log_add(f"✅ [{host}] Arquivo enviado!", "success")
            
            # Marca na máquina
            with machines_lock:
                for m in machines:
                    if m["id"] == machine["id"]:
                        m["file_sent"] = True
                        break
            
            return True
            
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
                
    except subprocess.TimeoutExpired:
        log_add(f"❌ [{host}] Timeout no envio", "error")
        return False
    except Exception as e:
        log_add(f"❌ [{host}] Erro: {str(e)[:60]}", "error")
        return False


def send_file_to_all_machines():
    """Envia o arquivo solver para todas as máquinas conectadas"""
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        log_add("❌ Nenhuma máquina disponível!", "error")
        return 0
    
    log_add(f"📤 Enviando arquivo para {len(current_machines)} máquinas...", "info")
    
    success_count = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(send_file_to_machine, m): m for m in current_machines}
        
        for future in as_completed(futures):
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                log_add(f"Erro ao enviar: {e}", "error")
    
    log_add(f"✅ Arquivo enviado: {success_count}/{len(current_machines)} máquinas", "success")
    return success_count


def deploy_solver_simple(machine: dict, tabs: int = 5):
    """
    Deploy simplificado - envia apenas o solver e instala dependências mínimas.
    
    Etapas:
    1. Envia turnstile_persistent_solver.py via SCP
    2. Instala patchright (única dependência externa)
    3. Instala Chromium via patchright
    4. Executa o solver
    """
    global should_stop
    
    if should_stop:
        return False
    
    host = machine["host"]
    port = machine["port"]
    
    log_add(f"🚀 [{host}] Deploy simples ({tabs} tabs)...", "info")
    
    try:
        # Caminho da chave SSH
        ssh_key = os.path.expanduser("~/.ssh/id_rsa")
        
        # Lê o arquivo solver local
        solver_path = os.path.join(os.path.dirname(__file__), "turnstile_persistent_solver.py")
        if not os.path.exists(solver_path):
            log_add(f"❌ [{host}] Arquivo solver não encontrado: {solver_path}", "error")
            return False
        
        with open(solver_path, "r", encoding="utf-8") as f:
            solver_content = f.read()
        
        # Converte para formato Unix (remove \r)
        solver_content_unix = solver_content.replace('\r\n', '\n').replace('\r', '')
        
        # Salva temporariamente
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8', newline='\n') as f:
            f.write(solver_content_unix)
            temp_path = f.name
        
        try:
            # =========================================
            # ETAPA 1: Envia o solver via SCP
            # =========================================
            log_add(f"📤 [{host}] Enviando solver...", "info")
            
            scp_cmd = [
                "scp",
                "-i", ssh_key,
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=30",
                "-o", "LogLevel=ERROR",
                "-P", str(port),
                temp_path,
                f"root@{host}:/tmp/turnstile_persistent_solver.py"
            ]
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=120)
            
            # Verifica erros reais (ignora mensagens de boas-vindas)
            error_keywords = ["Permission denied", "Connection refused", "Connection timed out", 
                            "Host key verification failed", "lost connection", "Connection reset"]
            output = result.stdout + result.stderr
            
            if any(err.lower() in output.lower() for err in error_keywords):
                log_add(f"❌ [{host}] Erro SCP: {output[:100]}", "error")
                return False
            
            log_add(f"✅ [{host}] Solver enviado", "success")
            
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
        
        # =========================================
        # ETAPA 2: Mata processos antigos
        # =========================================
        log_add(f"🔄 [{host}] Limpando processos...", "info")
        run_ssh_command(machine, 
            "pkill -9 -f 'turnstile|patchright|chromium' 2>/dev/null || true; sleep 1", 
            timeout=30)
        
        # =========================================
        # ETAPA 3: Instala patchright (única dep)
        # =========================================
        log_add(f"📦 [{host}] Instalando patchright...", "info")
        success, output = run_ssh_command(machine, 
            "pip3 install --quiet patchright 2>/dev/null || pip install --quiet patchright 2>/dev/null; echo INSTALL_DONE", 
            timeout=180)
        
        if not success or "INSTALL_DONE" not in output:
            log_add(f"⚠️ [{host}] Aviso na instalação do patchright", "warning")
        
        # =========================================
        # ETAPA 4: Instala Chromium
        # =========================================
        log_add(f"🌐 [{host}] Instalando Chromium...", "info")
        run_ssh_command(machine, 
            "python3 -m patchright install chromium 2>/dev/null || true", 
            timeout=300)
        
        # =========================================
        # ETAPA 5: Prepara e executa solver
        # =========================================
        log_add(f"▶️ [{host}] Executando solver ({tabs} tabs)...", "info")
        
        # Limpa arquivo de tokens anterior e executa
        run_ssh_command(machine, 
            f"cd /tmp && rm -f turnstile_token.json 2>/dev/null; "
            f"export DISPLAY=:0; "
            f"nohup python3 turnstile_persistent_solver.py --tabs {tabs} > solver.log 2>&1 &", 
            timeout=30)
        
        # =========================================
        # ETAPA 6: Verifica se está rodando
        # =========================================
        time.sleep(5)
        
        success, output = run_ssh_command(machine, 
            "pgrep -f 'turnstile_persistent|chromium' > /dev/null && echo RUNNING || echo NOT_RUNNING", 
            timeout=15)
        
        if "RUNNING" in output and "NOT_RUNNING" not in output:
            log_add(f"✅ [{host}] Solver rodando com {tabs} tabs!", "success")
            
            with machines_lock:
                for m in machines:
                    if m["id"] == machine["id"]:
                        m["status"] = "running"
                        break
            return True
        else:
            # Pega log de erro
            _, log_out = run_ssh_command(machine, "tail -10 /tmp/solver.log 2>/dev/null", timeout=15)
            # Filtra boas-vindas
            lines = [l for l in log_out.split('\n') if l.strip() and 'Welcome' not in l and 'Have fun' not in l]
            log_add(f"❌ [{host}] Falhou: {' | '.join(lines[-2:])[:100]}", "error")
            return False
            
    except subprocess.TimeoutExpired:
        log_add(f"❌ [{host}] Timeout no deploy", "error")
        return False
    except Exception as e:
        log_add(f"❌ [{host}] Erro: {str(e)[:80]}", "error")
        return False


def deploy_to_machine(machine: dict, solver_content: str, config: dict):
    """Faz deploy do solver em uma máquina (método legado, usa deploy_solver_simple)"""
    tabs = config.get("tabs_per_machine", 5)
    return deploy_solver_simple(machine, tabs)


def deploy_all_simple(tabs: int = 5):
    """
    Faz deploy simples em todas as máquinas conectadas.
    Envia apenas o solver e instala dependências mínimas.
    """
    global should_stop
    should_stop = False
    
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        log_add("❌ Nenhuma máquina disponível. Sincronize primeiro!", "error")
        return 0
    
    log_add(f"🚀 Deploy simples em {len(current_machines)} máquinas ({tabs} tabs cada)...", "info")
    
    with stats_lock:
        stats["start_time"] = time.time()
    
    success_count = 0
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(deploy_solver_simple, m, tabs): m 
            for m in current_machines
        }
        
        for future in as_completed(futures):
            if should_stop:
                break
            
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                log_add(f"Erro no deploy: {e}", "error")
    
    with stats_lock:
        stats["running_machines"] = success_count
    
    log_add(f"✅ Deploy simples finalizado: {success_count}/{len(current_machines)} sucesso", "success")
    
    return success_count


def deploy_all_machines():
    """Faz deploy em todas as máquinas (usa deploy simples)"""
    config = get_config()
    tabs = config.get("tabs_per_machine", 5)
    
    success = deploy_all_simple(tabs)
    
    # Aguarda e atualiza status
    time.sleep(5)
    update_all_status()
    
    return success


# ============================================================
# STATUS E MONITORAMENTO
# ============================================================

def get_machine_status(machine: dict):
    """Obtém status detalhado de uma máquina"""
    host = machine["host"]
    
    result = {
        "running": False,
        "processes": 0,
        "tokens": 0,
        "last_log": ""
    }
    
    # Verifica processos rodando (turnstile_persistent_solver ou chromium do patchright)
    success, output = run_ssh_command(
        machine, 
        "ps aux | grep -E 'turnstile_persistent|patchright|chromium' | grep -v grep | wc -l",
        timeout=15
    )
    
    if success:
        try:
            # Filtra linhas que são números
            for line in output.split('\n'):
                line = line.strip()
                if line.isdigit():
                    result["processes"] = int(line)
                    result["running"] = result["processes"] > 0
                    break
        except:
            pass
    
    # Conta tokens (arquivo turnstile_token.json usado pelo persistent solver)
    success, output = run_ssh_command(
        machine,
        "cat /tmp/turnstile_token.json 2>/dev/null | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 1)' 2>/dev/null || echo 0",
        timeout=15
    )
    
    if success:
        try:
            result["tokens"] = int(output.strip())
        except:
            pass
    
    # Últimas linhas do log
    success, output = run_ssh_command(
        machine,
        "tail -5 /tmp/solver.log 2>/dev/null || echo 'Sem logs'",
        timeout=15
    )
    
    if success:
        result["last_log"] = output.strip()[-200:] if output else ""
    
    return result


def update_all_status():
    """Atualiza status de todas as máquinas"""
    global machines
    
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        return
    
    log_add("🔄 Atualizando status de todas as máquinas...", "info")
    
    total_tokens = 0
    running_count = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_machine_status, m): m for m in current_machines}
        
        for future in as_completed(futures):
            machine = futures[future]
            try:
                status = future.result()
                
                with machines_lock:
                    for m in machines:
                        if m["id"] == machine["id"]:
                            m["status"] = "running" if status["running"] else "stopped"
                            m["processes"] = status["processes"]
                            m["tokens"] = status["tokens"]
                            m["last_log"] = status["last_log"]
                            break
                
                total_tokens += status["tokens"]
                if status["running"]:
                    running_count += 1
                    
            except Exception as e:
                log_add(f"❌ Erro ao obter status de {machine['host']}: {e}", "error")
    
    with stats_lock:
        stats["total_tokens"] = total_tokens
        stats["running_machines"] = running_count
    
    log_add(f"✅ Status atualizado: {running_count} rodando, {total_tokens} tokens", "success")


# ============================================================
# KILL PROCESSES
# ============================================================

def kill_machine_processes(machine: dict):
    """Mata todos os processos do solver em uma máquina"""
    host = machine["host"]
    
    log_add(f"🛑 [{host}] Parando processos...", "info")
    
    # Comandos para matar o turnstile_persistent_solver e seus processos
    commands = 'pkill -9 -f "turnstile_persistent" 2>/dev/null || true; pkill -9 -f "patchright" 2>/dev/null || true; pkill -9 -f "chromium" 2>/dev/null || true; pkill -9 -f "python3.*turnstile" 2>/dev/null || true; echo "KILL_DONE"'
    
    success, output = run_ssh_command(machine, commands, timeout=30)
    
    if success and "KILL_DONE" in output:
        log_add(f"✅ [{host}] Processos finalizados", "success")
        return True
    else:
        log_add(f"⚠️ [{host}] Possível erro ao parar: {output[:50]}", "warning")
        return False


def run_solver_on_machine(machine: dict, tabs: int = 5):
    """
    Executa o solver em uma máquina (assumindo que o arquivo já foi enviado).
    Não faz deploy - apenas executa.
    """
    host = machine["host"]
    
    log_add(f"▶️ [{host}] Iniciando solver ({tabs} tabs)...", "info")
    
    try:
        # Primeiro mata processos existentes
        run_ssh_command(machine, 
            "pkill -9 -f 'turnstile_persistent|patchright|chromium' 2>/dev/null || true; sleep 1", 
            timeout=30)
        
        # Verifica se o arquivo existe
        success, output = run_ssh_command(machine, 
            "test -f /tmp/turnstile_persistent_solver.py && echo 'FILE_EXISTS' || echo 'FILE_NOT_FOUND'",
            timeout=15)
        
        if "FILE_NOT_FOUND" in output:
            log_add(f"⚠️ [{host}] Arquivo não encontrado! Use 'Enviar Arquivo' primeiro.", "warning")
            return False
        
        # Limpa arquivo de tokens anterior e executa
        run_ssh_command(machine, 
            f"cd /tmp && rm -f turnstile_token.json 2>/dev/null; "
            f"export DISPLAY=:0; "
            f"nohup python3 turnstile_persistent_solver.py --tabs {tabs} > solver.log 2>&1 &", 
            timeout=30)
        
        # Verifica se está rodando
        time.sleep(3)
        
        success, output = run_ssh_command(machine, 
            "pgrep -f 'turnstile_persistent|chromium' > /dev/null && echo RUNNING || echo NOT_RUNNING", 
            timeout=15)
        
        if "RUNNING" in output and "NOT_RUNNING" not in output:
            log_add(f"✅ [{host}] Solver iniciado com {tabs} tabs!", "success")
            
            with machines_lock:
                for m in machines:
                    if m["id"] == machine["id"]:
                        m["status"] = "running"
                        break
            return True
        else:
            # Pega log de erro
            _, log_out = run_ssh_command(machine, "tail -10 /tmp/solver.log 2>/dev/null", timeout=15)
            lines = [l for l in log_out.split('\n') if l.strip() and 'Welcome' not in l and 'Have fun' not in l]
            log_add(f"❌ [{host}] Falhou ao iniciar: {' | '.join(lines[-2:])[:100]}", "error")
            return False
            
    except Exception as e:
        log_add(f"❌ [{host}] Erro: {str(e)[:80]}", "error")
        return False


def run_solver_on_all_machines(tabs: int = 5):
    """
    Executa o solver em todas as máquinas conectadas.
    Assume que o arquivo já foi enviado via 'Enviar Arquivo'.
    """
    global should_stop
    should_stop = False
    
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        log_add("❌ Nenhuma máquina disponível! Sincronize primeiro.", "error")
        return 0
    
    log_add(f"▶️ Iniciando solver em {len(current_machines)} máquinas ({tabs} tabs cada)...", "info")
    
    with stats_lock:
        stats["start_time"] = time.time()
    
    success_count = 0
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(run_solver_on_machine, m, tabs): m 
            for m in current_machines
        }
        
        for future in as_completed(futures):
            if should_stop:
                break
            
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                log_add(f"Erro ao iniciar: {e}", "error")
    
    with stats_lock:
        stats["running_machines"] = success_count
    
    log_add(f"✅ Solver iniciado em {success_count}/{len(current_machines)} máquinas", "success")
    
    return success_count


def kill_all_machines():
    """Mata processos em todas as máquinas"""
    global should_stop
    should_stop = True
    
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        log_add("Nenhuma máquina para parar", "warning")
        return
    
    log_add(f"🛑 Parando processos em {len(current_machines)} máquinas...", "warning")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(kill_machine_processes, current_machines))
    
    # Atualiza status das máquinas
    with machines_lock:
        for m in machines:
            m["status"] = "stopped"
            m["processes"] = 0
    
    with stats_lock:
        stats["running_machines"] = 0
    
    log_add("✅ Todos os processos foram finalizados", "success")


# ============================================================
# FETCH TOKENS
# ============================================================

def fetch_tokens_from_machine(machine: dict):
    """Baixa tokens de uma máquina"""
    host = machine["host"]
    
    success, output = run_ssh_command(
        machine,
        "cat /tmp/turnstile_tokens.jsonl 2>/dev/null || echo ''",
        timeout=60
    )
    
    tokens = []
    if success and output.strip():
        for line in output.strip().split("\n"):
            try:
                token_data = json.loads(line)
                token_data["source_host"] = host
                token_data["machine_id"] = machine["id"]
                tokens.append(token_data)
            except:
                pass
    
    return tokens


def fetch_all_tokens():
    """Baixa tokens de todas as máquinas"""
    with machines_lock:
        current_machines = machines.copy()
    
    log_add("📥 Baixando tokens de todas as máquinas...", "info")
    
    all_tokens = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_tokens_from_machine, m): m for m in current_machines}
        
        for future in as_completed(futures):
            machine = futures[future]
            try:
                tokens = future.result()
                all_tokens.extend(tokens)
                if tokens:
                    log_add(f"✅ [{machine['host']}] {len(tokens)} tokens", "success")
            except Exception as e:
                log_add(f"⚠️ [{machine['host']}] Erro: {e}", "warning")
    
    # Salva em arquivo
    if all_tokens:
        with open("all_tokens.jsonl", "w", encoding="utf-8") as f:
            for t in all_tokens:
                f.write(json.dumps(t) + "\n")
        log_add(f"✅ Total: {len(all_tokens)} tokens salvos em all_tokens.jsonl", "success")
    else:
        log_add("⚠️ Nenhum token encontrado", "warning")
    
    return all_tokens


# ============================================================
# LOGS EM TEMPO REAL
# ============================================================

def get_machine_logs(machine: dict, lines: int = 50):
    """Obtém logs recentes de uma máquina"""
    success, output = run_ssh_command(
        machine,
        f"tail -{lines} /tmp/solver.log 2>/dev/null || echo 'Sem logs disponíveis'",
        timeout=30
    )
    
    return output if success else "Erro ao obter logs"


# ============================================================
# HTML TEMPLATE
# ============================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Solver Deploy Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-primary: #0d0f1a;
            --bg-secondary: #161929;
            --bg-tertiary: #1e2235;
            --accent-primary: #00d4aa;
            --accent-secondary: #7c3aed;
            --accent-danger: #ef4444;
            --accent-warning: #f59e0b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --border-color: rgba(255,255,255,0.08);
        }
        
        body {
            font-family: 'Outfit', sans-serif;
            background: var(--bg-primary);
            min-height: 100vh;
            color: var(--text-primary);
        }
        
        /* Background Pattern */
        body::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: 
                radial-gradient(ellipse at 20% 20%, rgba(124, 58, 237, 0.15) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(0, 212, 170, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(0, 0, 0, 0.5) 0%, transparent 100%);
            pointer-events: none;
            z-index: -1;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }
        
        /* Header */
        header {
            text-align: center;
            padding: 40px 30px;
            background: var(--bg-secondary);
            border-radius: 20px;
            margin-bottom: 24px;
            border: 1px solid var(--border-color);
            position: relative;
            overflow: hidden;
        }
        
        header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
        }
        
        header h1 {
            font-size: 2.8rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }
        
        header p {
            color: var(--text-secondary);
            font-size: 1.1rem;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }
        
        @media (max-width: 1200px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
        
        @media (max-width: 600px) {
            .stats-grid { grid-template-columns: 1fr; }
        }
        
        .stat-card {
            background: var(--bg-secondary);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            border: 1px solid var(--border-color);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .stat-card:hover {
            transform: translateY(-4px);
            border-color: var(--accent-primary);
            box-shadow: 0 20px 40px rgba(0, 212, 170, 0.1);
        }
        
        .stat-card .icon {
            font-size: 2.5rem;
            margin-bottom: 12px;
            display: inline-block;
        }
        
        .stat-card .value {
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--accent-primary);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .stat-card .label {
            color: var(--text-secondary);
            font-size: 0.95rem;
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .stat-card:nth-child(2) .value { color: #3b82f6; }
        .stat-card:nth-child(3) .value { color: var(--accent-secondary); }
        .stat-card:nth-child(4) .value { color: var(--accent-warning); font-style: italic; }
        
        /* Panel */
        .panel {
            background: var(--bg-secondary);
            border-radius: 20px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid var(--border-color);
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .panel-title {
            font-size: 1.4rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .panel-badge {
            background: var(--bg-tertiary);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.9rem;
            color: var(--text-secondary);
        }
        
        /* Buttons */
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 12px;
            cursor: pointer;
            font-size: 0.95rem;
            font-weight: 600;
            font-family: 'Outfit', sans-serif;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn:hover { transform: translateY(-2px); }
        .btn:active { transform: translateY(0); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-primary), #00b894);
            color: #000;
            box-shadow: 0 4px 20px rgba(0, 212, 170, 0.3);
        }
        
        .btn-primary:hover { box-shadow: 0 6px 30px rgba(0, 212, 170, 0.4); }
        
        .btn-danger {
            background: linear-gradient(135deg, var(--accent-danger), #dc2626);
            color: #fff;
            box-shadow: 0 4px 20px rgba(239, 68, 68, 0.3);
        }
        
        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        
        .btn-secondary:hover { border-color: var(--accent-primary); }
        
        .actions {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        
        /* Config */
        .config-group {
            display: flex;
            gap: 20px;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .config-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .config-item label {
            color: var(--text-secondary);
            font-size: 0.95rem;
        }
        
        .config-item input[type="number"] {
            width: 80px;
            padding: 10px 14px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-primary);
            font-size: 1rem;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .config-item input:focus {
            outline: none;
            border-color: var(--accent-primary);
        }
        
        /* Machine Grid */
        .machine-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 16px;
        }
        
        .machine-card {
            background: var(--bg-tertiary);
            border-radius: 14px;
            padding: 18px;
            border: 1px solid var(--border-color);
            transition: all 0.2s ease;
        }
        
        .machine-card:hover {
            border-color: rgba(0, 212, 170, 0.3);
        }
        
        .machine-card .header {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 14px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .machine-card .host {
            font-weight: 600;
            font-size: 1rem;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .machine-card .id {
            font-size: 0.8rem;
            color: var(--text-secondary);
            background: var(--bg-primary);
            padding: 2px 8px;
            border-radius: 6px;
        }
        
        .machine-card .info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            font-size: 0.9rem;
        }
        
        .machine-card .info-item {
            color: var(--text-secondary);
        }
        
        .machine-card .info-item span {
            color: var(--accent-primary);
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }
        
        /* Status Dot */
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            flex-shrink: 0;
        }
        
        .status-running { 
            background: var(--accent-primary); 
            box-shadow: 0 0 12px var(--accent-primary);
            animation: pulse 2s infinite;
        }
        
        .status-connected { 
            background: #22c55e;
            box-shadow: 0 0 10px #22c55e;
        }
        
        .status-stopped { background: var(--accent-danger); }
        .status-unknown { background: #64748b; }
        .status-offline { background: var(--accent-danger); opacity: 0.6; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(0.95); }
        }
        
        /* Logs */
        .logs-container {
            background: var(--bg-primary);
            border-radius: 12px;
            padding: 16px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            line-height: 1.6;
        }
        
        .logs-container::-webkit-scrollbar {
            width: 8px;
        }
        
        .logs-container::-webkit-scrollbar-track {
            background: var(--bg-tertiary);
            border-radius: 4px;
        }
        
        .logs-container::-webkit-scrollbar-thumb {
            background: var(--accent-primary);
            border-radius: 4px;
        }
        
        .log-entry {
            padding: 6px 0;
            border-bottom: 1px solid rgba(255,255,255,0.03);
        }
        
        .log-time { 
            color: #64748b; 
            margin-right: 12px;
        }
        
        .log-success { color: var(--accent-primary); }
        .log-error { color: var(--accent-danger); }
        .log-warning { color: var(--accent-warning); }
        .log-info { color: #60a5fa; }
        
        /* Loading */
        .loading {
            position: relative;
            pointer-events: none;
        }
        
        .loading::after {
            content: '';
            position: absolute;
            inset: 0;
            background: rgba(0, 0, 0, 0.5);
            border-radius: inherit;
        }
        
        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: var(--accent-primary);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        
        .empty-state .icon { font-size: 4rem; margin-bottom: 16px; opacity: 0.5; }
        .empty-state p { max-width: 300px; margin: 0 auto; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🚀 Solver Deploy Dashboard</h1>
            <p>Controle de Deploy e Monitoramento de Solvers via Vast.ai</p>
        </header>
        
        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="icon">🎫</div>
                <div class="value" id="totalTokens">0</div>
                <div class="label">Tokens Totais</div>
            </div>
            <div class="stat-card">
                <div class="icon">💻</div>
                <div class="value" id="runningMachines">0</div>
                <div class="label">Máquinas Rodando</div>
            </div>
            <div class="stat-card">
                <div class="icon">📊</div>
                <div class="value" id="totalMachines">0</div>
                <div class="label">Total Máquinas</div>
            </div>
            <div class="stat-card">
                <div class="icon">⏱️</div>
                <div class="value" id="runtime">0:00</div>
                <div class="label">Tempo Rodando</div>
            </div>
        </div>
        
        <!-- Controls -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">⚙️ Controles</div>
            </div>
            
            <div class="config-group">
                <div class="config-item">
                    <label>Tabs por máquina:</label>
                    <input type="number" id="tabsPerMachine" value="5" min="1" max="20">
                </div>
            </div>
            
            <div class="actions">
                <button class="btn btn-secondary" onclick="syncVast()" id="btnSync">
                    🔄 Sincronizar Vast.ai
                </button>
                <button class="btn btn-secondary" onclick="updateStatus()" id="btnStatus">
                    📊 Atualizar Status
                </button>
                <button class="btn btn-secondary" onclick="sendFile()" id="btnSendFile">
                    📤 Enviar Arquivo
                </button>
                <button class="btn btn-secondary" onclick="installDeps()" id="btnInstallDeps">
                    📦 Instalar Dependências
                </button>
                <button class="btn btn-primary" onclick="deploySimple()" id="btnDeploySimple">
                    🚀 Deploy Completo
                </button>
                <button class="btn btn-primary" onclick="runSolver()" id="btnRunSolver" style="background: linear-gradient(135deg, #22c55e, #16a34a);">
                    ▶️ Rodar Solver
                </button>
                <button class="btn btn-danger" onclick="killAll()" id="btnKill">
                    ⏹️ Parar Solver
                </button>
                <button class="btn btn-secondary" onclick="fetchTokens()" id="btnTokens">
                    📥 Baixar Tokens
                </button>
            </div>
        </div>
        
        <!-- Machines -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">💻 Máquinas</div>
                <span class="panel-badge" id="machineCount">0 máquinas</span>
            </div>
            <div class="machine-grid" id="machineGrid">
                <div class="empty-state">
                    <div class="icon">🔌</div>
                    <p>Clique em "Sincronizar Vast.ai" para carregar as máquinas</p>
                </div>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">📋 Logs</div>
                <button class="btn btn-secondary" onclick="clearLogs()">🗑️ Limpar</button>
            </div>
            <div class="logs-container" id="logsContainer">
                <div class="log-entry log-info">
                    <span class="log-time">[--:--:--]</span>
                    Sistema iniciado. Clique em "Sincronizar Vast.ai" para começar.
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let startTime = null;
        
        // Auto-update
        setInterval(updateStats, 5000);
        setInterval(updateRuntime, 1000);
        setInterval(fetchLogs, 3000);
        
        function updateStats() {
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('totalTokens').textContent = data.total_tokens;
                    document.getElementById('runningMachines').textContent = data.running_machines;
                    document.getElementById('totalMachines').textContent = data.total_machines;
                    if (data.start_time) {
                        startTime = data.start_time * 1000;
                    }
                });
        }
        
        function updateRuntime() {
            if (startTime) {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const mins = Math.floor(elapsed / 60);
                const secs = elapsed % 60;
                document.getElementById('runtime').textContent = 
                    `${mins}:${secs.toString().padStart(2, '0')}`;
            }
        }
        
        function setLoading(loading) {
            const btns = document.querySelectorAll('.btn');
            btns.forEach(btn => btn.disabled = loading);
        }
        
        function syncVast() {
            setLoading(true);
            document.getElementById('btnSync').innerHTML = '<span class="spinner"></span> Sincronizando...';
            
            fetch('/api/sync-vast', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    renderMachines(data.machines);
                    updateStats();
                    fetchLogs();
                    
                    // Aguarda verificação de conexões
                    setTimeout(() => {
                        fetch('/api/machines').then(r => r.json())
                            .then(d => renderMachines(d.machines));
                        fetchLogs();
                    }, 5000);
                })
                .finally(() => {
                    setLoading(false);
                    document.getElementById('btnSync').innerHTML = '🔄 Sincronizar Vast.ai';
                });
        }
        
        function updateStatus() {
            setLoading(true);
            document.getElementById('btnStatus').innerHTML = '<span class="spinner"></span> Atualizando...';
            
            fetch('/api/update-status', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    renderMachines(data.machines);
                    updateStats();
                    fetchLogs();
                })
                .finally(() => {
                    setLoading(false);
                    document.getElementById('btnStatus').innerHTML = '📊 Atualizar Status';
                });
        }
        
        function sendFile() {
            if (!confirm('Enviar arquivo turnstile_persistent_solver.py para todas as máquinas?')) return;
            
            setLoading(true);
            document.getElementById('btnSendFile').innerHTML = '<span class="spinner"></span> Enviando...';
            
            fetch('/api/send-file', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    fetchLogs();
                    alert(`✅ Arquivo enviado para ${data.success_count}/${data.total_count} máquinas`);
                })
                .finally(() => {
                    setLoading(false);
                    document.getElementById('btnSendFile').innerHTML = '📤 Enviar Arquivo';
                });
        }
        
        function installDeps() {
            if (!confirm('Instalar dependências (python3, pip, patchright, playwright, chromium) em todas as máquinas?\\n\\nIsso pode demorar alguns minutos.')) return;
            
            setLoading(true);
            document.getElementById('btnInstallDeps').innerHTML = '<span class="spinner"></span> Instalando...';
            
            fetch('/api/install-deps', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    fetchLogs();
                    alert(`✅ Dependências instaladas em ${data.success_count}/${data.total_count} máquinas`);
                })
                .finally(() => {
                    setLoading(false);
                    document.getElementById('btnInstallDeps').innerHTML = '📦 Instalar Dependências';
                });
        }
        
        function deploySimple() {
            const tabs = document.getElementById('tabsPerMachine').value;
            
            if (!confirm(`Deploy simples com ${tabs} tabs em todas as máquinas?\n\nIsso irá:\n• Enviar o solver\n• Instalar patchright\n• Instalar Chromium\n• Executar solver`)) return;
            
            setLoading(true);
            document.getElementById('btnDeploySimple').innerHTML = '<span class="spinner"></span> Deploying...';
            
            fetch('/api/deploy-simple', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tabs: parseInt(tabs) })
            })
                .then(r => r.json())
                .then(data => {
                    fetchLogs();
                    // Aguarda deploy e atualiza status
                    setTimeout(() => {
                        updateStatus();
                        setLoading(false);
                        document.getElementById('btnDeploySimple').innerHTML = '📦 Deploy Simples';
                    }, 15000);
                });
        }
        
        function runSolver() {
            const tabs = document.getElementById('tabsPerMachine').value;
            
            if (!confirm(`▶️ Rodar solver com ${tabs} tabs em todas as máquinas?\n\nNota: O arquivo deve ter sido enviado antes via "Enviar Arquivo" ou "Deploy Completo".`)) return;
            
            setLoading(true);
            document.getElementById('btnRunSolver').innerHTML = '<span class="spinner"></span> Iniciando...';
            
            fetch('/api/run-solver', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tabs: parseInt(tabs) })
            })
                .then(r => r.json())
                .then(data => {
                    fetchLogs();
                    setTimeout(() => {
                        updateStatus();
                        setLoading(false);
                        document.getElementById('btnRunSolver').innerHTML = '▶️ Rodar Solver';
                    }, 8000);
                });
        }
        
        function killAll() {
            if (!confirm('⚠️ Parar solver em TODAS as máquinas?')) return;
            
            setLoading(true);
            document.getElementById('btnKill').innerHTML = '<span class="spinner"></span> Parando...';
            
            fetch('/api/kill-all', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    fetchLogs();
                    setTimeout(() => {
                        updateStatus();
                        setLoading(false);
                        document.getElementById('btnKill').innerHTML = '⏹️ Parar Solver';
                    }, 3000);
                });
        }
        
        function fetchTokens() {
            setLoading(true);
            document.getElementById('btnTokens').innerHTML = '<span class="spinner"></span> Baixando...';
            
            fetch('/api/fetch-tokens', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    fetchLogs();
                    alert(`✅ ${data.count} tokens baixados e salvos em all_tokens.jsonl`);
                })
                .finally(() => {
                    setLoading(false);
                    document.getElementById('btnTokens').innerHTML = '📥 Baixar Tokens';
                });
        }
        
        function fetchLogs() {
            fetch('/api/logs')
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('logsContainer');
                    container.innerHTML = data.logs.map(log => `
                        <div class="log-entry log-${log.level}">
                            <span class="log-time">[${log.time}]</span>
                            ${log.msg}
                        </div>
                    `).join('');
                    container.scrollTop = container.scrollHeight;
                });
        }
        
        function clearLogs() {
            fetch('/api/clear-logs', { method: 'POST' })
                .then(() => fetchLogs());
        }
        
        function renderMachines(machines) {
            const grid = document.getElementById('machineGrid');
            document.getElementById('machineCount').textContent = `${machines.length} máquinas`;
            
            if (!machines || machines.length === 0) {
                grid.innerHTML = `
                    <div class="empty-state">
                        <div class="icon">🔌</div>
                        <p>Nenhuma máquina encontrada. Verifique se você tem instâncias ativas na Vast.ai</p>
                    </div>
                `;
                return;
            }
            
            grid.innerHTML = machines.map(m => `
                <div class="machine-card">
                    <div class="header">
                        <span class="status-dot status-${m.status}"></span>
                        <span class="host">${m.host}:${m.port}</span>
                        <span class="id">ID: ${m.id}</span>
                    </div>
                    <div class="info">
                        <div class="info-item">Tokens: <span>${m.tokens}</span></div>
                        <div class="info-item">Processos: <span>${m.processes}</span></div>
                        <div class="info-item">GPU: <span>${m.gpu}</span></div>
                        <div class="info-item">RAM: <span>${m.cpu_ram} GB</span></div>
                    </div>
                </div>
            `).join('');
        }
        
        // Initial load
        fetchLogs();
    </script>
</body>
</html>
'''


# ============================================================
# API ROUTES
# ============================================================

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/stats")
def api_stats():
    with stats_lock:
        return jsonify(stats)


@app.route("/api/logs")
def api_logs():
    with logs_lock:
        return jsonify({"logs": logs[-150:]})


@app.route("/api/clear-logs", methods=["POST"])
def api_clear_logs():
    global logs
    with logs_lock:
        logs = [{"time": datetime.now().strftime("%H:%M:%S"), "msg": "Logs limpos", "level": "info"}]
    return jsonify({"success": True})


@app.route("/api/machines")
def api_machines():
    with machines_lock:
        return jsonify({"machines": machines})


@app.route("/api/sync-vast", methods=["POST"])
def api_sync_vast():
    result = fetch_vast_instances()
    
    # Verifica conexões em background
    thread = threading.Thread(target=verify_all_connections)
    thread.start()
    
    with machines_lock:
        return jsonify({"machines": machines})


@app.route("/api/update-status", methods=["POST"])
def api_update_status():
    thread = threading.Thread(target=update_all_status)
    thread.start()
    thread.join(timeout=120)
    
    with machines_lock:
        return jsonify({"machines": machines})


@app.route("/api/deploy", methods=["POST"])
def api_deploy():
    data = request.json or {}
    tabs = data.get("tabs", 5)
    
    log_add(f"📥 Recebido pedido de deploy com {tabs} tabs", "info")
    
    config = get_config()
    config["tabs_per_machine"] = tabs
    save_config(config)
    
    with machines_lock:
        count = len(machines)
    
    if count == 0:
        log_add("❌ Nenhuma máquina disponível! Sincronize primeiro.", "error")
        return jsonify({"success": False, "message": "Nenhuma máquina"})
    
    log_add(f"🚀 Iniciando deploy em {count} máquinas...", "info")
    
    thread = threading.Thread(target=deploy_all_machines)
    thread.start()
    
    return jsonify({"success": True, "message": f"Deploy iniciado em {count} máquinas"})


@app.route("/api/deploy-simple", methods=["POST"])
def api_deploy_simple():
    """
    Deploy simplificado - envia apenas o solver e instala deps mínimas.
    Mais rápido e leve que o deploy completo.
    """
    data = request.json or {}
    tabs = data.get("tabs", 5)
    
    log_add(f"📦 Deploy simples solicitado ({tabs} tabs)", "info")
    
    with machines_lock:
        count = len(machines)
    
    if count == 0:
        log_add("❌ Nenhuma máquina! Sincronize primeiro.", "error")
        return jsonify({"success": False, "message": "Nenhuma máquina"})
    
    # Salva config
    config = get_config()
    config["tabs_per_machine"] = tabs
    save_config(config)
    
    log_add(f"🚀 Deploy simples em {count} máquinas...", "info")
    
    # Executa em background
    def run_deploy():
        deploy_all_simple(tabs)
        time.sleep(3)
        update_all_status()
    
    thread = threading.Thread(target=run_deploy)
    thread.start()
    
    return jsonify({"success": True, "message": f"Deploy simples iniciado em {count} máquinas"})


@app.route("/api/deploy-single/<int:machine_id>", methods=["POST"])
def api_deploy_single(machine_id):
    """Deploy simples em uma máquina específica"""
    data = request.json or {}
    tabs = data.get("tabs", 5)
    
    with machines_lock:
        machine = next((m for m in machines if m["id"] == machine_id), None)
    
    if not machine:
        return jsonify({"success": False, "error": "Máquina não encontrada"})
    
    log_add(f"🚀 Deploy simples em [{machine['host']}] ({tabs} tabs)...", "info")
    
    def run_single():
        deploy_solver_simple(machine, tabs)
    
    thread = threading.Thread(target=run_single)
    thread.start()
    
    return jsonify({"success": True, "message": f"Deploy iniciado em {machine['host']}"})


@app.route("/api/send-file", methods=["POST"])
def api_send_file():
    """Envia apenas o arquivo solver para todas as máquinas (sem instalar deps)"""
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        log_add("❌ Nenhuma máquina! Sincronize primeiro.", "error")
        return jsonify({"success": False, "success_count": 0, "total_count": 0})
    
    log_add(f"📤 Enviando arquivo para {len(current_machines)} máquinas...", "info")
    
    def send_to_all():
        success = send_file_to_all_machines()
        return success
    
    thread = threading.Thread(target=send_to_all)
    thread.start()
    thread.join(timeout=180)
    
    # Conta sucessos
    success_count = sum(1 for m in current_machines if m.get("file_sent"))
    
    return jsonify({
        "success": True, 
        "success_count": success_count, 
        "total_count": len(current_machines)
    })


@app.route("/api/install-deps", methods=["POST"])
def api_install_deps():
    """Instala dependências (python3, pip, patchright, playwright, chromium) em todas as máquinas"""
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        log_add("❌ Nenhuma máquina! Sincronize primeiro.", "error")
        return jsonify({"success": False, "success_count": 0, "total_count": 0})
    
    log_add(f"📦 Instalando dependências em {len(current_machines)} máquinas...", "info")
    
    success_count = 0
    
    def install_on_all():
        nonlocal success_count
        for machine in current_machines:
            try:
                result = install_requirements(machine)
                if result:
                    success_count += 1
            except Exception as e:
                log_add(f"❌ [{machine['host']}] Erro: {e}", "error")
    
    thread = threading.Thread(target=install_on_all)
    thread.start()
    thread.join(timeout=600)  # 10 min timeout
    
    return jsonify({
        "success": True,
        "success_count": success_count,
        "total_count": len(current_machines)
    })


@app.route("/api/run-solver", methods=["POST"])
def api_run_solver():
    """
    Executa o solver em todas as máquinas.
    O arquivo deve ter sido enviado antes via 'Enviar Arquivo'.
    """
    data = request.json or {}
    tabs = data.get("tabs", 5)
    
    log_add(f"▶️ Recebido pedido para rodar solver ({tabs} tabs)", "info")
    
    with machines_lock:
        count = len(machines)
    
    if count == 0:
        log_add("❌ Nenhuma máquina! Sincronize primeiro.", "error")
        return jsonify({"success": False, "message": "Nenhuma máquina"})
    
    # Executa em background
    def run_solver():
        run_solver_on_all_machines(tabs)
        time.sleep(3)
        update_all_status()
    
    thread = threading.Thread(target=run_solver)
    thread.start()
    
    return jsonify({"success": True, "message": f"Iniciando solver em {count} máquinas"})


@app.route("/api/kill-all", methods=["POST"])
def api_kill_all():
    log_add("🛑 Recebido pedido para parar todos os processos", "warning")
    
    thread = threading.Thread(target=kill_all_machines)
    thread.start()
    
    return jsonify({"success": True, "message": "Kill iniciado"})


@app.route("/api/fetch-tokens", methods=["POST"])
def api_fetch_tokens():
    tokens = fetch_all_tokens()
    return jsonify({"success": True, "count": len(tokens)})


@app.route("/api/machine-logs/<int:machine_id>")
def api_machine_logs(machine_id):
    """Obtém logs de uma máquina específica"""
    with machines_lock:
        machine = next((m for m in machines if m["id"] == machine_id), None)
    
    if not machine:
        return jsonify({"success": False, "error": "Máquina não encontrada"})
    
    logs_content = get_machine_logs(machine)
    return jsonify({"success": True, "logs": logs_content})


@app.route("/api/check-requirements/<int:machine_id>")
def api_check_requirements(machine_id):
    """Verifica requisitos de uma máquina"""
    with machines_lock:
        machine = next((m for m in machines if m["id"] == machine_id), None)
    
    if not machine:
        return jsonify({"success": False, "error": "Máquina não encontrada"})
    
    reqs = check_machine_requirements(machine)
    return jsonify({"success": True, "requirements": reqs})


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("🚀 SOLVER DEPLOY DASHBOARD")
    print("=" * 60)
    print()
    print("  Dashboard para controle de deploy de solvers via Vast.ai")
    print()
    print("  📌 Acesse: http://localhost:5020")
    print()
    print("  Funcionalidades:")
    print("    • Sincronizar máquinas Vast.ai")
    print("    • Deploy automático do solver")
    print("    • Monitoramento de status e logs")
    print("    • Parar processos em todas as máquinas")
    print("    • Baixar tokens gerados")
    print()
    print("=" * 60)
    print()
    
    # Adiciona log inicial
    log_add("Dashboard iniciado. Clique em 'Sincronizar Vast.ai' para começar.", "info")
    
    # Inicia Flask
    app.run(
        host="0.0.0.0",
        port=5020,
        debug=False,
        threaded=True
    )

