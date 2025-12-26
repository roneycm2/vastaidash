"""
Dashboard para monitorar servidores Ansible e status de deploy
"""

from flask import Flask, render_template_string, jsonify, request
import subprocess
import json
import yaml
import os
import threading
import time
from datetime import datetime
from pathlib import Path

app = Flask(__name__)

# Estado global dos servidores
servers_status = {}
status_lock = threading.Lock()

# Caminhos
INVENTORY_FILE = "inventory.yml"
PLAYBOOK_FILE = "deploy_golang.yml"
ANSIBLE_CFG = "ansible.cfg"

def load_inventory():
    """Carrega o arquivo inventory.yml"""
    try:
        with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Erro ao carregar inventory: {e}")
        return None

def test_server_connection(hostname, host_config):
    """Testa conexão SSH com um servidor"""
    try:
        # Executa ansible ping
        cmd = [
            "ansible",
            hostname,
            "-m", "ping",
            "-i", INVENTORY_FILE
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        return {
            "accessible": result.returncode == 0,
            "output": result.stdout + result.stderr,
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except subprocess.TimeoutExpired:
        return {
            "accessible": False,
            "output": "Timeout ao conectar",
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {
            "accessible": False,
            "output": str(e),
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

def check_code_deployed(hostname):
    """Verifica se o código foi copiado e compilado no servidor"""
    try:
        # Verifica se o executável existe
        cmd = [
            "ansible",
            hostname,
            "-m", "shell",
            "-a", "test -f /opt/abrir_site_proxy/abrir_site_proxy && echo 'EXISTS' || echo 'NOT_FOUND'",
            "-i", INVENTORY_FILE
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        executable_exists = "EXISTS" in result.stdout
        
        # Verifica se o processo está rodando
        cmd_process = [
            "ansible",
            hostname,
            "-m", "shell",
            "-a", "pgrep -f abrir_site_proxy && echo 'RUNNING' || echo 'NOT_RUNNING'",
            "-i", INVENTORY_FILE
        ]
        
        result_process = subprocess.run(
            cmd_process,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        process_running = "RUNNING" in result_process.stdout
        
        return {
            "code_copied": executable_exists,
            "process_running": process_running,
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        return {
            "code_copied": False,
            "process_running": False,
            "error": str(e),
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

def update_all_servers_status():
    """Atualiza status de todos os servidores"""
    inventory = load_inventory()
    if not inventory:
        return
    
    hosts = inventory.get('all', {}).get('hosts', {})
    
    for hostname, host_config in hosts.items():
        # Testa conexão
        connection_status = test_server_connection(hostname, host_config)
        
        # Se conectou, verifica se código foi deployado
        code_status = None
        if connection_status["accessible"]:
            code_status = check_code_deployed(hostname)
        
        with status_lock:
            servers_status[hostname] = {
                "hostname": hostname,
                "ip": host_config.get("ansible_host", "N/A"),
                "port": host_config.get("ansible_port", 22),
                "connection": connection_status,
                "code_status": code_status,
                "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

# Thread para atualizar status periodicamente
def status_updater_thread():
    """Thread que atualiza status dos servidores periodicamente"""
    # Aguarda um pouco antes de começar
    time.sleep(5)
    while True:
        try:
            update_all_servers_status()
            time.sleep(30)  # Atualiza a cada 30 segundos
        except Exception as e:
            print(f"Erro no thread de atualização: {e}")
            time.sleep(60)

# Inicia thread de atualização (não bloqueia o Flask)
updater_thread = threading.Thread(target=status_updater_thread, daemon=True)
updater_thread.start()

# Inicializa status vazio (será preenchido pela thread)
inventory = load_inventory()
if inventory:
    hosts = inventory.get('all', {}).get('hosts', {})
    for hostname, host_config in hosts.items():
        with status_lock:
            servers_status[hostname] = {
                "hostname": hostname,
                "ip": host_config.get("ansible_host", "N/A"),
                "port": host_config.get("ansible_port", 22),
                "connection": {"accessible": None, "output": "Aguardando verificação...", "last_check": "N/A"},
                "code_status": None,
                "last_update": "N/A"
            }

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Ansible Dashboard - Monitoramento de Servidores</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e27;
            --bg-secondary: #141b2d;
            --bg-card: #1a2332;
            --accent: #00d4ff;
            --accent-hover: #00b8e6;
            --success: #00ff88;
            --danger: #ff4757;
            --warning: #ffa502;
            --text-primary: #ffffff;
            --text-secondary: #94a3b8;
            --border: #2a3441;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at top left, rgba(0, 212, 255, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at bottom right, rgba(0, 255, 136, 0.1) 0%, transparent 50%);
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }
        
        .header-title {
            font-size: 32px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .header-title .icon {
            color: var(--accent);
        }
        
        .header-actions {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 12px;
            font-family: inherit;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent), var(--accent-hover));
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }
        
        .btn-success {
            background: linear-gradient(135deg, var(--success), #00cc6a);
            color: white;
        }
        
        .btn-success:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 255, 136, 0.4);
        }
        
        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        
        .btn-secondary:hover {
            background: var(--bg-card);
            border-color: var(--accent);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            transition: all 0.2s;
        }
        
        .stat-card:hover {
            transform: translateY(-2px);
            border-color: var(--accent);
        }
        
        .stat-label {
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }
        
        .stat-value {
            font-size: 36px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .stat-value.success { color: var(--success); }
        .stat-value.danger { color: var(--danger); }
        .stat-value.warning { color: var(--warning); }
        .stat-value.accent { color: var(--accent); }
        
        .servers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 20px;
        }
        
        .server-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            transition: all 0.2s;
        }
        
        .server-card.accessible {
            border-color: var(--success);
        }
        
        .server-card.inaccessible {
            border-color: var(--danger);
        }
        
        .server-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.3);
        }
        
        .server-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        
        .server-name {
            font-size: 18px;
            font-weight: 600;
            color: var(--accent);
        }
        
        .server-status {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-dot.online {
            background: var(--success);
        }
        
        .status-dot.offline {
            background: var(--danger);
            animation: none;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.4); }
            50% { opacity: 0.8; box-shadow: 0 0 0 8px rgba(0, 255, 136, 0); }
        }
        
        .server-info {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
        }
        
        .info-row:last-child {
            border-bottom: none;
        }
        
        .info-label {
            font-size: 13px;
            color: var(--text-secondary);
        }
        
        .info-value {
            font-size: 13px;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
        }
        
        .info-value.success {
            color: var(--success);
        }
        
        .info-value.danger {
            color: var(--danger);
        }
        
        .info-value.warning {
            color: var(--warning);
        }
        
        .badge {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .badge.success {
            background: rgba(0, 255, 136, 0.2);
            color: var(--success);
        }
        
        .badge.danger {
            background: rgba(255, 71, 87, 0.2);
            color: var(--danger);
        }
        
        .badge.warning {
            background: rgba(255, 165, 2, 0.2);
            color: var(--warning);
        }
        
        .loading {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid var(--border);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        
        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }
        
        .last-update {
            text-align: center;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-title">
                <span class="icon">🚀</span>
                <span>Ansible Dashboard</span>
            </div>
            <div class="header-actions">
                <button class="btn btn-secondary" onclick="refreshStatus()">
                    🔄 Atualizar
                </button>
                <button class="btn btn-primary" onclick="runPlaybook()">
                    ▶️ Executar Deploy
                </button>
            </div>
        </header>
        
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="stat-label">Total de Servidores</div>
                <div class="stat-value accent" id="totalServers">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Acessíveis</div>
                <div class="stat-value success" id="accessibleServers">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Código Deployado</div>
                <div class="stat-value success" id="deployedServers">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Processos Rodando</div>
                <div class="stat-value success" id="runningServers">0</div>
            </div>
        </div>
        
        <div class="servers-grid" id="serversGrid">
            <div class="empty-state">
                <div class="empty-state-icon">⏳</div>
                <div>Carregando servidores...</div>
            </div>
        </div>
        
        <div class="last-update" id="lastUpdate">
            Última atualização: Carregando...
        </div>
    </div>
    
    <script>
        function updateDashboard() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    // Atualiza estatísticas
                    document.getElementById('totalServers').textContent = data.total_servers;
                    document.getElementById('accessibleServers').textContent = data.accessible_servers;
                    document.getElementById('deployedServers').textContent = data.deployed_servers;
                    document.getElementById('runningServers').textContent = data.running_servers;
                    document.getElementById('lastUpdate').textContent = `Última atualização: ${data.last_update}`;
                    
                    // Atualiza cards dos servidores
                    const grid = document.getElementById('serversGrid');
                    
                    if (data.servers.length === 0) {
                        grid.innerHTML = `
                            <div class="empty-state" style="grid-column: 1/-1;">
                                <div class="empty-state-icon">📭</div>
                                <div>Nenhum servidor configurado</div>
                            </div>
                        `;
                    } else {
                        grid.innerHTML = data.servers.map(server => {
                            const accessible = server.connection?.accessible;
                            const codeCopied = server.code_status?.code_copied;
                            const processRunning = server.code_status?.process_running;
                            
                            return `
                                <div class="server-card ${accessible ? 'accessible' : 'inaccessible'}">
                                    <div class="server-header">
                                        <div class="server-name">${server.hostname}</div>
                                        <div class="server-status">
                                            <span class="status-dot ${accessible ? 'online' : 'offline'}"></span>
                                            ${accessible ? 'Online' : 'Offline'}
                                        </div>
                                    </div>
                                    <div class="server-info">
                                        <div class="info-row">
                                            <span class="info-label">IP:</span>
                                            <span class="info-value">${server.ip}:${server.port}</span>
                                        </div>
                                        <div class="info-row">
                                            <span class="info-label">Conexão:</span>
                                            <span class="info-value ${accessible ? 'success' : 'danger'}">
                                                ${accessible ? '✅ Acessível' : '❌ Inacessível'}
                                            </span>
                                        </div>
                                        <div class="info-row">
                                            <span class="info-label">Código Copiado:</span>
                                            <span class="info-value ${codeCopied ? 'success' : 'danger'}">
                                                ${codeCopied ? '✅ Sim' : '❌ Não'}
                                            </span>
                                        </div>
                                        <div class="info-row">
                                            <span class="info-label">Processo Rodando:</span>
                                            <span class="info-value ${processRunning ? 'success' : 'danger'}">
                                                ${processRunning ? '✅ Sim' : '❌ Não'}
                                            </span>
                                        </div>
                                        <div class="info-row">
                                            <span class="info-label">Última Verificação:</span>
                                            <span class="info-value">${server.last_update || 'N/A'}</span>
                                        </div>
                                    </div>
                                </div>
                            `;
                        }).join('');
                    }
                })
                .catch(err => {
                    console.error('Erro ao atualizar:', err);
                });
        }
        
        function refreshStatus() {
            fetch('/api/refresh', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        setTimeout(updateDashboard, 2000);
                    }
                });
        }
        
        function runPlaybook() {
            if (!confirm('Deseja executar o playbook em todos os servidores acessíveis?')) {
                return;
            }
            
            fetch('/api/run-playbook', { method: 'POST' })
                .then(r => r.json())
                .then(data => {
                    alert(data.message || 'Playbook executado! Verifique o status em alguns instantes.');
                    setTimeout(updateDashboard, 5000);
                });
        }
        
        // Atualiza a cada 5 segundos
        setInterval(updateDashboard, 5000);
        updateDashboard();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """Página principal do dashboard"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def api_status():
    """Retorna status de todos os servidores"""
    with status_lock:
        servers = list(servers_status.values())
        
        total = len(servers)
        accessible = sum(1 for s in servers if s.get("connection", {}).get("accessible", False))
        deployed = sum(1 for s in servers if s.get("code_status", {}).get("code_copied", False))
        running = sum(1 for s in servers if s.get("code_status", {}).get("process_running", False))
        
        return jsonify({
            "total_servers": total,
            "accessible_servers": accessible,
            "deployed_servers": deployed,
            "running_servers": running,
            "servers": servers,
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

@app.route('/api/refresh', methods=['POST'])
def api_refresh():
    """Força atualização do status"""
    try:
        update_all_servers_status()
        return jsonify({"success": True, "message": "Status atualizado"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/run-playbook', methods=['POST'])
def api_run_playbook():
    """Executa o playbook Ansible"""
    try:
        # Executa o playbook em background
        def run_playbook():
            cmd = ["ansible-playbook", PLAYBOOK_FILE, "-i", INVENTORY_FILE]
            subprocess.run(cmd, capture_output=True, text=True)
        
        thread = threading.Thread(target=run_playbook, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "message": "Playbook iniciado em background. Verifique o status em alguns instantes."
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    import sys
    import io
    # Configura encoding UTF-8 para stdout no Windows
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    print("Iniciando Ansible Dashboard...")
    print("Acesse: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)

