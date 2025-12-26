"""
Dashboard Solver Remote - Controle de Solvers via SSH
======================================================
Baseado no dashboard_browserless_v3.py

Funcionalidades:
- Sincronização com Vast.ai
- Deploy solver em máquinas remotas
- Kill processos em todas as máquinas
- Status em tempo real
- Fetch tokens
- Logs em tempo real
"""

import json
import os
import sys
import time
import subprocess
import threading
import requests
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, Response
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

VAST_API_KEY = "aedf78cb67968495b0e91b71886b7444fd24d9146ce0da4c12cd5a356451d6c7"
VAST_API_URL = "https://console.vast.ai/api/v0/instances/"
CONFIG_FILE = "solver_remote_config.json"
SOLVER_FILE = "turnstile_remote_solver.py"

# Estado global
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

# Processos em execução
running_processes = {}
processes_lock = threading.Lock()
should_stop = False


def log_add(msg: str, level: str = "info"):
    """Adiciona log"""
    with logs_lock:
        logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "msg": msg,
            "level": level
        })
        # Mantém últimos 200 logs
        if len(logs) > 200:
            logs.pop(0)


def get_config():
    """Carrega configuração"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {
        "tabs_per_machine": 5,
        "use_proxy": True,
        "headless": True
    }


def save_config(config):
    """Salva configuração"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ============================================================
# VAST.AI
# ============================================================

def fetch_vast_instances():
    """Busca instâncias na Vast.ai"""
    global machines
    
    log_add("🔄 Buscando instâncias na Vast.ai...")
    
    try:
        headers = {"Authorization": f"Bearer {VAST_API_KEY}"}
        resp = requests.get(VAST_API_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        
        data = resp.json()
        instances = data.get("instances", [])
        
        running = [i for i in instances if i.get("actual_status") == "running"]
        log_add(f"📋 {len(running)} instâncias running encontradas", "info")
        
        result = []
        for inst in running:
            instance_id = inst.get("id")
            
            # SSH da Vast.ai (usa proxy SSH)
            ssh_host = inst.get("ssh_host")
            ssh_port = inst.get("ssh_port")
            public_ip = inst.get("public_ipaddr")
            
            # Log detalhado com todas as infos
            log_add(f"📌 [{instance_id}] SSH: {ssh_host}:{ssh_port} | IP: {public_ip}", "info")
            
            if ssh_host and ssh_port:
                result.append({
                    "id": instance_id,
                    "host": ssh_host,
                    "port": ssh_port,
                    "public_ip": public_ip,  # Guardar IP público também
                    "gpu": inst.get("gpu_name", "Unknown"),
                    "ram": round(inst.get("cpu_ram", 0) / 1024, 1),
                    "status": "unknown",
                    "tokens": 0,
                    "processes": 0
                })
            else:
                log_add(f"⚠️ [{instance_id}] Sem SSH configurado (host={ssh_host}, port={ssh_port})", "warning")
        
        with machines_lock:
            machines = result
        
        log_add(f"✅ {len(result)} máquinas prontas para SSH", "success")
        
        with stats_lock:
            stats["total_machines"] = len(result)
        
        return result
        
    except requests.exceptions.RequestException as e:
        log_add(f"❌ Erro ao conectar Vast.ai: {e}", "error")
        return []
    except Exception as e:
        log_add(f"❌ Erro: {e}", "error")
        return []


# ============================================================
# SSH COMMANDS
# ============================================================

def run_ssh_command(machine: dict, command: str, timeout: int = 30):
    """Executa comando SSH"""
    host = machine["host"]
    port = machine["port"]
    
    try:
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            "-p", str(port),
            f"root@{host}",
            command
        ]
        
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout + result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def check_ssh_connection(machine: dict):
    """Verifica se SSH está acessível"""
    host = machine["host"]
    port = machine["port"]
    
    success, output = run_ssh_command(machine, "echo OK", timeout=15)
    if success and "OK" in output:
        return True
    return False


