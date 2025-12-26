"""
Dashboard Captcha Solver - Turnstile Persistent Solver via Browserless
======================================================================
Baseado no dashboard_browserless_v3.py, focado em resolver captchas Turnstile.

Funcionalidades:
- Sincronização de máquinas Vast.ai
- Múltiplos servidores com status de conexão
- Logs de conexão em tempo real
- Turnstile Persistent Solver via Browserless
- Workers persistentes que recarregam após cada resolução

Uso:
    python dashboard_captcha_solver.py
    Acesse: http://localhost:5001
"""
import json
import random
import re
import time
import os
import sys
import requests
import base64
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from playwright.sync_api import sync_playwright
import warnings

# Suprimir warnings do Playwright sobre erros internos
warnings.filterwarnings('ignore', category=UserWarning)

# Handler global para suprimir erros do Playwright que ocorrem em event listeners
def suppress_playwright_errors(exctype, value, traceback):
    """Suprime erros do Playwright que ocorrem em event listeners."""
    if exctype == KeyError and 'error' in str(value):
        print(f"[WARNING] Erro interno do Playwright suprimido: {value}", file=sys.stderr)
        return
    sys.__excepthook__(exctype, value, traceback)

original_excepthook = sys.excepthook

# Configurações Padrão
DEFAULT_WS_ENDPOINT = "ws://50.217.254.165:40422/chrome"

# Proxy residencial Brasil
PROXY_CONFIG = {
    "server": "http://fb29d01db8530b99.shg.na.pyproxy.io:16666",
    "username": "liderbet1-zone-mob-region-br",
    "password": "Aa10203040"
}

# Vast.ai API
VAST_AI_API_KEY = "aedf78cb67968495b0e91b71886b7444fd24d9146ce0da4c12cd5a356451d6c7"
VAST_AI_API_URL = "https://console.vast.ai/api/v0/instances/"
BROWSERLESS_INTERNAL_PORT = 3000
DEFAULT_BROWSERLESS_PORT = 40422

app = Flask(__name__)

# Estado global
state = {
    "ws_endpoint": DEFAULT_WS_ENDPOINT,
    "proxy_server": PROXY_CONFIG["server"],
    "proxy_username": PROXY_CONFIG["username"],
    "proxy_password": PROXY_CONFIG["password"]
}

state_lock = threading.Lock()

# Arquivos de dados
TURNSTILE_TOKEN_FILE = "turnstile_token.json"
TURNSTILE_SITEKEY_FILE = "turnstile_sitekey.json"
CONFIG_FILE = "captcha_solver_config.json"
LOG_FILE = "captcha_solver_logs.txt"

# Locks
turnstile_token_lock = threading.Lock()
log_file_lock = threading.Lock()
logs_enabled_lock = threading.Lock()

# Estado global: logs habilitados
logs_enabled = True

# Estatísticas globais de Captcha/Turnstile
captcha_stats = {
    "solved": 0,
    "failed": 0,
    "reloads": 0,
    "start_time": None
}
captcha_stats_lock = threading.Lock()

# Flag para parar workers
workers_should_stop = False
workers_stop_lock = threading.Lock()


def escrever_log(mensagem):
    """Escreve uma mensagem no arquivo de log com timestamp."""
    with logs_enabled_lock:
        if not logs_enabled:
            return
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {mensagem}\n"
        with log_file_lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
    except:
        pass


def log_print(mensagem):
    """Print que também escreve no arquivo de log."""
    with logs_enabled_lock:
        enabled = logs_enabled
    if not enabled:
        return
    print(mensagem, flush=True)
    escrever_log(mensagem)


