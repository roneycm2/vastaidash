"""
Dashboard Web para YouTube Browserless Viewer.
Interface moderna para gerenciar visualizações de YouTube via Browserless.
"""

from flask import Flask, render_template_string, jsonify, request
from youtube_browserless import browser_manager, open_multiple_youtube, PROXY_CONFIG, BROWSERLESS_API_KEY
import threading
import asyncio

app = Flask(__name__)

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 YouTube Browserless Viewer</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Sora:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a25;
            --bg-elevated: #222230;
            --accent: #ff0044;
            --accent-light: #ff3366;
            --accent-glow: rgba(255, 0, 68, 0.25);
            --success: #00ff88;
            --success-glow: rgba(0, 255, 136, 0.2);
            --warning: #ffaa00;
            --error: #ff4466;
            --text-primary: #ffffff;
            --text-secondary: #a0a0b0;
            --text-muted: #606070;
            --border: #2a2a3a;
            --gradient-red: linear-gradient(135deg, #ff0044 0%, #cc0033 100%);
            --gradient-dark: linear-gradient(180deg, #0a0a0f 0%, #12121a 100%);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Sora', sans-serif;
            background: var(--gradient-dark);
            color: var(--text-primary);
            min-height: 100vh;
            overflow-x: hidden;
        }
        
        /* Animated background */
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: 
                radial-gradient(ellipse 100% 60% at 50% -10%, var(--accent-glow), transparent),
                radial-gradient(circle at 10% 90%, rgba(255,0,68,0.05), transparent 40%),
                radial-gradient(circle at 90% 20%, rgba(0,255,136,0.03), transparent 30%);
            pointer-events: none;
            z-index: 0;
        }
        
        /* Grid lines background */
        body::after {
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: 
                linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px),
                linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px);
            background-size: 60px 60px;
            pointer-events: none;
            z-index: 0;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
            position: relative;
            z-index: 1;
        }
        
        /* Header */
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 24px;
            margin-bottom: 24px;
            border-bottom: 1px solid var(--border);
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 16px;
        }
        
        .logo-icon {
            width: 60px;
            height: 60px;
            background: var(--gradient-red);
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 30px;
            box-shadow: 0 8px 40px var(--accent-glow);
            animation: pulse-glow 3s ease-in-out infinite;
        }
        
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 8px 40px var(--accent-glow); }
            50% { box-shadow: 0 8px 60px rgba(255, 0, 68, 0.4); }
        }
        
        .logo h1 {
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -1px;
        }
        
        .logo h1 span { color: var(--accent); }
        
        .logo p {
            color: var(--text-muted);
            font-size: 13px;
            margin-top: 2px;
        }
        
        .status-pill {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 24px;
            background: var(--bg-card);
            border-radius: 50px;
            border: 1px solid var(--border);
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: var(--text-muted);
            transition: all 0.3s;
        }
        
        .status-dot.active {
            background: var(--success);
            box-shadow: 0 0 20px var(--success-glow);
            animation: blink 1.5s infinite;
        }
        
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        /* Control Panel */
        .control-panel {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 24px;
            padding: 32px;
            margin-bottom: 24px;
        }
        
        .control-title {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
            font-size: 20px;
            font-weight: 600;
        }
        
        .control-grid {
            display: grid;
            grid-template-columns: 1fr 140px 140px 160px;
            gap: 16px;
            align-items: end;
        }
        
        @media (max-width: 1000px) {
            .control-grid {
                grid-template-columns: 1fr 1fr;
            }
        }
        
        @media (max-width: 600px) {
            .control-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .field {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        
        .field label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            color: var(--text-muted);
        }
        
        .field input, .field select {
            padding: 16px 20px;
            background: var(--bg-primary);
            border: 1px solid var(--border);
            border-radius: 14px;
            color: var(--text-primary);
            font-family: 'Space Mono', monospace;
            font-size: 14px;
            transition: all 0.2s;
        }
        
        .field input:focus, .field select:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 4px var(--accent-glow);
        }
        
        .field input::placeholder {
            color: var(--text-muted);
        }
        
        .btn {
            padding: 16px 28px;
            border: none;
            border-radius: 14px;
            font-family: 'Sora', sans-serif;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }
        
        .btn-primary {
            background: var(--gradient-red);
            color: white;
            box-shadow: 0 6px 30px var(--accent-glow);
        }
        
        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 40px var(--accent-glow);
        }
        
        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-secondary {
            background: var(--bg-elevated);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        
        .btn-secondary:hover {
            background: var(--border);
        }
        
        /* Stats */
        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 24px;
        }
        
        @media (max-width: 900px) {
            .stats-row { grid-template-columns: repeat(2, 1fr); }
        }
        
        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            padding: 24px;
            transition: all 0.3s;
            position: relative;
            overflow: hidden;
        }
        
        .stat-card::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: var(--border);
        }
        
        .stat-card:hover {
            transform: translateY(-4px);
            border-color: var(--accent);
        }
        
        .stat-card.highlight {
            border-color: var(--accent);
        }
        
        .stat-card.highlight::before {
            background: var(--gradient-red);
        }
        
        .stat-icon {
            width: 48px;
            height: 48px;
            background: var(--bg-elevated);
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
            margin-bottom: 16px;
        }
        
        .stat-card.highlight .stat-icon {
            background: var(--accent);
        }
        
        .stat-value {
            font-family: 'Space Mono', monospace;
            font-size: 42px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 6px;
        }
        
        .stat-label {
            font-size: 13px;
            color: var(--text-muted);
        }
        
        /* Main Grid */
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 380px;
            gap: 24px;
        }
        
        @media (max-width: 1200px) {
            .main-grid { grid-template-columns: 1fr; }
        }
        
        .panel {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            overflow: hidden;
        }
        
        .panel-header {
            padding: 20px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .panel-header h3 {
            font-size: 16px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .panel-badge {
            padding: 4px 12px;
            background: var(--bg-elevated);
            border-radius: 20px;
            font-size: 12px;
            color: var(--text-muted);
            font-family: 'Space Mono', monospace;
        }
        
        .panel-content {
            padding: 20px;
            max-height: 500px;
            overflow-y: auto;
        }
        
        /* Sessions */
        .sessions-list {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        
        .session-item {
            background: var(--bg-elevated);
            border-radius: 14px;
            padding: 18px;
            display: grid;
            grid-template-columns: 50px 1fr auto;
            gap: 16px;
            align-items: center;
            border: 1px solid transparent;
            transition: all 0.2s;
        }
        
        .session-item:hover {
            border-color: var(--border);
        }
        
        .session-num {
            width: 50px;
            height: 50px;
            background: var(--accent);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 18px;
        }
        
        .session-info h4 {
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 6px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 400px;
        }
        
        .session-meta {
            display: flex;
            gap: 16px;
            font-size: 12px;
            color: var(--text-secondary);
            font-family: 'Space Mono', monospace;
        }
        
        .session-meta span {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .status-badge {
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-badge.connecting { background: rgba(255,170,0,0.15); color: var(--warning); }
        .status-badge.watching { background: rgba(0,255,136,0.15); color: var(--success); }
        .status-badge.error { background: rgba(255,68,102,0.15); color: var(--error); }
        .status-badge.done { background: rgba(0,255,136,0.2); color: var(--success); }
        
        /* IPs */
        .ips-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .ip-chip {
            padding: 12px 18px;
            background: var(--bg-elevated);
            border-radius: 12px;
            font-family: 'Space Mono', monospace;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
            border: 1px solid rgba(0,255,136,0.2);
        }
        
        .ip-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--success);
        }
        
        .ip-dot.inactive { background: var(--text-muted); }
        
        /* IPs History */
        .ip-history-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
        }
        
        .ip-history-item:last-child { border-bottom: none; }
        
        .ip-history-item .ip {
            font-family: 'Space Mono', monospace;
            color: var(--success);
            min-width: 120px;
        }
        
        .ip-history-item .location {
            color: var(--text-secondary);
            flex: 1;
        }
        
        .ip-history-item .time {
            color: var(--text-muted);
            font-family: 'Space Mono', monospace;
        }
        
        .ip-history-item .status-icon {
            font-size: 14px;
        }
        
        /* Logs */
        .logs-list {
            display: flex;
            flex-direction: column;
        }
        
        .log-item {
            display: flex;
            gap: 12px;
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            font-size: 13px;
            font-family: 'Space Mono', monospace;
        }
        
        .log-item:hover { background: var(--bg-elevated); }
        
        .log-time {
            color: var(--text-muted);
            white-space: nowrap;
        }
        
        .log-msg {
            color: var(--text-secondary);
            word-break: break-word;
        }
        
        .log-msg.success { color: var(--success); }
        .log-msg.error { color: var(--error); }
        .log-msg.warning { color: var(--warning); }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-muted);
        }
        
        .empty-icon {
            font-size: 56px;
            margin-bottom: 16px;
            opacity: 0.4;
        }
        
        .empty-state p {
            margin-bottom: 8px;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-primary); }
        ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
        
        /* Loading */
        .spinner {
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            border-top-color: white;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }
        
        /* Right column stack */
        .right-col {
            display: flex;
            flex-direction: column;
            gap: 24px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                <div class="logo-icon">▶️</div>
                <div>
                    <h1>YouTube <span>Browserless</span></h1>
                    <p>Viewer com Proxy Residencial Brasil</p>
                </div>
            </div>
            <div class="status-pill">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">Aguardando</span>
            </div>
        </header>
        
        <div class="control-panel">
            <div class="control-title">
                <span>🎮</span>
                Painel de Controle
            </div>
            <div class="control-grid">
                <div class="field">
                    <label>Link do YouTube</label>
                    <input type="text" id="youtubeUrl" placeholder="https://www.youtube.com/watch?v=..." />
                </div>
                <div class="field">
                    <label>Navegadores</label>
                    <select id="numBrowsers">
                        <option value="1">1</option>
                        <option value="2">2</option>
                        <option value="3">3</option>
                        <option value="5" selected>5</option>
                        <option value="10">10</option>
                        <option value="15">15</option>
                        <option value="20">20</option>
                    </select>
                </div>
                <div class="field">
                    <label>Duração</label>
                    <select id="watchDuration">
                        <option value="10">10 seg</option>
                        <option value="30" selected>30 seg</option>
                        <option value="60">1 min</option>
                        <option value="120">2 min</option>
                        <option value="180">3 min</option>
                        <option value="300">5 min</option>
                    </select>
                </div>
                <button class="btn btn-primary" id="startBtn" onclick="startViewing()">
                    ▶️ Iniciar Visualização
                </button>
            </div>
        </div>
        
        <div class="stats-row">
            <div class="stat-card highlight">
                <div class="stat-icon">🌐</div>
                <div class="stat-value" id="activeBrowsers">0</div>
                <div class="stat-label">Navegadores Ativos</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-value" id="totalOpened">0</div>
                <div class="stat-label">Total Abertos</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">✅</div>
                <div class="stat-value" style="color: var(--success);" id="totalSuccess">0</div>
                <div class="stat-label">Sucesso</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">❌</div>
                <div class="stat-value" style="color: var(--error);" id="totalFailed">0</div>
                <div class="stat-label">Falhas</div>
            </div>
        </div>
        
        <div class="main-grid">
            <div style="display: flex; flex-direction: column; gap: 24px;">
                <div class="panel">
                    <div class="panel-header">
                        <h3>🖥️ Sessões Ativas</h3>
                        <span class="panel-badge" id="sessionsCount">0 sessões</span>
                    </div>
                    <div class="panel-content">
                        <div class="sessions-list" id="sessionsContainer">
                            <div class="empty-state">
                                <div class="empty-icon">🎬</div>
                                <p>Nenhuma sessão ativa</p>
                                <p style="font-size: 13px;">Cole um link do YouTube e clique em Iniciar</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="panel">
                    <div class="panel-header">
                        <h3>📜 Histórico de IPs</h3>
                        <span class="panel-badge" id="ipsCount">0 IPs</span>
                    </div>
                    <div class="panel-content" style="max-height: 300px;">
                        <div id="ipsHistory">
                            <div class="empty-state" style="padding: 30px;">
                                <p>Nenhum IP registrado ainda</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="right-col">
                <div class="panel">
                    <div class="panel-header">
                        <h3>🌍 IPs Ativos Agora</h3>
                    </div>
                    <div class="panel-content">
                        <div class="ips-grid" id="activeIps">
                            <div class="empty-state" style="padding: 20px; width: 100%;">
                                <p>Nenhum IP ativo</p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="panel" style="flex: 1;">
                    <div class="panel-header">
                        <h3>📋 Logs em Tempo Real</h3>
                        <button class="btn btn-secondary" style="padding: 8px 16px; font-size: 12px;" onclick="clearLogs()">Limpar</button>
                    </div>
                    <div class="panel-content logs-list" id="logsContainer" style="max-height: 400px;">
                        <div class="empty-state" style="padding: 30px;">
                            <p>Aguardando atividade...</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let isRunning = false;
        
        function getStatusBadgeClass(status) {
            const s = status.toLowerCase();
            if (s.includes('assistindo') || s.includes('abrindo')) return 'watching';
            if (s.includes('conectando') || s.includes('obtendo') || s.includes('iniciando')) return 'connecting';
            if (s.includes('erro') || s.includes('timeout')) return 'error';
            if (s.includes('concluído')) return 'done';
            return 'connecting';
        }
        
        function getLogClass(level) {
            if (level === 'success') return 'success';
            if (level === 'error') return 'error';
            if (level === 'warning') return 'warning';
            return '';
        }
        
        function startViewing() {
            const url = document.getElementById('youtubeUrl').value.trim();
            const numBrowsers = parseInt(document.getElementById('numBrowsers').value);
            const watchDuration = parseInt(document.getElementById('watchDuration').value);
            
            if (!url) {
                alert('Por favor, insira um link do YouTube');
                return;
            }
            
            if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
                alert('Por favor, insira um link válido do YouTube');
                return;
            }
            
            const btn = document.getElementById('startBtn');
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Processando...';
            
            fetch('/api/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    num_browsers: numBrowsers,
                    watch_duration: watchDuration
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    isRunning = true;
                    document.getElementById('statusDot').classList.add('active');
                    document.getElementById('statusText').textContent = 'Executando';
                }
                setTimeout(() => {
                    btn.disabled = false;
                    btn.innerHTML = '▶️ Iniciar Visualização';
                }, 2000);
            })
            .catch(err => {
                console.error(err);
                btn.disabled = false;
                btn.innerHTML = '▶️ Iniciar Visualização';
            });
        }
        
        function clearLogs() {
            fetch('/api/reset', { method: 'POST' })
                .then(r => r.json())
                .then(() => updateDashboard());
        }
        
        function updateDashboard() {
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    // Stats
                    document.getElementById('activeBrowsers').textContent = data.active_browsers;
                    document.getElementById('totalOpened').textContent = data.total_opened;
                    document.getElementById('totalSuccess').textContent = data.total_success;
                    document.getElementById('totalFailed').textContent = data.total_failed;
                    
                    // Status
                    if (data.active_browsers > 0) {
                        document.getElementById('statusDot').classList.add('active');
                        document.getElementById('statusText').textContent = data.active_browsers + ' ativo(s)';
                    } else if (data.total_opened > 0) {
                        document.getElementById('statusDot').classList.remove('active');
                        document.getElementById('statusText').textContent = 'Concluído';
                    } else {
                        document.getElementById('statusDot').classList.remove('active');
                        document.getElementById('statusText').textContent = 'Aguardando';
                    }
                    
                    // Sessions
                    const sessionsContainer = document.getElementById('sessionsContainer');
                    document.getElementById('sessionsCount').textContent = data.sessions.length + ' sessões';
                    
                    if (data.sessions.length === 0) {
                        sessionsContainer.innerHTML = `
                            <div class="empty-state">
                                <div class="empty-icon">🎬</div>
                                <p>Nenhuma sessão ativa</p>
                                <p style="font-size: 13px;">Cole um link do YouTube e clique em Iniciar</p>
                            </div>
                        `;
                    } else {
                        sessionsContainer.innerHTML = data.sessions.map((s, i) => `
                            <div class="session-item">
                                <div class="session-num">${i + 1}</div>
                                <div class="session-info">
                                    <h4>${s.title || s.youtube_url.substring(0, 60) + '...'}</h4>
                                    <div class="session-meta">
                                        <span>🌐 ${s.ip_address || 'Obtendo...'}</span>
                                        <span>📍 ${s.location || 'Brasil'}</span>
                                        <span>⏱️ ${s.duration}s</span>
                                    </div>
                                </div>
                                <span class="status-badge ${getStatusBadgeClass(s.status)}">${s.status}</span>
                            </div>
                        `).join('');
                    }
                    
                    // Active IPs
                    const activeIpsContainer = document.getElementById('activeIps');
                    if (data.active_ips && data.active_ips.length > 0) {
                        activeIpsContainer.innerHTML = data.active_ips.map(ip => `
                            <div class="ip-chip">
                                <span class="ip-dot"></span>
                                ${ip}
                            </div>
                        `).join('');
                    } else {
                        activeIpsContainer.innerHTML = `
                            <div class="empty-state" style="padding: 20px; width: 100%;">
                                <p>Nenhum IP ativo</p>
                            </div>
                        `;
                    }
                    
                    // IPs History
                    const ipsHistory = document.getElementById('ipsHistory');
                    document.getElementById('ipsCount').textContent = (data.all_ips ? data.all_ips.length : 0) + ' IPs';
                    
                    if (data.all_ips && data.all_ips.length > 0) {
                        ipsHistory.innerHTML = data.all_ips.slice(0, 30).map(item => `
                            <div class="ip-history-item">
                                <span class="status-icon">${item.success ? '✅' : '❌'}</span>
                                <span class="ip">${item.ip}</span>
                                <span class="location">${item.location}</span>
                                <span class="time">${item.time}</span>
                            </div>
                        `).join('');
                    } else {
                        ipsHistory.innerHTML = `
                            <div class="empty-state" style="padding: 30px;">
                                <p>Nenhum IP registrado ainda</p>
                            </div>
                        `;
                    }
                    
                    // Logs
                    const logsContainer = document.getElementById('logsContainer');
                    if (data.logs && data.logs.length > 0) {
                        logsContainer.innerHTML = data.logs.slice(0, 50).map(log => `
                            <div class="log-item">
                                <span class="log-time">${log.time}</span>
                                <span class="log-msg ${getLogClass(log.level)}">${log.message}</span>
                            </div>
                        `).join('');
                    } else {
                        logsContainer.innerHTML = `
                            <div class="empty-state" style="padding: 30px;">
                                <p>Aguardando atividade...</p>
                            </div>
                        `;
                    }
                })
                .catch(err => console.error('Erro ao atualizar:', err));
        }
        
        // Update every second
        setInterval(updateDashboard, 1000);
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
    return jsonify(browser_manager.get_stats())


@app.route('/api/start', methods=['POST'])
def api_start():
    data = request.json
    youtube_url = data.get('url', '')
    num_browsers = data.get('num_browsers', 1)
    watch_duration = data.get('watch_duration', 30)
    
    if not youtube_url:
        return jsonify({"success": False, "error": "URL é obrigatória"})
    
    def run_in_background():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(open_multiple_youtube(youtube_url, num_browsers, watch_duration))
        finally:
            loop.close()
    
    thread = threading.Thread(target=run_in_background, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": f"Iniciando {num_browsers} navegador(es)"})


@app.route('/api/reset', methods=['POST'])
def api_reset():
    browser_manager.reset()
    return jsonify({"success": True})


def iniciar_dashboard(port=5001):
    """Inicia o servidor do dashboard."""
    print(f"\n{'='*60}")
    print(f"🎬 YouTube Browserless Viewer Dashboard")
    print(f"{'='*60}")
    print(f"🌐 Dashboard: http://localhost:{port}")
    print(f"📡 Proxy: {PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}")
    print(f"🔑 API Key: {BROWSERLESS_API_KEY[:20]}...")
    print(f"{'='*60}\n")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == '__main__':
    iniciar_dashboard(5001)