def verify_all_connections():
    """Verifica conexão SSH de todas as máquinas"""
    global machines
    
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        return
    
    log_add("🔍 Verificando conexões SSH...")
    
    connected = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_ssh_connection, m): m for m in current_machines}
        
        for future in as_completed(futures):
            machine = futures[future]
            try:
                is_connected = future.result()
                
                with machines_lock:
                    for m in machines:
                        if m["host"] == machine["host"] and m["port"] == machine["port"]:
                            m["status"] = "connected" if is_connected else "offline"
                            break
                
                if is_connected:
                    connected += 1
                    log_add(f"🟢 [{machine['host']}:{machine['port']}] Conectado", "success")
                else:
                    log_add(f"🔴 [{machine['host']}:{machine['port']}] Offline", "error")
                    
            except Exception as e:
                log_add(f"⚠️ [{machine['host']}] Erro: {e}", "warning")
    
    log_add(f"✅ {connected}/{len(current_machines)} máquinas conectadas", "success")


def get_machine_status(machine: dict):
    """Verifica status de uma máquina"""
    host = machine["host"]
    port = machine["port"]
    
    # Processos rodando
    success, output = run_ssh_command(machine, "ps aux | grep -E 'turnstile|patchright' | grep -v grep | wc -l")
    processes = 0
    if success:
        try:
            processes = int(output.strip())
        except:
            pass
    else:
        log_add(f"⚠️ [{host}:{port}] SSH falhou: {output[:50]}", "warning")
    
    # Tokens salvos
    success2, output2 = run_ssh_command(machine, "wc -l < /tmp/turnstile_tokens.jsonl 2>/dev/null || echo 0")
    tokens = 0
    if success2:
        try:
            tokens = int(output2.strip())
        except:
            pass
    
    # Log do status
    if processes > 0:
        log_add(f"🟢 [{host}] {processes} processos, {tokens} tokens", "success")
    
    return {
        "running": processes > 0,
        "processes": processes,
        "tokens": tokens
    }


def update_all_status():
    """Atualiza status de todas as máquinas"""
    global machines
    
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        return
    
    log_add("🔄 Atualizando status...")
    
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
                        if m["host"] == machine["host"] and m["port"] == machine["port"]:
                            m["status"] = "running" if status["running"] else "stopped"
                            m["processes"] = status["processes"]
                            m["tokens"] = status["tokens"]
                            break
                
                total_tokens += status["tokens"]
                if status["running"]:
                    running_count += 1
                    
            except Exception as e:
                log_add(f"❌ Erro status {machine['host']}: {e}", "error")
    
    with stats_lock:
        stats["total_tokens"] = total_tokens
        stats["running_machines"] = running_count
    
    log_add(f"✅ Status atualizado: {running_count} rodando, {total_tokens} tokens", "success")


def kill_machine(machine: dict):
    """Mata processos em uma máquina"""
    host = machine["host"]
    port = machine["port"]
    
    log_add(f"🛑 Matando processos em {host}:{port}...")
    
    commands = "pkill -f turnstile ; pkill -f patchright ; pkill -f chromium ; killall python3 2>/dev/null || true"
    success, output = run_ssh_command(machine, commands)
    
    if success:
        log_add(f"✅ [{host}] Processos finalizados", "success")
    else:
        log_add(f"⚠️ [{host}] Possível erro: {output[:50]}", "warning")
    
    return success


def kill_all_machines():
    """Mata processos em todas as máquinas"""
    global should_stop
    should_stop = True
    
    with machines_lock:
        current_machines = machines.copy()
    
    log_add("🛑 Matando processos em todas as máquinas...", "warning")
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(kill_machine, current_machines))
    
    log_add("✅ Todos os processos foram finalizados", "success")
    
    # Atualiza status
    time.sleep(2)
    update_all_status()