# ==================== HTML TEMPLATE ====================
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🔐 Captcha Solver Dashboard - Turnstile via Browserless</title>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        :root {
            --bg-dark: #0a0a0f;
            --bg-card: #12121a;
            --bg-hover: #1a1a25;
            --accent-purple: #8b5cf6;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --border-color: #1e1e2e;
        }
        
        body {
            font-family: 'Space Grotesk', sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 10% 0%, rgba(139, 92, 246, 0.12) 0%, transparent 50%),
                radial-gradient(ellipse at 90% 100%, rgba(59, 130, 246, 0.08) 0%, transparent 50%);
        }
        
        .container { max-width: 1500px; margin: 0 auto; padding: 1.5rem; }
        
        header {
            text-align: center;
            padding: 2rem;
            background: linear-gradient(135deg, var(--bg-card) 0%, rgba(139, 92, 246, 0.1) 100%);
            border-radius: 20px;
            border: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
        }
        
        h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        
        .subtitle { color: var(--text-secondary); font-size: 1rem; }
        
        /* Cards */
        .card {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
        }
        
        .card-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        
        .card-icon {
            width: 48px;
            height: 48px;
            background: rgba(139, 92, 246, 0.2);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
        }
        
        .card-title { font-size: 1.2rem; font-weight: 600; }
        .card-desc { color: var(--text-secondary); font-size: 0.85rem; }
        
        /* Config Grid */
        .config-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1rem;
        }
        
        .config-field {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .config-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 500;
        }
        
        .config-input {
            padding: 0.75rem 1rem;
            border: 2px solid var(--border-color);
            border-radius: 10px;
            background: var(--bg-dark);
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        
        .config-input:focus {
            outline: none;
            border-color: var(--accent-purple);
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2);
        }
        
        /* Buttons */
        .btn {
            padding: 0.75rem 1.5rem;
            border: none;
            border-radius: 10px;
            font-family: inherit;
            font-size: 0.95rem;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
            color: white;
        }
        .btn-primary:hover { box-shadow: 0 5px 20px rgba(139, 92, 246, 0.4); transform: translateY(-1px); }
        .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        
        .btn-success {
            background: linear-gradient(135deg, var(--accent-green), #059669);
            color: white;
        }
        .btn-success:hover { box-shadow: 0 5px 20px rgba(16, 185, 129, 0.4); }
        
        .btn-danger {
            background: linear-gradient(135deg, var(--accent-red), #dc2626);
            color: white;
        }
        .btn-danger:hover { box-shadow: 0 5px 20px rgba(239, 68, 68, 0.4); }
        
        .btn-secondary {
            background: var(--bg-hover);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        .btn-secondary:hover { background: var(--border-color); }
        
        /* Servers List */
        .server-card {
            background: var(--bg-dark);
            border: 2px solid var(--border-color);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.75rem;
            display: flex;
            gap: 1rem;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .server-status {
            width: 14px;
            height: 14px;
            border-radius: 50%;
            flex-shrink: 0;
            transition: all 0.3s;
        }
        
        .server-status.pending { background: #64748b; }
        .server-status.testing {
            background: var(--accent-yellow);
            box-shadow: 0 0 12px rgba(245, 158, 11, 0.8);
            animation: pulse 1.5s infinite;
        }
        .server-status.connected {
            background: var(--accent-green);
            box-shadow: 0 0 12px rgba(16, 185, 129, 0.6);
        }
        .server-status.disconnected {
            background: var(--accent-red);
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.6);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(1.2); }
        }
        
        .server-card input {
            flex: 1;
            min-width: 200px;
            padding: 0.65rem;
            border: 2px solid var(--border-color);
            border-radius: 8px;
            background: var(--bg-card);
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
        }
        
        .server-card input:focus {
            outline: none;
            border-color: var(--accent-purple);
        }
        
        .server-workers-input {
            width: 90px !important;
            text-align: center;
        }
        
        .server-remove-btn {
            padding: 0.5rem 0.75rem;
            background: var(--accent-red);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .stat-card {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.25rem;
            border: 1px solid var(--border-color);
            text-align: center;
        }
        
        .stat-icon { font-size: 1.8rem; margin-bottom: 0.5rem; }
        
        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        
        .stat-label { color: var(--text-secondary); font-size: 0.85rem; }
        
        .stat-value.purple { color: var(--accent-purple); }
        .stat-value.green { color: var(--accent-green); }
        .stat-value.yellow { color: var(--accent-yellow); }
        .stat-value.red { color: var(--accent-red); }
        .stat-value.blue { color: var(--accent-blue); }
        
        /* Workers Grid */
        .workers-container {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
        }
        
        .workers-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .workers-title { font-size: 1.2rem; font-weight: 600; }
        
        .workers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 0.75rem;
            max-height: 500px;
            overflow-y: auto;
        }
        
        .workers-grid::-webkit-scrollbar { width: 8px; }
        .workers-grid::-webkit-scrollbar-track { background: var(--bg-dark); border-radius: 4px; }
        .workers-grid::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        
        .worker-card {
            background: var(--bg-dark);
            border-radius: 12px;
            padding: 1rem;
            border: 2px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 0.75rem;
            transition: all 0.3s;
        }
        
        .worker-card.pending { border-color: #475569; }
        .worker-card.running { border-color: var(--accent-yellow); animation: worker-pulse 1.5s infinite; }
        .worker-card.success { border-color: var(--accent-green); background: rgba(16, 185, 129, 0.1); }
        .worker-card.error { border-color: var(--accent-red); background: rgba(239, 68, 68, 0.1); }
        
        @keyframes worker-pulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
            50% { box-shadow: 0 0 0 6px rgba(245, 158, 11, 0); }
        }
        
        .worker-number {
            width: 36px;
            height: 36px;
            background: var(--bg-card);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 0.85rem;
        }
        
        .worker-info { flex: 1; min-width: 0; }
        .worker-status-text { font-weight: 600; font-size: 0.9rem; margin-bottom: 0.25rem; }
        .worker-details { 
            font-size: 0.75rem; 
            color: var(--text-secondary); 
            font-family: 'JetBrains Mono', monospace;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .worker-icon { font-size: 1.4rem; }
        
        /* Logs */
        .logs-box {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border-color);
        }
        
        .logs-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .logs-title { font-size: 1.2rem; font-weight: 600; }
        
        .logs-content {
            background: var(--bg-dark);
            border-radius: 10px;
            padding: 1rem;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.6;
        }
        
        .log-line { padding: 0.2rem 0; border-bottom: 1px solid var(--bg-card); }
        .log-success { color: var(--accent-green); }
        .log-error { color: var(--accent-red); }
        .log-info { color: var(--accent-blue); }
        .log-warning { color: var(--accent-yellow); }
        
        /* Action Buttons Row */
        .action-row {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            align-items: center;
            margin-top: 1rem;
        }
        
        .checkbox-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.65rem 1rem;
            background: var(--bg-hover);
            border-radius: 10px;
            cursor: pointer;
            border: 1px solid var(--border-color);
            font-size: 0.9rem;
        }
        .checkbox-label input { width: 16px; height: 16px; cursor: pointer; }
        
        footer { 
            text-align: center; 
            padding: 1.5rem; 
            color: var(--text-secondary); 
            font-size: 0.85rem; 
        }
        
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        .status-badge.connected {
            background: rgba(16, 185, 129, 0.2);
            color: var(--accent-green);
            border: 1px solid var(--accent-green);
        }
        .status-badge.disconnected {
            background: rgba(239, 68, 68, 0.2);
            color: var(--accent-red);
            border: 1px solid var(--accent-red);
        }
        
        /* Progress */
        .progress-container {
            background: var(--bg-dark);
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin-bottom: 1rem;
        }
        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
            font-size: 0.9rem;
        }
        .progress-bar {
            height: 10px;
            background: var(--border-color);
            border-radius: 5px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-purple), var(--accent-blue));
            border-radius: 5px;
            transition: width 0.3s;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔐 Captcha Solver Dashboard</h1>
            <p class="subtitle">Turnstile Persistent Solver via Browserless + Vast.ai</p>
        </header>
        
        <!-- Config Card -->
        <div class="card">
            <div class="card-header">
                <div class="card-icon">⚙️</div>
                <div>
                    <div class="card-title">Configuração</div>
                    <div class="card-desc">Configure proxy e timeout de conexão</div>
                </div>
                <span class="status-badge disconnected" id="server-status">⚪ Não testado</span>
            </div>
            <div class="config-grid">
                <div class="config-field">
                    <label class="config-label">🌐 Proxy Server</label>
                    <input type="text" class="config-input" id="proxy-server" 
                           value="http://fb29d01db8530b99.shg.na.pyproxy.io:16666"
                           placeholder="http://host:porta">
                </div>
                <div class="config-field">
                    <label class="config-label">👤 Proxy Username</label>
                    <input type="text" class="config-input" id="proxy-username" 
                           value="liderbet1-zone-mob-region-br"
                           placeholder="username">
                </div>
                <div class="config-field">
                    <label class="config-label">🔑 Proxy Password</label>
                    <input type="password" class="config-input" id="proxy-password" 
                           value="Aa10203040"
                           placeholder="password">
                </div>
                <div class="config-field">
                    <label class="config-label">⏱️ Timeout (Minutos)</label>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <input type="number" class="config-input" id="ws-timeout-minutes" 
                               value="30" min="1" max="1440" step="1"
                               style="flex: 1;" onchange="atualizarTimeoutPreview()">
                        <span style="color: var(--text-secondary); font-size: 0.85rem;" id="timeout-preview">(1800000ms)</span>
                    </div>
                </div>
            </div>
            <div class="action-row">
                <button class="btn btn-secondary" onclick="saveConfig()">💾 Salvar Config</button>
            </div>
        </div>
        
        <!-- Servers Card -->
        <div class="card" style="border-color: rgba(139, 92, 246, 0.3);">
            <div class="card-header">
                <div class="card-icon" style="background: rgba(139, 92, 246, 0.2);">🖥️</div>
                <div>
                    <div class="card-title">Servidores Browserless</div>
                    <div class="card-desc">Adicione servidores e sincronize com Vast.ai</div>
                </div>
            </div>
            <div id="servers-list" style="margin-bottom: 1rem;"></div>
            <div class="action-row">
                <button class="btn btn-secondary" onclick="addServer()">➕ Adicionar Servidor</button>
                <button class="btn btn-primary" onclick="syncVastAI()">🔄 Sincronizar Vast.ai</button>
                <button class="btn btn-secondary" onclick="clearServers()">🗑️ Limpar Todos</button>
                <button class="btn btn-secondary" onclick="testAllServers()">🔍 Testar Todos</button>
                <div style="display: flex; gap: 0.5rem; align-items: center; margin-left: auto;">
                    <input type="number" id="global-workers-input" value="5" min="1" max="100"
                           style="width: 70px; padding: 0.5rem; border: 2px solid var(--border-color); border-radius: 8px; background: var(--bg-dark); color: var(--text-primary); text-align: center;">
                    <button class="btn btn-success" onclick="setAllWorkers()">⚡ Aplicar a Todos</button>
                </div>
            </div>
            <div id="servers-summary" style="margin-top: 1rem; color: var(--text-secondary); font-size: 0.9rem;"></div>
        </div>
        
        <!-- Action Card -->
        <div class="card" style="border-color: rgba(16, 185, 129, 0.3);">
            <div class="card-header">
                <div class="card-icon" style="background: rgba(16, 185, 129, 0.2);">🚀</div>
                <div>
                    <div class="card-title">Iniciar Solver</div>
                    <div class="card-desc">Inicie os workers para resolver Turnstile continuamente</div>
                </div>
            </div>
            <div class="action-row">
                <label class="checkbox-label">
                    <input type="checkbox" id="use-proxy" checked>
                    <span>🇧🇷 Usar Proxy BR</span>
                </label>
                <button class="btn btn-primary" id="start-captcha-btn" onclick="startCaptchaSolver()">
                    🔐 Iniciar Captcha Solver
                </button>
                <button class="btn btn-danger" id="stop-btn" onclick="stopWorkers()" style="display: none;">
                    ⏹️ Parar Workers
                </button>
                <button class="btn btn-secondary" onclick="resetStats()">🔄 Resetar Stats</button>
            </div>
        </div>
        
        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">🔐</div>
                <div class="stat-value purple" id="stat-solved">0</div>
                <div class="stat-label">Captchas Resolvidos</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⚡</div>
                <div class="stat-value yellow" id="stat-running">0</div>
                <div class="stat-label">Workers Ativos</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔄</div>
                <div class="stat-value blue" id="stat-reloads">0</div>
                <div class="stat-label">Reloads (Timeout)</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📈</div>
                <div class="stat-value green" id="stat-rate">0.0</div>
                <div class="stat-label">Tokens/Minuto</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⏱️</div>
                <div class="stat-value" style="color: var(--text-primary);" id="stat-time">0:00</div>
                <div class="stat-label">Tempo Total</div>
            </div>
        </div>
        
        <!-- Progress -->
        <div class="progress-container" id="progress-container" style="display: none;">
            <div class="progress-header">
                <span>Workers Conectados</span>
                <span id="progress-text">0 / 0</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
            </div>
        </div>
        
        <!-- Workers Grid -->
        <div class="workers-container">
            <div class="workers-header">
                <span class="workers-title">👁️ Status dos Workers</span>
                <button class="btn btn-secondary" onclick="clearWorkers()" style="padding: 0.5rem 1rem;">🗑️ Limpar</button>
            </div>
            <div class="workers-grid" id="workers-grid">
                <div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: var(--text-secondary);">
                    Configure servidores e clique em "Iniciar Captcha Solver"
                </div>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="logs-box">
            <div class="logs-header">
                <span class="logs-title">📋 Logs de Conexão</span>
                <div style="display: flex; gap: 0.5rem;">
                    <button class="btn btn-secondary" id="toggle-logs-btn" onclick="toggleLogs()" style="padding: 0.5rem 0.75rem;">🔊</button>
                    <button class="btn btn-secondary" onclick="clearLogs()" style="padding: 0.5rem 0.75rem;">🗑️</button>
                </div>
            </div>
            <div class="logs-content" id="logs">
                <div class="log-line log-info">[Sistema] Dashboard pronto - configure servidores e inicie o solver</div>
            </div>
        </div>
        
        <footer>🔐 Captcha Solver Dashboard - Turnstile via Browserless + Vast.ai</footer>
    </div>
    
    <script>
        let isRunning = false;
        let startTime = null;
        let statsInterval = null;
        let workers = [];
        let serverCounter = 0;
        let logsEnabled = true;
        const serverStatusCache = {};
        
        // ==================== Logs ====================
        function addLog(msg, type = 'info') {
            if (!logsEnabled) return;
            const logs = document.getElementById('logs');
            const time = new Date().toLocaleTimeString('pt-BR');
            logs.innerHTML = `<div class="log-line log-${type}">[${time}] ${msg}</div>` + logs.innerHTML;
            while (logs.children.length > 300) logs.removeChild(logs.lastChild);
        }
        
        function clearLogs() {
            document.getElementById('logs').innerHTML = '<div class="log-line log-info">[Sistema] Logs limpos</div>';
        }
        
        async function toggleLogs() {
            try {
                const response = await fetch('/api/toggle-logs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: !logsEnabled })
                });
                const result = await response.json();
                if (result.success) {
                    logsEnabled = result.enabled;
                    const btn = document.getElementById('toggle-logs-btn');
                    btn.innerHTML = logsEnabled ? '🔊' : '🔇';
                    btn.style.background = logsEnabled ? '' : 'var(--accent-red)';
                }
            } catch (error) {
                console.error('Erro ao alternar logs:', error);
            }
        }
        
        // ==================== Timeout ====================
        function atualizarTimeoutPreview() {
            const minutos = parseFloat(document.getElementById('ws-timeout-minutes').value) || 30;
            const ms = Math.round(minutos * 60 * 1000);
            document.getElementById('timeout-preview').textContent = `(${ms.toLocaleString('pt-BR')}ms)`;
        }
        
        function obterTimeoutQueryString() {
            const minutos = parseFloat(document.getElementById('ws-timeout-minutes').value) || 30;
            const ms = Math.round(minutos * 60 * 1000);
            return `?timeout=${ms}`;
        }
        
        function adicionarTimeoutAoEndpoint(endpoint) {
            if (!endpoint || endpoint.includes('timeout=')) return endpoint;
            const timeout = obterTimeoutQueryString();
            return endpoint.includes('?') ? endpoint + '&' + timeout.substring(1) : endpoint + timeout;
        }
        
        // ==================== Servers ====================
        async function testServerConnection(serverId, endpoint) {
            endpoint = adicionarTimeoutAoEndpoint(endpoint);
            try {
                const statusEl = document.getElementById('status-' + serverId);
                if (!statusEl) return;
                
                // Se já está conectado (verde), não testa novamente
                if (statusEl.classList.contains('connected')) return;
                
                const proxy = {
                    server: document.getElementById('proxy-server').value,
                    username: document.getElementById('proxy-username').value,
                    password: document.getElementById('proxy-password').value
                };
                
                statusEl.className = 'server-status testing';
                statusEl.title = 'Testando conexão com proxy...';
                
                const response = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ws_endpoint: endpoint,
                        proxy_server: proxy.server,
                        proxy_username: proxy.username,
                        proxy_password: proxy.password
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    statusEl.className = 'server-status connected';
                    statusEl.title = `✅ Conexão OK com proxy | IP: ${data.ip || 'N/A'} | ${data.country || 'N/A'}`;
                    addLog(`✅ Servidor ${serverId} conectado | IP: ${data.ip} | ${data.country || ''} ${data.city || ''}`, 'success');
                } else {
                    statusEl.className = 'server-status disconnected';
                    statusEl.title = `❌ Erro: ${data.error || 'Falhou'}`;
                    addLog(`❌ Servidor ${serverId} falhou: ${data.error}`, 'error');
                }
                // Atualizar resumo após cada teste - usar setTimeout para garantir que DOM atualizou
                setTimeout(updateServersSummary, 100);
            } catch (error) {
                const statusEl = document.getElementById('status-' + serverId);
                if (statusEl) {
                    statusEl.className = 'server-status disconnected';
                    statusEl.title = 'Erro de conexão';
                }
                addLog(`❌ Erro ao testar servidor ${serverId}: ${error.message}`, 'error');
                // Atualizar resumo após erro também
                setTimeout(updateServersSummary, 100);
            }
        }
        
        function addServer(endpoint = '', numWorkers = 5) {
            serverCounter++;
            const serversList = document.getElementById('servers-list');
            const defaultEndpoint = endpoint || 'ws://50.217.254.165:40422/chrome';
            
            const serverCard = document.createElement('div');
            serverCard.className = 'server-card';
            serverCard.id = 'server-' + serverCounter;
            serverCard.innerHTML = `
                <div class="server-status pending" id="status-${serverCounter}" title="Clique em testar"></div>
                <input type="text" class="server-endpoint" 
                       placeholder="ws://IP:PORTA" 
                       value="${defaultEndpoint}"
                       title="WebSocket Endpoint">
                <input type="number" class="server-workers-input" 
                       placeholder="Workers" 
                       value="${numWorkers}" 
                       min="1" max="100"
                       title="Número de tabs/workers">
                <button class="server-remove-btn" onclick="removeServer(${serverCounter})">🗑️</button>
            `;
            
            serversList.appendChild(serverCard);
            updateServersSummary();
            
            // Testar conexão automaticamente
            testServerConnection(serverCounter, defaultEndpoint);
        }
        
        function removeServer(serverId) {
            const card = document.getElementById('server-' + serverId);
            if (card) {
                card.remove();
                updateServersSummary();
            }
        }
        
        function clearServers() {
            if (!confirm('Limpar todos os servidores?')) return;
            document.getElementById('servers-list').innerHTML = '';
            serverCounter = 0;
            updateServersSummary();
            addLog('🗑️ Servidores limpos', 'info');
        }
        
        function testAllServers() {
            const cards = document.querySelectorAll('.server-card');
            cards.forEach(card => {
                const serverId = card.id.replace('server-', '');
                const endpoint = card.querySelector('.server-endpoint').value;
                const statusEl = card.querySelector('.server-status');
                // Reset status para permitir re-teste
                statusEl.className = 'server-status pending';
                testServerConnection(serverId, endpoint);
            });
            addLog(`🔍 Testando ${cards.length} servidor(es)...`, 'info');
        }
        
        async function syncVastAI() {
            try {
                addLog('🔄 Buscando instâncias na Vast.ai...', 'info');
                
                const response = await fetch('/api/sync-vast-ai', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const result = await response.json();
                
                if (result.status === 'success') {
                    const servers = result.servers || [];
                    const existingEndpoints = new Set();
                    document.querySelectorAll('.server-endpoint').forEach(input => {
                        existingEndpoints.add(input.value.trim());
                    });
                    
                    let added = 0;
                    for (const server of servers) {
                        if (!existingEndpoints.has(server.endpoint)) {
                            addServer(server.endpoint, server.workers);
                            existingEndpoints.add(server.endpoint);
                            added++;
                            addLog(`➕ Adicionado: ${server.label || server.ip} (${server.workers} workers, ${server.cpu_ram_gb || 'N/A'} GB RAM)`, 'success');
                        }
                    }
                    
                    if (added > 0) {
                        addLog(`✅ ${added} servidor(es) adicionado(s) da Vast.ai (${result.total} running)`, 'success');
                    } else {
                        addLog(`ℹ️ Nenhum servidor novo. ${result.total} instância(s) running.`, 'info');
                    }
                } else {
                    addLog(`❌ Erro ao sincronizar: ${result.message}`, 'error');
                }
            } catch (error) {
                addLog(`❌ Erro ao sincronizar Vast.ai: ${error.message}`, 'error');
            }
        }
        
        function setAllWorkers() {
            const value = parseInt(document.getElementById('global-workers-input').value);
            if (isNaN(value) || value < 1 || value > 100) {
                addLog('⚠️ Valor inválido! Use entre 1 e 100', 'warning');
                return;
            }
            
            const inputs = document.querySelectorAll('.server-workers-input');
            inputs.forEach(input => input.value = value);
            updateServersSummary();
            addLog(`✅ ${inputs.length} servidor(es) configurados para ${value} workers`, 'success');
        }
        
        function getServers() {
            const servers = [];
            document.querySelectorAll('.server-card').forEach(card => {
                let endpoint = card.querySelector('.server-endpoint').value.trim();
                const workersInput = parseInt(card.querySelector('.server-workers-input').value) || 0;
                const statusEl = card.querySelector('.server-status');
                const isConnected = statusEl && statusEl.classList.contains('connected');
                
                // Verificar se tem /chrome no final, se não, adicionar
                if (endpoint && !endpoint.endsWith('/chrome')) {
                    endpoint = endpoint + '/chrome';
                }
                
                if (endpoint && workersInput > 0 && isConnected) {
                    servers.push({
                        endpoint: adicionarTimeoutAoEndpoint(endpoint),
                        workers: workersInput
                    });
                }
            });
            return servers;
        }
        
        function updateServersSummary() {
            const servers = getServers();
            const total = servers.reduce((sum, s) => sum + s.workers, 0);
            const summary = document.getElementById('servers-summary');
            const btn = document.getElementById('start-captcha-btn');
            
            if (servers.length > 0) {
                summary.textContent = `📊 ${servers.length} servidor(es) conectados | ${total} workers total`;
                btn.innerHTML = `🔐 Iniciar ${total} Workers`;
            } else {
                summary.textContent = 'Nenhum servidor conectado (verde)';
                btn.innerHTML = '🔐 Iniciar Captcha Solver';
            }
        }
        
        // ==================== Config ====================
        async function saveConfig() {
            try {
                const config = {
                    proxy_server: document.getElementById('proxy-server').value,
                    proxy_username: document.getElementById('proxy-username').value,
                    proxy_password: document.getElementById('proxy-password').value,
                    timeout_minutes: document.getElementById('ws-timeout-minutes').value,
                    use_proxy: document.getElementById('use-proxy').checked
                };
                
                const response = await fetch('/api/save-config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                
                const result = await response.json();
                if (result.status === 'success') {
                    addLog('💾 Configuração salva!', 'success');
                } else {
                    addLog(`❌ Erro ao salvar: ${result.message}`, 'error');
                }
            } catch (error) {
                addLog(`❌ Erro: ${error.message}`, 'error');
            }
        }
        
        async function loadConfig() {
            try {
                const response = await fetch('/api/load-config');
                const result = await response.json();
                
                if (result.status === 'success' && result.config) {
                    const cfg = result.config;
                    if (cfg.proxy_server) document.getElementById('proxy-server').value = cfg.proxy_server;
                    if (cfg.proxy_username) document.getElementById('proxy-username').value = cfg.proxy_username;
                    if (cfg.proxy_password) document.getElementById('proxy-password').value = cfg.proxy_password;
                    if (cfg.timeout_minutes) document.getElementById('ws-timeout-minutes').value = cfg.timeout_minutes;
                    if (cfg.use_proxy !== undefined) document.getElementById('use-proxy').checked = cfg.use_proxy;
                    addLog('✅ Configuração carregada', 'success');
                }
            } catch (error) {
                console.log('Usando configuração padrão');
            }
        }
        
        // ==================== Workers ====================
        function createWorkerCards(numWorkers) {
            const grid = document.getElementById('workers-grid');
            grid.innerHTML = '';
            workers = [];
            
            for (let i = 1; i <= numWorkers; i++) {
                workers.push({ id: i, status: 'pending', solved: 0, details: '' });
                
                const card = document.createElement('div');
                card.id = 'worker-' + i;
                card.className = 'worker-card pending';
                card.innerHTML = `
                    <div class="worker-number">#${i}</div>
                    <div class="worker-info">
                        <div class="worker-status-text">⏳ Aguardando</div>
                        <div class="worker-details">-</div>
                    </div>
                    <div class="worker-icon">⏳</div>
                `;
                grid.appendChild(card);
            }
            
            document.getElementById('stat-running').textContent = '0';
        }
        
        function updateWorkerCard(id, status, details = '', solved = 0) {
            const card = document.getElementById('worker-' + id);
            if (!card) return;
            
            const worker = workers.find(w => w.id === id);
            if (worker) {
                worker.status = status;
                worker.details = details;
                worker.solved = solved;
            }
            
            card.className = 'worker-card ' + status;
            
            const statusText = {
                'pending': '⏳ Aguardando',
                'running': '🔄 Resolvendo...',
                'success': `✅ ${solved} resolvidos`,
                'error': '❌ Erro'
            };
            const icons = { 'pending': '⏳', 'running': '🔄', 'success': '✅', 'error': '❌' };
            
            card.querySelector('.worker-status-text').textContent = statusText[status] || status;
            card.querySelector('.worker-details').textContent = details || '-';
            card.querySelector('.worker-icon').textContent = icons[status] || '❓';
        }
        
        function clearWorkers() {
            if (isRunning) {
                addLog('⚠️ Pare os workers antes de limpar!', 'warning');
                return;
            }
            workers = [];
            document.getElementById('workers-grid').innerHTML = 
                '<div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: var(--text-secondary);">Nenhum worker</div>';
            addLog('🗑️ Workers limpos', 'info');
        }
        
        function updateStats() {
            let running = workers.filter(w => w.status === 'running').length;
            document.getElementById('stat-running').textContent = running;
            
            if (startTime) {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const mins = Math.floor(elapsed / 60);
                const secs = elapsed % 60;
                document.getElementById('stat-time').textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
            }
        }
        
        async function fetchCaptchaStats() {
            try {
                const response = await fetch('/api/captcha-stats');
                const stats = await response.json();
                if (stats.success) {
                    document.getElementById('stat-solved').textContent = stats.solved;
                    document.getElementById('stat-reloads').textContent = stats.reloads;
                    document.getElementById('stat-rate').textContent = stats.rate_per_minute.toFixed(1);
                }
            } catch (e) {}
        }
        
        async function resetStats() {
            try {
                await fetch('/api/reset-captcha-stats', { method: 'POST' });
                document.getElementById('stat-solved').textContent = '0';
                document.getElementById('stat-reloads').textContent = '0';
                document.getElementById('stat-rate').textContent = '0.0';
                document.getElementById('stat-time').textContent = '0:00';
                addLog('🔄 Estatísticas resetadas', 'info');
            } catch (e) {
                addLog('❌ Erro ao resetar stats', 'error');
            }
        }
        
        // ==================== Captcha Solver ====================
        async function startCaptchaSolver() {
            if (isRunning) {
                addLog('⚠️ Já está em execução!', 'warning');
                return;
            }
            
            const servers = getServers();
            if (servers.length === 0) {
                const total = document.querySelectorAll('.server-card').length;
                if (total > 0) {
                    addLog('❌ Nenhum servidor conectado (verde)! Teste as conexões primeiro.', 'error');
                } else {
                    addLog('❌ Adicione pelo menos um servidor!', 'error');
                }
                return;
            }
            
            const numWorkers = servers.reduce((sum, s) => sum + s.workers, 0);
            const useProxy = document.getElementById('use-proxy').checked;
            const proxyServer = document.getElementById('proxy-server').value;
            const proxyUsername = document.getElementById('proxy-username').value;
            const proxyPassword = document.getElementById('proxy-password').value;
            
            isRunning = true;
            startTime = Date.now();
            
            // Atualizar UI
            document.getElementById('start-captcha-btn').style.display = 'none';
            document.getElementById('stop-btn').style.display = 'inline-flex';
            document.getElementById('progress-container').style.display = 'block';
            
            addLog(`🔐 Iniciando ${numWorkers} workers em ${servers.length} servidor(es)...`, 'info');
            
            // Criar cards
            createWorkerCards(numWorkers);
            
            // Iniciar polling de stats
            statsInterval = setInterval(() => {
                updateStats();
                fetchCaptchaStats();
            }, 1000);
            
            try {
                const response = await fetch('/api/run-captcha-solver', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        servers: servers,
                        use_proxy: useProxy,
                        proxy_server: proxyServer,
                        proxy_username: proxyUsername,
                        proxy_password: proxyPassword
                    })
                });
                
                if (!response.ok) throw new Error('Erro HTTP: ' + response.status);
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const text = decoder.decode(value);
                    const lines = text.split('\\n').filter(l => l.trim());
                    
                    for (const line of lines) {
                        try {
                            const data = JSON.parse(line);
                            
                            if (data.type === 'worker_start') {
                                updateWorkerCard(data.worker_id, 'running', 'Conectando...');
                                addLog(`🔄 Worker #${data.worker_id} iniciado`, 'info');
                            }
                            else if (data.type === 'worker_connected') {
                                updateWorkerCard(data.worker_id, 'running', `Conectado - Tab pronta`);
                                addLog(`✅ Worker #${data.worker_id} conectado`, 'success');
                                
                                // Atualizar progresso
                                const connected = workers.filter(w => w.status === 'running' || w.status === 'success').length;
                                document.getElementById('progress-text').textContent = `${connected} / ${workers.length}`;
                                document.getElementById('progress-fill').style.width = `${(connected / workers.length) * 100}%`;
                            }
                            else if (data.type === 'captcha_solved') {
                                updateWorkerCard(data.worker_id, 'running', `Resolvido #${data.solve_count} em ${data.time}s`);
                                addLog(`🔐 ✅ Worker #${data.worker_id} RESOLVEU #${data.solve_count} em ${data.time}s (Total: ${data.total_solved})`, 'success');
                                document.getElementById('stat-solved').textContent = data.total_solved;
                            }
                            else if (data.type === 'captcha_reload') {
                                updateWorkerCard(data.worker_id, 'running', 'Timeout - Recarregando...');
                                addLog(`⟳ Worker #${data.worker_id} timeout - recarregando`, 'warning');
                            }
                            else if (data.type === 'worker_error') {
                                updateWorkerCard(data.worker_id, 'error', data.error || 'Erro');
                                addLog(`❌ Worker #${data.worker_id} erro: ${data.error}`, 'error');
                            }
                            else if (data.type === 'complete') {
                                addLog(`🏁 Finalizado! Total: ${data.total_solved} captchas`, 'success');
                            }
                        } catch (e) {
                            console.error('Erro ao processar:', e, line);
                        }
                    }
                }
            } catch (error) {
                addLog(`❌ Erro: ${error.message}`, 'error');
            } finally {
                finishExecution();
            }
        }
        
        function finishExecution() {
            isRunning = false;
            if (statsInterval) {
                clearInterval(statsInterval);
                statsInterval = null;
            }
            updateStats();
            
            document.getElementById('start-captcha-btn').style.display = 'inline-flex';
            document.getElementById('stop-btn').style.display = 'none';
        }
        
        async function stopWorkers() {
            if (!isRunning) {
                addLog('⚠️ Nenhum worker em execução', 'warning');
                return;
            }
            try {
                await fetch('/api/stop-workers', { method: 'POST' });
                addLog('⏹️ Parando workers...', 'warning');
                finishExecution();
            } catch (error) {
                addLog(`❌ Erro ao parar: ${error.message}`, 'error');
                finishExecution();
            }
        }
        
        // ==================== Event Listeners ====================
        document.addEventListener('input', function(e) {
            if (e.target.classList.contains('server-endpoint')) {
                const card = e.target.closest('.server-card');
                if (card) {
                    const statusEl = card.querySelector('.server-status');
                    if (statusEl && !statusEl.classList.contains('connected')) {
                        statusEl.className = 'server-status pending';
                    }
                }
                updateServersSummary();
            } else if (e.target.classList.contains('server-workers-input')) {
                updateServersSummary();
            }
        });
        
        // Inicialização
        loadConfig();
        atualizarTimeoutPreview();
        
        // Adicionar um servidor padrão após carregar
        setTimeout(() => {
            if (document.querySelectorAll('.server-card').length === 0) {
                addServer();
            }
            updateServersSummary();
        }, 200);
    </script>
