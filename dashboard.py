"""
Dashboard Web para monitorar o Google Ads Clicker.
Usa Flask para servir uma interface em tempo real.
"""

from flask import Flask, render_template_string, jsonify
from stats import stats_manager
import threading

app = Flask(__name__)

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎯 Google Ads Clicker - Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a25;
            --accent: #00ff88;
            --accent-dim: #00cc6a;
            --danger: #ff4757;
            --warning: #ffa502;
            --text-primary: #ffffff;
            --text-secondary: #8888aa;
            --border: #2a2a3a;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Space Grotesk', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at top left, rgba(0, 255, 136, 0.05) 0%, transparent 50%),
                radial-gradient(ellipse at bottom right, rgba(255, 71, 87, 0.05) 0%, transparent 50%);
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 30px;
        }
        
        .logo {
            font-size: 28px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .logo span {
            color: var(--accent);
        }
        
        .status-badge {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: var(--bg-card);
            border-radius: 20px;
            font-size: 14px;
        }
        
        .status-dot {
            width: 10px;
            height: 10px;
            background: var(--accent);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.4); }
            50% { opacity: 0.8; box-shadow: 0 0 0 10px rgba(0, 255, 136, 0); }
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
            transition: transform 0.2s, border-color 0.2s;
        }
        
        .stat-card:hover {
            transform: translateY(-2px);
            border-color: var(--accent);
        }
        
        .stat-card.accent {
            border-color: var(--accent);
            background: linear-gradient(135deg, var(--bg-card) 0%, rgba(0, 255, 136, 0.1) 100%);
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
        
        .stat-value.accent { color: var(--accent); }
        .stat-value.danger { color: var(--danger); }
        .stat-value.warning { color: var(--warning); }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 20px;
        }
        
        @media (max-width: 1200px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .panel {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
        }
        
        .panel-header {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .panel-content {
            padding: 20px;
        }
        
        .workers-grid {
            display: grid;
            gap: 16px;
        }
        
        .worker-card {
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 16px;
            display: grid;
            grid-template-columns: auto 1fr auto;
            gap: 16px;
            align-items: center;
        }
        
        .worker-id {
            width: 48px;
            height: 48px;
            background: var(--accent);
            color: var(--bg-primary);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
        }
        
        .worker-info h4 {
            font-size: 14px;
            margin-bottom: 4px;
        }
        
        .worker-info p {
            font-size: 12px;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .worker-stats {
            text-align: right;
        }
        
        .worker-stats .cliques {
            font-size: 24px;
            font-weight: 700;
            color: var(--accent);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .worker-stats .label {
            font-size: 11px;
            color: var(--text-secondary);
        }
        
        .worker-status {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 600;
        }
        
        .worker-status.buscando { background: rgba(0, 255, 136, 0.2); color: var(--accent); }
        .worker-status.captcha { background: rgba(255, 165, 2, 0.2); color: var(--warning); }
        .worker-status.erro { background: rgba(255, 71, 87, 0.2); color: var(--danger); }
        .worker-status.iniciando { background: rgba(136, 136, 170, 0.2); color: var(--text-secondary); }
        
        .logs-container {
            max-height: 400px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
        }
        
        .log-entry {
            padding: 8px 12px;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 10px;
        }
        
        .log-entry:hover {
            background: var(--bg-secondary);
        }
        
        .log-time {
            color: var(--text-secondary);
            white-space: nowrap;
        }
        
        .log-msg {
            color: var(--text-primary);
            word-break: break-word;
        }
        
        .domains-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }
        
        .domain-tag {
            padding: 6px 12px;
            background: var(--bg-secondary);
            border-radius: 8px;
            font-size: 12px;
            font-family: 'JetBrains Mono', monospace;
            color: var(--accent);
        }
        
        .empty-state {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }
        
        ::-webkit-scrollbar {
            width: 6px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--bg-secondary);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--border);
            border-radius: 3px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: var(--text-secondary);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                🎯 <span>Google Ads</span> Clicker
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                <span id="workers-ativos">0</span> workers ativos
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card accent">
                <div class="stat-label">Total de Cliques</div>
                <div class="stat-value accent" id="total-cliques">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Captchas Resolvidos</div>
                <div class="stat-value" id="captchas-ok">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Captchas Falhos</div>
                <div class="stat-value danger" id="captchas-fail">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Domínios Únicos</div>
                <div class="stat-value warning" id="dominios-unicos">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Palavras Processadas</div>
                <div class="stat-value" id="palavras">0</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Início</div>
                <div class="stat-value" style="font-size: 18px;" id="inicio">--:--:--</div>
            </div>
        </div>
        
        <div class="main-grid">
            <div class="panel">
                <div class="panel-header">
                    👥 Workers Ativos
                </div>
                <div class="panel-content">
                    <div class="workers-grid" id="workers-container">
                        <div class="empty-state">Aguardando workers...</div>
                    </div>
                </div>
            </div>
            
            <div style="display: flex; flex-direction: column; gap: 20px;">
                <div class="panel">
                    <div class="panel-header">
                        🌐 Domínios Clicados
                    </div>
                    <div class="panel-content">
                        <div class="domains-list" id="domains-container">
                            <div class="empty-state">Nenhum domínio ainda</div>
                        </div>
                    </div>
                </div>
                
                <div class="panel" style="flex: 1;">
                    <div class="panel-header">
                        📋 Logs em Tempo Real
                    </div>
                    <div class="logs-container" id="logs-container">
                        <div class="empty-state">Aguardando logs...</div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function getStatusClass(status) {
            if (status.includes('buscando') || status.includes('clicando')) return 'buscando';
            if (status.includes('captcha')) return 'captcha';
            if (status.includes('erro')) return 'erro';
            return 'iniciando';
        }
        
        function updateDashboard() {
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    // Stats globais
                    document.getElementById('total-cliques').textContent = data.global.total_cliques;
                    document.getElementById('captchas-ok').textContent = data.global.captchas_resolvidos;
                    document.getElementById('captchas-fail').textContent = data.global.captchas_falhos;
                    document.getElementById('dominios-unicos').textContent = data.global.dominios_unicos;
                    document.getElementById('palavras').textContent = data.global.palavras_processadas;
                    document.getElementById('inicio').textContent = data.global.inicio;
                    document.getElementById('workers-ativos').textContent = data.global.workers_ativos;
                    
                    // Workers
                    const workersContainer = document.getElementById('workers-container');
                    if (data.workers.length === 0) {
                        workersContainer.innerHTML = '<div class="empty-state">Aguardando workers...</div>';
                    } else {
                        workersContainer.innerHTML = data.workers.map(w => `
                            <div class="worker-card">
                                <div class="worker-id">${w.id}</div>
                                <div class="worker-info">
                                    <h4>
                                        <span class="worker-status ${getStatusClass(w.status)}">${w.status}</span>
                                    </h4>
                                    <p>🌐 ${w.ip || 'Obtendo IP...'} ${w.cidade ? `(${w.cidade}, ${w.estado})` : ''}</p>
                                    <p>🔍 ${w.palavra || 'Aguardando...'}</p>
                                </div>
                                <div class="worker-stats">
                                    <div class="cliques">${w.cliques}</div>
                                    <div class="label">cliques</div>
                                    <div style="margin-top: 4px; font-size: 11px; color: var(--text-secondary);">
                                        ✅ ${w.captchas_ok} ❌ ${w.captchas_fail}
                                    </div>
                                </div>
                            </div>
                        `).join('');
                    }
                    
                    // Domínios
                    const domainsContainer = document.getElementById('domains-container');
                    if (data.dominios_lista.length === 0) {
                        domainsContainer.innerHTML = '<div class="empty-state">Nenhum domínio ainda</div>';
                    } else {
                        domainsContainer.innerHTML = data.dominios_lista.map(d => 
                            `<span class="domain-tag">${d}</span>`
                        ).join('');
                    }
                    
                    // Logs
                    const logsContainer = document.getElementById('logs-container');
                    if (data.logs.length === 0) {
                        logsContainer.innerHTML = '<div class="empty-state">Aguardando logs...</div>';
                    } else {
                        logsContainer.innerHTML = data.logs.map(log => {
                            const match = log.match(/\\[(.+?)\\] (.+)/);
                            if (match) {
                                return `<div class="log-entry">
                                    <span class="log-time">${match[1]}</span>
                                    <span class="log-msg">${match[2]}</span>
                                </div>`;
                            }
                            return `<div class="log-entry"><span class="log-msg">${log}</span></div>`;
                        }).join('');
                    }
                })
                .catch(err => console.error('Erro ao atualizar:', err));
        }
        
        // Atualiza a cada 2 segundos
        setInterval(updateDashboard, 2000);
        updateDashboard();
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/stats')
def api_stats():
    return stats_manager.get_stats_json(), 200, {'Content-Type': 'application/json'}


def iniciar_dashboard(port=5000):
    """Inicia o servidor do dashboard em uma thread separada."""
    print(f"🌐 Dashboard disponível em: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)


def iniciar_dashboard_thread(port=5000):
    """Inicia o dashboard em uma thread separada."""
    thread = threading.Thread(target=iniciar_dashboard, args=(port,), daemon=True)
    thread.start()
    return thread


if __name__ == '__main__':
    iniciar_dashboard(5000)