def deploy_to_machine(machine: dict, solver_content: str, config: dict):
    """Deploy solver em uma máquina"""
    global should_stop
    
    if should_stop:
        return False
    
    host = machine["host"]
    port = machine["port"]
    tabs = config.get("tabs_per_machine", 5)
    
    log_add(f"🚀 Deploy em {host}:{port} ({tabs} tabs)...")
    
    try:
        # Script que instala deps e roda solver
        remote_script = f'''#!/bin/bash
cd /tmp

# Mata processos anteriores
pkill -f turnstile 2>/dev/null || true
pkill -f patchright 2>/dev/null || true

# Instala patchright se necessário
pip3 install patchright -q 2>/dev/null || pip install patchright -q 2>/dev/null

# Instala browser
python3 -m patchright install chromium 2>/dev/null || true

# Salva solver
cat > turnstile_solver.py << 'SOLVER_EOF'
{solver_content}
SOLVER_EOF

# Executa em background
nohup python3 turnstile_solver.py --tabs {tabs} --skip-install > /tmp/solver.log 2>&1 &

echo "DEPLOY_OK"
'''
        
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=30",
            "-p", str(port),
            f"root@{host}",
            "bash -s"
        ]
        
        process = subprocess.Popen(
            ssh_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        stdout, _ = process.communicate(input=remote_script, timeout=120)
        
        # Log detalhado do output
        if stdout:
            # Pega últimas 5 linhas relevantes
            lines = [l.strip() for l in stdout.split('\n') if l.strip()][-5:]
            for line in lines:
                if 'error' in line.lower() or 'failed' in line.lower():
                    log_add(f"⚠️ [{host}] {line[:80]}", "warning")
        
        if "DEPLOY_OK" in stdout:
            log_add(f"✅ [{host}] Deploy concluído", "success")
            return True
        else:
            # Mostra erro detalhado
            error_lines = [l for l in stdout.split('\n') if l.strip()][-3:]
            log_add(f"❌ [{host}] Deploy falhou: {' | '.join(error_lines)[:100]}", "error")
            return False
        
    except subprocess.TimeoutExpired:
        log_add(f"❌ [{host}] Timeout no deploy (>120s)", "error")
        return False
    except Exception as e:
        log_add(f"❌ [{host}] Erro SSH: {str(e)[:80]}", "error")
        return False


def deploy_all_machines():
    """Deploy em todas as máquinas"""
    global should_stop
    should_stop = False
    
    with machines_lock:
        current_machines = machines.copy()
    
    if not current_machines:
        log_add("❌ Nenhuma máquina disponível", "error")
        return
    
    # Lê solver
    solver_path = os.path.join(os.path.dirname(__file__), SOLVER_FILE)
    if not os.path.exists(solver_path):
        log_add(f"❌ Arquivo {SOLVER_FILE} não encontrado", "error")
        return
    
    with open(solver_path, "r", encoding="utf-8") as f:
        solver_content = f.read()
    
    config = get_config()
    
    log_add(f"🚀 Iniciando deploy em {len(current_machines)} máquinas...", "info")
    
    with stats_lock:
        stats["start_time"] = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(deploy_to_machine, m, solver_content, config) for m in current_machines]
        for future in as_completed(futures):
            if should_stop:
                break
            try:
                future.result()
            except:
                pass
    
    # Aguarda e atualiza status
    log_add("⏳ Aguardando inicialização...", "info")
    time.sleep(10)
    update_all_status()


def fetch_all_tokens():
    """Baixa tokens de todas as máquinas"""
    with machines_lock:
        current_machines = machines.copy()
    
    log_add("📥 Baixando tokens de todas as máquinas...")
    
    all_tokens = []
    
    for machine in current_machines:
        host = machine["host"]
        port = machine["port"]
        
        success, output = run_ssh_command(machine, "cat /tmp/turnstile_tokens.jsonl 2>/dev/null || echo ''", timeout=60)
        
        if success and output.strip():
            lines = output.strip().split("\n")
            for line in lines:
                try:
                    token_data = json.loads(line)
                    token_data["source_host"] = host
                    all_tokens.append(token_data)
                except:
                    pass
            log_add(f"✅ [{host}] {len(lines)} tokens", "success")
    
    # Salva
    if all_tokens:
        with open("all_tokens.jsonl", "w") as f:
            for t in all_tokens:
                f.write(json.dumps(t) + "\n")
        log_add(f"✅ Total: {len(all_tokens)} tokens salvos em all_tokens.jsonl", "success")
    else:
        log_add("⚠️ Nenhum token encontrado", "warning")
    
    return all_tokens