</body>
</html>
'''


# ==================== Funções de Turnstile ====================
def load_turnstile_sitekey() -> str:
    """Carrega a sitekey do Turnstile do arquivo."""
    try:
        with open(TURNSTILE_SITEKEY_FILE, 'r') as f:
            return json.load(f).get("sitekey", "0x4AAAAAAAykd8yJm3kQzNJc")
    except:
        return "0x4AAAAAAAykd8yJm3kQzNJc"


def save_turnstile_token(token: str, tab_id: int, processing_time: float, sitekey: str, solve_count: int):
    """Salva token do Turnstile com lock para thread-safety"""
    entry = {
        "token": token,
        "url": "https://7k.bet.br",
        "sitekey": sitekey,
        "tab_id": tab_id,
        "solve_number": solve_count,
        "timestamp": datetime.now().isoformat(),
        "expires_in": 300,
        "processing_time_seconds": round(processing_time, 2),
        "valid": True
    }
    
    with turnstile_token_lock:
        tokens = []
        if os.path.exists(TURNSTILE_TOKEN_FILE):
            try:
                with open(TURNSTILE_TOKEN_FILE, 'r') as f:
                    data = json.load(f)
                    tokens = data if isinstance(data, list) else [data]
            except:
                pass
        
        tokens.append(entry)
        
        with open(TURNSTILE_TOKEN_FILE, 'w') as f:
            json.dump(tokens, f, indent=2, ensure_ascii=False)
    
    log_print(f"[Captcha] ✅ Token salvo para tab {tab_id} (#{solve_count})")


def run_single_worker_captcha(worker_id: int, ws_endpoint: str,
                               proxy_server: str, proxy_username: str, proxy_password: str,
                               use_proxy: bool, results_queue: list = None):
    """
    Worker para resolver Turnstile continuamente via Browserless.
    Mantém a aba aberta e recarrega após cada resolução ou timeout.
    """
    global workers_should_stop, captcha_stats
    sys.excepthook = suppress_playwright_errors
    
    result = {
        "worker_id": worker_id,
        "success": False,
        "error": None,
        "captcha_solved": 0
    }
    
    start = time.time()
    browser = None
    context = None
    page = None
    solve_count = 0
    sitekey = load_turnstile_sitekey()
    
    # URL do site real - navegar diretamente para o site com Turnstile
    url = "https://7k.bet.br/"
    
    try:
        log_print(f"[Tab {worker_id}] Conectando ao Browserless...")
        
        # Notificar início
        if results_queue is not None:
            results_queue.append({
                "type": "worker_start",
                "worker_id": worker_id,
                "endpoint": ws_endpoint
            })
        
        with sync_playwright() as p:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                browser = p.chromium.connect_over_cdp(ws_endpoint, timeout=60000)
            
            # Pegar user agent real
            temp_page = browser.new_page()
            real_user_agent = temp_page.evaluate("navigator.userAgent")
            temp_page.close()
            
            log_print(f"[Tab {worker_id}] User-Agent: {real_user_agent[:60]}...")
            
            # Configurações do contexto
            context_opts = {
                "viewport": {"width": 380, "height": 320},
                "user_agent": real_user_agent,
                "ignore_https_errors": True
            }
            
            if use_proxy:
                context_opts["proxy"] = {
                    "server": proxy_server,
                    "username": proxy_username,
                    "password": proxy_password
                }
            
            context = browser.new_context(**context_opts)
            page = context.new_page()
            
            # Navegar diretamente para o site real
            # Aumentar timeout para 60s pois o site pode demorar
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                log_print(f"[Tab {worker_id}] Página carregada!")
            except Exception as nav_error:
                log_print(f"[Tab {worker_id}] Navegação: {str(nav_error)[:50]}...")
                # Tentar novamente com timeout maior
                page.goto(url, timeout=90000, wait_until="load")
            
            # Notificar conexão
            if results_queue is not None:
                results_queue.append({
                    "type": "worker_connected",
                    "worker_id": worker_id
                })
            
            # Aguardar iframe aparecer
            for _ in range(15):
                iframe = page.query_selector("iframe")
                if iframe:
                    break
                time.sleep(1)
                with workers_stop_lock:
                    if workers_should_stop:
                        break
            
            log_print(f"[Tab {worker_id}] Iniciando loop de resolução...")
            
            # Loop infinito até parar
            while True:
                with workers_stop_lock:
                    if workers_should_stop:
                        log_print(f"[Tab {worker_id}] Parando...")
                        break
                
                attempt_start = time.time()
                click_count = 0
                resolved = False
                max_time = 60
                
                # Aguardar iframe ficar pronto
                for _ in range(10):
                    iframe = page.query_selector("iframe")
                    if iframe:
                        box = iframe.bounding_box()
                        if box and box["width"] > 0:
                            break
                    time.sleep(1)
                    with workers_stop_lock:
                        if workers_should_stop:
                            break
                
                # Loop de resolução
                while time.time() - attempt_start < max_time:
                    with workers_stop_lock:
                        if workers_should_stop:
                            break
                    
                    # Verificar token - várias formas possíveis
                    try:
                        token = None
                        
                        # Método 1: Input hidden com name cf-turnstile-response
                        elem = page.query_selector("[name=cf-turnstile-response]")
                        if elem:
                            token = elem.get_attribute("value")
                        
                        # Método 2: Input com id cf-turnstile-response
                        if not token or len(token) < 50:
                            elem = page.query_selector("#cf-turnstile-response")
                            if elem:
                                token = elem.get_attribute("value")
                        
                        # Método 3: Verificar via JavaScript o callback do Turnstile
                        if not token or len(token) < 50:
                            try:
                                token = page.evaluate("""() => {
                                    // Tentar várias formas de obter o token
                                    const inputs = document.querySelectorAll('input[type="hidden"]');
                                    for (const input of inputs) {
                                        if (input.value && input.value.length > 100) {
                                            return input.value;
                                        }
                                    }
                                    // Verificar se existe window.turnstileToken
                                    if (window.turnstileToken) return window.turnstileToken;
                                    return null;
                                }""")
                            except:
                                pass
                        
                        if token and len(token) > 50:
                                processing_time = time.time() - attempt_start
                                solve_count += 1
                                
                                save_turnstile_token(token, worker_id, processing_time, sitekey, solve_count)
                                
                                with captcha_stats_lock:
                                    captcha_stats["solved"] += 1
                                    total_solved = captcha_stats["solved"]
                                
                                log_print(f"✓ [Tab {worker_id}] #{solve_count} RESOLVIDO em {processing_time:.1f}s (Total: {total_solved})")
                                
                                if results_queue is not None:
                                    results_queue.append({
                                        "type": "captcha_solved",
                                        "worker_id": worker_id,
                                        "solve_count": solve_count,
                                        "time": round(processing_time, 1),
                                        "total_solved": total_solved,
                                        "token_preview": token[:30] + "..."
                                    })
                                
                                resolved = True
                                break
                    except:
                        pass
                    
                    # Clicar no checkbox
                    if click_count < 5:
                        try:
                            iframe = page.query_selector("iframe")
                            if iframe:
                                box = iframe.bounding_box()
                                if box and box["width"] > 0:
                                    frame = iframe.content_frame()
                                    if frame:
                                        checkbox = frame.query_selector("input")
                                        if checkbox:
                                            cbox = checkbox.bounding_box()
                                            if cbox:
                                                x = cbox["x"] + cbox["width"]/2 + random.randint(-3, 3)
                                                y = cbox["y"] + cbox["height"]/2 + random.randint(-3, 3)
                                                page.mouse.click(x, y)
                                                click_count += 1
                                        elif click_count < 2:
                                            x = box["x"] + box["width"]/2
                                            y = box["y"] + box["height"]/2
                                            page.mouse.click(x, y)
                                            click_count += 1
                        except:
                            pass
                    
                    time.sleep(0.1)
                
                # Timeout
                if not resolved:
                    with workers_stop_lock:
                        if workers_should_stop:
                            break
                    
                    with captcha_stats_lock:
                        captcha_stats["reloads"] += 1
                    
                    log_print(f"⟳ [Tab {worker_id}] Timeout - recarregando...")
                    
                    if results_queue is not None:
                        results_queue.append({
                            "type": "captcha_reload",
                            "worker_id": worker_id
                        })
                
                # Recarregar
                with workers_stop_lock:
                    if workers_should_stop:
                        break
                
                try:
                    page.reload()
                    time.sleep(1)
                except:
                    try:
                        page.goto(url)
                    except:
                        pass
            
            result["success"] = True
            result["captcha_solved"] = solve_count
            
    except Exception as e:
        result["error"] = str(e)
        log_print(f"[Tab {worker_id}] ❌ Erro: {str(e)[:100]}")
        
        if results_queue is not None:
            results_queue.append({
                "type": "worker_error",
                "worker_id": worker_id,
                "error": str(e)[:100]
            })
    
    finally:
        try:
            if page:
                try:
                    page.close()
                except:
                    pass
        except:
            pass
        
        try:
            if context:
                try:
                    context.close()
                except:
                    pass
        except:
            pass
        
        try:
            if browser:
                try:
                    browser.close()
                except:
                    pass
        except:
            pass
    
    result["duration"] = round(time.time() - start, 2)
    sys.excepthook = original_excepthook
    
    return result


def run_captcha_workers_thread(servers: list, proxy_server: str, proxy_username: str,
                                proxy_password: str, use_proxy: bool, results_queue: list):
    """Thread que executa múltiplos workers de captcha em múltiplos servidores."""
    global workers_should_stop, captcha_stats
    
    with workers_stop_lock:
        workers_should_stop = False
    
    with captcha_stats_lock:
        captcha_stats["solved"] = 0
        captcha_stats["failed"] = 0
        captcha_stats["reloads"] = 0
        captcha_stats["start_time"] = time.time()
    
    start_time = time.time()
    
    # Criar lista de tarefas: (worker_id, ws_endpoint)
    tasks = []
    worker_id = 0
    for server in servers:
        endpoint = server["endpoint"]
        num_workers = server["workers"]
        for _ in range(num_workers):
            worker_id += 1
            tasks.append((worker_id, endpoint))
    
    log_print(f"[Captcha] Iniciando {len(tasks)} workers em {len(servers)} servidor(es)")
    
    # Executar workers em paralelo
    max_workers = min(len(tasks), 50)  # Limite de threads simultâneas
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for wid, endpoint in tasks:
            future = executor.submit(
                run_single_worker_captcha,
                wid, endpoint,
                proxy_server, proxy_username, proxy_password,
                use_proxy, results_queue
            )
            futures.append(future)
        
        # Aguardar todos finalizarem
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                log_print(f"[Captcha] Erro em worker: {str(e)[:50]}")
    
    # Resumo final
    elapsed = time.time() - start_time
    with captcha_stats_lock:
        total_solved = captcha_stats["solved"]
    
    results_queue.append({
        "type": "complete",
        "total_solved": total_solved,
        "elapsed": round(elapsed, 1)
    })
    
    log_print(f"[Captcha] Finalizado! {total_solved} captchas em {elapsed:.1f}s")


# ==================== API Routes ====================
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/test-connection", methods=["POST"])
def api_test_connection():
    """Testa conexão com um servidor Browserless."""
    data = request.get_json()
    ws_endpoint = data.get("ws_endpoint", DEFAULT_WS_ENDPOINT)
    proxy_server = data.get("proxy_server", PROXY_CONFIG["server"])
    proxy_username = data.get("proxy_username", PROXY_CONFIG["username"])
    proxy_password = data.get("proxy_password", PROXY_CONFIG["password"])
    
    browser = None
    context = None
    page = None
    
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(ws_endpoint, timeout=15000)
            except Exception as conn_error:
                error_msg = str(conn_error)
                if "KeyError" in error_msg:
                    return jsonify({
                        "success": False,
                        "error": "Erro interno do Playwright. Verifique o endpoint WebSocket."
                    }), 500
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Falha ao conectar: {error_msg[:100]}"
                    }), 500
            
            try:
                context = browser.new_context(
                    proxy={
                        "server": proxy_server,
                        "username": proxy_username,
                        "password": proxy_password
                    },
                    ignore_https_errors=True
                )
                page = context.new_page()
                page.goto("https://ipinfo.io/json", timeout=30000, wait_until="domcontentloaded")
                content = page.content()
                
                ip_match = re.search(r'"ip":\s*"([^"]+)"', content)
                country_match = re.search(r'"country":\s*"([^"]+)"', content)
                city_match = re.search(r'"city":\s*"([^"]+)"', content)
                
                ip = ip_match.group(1) if ip_match else "N/A"
                country = country_match.group(1) if country_match else "N/A"
                city = city_match.group(1) if city_match else "N/A"
                
                return jsonify({
                    "success": True,
                    "ip": ip,
                    "country": country,
                    "city": city
                })
            except Exception as inner_error:
                error_msg = str(inner_error)
                if "KeyError" in error_msg:
                    return jsonify({
                        "success": False,
                        "error": "Erro interno do Playwright (WebSocket/CDP)"
                    }), 500
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Erro na navegação: {error_msg[:100]}"
                    }), 500
            finally:
                try:
                    if page:
                        page.close()
                except:
                    pass
                try:
                    if context:
                        context.close()
                except:
                    pass
                try:
                    if browser:
                        browser.close()
                except:
                    pass
    except Exception as e:
        return jsonify({"success": False, "error": str(e)[:100]}), 500


@app.route("/api/sync-vast-ai", methods=["POST"])
def api_sync_vast_ai():
    """Busca instâncias running na Vast.ai."""
    try:
        headers = {"Authorization": f"Bearer {VAST_AI_API_KEY}"}
        response = requests.get(VAST_AI_API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        instances = data.get("instances", [])
        
        running_instances = [
            inst for inst in instances 
            if inst.get("actual_status") == "running" or inst.get("cur_state") == "running"
        ]
        
        servers_to_add = []
        for instance in running_instances:
            public_ip = instance.get("public_ipaddr")
            instance_id = instance.get("id")
            label = instance.get("label", f"Instance {instance_id}")
            
            if public_ip:
                ports = instance.get("ports", {})
                browserless_port = None
                
                port_key = f"{BROWSERLESS_INTERNAL_PORT}/tcp"
                if port_key in ports:
                    port_mappings = ports[port_key]
                    if port_mappings and len(port_mappings) > 0:
                        browserless_port = port_mappings[0].get("HostPort")
                
                if browserless_port:
                    ws_endpoint = f"ws://{public_ip}:{browserless_port}/chrome"
                else:
                    ws_endpoint = f"ws://{public_ip}:{DEFAULT_BROWSERLESS_PORT}/chrome"
                
                cpu_ram_mb = instance.get("cpu_ram") or 0
                # 1 worker para cada 1GB de RAM (mínimo 1, máximo 10)
                num_workers = max(1, min(10, int(cpu_ram_mb / 1024))) if cpu_ram_mb > 0 else 5
                
                servers_to_add.append({
                    "endpoint": ws_endpoint,
                    "workers": num_workers,
                    "label": label,
                    "instance_id": instance_id,
                    "ip": public_ip,
                    "port": browserless_port or DEFAULT_BROWSERLESS_PORT,
                    "cpu_ram_mb": cpu_ram_mb,
                    "cpu_ram_gb": round(cpu_ram_mb / 1024, 2) if cpu_ram_mb else 0
                })
        
        return jsonify({
            "status": "success",
            "total": len(running_instances),
            "added": len(servers_to_add),
            "servers": servers_to_add
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error",
            "message": f"Erro ao conectar com Vast.ai: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Erro: {str(e)}"
        }), 500


@app.route("/api/run-captcha-solver", methods=["POST"])
def api_run_captcha_solver():
    """Inicia os workers de captcha."""
    global workers_should_stop
    
    try:
        data = request.get_json()
        servers = data.get("servers", [])
        use_proxy = data.get("use_proxy", True)
        proxy_server = data.get("proxy_server", PROXY_CONFIG["server"])
        proxy_username = data.get("proxy_username", PROXY_CONFIG["username"])
        proxy_password = data.get("proxy_password", PROXY_CONFIG["password"])
        
        if not servers:
            return jsonify({"error": "Nenhum servidor fornecido"}), 400
        
        with workers_stop_lock:
            workers_should_stop = False
        
        results_queue = []
        
        thread = threading.Thread(
            target=run_captcha_workers_thread,
            args=(servers, proxy_server, proxy_username, proxy_password, use_proxy, results_queue)
        )
        thread.start()
        
        def generate():
            sent_count = 0
            while thread.is_alive() or sent_count < len(results_queue):
                while sent_count < len(results_queue):
                    yield json.dumps(results_queue[sent_count]) + "\n"
                    sent_count += 1
                time.sleep(0.1)
            
            while sent_count < len(results_queue):
                yield json.dumps(results_queue[sent_count]) + "\n"
                sent_count += 1
        
        return app.response_class(generate(), mimetype='application/x-ndjson')
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stop-workers", methods=["POST"])
def api_stop_workers():
    """Para todos os workers."""
    global workers_should_stop
    with workers_stop_lock:
        workers_should_stop = True
    return jsonify({"status": "requested", "message": "Workers serão parados"})


@app.route("/api/captcha-stats", methods=["GET"])
def api_captcha_stats():
    """Retorna estatísticas dos captchas."""
    try:
        with captcha_stats_lock:
            elapsed = 0
            rate = 0
            if captcha_stats["start_time"]:
                elapsed = time.time() - captcha_stats["start_time"]
                if elapsed > 0:
                    rate = captcha_stats["solved"] / (elapsed / 60)
            
            return jsonify({
                "success": True,
                "solved": captcha_stats["solved"],
                "failed": captcha_stats["failed"],
                "reloads": captcha_stats["reloads"],
                "elapsed_seconds": round(elapsed, 1),
                "rate_per_minute": round(rate, 1)
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/reset-captcha-stats", methods=["POST"])
def api_reset_captcha_stats():
    """Reseta as estatísticas."""
    global captcha_stats
    try:
        with captcha_stats_lock:
            captcha_stats["solved"] = 0
            captcha_stats["failed"] = 0
            captcha_stats["reloads"] = 0
            captcha_stats["start_time"] = None
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/save-config", methods=["POST"])
def api_save_config():
    """Salva configuração."""
    try:
        data = request.get_json()
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/load-config", methods=["GET"])
def api_load_config():
    """Carrega configuração."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            return jsonify({"status": "success", "config": config})
        return jsonify({"status": "not_found", "config": None})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/toggle-logs", methods=["POST"])
def api_toggle_logs():
    """Ativa/desativa logs."""
    global logs_enabled
    try:
        data = request.get_json()
        enabled = data.get("enabled", True)
        with logs_enabled_lock:
            logs_enabled = enabled
        return jsonify({"success": True, "enabled": logs_enabled})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== Main ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🔐 CAPTCHA SOLVER DASHBOARD")
    print("=" * 60)
    print()
    print("Funcionalidades:")
    print("  • Sincronização de máquinas Vast.ai")
    print("  • Múltiplos servidores Browserless")
    print("  • Turnstile Persistent Solver")
    print("  • Logs de conexão em tempo real")
    print()
    print("Acesse: http://localhost:5001")
    print()
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)