# ============================================================
# HTML TEMPLATE
# ============================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔐 Solver Remote Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
            min-height: 100vh;
            color: #fff;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            text-align: center;
            padding: 30px 0;
            background: rgba(0,0,0,0.3);
            border-radius: 16px;
            margin-bottom: 20px;
        }
        
        header h1 {
            font-size: 2.5rem;
            background: linear-gradient(to right, #4ade80, #22d3ee);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        header p {
            color: #888;
            font-size: 1rem;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .stat-card .icon { font-size: 2rem; margin-bottom: 10px; }
        .stat-card .value { font-size: 2rem; font-weight: bold; color: #4ade80; }
        .stat-card .label { color: #888; font-size: 0.9rem; }
        
        .panel {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .panel-title {
            font-size: 1.3rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 600;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #4ade80, #22d3ee);
            color: #000;
        }
        
        .btn-danger {
            background: linear-gradient(135deg, #ef4444, #f97316);
            color: #fff;
        }
        
        .btn-secondary {
            background: rgba(255,255,255,0.1);
            color: #fff;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .btn:hover { transform: translateY(-2px); opacity: 0.9; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .actions {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .config-group {
            display: flex;
            gap: 15px;
            align-items: center;
            margin-bottom: 15px;
            flex-wrap: wrap;
        }
        
        .config-item {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .config-item label { color: #aaa; }
        
        .config-item input[type="number"] {
            width: 80px;
            padding: 8px 12px;
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 6px;
            color: #fff;
            font-size: 1rem;
        }
        
        .machine-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }
        
        .machine-card {
            background: rgba(0,0,0,0.2);
            border-radius: 12px;
            padding: 15px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .machine-card .host {
            font-weight: 600;
            font-size: 1.1rem;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .machine-card .info {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            font-size: 0.85rem;
            color: #aaa;
        }
        
        .machine-card .info span { color: #4ade80; font-weight: 600; }
        
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            display: inline-block;
        }
        
        .status-running { background: #4ade80; box-shadow: 0 0 10px #4ade80; animation: pulse 2s infinite; }
        .status-connected { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
        .status-stopped { background: #ef4444; }
        .status-unknown { background: #888; }
        .status-offline { background: #ef4444; animation: none; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .logs-container {
            background: rgba(0,0,0,0.4);
            border-radius: 8px;
            padding: 15px;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Consolas', monospace;
            font-size: 0.85rem;
        }
        
        .log-entry {
            padding: 4px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        
        .log-time { color: #666; margin-right: 10px; }
        .log-success { color: #4ade80; }
        .log-error { color: #ef4444; }
        .log-warning { color: #f59e0b; }
        .log-info { color: #60a5fa; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .loading { animation: pulse 1s infinite; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔐 Solver Remote Dashboard</h1>
            <p>Controle de Turnstile Solvers via SSH</p>
        </header>
        
        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="icon">🎟️</div>
                <div class="value" id="totalTokens">0</div>
                <div class="label">Tokens Totais</div>
            </div>
            <div class="stat-card">
                <div class="icon">🖥️</div>
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
        
        <!-- Controles -->
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
                <button class="btn btn-secondary" onclick="syncVast()">🔄 Sincronizar Vast.ai</button>
                <button class="btn btn-secondary" onclick="updateStatus()">📊 Atualizar Status</button>
                <button class="btn btn-primary" onclick="deployAll()">🚀 Deploy Todos</button>
                <button class="btn btn-danger" onclick="killAll()">🛑 Parar Todos</button>
                <button class="btn btn-secondary" onclick="fetchTokens()">📥 Baixar Tokens</button>
            </div>
        </div>
        
        <!-- Máquinas -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">🖥️ Máquinas</div>
                <span id="machineCount">0 máquinas</span>
            </div>
            <div class="machine-grid" id="machineGrid">
                <p style="color: #666;">Clique em "Sincronizar Vast.ai" para carregar máquinas</p>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="panel">
            <div class="panel-header">
                <div class="panel-title">📋 Logs</div>
                <button class="btn btn-secondary" onclick="clearLogs()">🗑️ Limpar</button>
            </div>
            <div class="logs-container" id="logsContainer">
                <div class="log-entry log-info">Sistema iniciado</div>
            </div>
        </div>
    </div>
    
    <script>
        let startTime = null;
        
        // Atualiza stats a cada 5 segundos
        setInterval(updateStats, 5000);
        setInterval(updateRuntime, 1000);
        
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
                document.getElementById('runtime').textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
            }
        }
        
        function syncVast() {
            setLoading(true);
            fetch('/api/sync-vast', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    renderMachines(data.machines);
                    updateStats();
                    fetchLogs();
                    // Aguarda verificação de conexões e atualiza
                    setTimeout(() => {
                        fetch('/api/machines').then(r => r.json()).then(d => renderMachines(d.machines));
                        fetchLogs();
                    }, 3000);
                    setTimeout(() => {
                        fetch('/api/machines').then(r => r.json()).then(d => renderMachines(d.machines));
                        fetchLogs();
                        setLoading(false);
                    }, 8000);
                })
                .catch(() => setLoading(false));
        }
        
        function updateStatus() {
            setLoading(true);
            fetch('/api/update-status', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    renderMachines(data.machines);
                    updateStats();
                    fetchLogs();
                })
                .finally(() => setLoading(false));
        }
        
        function deployAll() {
            const tabs = document.getElementById('tabsPerMachine').value;
            
            if (!confirm(`Deploy solver com ${tabs} tabs em todas as máquinas?`)) return;
            
            setLoading(true);
            fetch('/api/deploy', { 
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
                    }, 5000);
                });
        }
        
        function killAll() {
            if (!confirm('Parar solver em TODAS as máquinas?')) return;
            
            setLoading(true);
            fetch('/api/kill-all', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    fetchLogs();
                    setTimeout(() => {
                        updateStatus();
                        setLoading(false);
                    }, 3000);
                });
        }
        
        function fetchTokens() {
            setLoading(true);
            fetch('/api/fetch-tokens', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    fetchLogs();
                    alert(`${data.count} tokens baixados para all_tokens.jsonl`);
                })
                .finally(() => setLoading(false));
        }
        
        function fetchLogs() {
            fetch('/api/logs')
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('logsContainer');
                    container.innerHTML = data.logs.map(log => 
                        `<div class="log-entry log-${log.level}">
                            <span class="log-time">[${log.time}]</span>
                            ${log.msg}
                        </div>`
                    ).join('');
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
            
            if (machines.length === 0) {
                grid.innerHTML = '<p style="color: #666;">Nenhuma máquina encontrada</p>';
                return;
            }
            
            grid.innerHTML = machines.map(m => `
                <div class="machine-card">
                    <div class="host">
                        <span class="status-dot status-${m.status}"></span>
                        ${m.host}
                    </div>
                    <div class="info">
                        <div>Porta: <span>${m.port}</span></div>
                        <div>Tokens: <span>${m.tokens}</span></div>
                        <div>Processos: <span>${m.processes}</span></div>
                        <div>GPU: <span>${m.gpu}</span></div>
                    </div>
                </div>
            `).join('');
        }
        
        function setLoading(loading) {
            const buttons = document.querySelectorAll('.btn');
            buttons.forEach(btn => btn.disabled = loading);
        }
        
        // Carrega logs a cada 3 segundos
        setInterval(fetchLogs, 3000);
        
        // Carrega inicial
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
        return jsonify({"logs": logs[-100:]})


@app.route("/api/clear-logs", methods=["POST"])
def api_clear_logs():
    global logs
    with logs_lock:
        logs = []
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


@app.route("/api/verify-connections", methods=["POST"])
def api_verify_connections():
    thread = threading.Thread(target=verify_all_connections)
    thread.start()
    return jsonify({"success": True, "message": "Verificação iniciada"})


@app.route("/api/update-status", methods=["POST"])
def api_update_status():
    thread = threading.Thread(target=update_all_status)
    thread.start()
    thread.join(timeout=60)
    
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
        log_add("❌ Nenhuma máquina disponível! Clique em 'Sincronizar' primeiro", "error")
        return jsonify({"success": False, "message": "Nenhuma máquina"})
    
    log_add(f"🚀 Iniciando deploy em {count} máquinas...", "info")
    thread = threading.Thread(target=deploy_all_machines)
    thread.start()
    
    return jsonify({"success": True, "message": f"Deploy iniciado em {count} máquinas"})


@app.route("/api/kill-all", methods=["POST"])
def api_kill_all():
    thread = threading.Thread(target=kill_all_machines)
    thread.start()
    
    return jsonify({"success": True, "message": "Kill iniciado"})


@app.route("/api/fetch-tokens", methods=["POST"])
def api_fetch_tokens():
    tokens = fetch_all_tokens()
    return jsonify({"success": True, "count": len(tokens)})


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🔐 SOLVER REMOTE DASHBOARD")
    print("=" * 60)
    print()
    print("Acesse: http://localhost:5002")
    print()
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=5002, debug=False, threaded=True)

