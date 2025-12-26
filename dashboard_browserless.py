"""
Dashboard Browserless - Monitoramento de Conexão
Visualize status, IP, e teste de acesso ao YouTube
"""
import asyncio
import json
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
import aiohttp
import threading

# Configurações
BROWSERLESS_API_KEY = "2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72"
BROWSERLESS_REST_URL = "https://production-sfo.browserless.io"
BROWSERLESS_WS_URL = f"wss://production-sfo.browserless.io?token={BROWSERLESS_API_KEY}"

app = Flask(__name__)

# Estado global
state = {
    "last_test": None,
    "ip_info": None,
    "youtube_test": None,
    "connection_status": "não testado",
    "tests_count": 0,
    "success_count": 0,
    "fail_count": 0
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌐 Browserless Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-card: #1a1f2e;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-purple: #8b5cf6;
            --accent-orange: #f59e0b;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --border: #374151;
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
                radial-gradient(ellipse at top left, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
                radial-gradient(ellipse at bottom right, rgba(139, 92, 246, 0.1) 0%, transparent 50%);
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        header {
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem;
            background: linear-gradient(135deg, var(--bg-card) 0%, rgba(59, 130, 246, 0.1) 100%);
            border-radius: 20px;
            border: 1px solid var(--border);
        }
        
        h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }
        
        .subtitle {
            color: var(--text-secondary);
            font-size: 1.1rem;
        }
        
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1.5rem;
            border-radius: 50px;
            font-weight: 600;
            font-size: 0.9rem;
            margin-top: 1rem;
        }
        
        .status-connected {
            background: rgba(16, 185, 129, 0.2);
            color: var(--accent-green);
            border: 1px solid var(--accent-green);
        }
        
        .status-disconnected {
            background: rgba(239, 68, 68, 0.2);
            color: var(--accent-red);
            border: 1px solid var(--accent-red);
        }
        
        .status-testing {
            background: rgba(245, 158, 11, 0.2);
            color: var(--accent-orange);
            border: 1px solid var(--accent-orange);
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .pulse-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: currentColor;
            animation: pulse 1.5s infinite;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .card {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
        }
        
        .card-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        
        .card-icon {
            width: 40px;
            height: 40px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.2rem;
        }
        
        .icon-blue { background: rgba(59, 130, 246, 0.2); }
        .icon-green { background: rgba(16, 185, 129, 0.2); }
        .icon-purple { background: rgba(139, 92, 246, 0.2); }
        .icon-orange { background: rgba(245, 158, 11, 0.2); }
        
        .card-title {
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-secondary);
        }
        
        .card-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .card-value.small {
            font-size: 1rem;
            word-break: break-all;
        }
        
        .info-grid {
            display: grid;
            gap: 0.75rem;
        }
        
        .info-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--border);
        }
        
        .info-row:last-child {
            border-bottom: none;
        }
        
        .info-label {
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
        
        .info-value {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 1rem 2rem;
            border: none;
            border-radius: 12px;
            font-family: inherit;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
            color: white;
        }
        
        .btn-primary:hover {
            transform: scale(1.02);
            box-shadow: 0 5px 20px rgba(59, 130, 246, 0.4);
        }
        
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        
        .actions {
            display: flex;
            gap: 1rem;
            justify-content: center;
            flex-wrap: wrap;
            margin-bottom: 2rem;
        }
        
        .url-tester {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border);
            margin-bottom: 2rem;
        }
        
        .url-tester-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1rem;
        }
        
        .url-input-container {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }
        
        .url-input {
            flex: 1;
            min-width: 300px;
            padding: 1rem 1.5rem;
            border: 2px solid var(--border);
            border-radius: 12px;
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.95rem;
            transition: all 0.2s;
        }
        
        .url-input:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
        }
        
        .url-input::placeholder {
            color: var(--text-secondary);
            opacity: 0.7;
        }
        
        .btn-go {
            background: linear-gradient(135deg, var(--accent-green), #059669);
            color: white;
            padding: 1rem 2rem;
            min-width: 150px;
        }
        
        .btn-go:hover {
            transform: scale(1.02);
            box-shadow: 0 5px 20px rgba(16, 185, 129, 0.4);
        }
        
        .url-result {
            margin-top: 1.5rem;
            padding: 1rem;
            background: var(--bg-primary);
            border-radius: 12px;
            display: none;
        }
        
        .url-result.show {
            display: block;
        }
        
        .url-result.success {
            border-left: 4px solid var(--accent-green);
        }
        
        .url-result.error {
            border-left: 4px solid var(--accent-red);
        }
        
        .result-title {
            font-weight: 600;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .result-details {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .quick-links {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }
        
        .quick-link {
            padding: 0.4rem 0.8rem;
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 20px;
            font-size: 0.8rem;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .quick-link:hover {
            background: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
        }
        
        .log-container {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 1.5rem;
            border: 1px solid var(--border);
        }
        
        .log-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .log-title {
            font-size: 1.2rem;
            font-weight: 600;
        }
        
        .log-content {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            background: var(--bg-primary);
            padding: 1rem;
            border-radius: 8px;
            max-height: 300px;
            overflow-y: auto;
            white-space: pre-wrap;
            line-height: 1.6;
        }
        
        .log-line {
            padding: 0.25rem 0;
        }
        
        .log-success { color: var(--accent-green); }
        .log-error { color: var(--accent-red); }
        .log-info { color: var(--accent-blue); }
        .log-warning { color: var(--accent-orange); }
        
        .stats-row {
            display: flex;
            gap: 2rem;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 1rem;
        }
        
        .stat {
            text-align: center;
        }
        
        .stat-value {
            font-family: 'JetBrains Mono', monospace;
            font-size: 2rem;
            font-weight: 700;
        }
        
        .stat-label {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .youtube-preview {
            background: linear-gradient(135deg, #ff0000 0%, #cc0000 100%);
            border-radius: 12px;
            padding: 1rem;
            margin-top: 1rem;
        }
        
        .yt-title {
            font-weight: 600;
            margin-bottom: 0.5rem;
        }
        
        .yt-url {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            opacity: 0.8;
            word-break: break-all;
        }
        
        .api-key-display {
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg-primary);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.85rem;
            display: inline-block;
        }
        
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid transparent;
            border-top-color: currentColor;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        footer {
            text-align: center;
            padding: 2rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌐 Browserless Dashboard</h1>
            <p class="subtitle">Monitoramento de Conexão e Testes</p>
            <div id="status-badge" class="status-badge status-disconnected">
                <span class="pulse-dot"></span>
                <span id="status-text">Aguardando teste...</span>
            </div>
        </header>
        
        <div class="actions">
            <button class="btn btn-primary" onclick="runTest()" id="test-btn">
                🧪 Testar Conexão
            </button>
            <button class="btn btn-secondary" onclick="runYoutubeTest()">
                📺 Testar YouTube
            </button>
            <button class="btn btn-secondary" onclick="refreshData()">
                🔄 Atualizar
            </button>
        </div>
        
        <!-- URL Input Section -->
        <div style="background: linear-gradient(135deg, #1a1f2e 0%, rgba(16, 185, 129, 0.1) 100%); border-radius: 16px; padding: 1.5rem; border: 1px solid #374151; margin-bottom: 2rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;">
                <div style="width: 40px; height: 40px; border-radius: 10px; background: rgba(16, 185, 129, 0.2); display: flex; align-items: center; justify-content: center; font-size: 1.2rem;">🌍</div>
                <div>
                    <div style="font-size: 1.2rem; font-weight: 600; color: #f3f4f6;">Testar URL Personalizada</div>
                    <div style="color: #9ca3af; font-size: 0.85rem;">Digite qualquer URL para acessar via Browserless</div>
                </div>
            </div>
            <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                <input type="text" id="custom-url" 
                       style="flex: 1; min-width: 300px; padding: 1rem 1.5rem; border: 2px solid #374151; border-radius: 12px; background: #0a0e17; color: #f3f4f6; font-family: 'JetBrains Mono', monospace; font-size: 0.95rem;"
                       placeholder="https://exemplo.com ou www.exemplo.com"
                       onkeypress="if(event.key === 'Enter') testCustomUrl()">
                <button onclick="testCustomUrl()" id="url-btn" 
                        style="background: linear-gradient(135deg, #10b981, #059669); color: white; padding: 1rem 2rem; min-width: 150px; border: none; border-radius: 12px; font-family: inherit; font-size: 1rem; font-weight: 600; cursor: pointer;">
                    🚀 Buscar
                </button>
            </div>
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1rem;">
                <span style="color: #9ca3af; font-size: 0.8rem; margin-right: 0.5rem;">Links rápidos:</span>
                <span onclick="document.getElementById('custom-url').value='https://www.google.com'" style="padding: 0.4rem 0.8rem; background: #111827; border: 1px solid #374151; border-radius: 20px; font-size: 0.8rem; color: #9ca3af; cursor: pointer;">Google</span>
                <span onclick="document.getElementById('custom-url').value='https://www.youtube.com'" style="padding: 0.4rem 0.8rem; background: #111827; border: 1px solid #374151; border-radius: 20px; font-size: 0.8rem; color: #9ca3af; cursor: pointer;">YouTube</span>
                <span onclick="document.getElementById('custom-url').value='https://www.bet365.com'" style="padding: 0.4rem 0.8rem; background: #111827; border: 1px solid #374151; border-radius: 20px; font-size: 0.8rem; color: #9ca3af; cursor: pointer;">Bet365</span>
                <span onclick="document.getElementById('custom-url').value='https://www.bet7k.com'" style="padding: 0.4rem 0.8rem; background: #111827; border: 1px solid #374151; border-radius: 20px; font-size: 0.8rem; color: #9ca3af; cursor: pointer;">Bet7k</span>
                <span onclick="document.getElementById('custom-url').value='https://ipinfo.io/json'" style="padding: 0.4rem 0.8rem; background: #111827; border: 1px solid #374151; border-radius: 20px; font-size: 0.8rem; color: #9ca3af; cursor: pointer;">IP Info</span>
            </div>
            <div id="url-result" style="margin-top: 1.5rem; padding: 1rem; background: #0a0e17; border-radius: 12px; display: none; border-left: 4px solid #10b981;">
                <div style="font-weight: 600; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem;">
                    <span id="result-icon">✓</span>
                    <span id="result-text">Resultado</span>
                </div>
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #9ca3af;">
                    <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #374151;">
                        <span>URL Acessada</span>
                        <span id="result-url" style="color: #f3f4f6; word-break: break-all;">-</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #374151;">
                        <span>Título</span>
                        <span id="result-page-title" style="color: #f3f4f6;">-</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #374151;">
                        <span>Status</span>
                        <span id="result-status" style="color: #f3f4f6;">-</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; padding: 0.5rem 0;">
                        <span>Tamanho</span>
                        <span id="result-size" style="color: #f3f4f6;">-</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- URL Tester -->
        <div class="url-tester">
            <div class="url-tester-header">
                <div class="card-icon icon-green">🌍</div>
                <div>
                    <div class="card-title" style="color: var(--text-primary); font-size: 1.2rem;">Testar URL Personalizada</div>
                    <div style="color: var(--text-secondary); font-size: 0.85rem;">Digite qualquer URL para acessar via Browserless</div>
                </div>
            </div>
            <div class="url-input-container">
                <input type="text" class="url-input" id="custom-url" 
                       placeholder="https://exemplo.com ou www.exemplo.com"
                       onkeypress="if(event.key === 'Enter') testCustomUrl()">
                <button class="btn btn-go" onclick="testCustomUrl()" id="url-btn">
                    🚀 Acessar
                </button>
            </div>
            <div class="quick-links">
                <span style="color: var(--text-secondary); font-size: 0.8rem; margin-right: 0.5rem;">Links rápidos:</span>
                <span class="quick-link" onclick="setUrl('https://www.google.com')">Google</span>
                <span class="quick-link" onclick="setUrl('https://www.youtube.com')">YouTube</span>
                <span class="quick-link" onclick="setUrl('https://www.facebook.com')">Facebook</span>
                <span class="quick-link" onclick="setUrl('https://www.instagram.com')">Instagram</span>
                <span class="quick-link" onclick="setUrl('https://www.bet365.com')">Bet365</span>
                <span class="quick-link" onclick="setUrl('https://www.bet7k.com')">Bet7k</span>
                <span class="quick-link" onclick="setUrl('https://ipinfo.io/json')">IP Info</span>
            </div>
            <div class="url-result" id="url-result">
                <div class="result-title" id="result-title">
                    <span id="result-icon">✓</span>
                    <span id="result-text">Resultado</span>
                </div>
                <div class="result-details">
                    <div class="info-grid">
                        <div class="info-row">
                            <span class="info-label">URL Acessada</span>
                            <span class="info-value small" id="result-url">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Título da Página</span>
                            <span class="info-value" id="result-page-title">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Status</span>
                            <span class="info-value" id="result-status">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Tamanho do Conteúdo</span>
                            <span class="info-value" id="result-size">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Tempo de Resposta</span>
                            <span class="info-value" id="result-time">-</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="grid">
            <!-- Connection Card -->
            <div class="card">
                <div class="card-header">
                    <div class="card-icon icon-blue">🔌</div>
                    <div class="card-title">Status da Conexão</div>
                </div>
                <div class="info-grid">
                    <div class="info-row">
                        <span class="info-label">Servidor</span>
                        <span class="info-value">production-sfo.browserless.io</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Protocolo</span>
                        <span class="info-value">WebSocket (CDP)</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Região</span>
                        <span class="info-value">San Francisco, USA</span>
                    </div>
                </div>
            </div>
            
            <!-- API Key Card -->
            <div class="card">
                <div class="card-header">
                    <div class="card-icon icon-purple">🔑</div>
                    <div class="card-title">API Key</div>
                </div>
                <div class="api-key-display">
                    {{ api_key_masked }}
                </div>
                <div class="info-grid" style="margin-top: 1rem;">
                    <div class="info-row">
                        <span class="info-label">Tipo</span>
                        <span class="info-value">BaaS v2</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Endpoints</span>
                        <span class="info-value">/content, /scrape, CDP</span>
                    </div>
                </div>
            </div>
            
            <!-- IP Info Card -->
            <div class="card">
                <div class="card-header">
                    <div class="card-icon icon-green">📍</div>
                    <div class="card-title">IP do Navegador (Browserless)</div>
                </div>
                <div id="ip-info">
                    <div class="card-value" id="ip-address">---.---.---.---</div>
                    <div class="info-grid" style="margin-top: 1rem;">
                        <div class="info-row">
                            <span class="info-label">Cidade</span>
                            <span class="info-value" id="ip-city">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Região</span>
                            <span class="info-value" id="ip-region">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">País</span>
                            <span class="info-value" id="ip-country">-</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Org</span>
                            <span class="info-value" id="ip-org">-</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Stats Card -->
            <div class="card">
                <div class="card-header">
                    <div class="card-icon icon-orange">📊</div>
                    <div class="card-title">Estatísticas</div>
                </div>
                <div class="stats-row">
                    <div class="stat">
                        <div class="stat-value" id="total-tests" style="color: var(--accent-blue);">0</div>
                        <div class="stat-label">Testes</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="success-tests" style="color: var(--accent-green);">0</div>
                        <div class="stat-label">Sucesso</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value" id="fail-tests" style="color: var(--accent-red);">0</div>
                        <div class="stat-label">Falha</div>
                    </div>
                </div>
                <div class="info-row" style="margin-top: 1rem;">
                    <span class="info-label">Último teste</span>
                    <span class="info-value" id="last-test">-</span>
                </div>
            </div>
        </div>
        
        <!-- YouTube Test Result -->
        <div class="card" style="margin-bottom: 2rem;">
            <div class="card-header">
                <div class="card-icon icon-purple">📺</div>
                <div class="card-title">Último Teste YouTube</div>
            </div>
            <div id="youtube-result">
                <div class="info-grid">
                    <div class="info-row">
                        <span class="info-label">Título</span>
                        <span class="info-value" id="yt-title">-</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">URL</span>
                        <span class="info-value small" id="yt-url">-</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Status</span>
                        <span class="info-value" id="yt-status">-</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">Conteúdo (bytes)</span>
                        <span class="info-value" id="yt-size">-</span>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="log-container">
            <div class="log-header">
                <h3 class="log-title">📋 Logs</h3>
                <button class="btn btn-secondary" onclick="clearLogs()" style="padding: 0.5rem 1rem; font-size: 0.85rem;">
                    🗑️ Limpar
                </button>
            </div>
            <div class="log-content" id="logs">
<span class="log-info">[Sistema] Dashboard iniciado - aguardando testes...</span>
            </div>
        </div>
        
        <footer>
            🚀 Browserless BaaS v2 | Documentação: <a href="https://docs.browserless.io/baas/start" target="_blank" style="color: var(--accent-blue);">docs.browserless.io</a>
        </footer>
    </div>
    
    <script>
        function addLog(message, type = 'info') {
            const logs = document.getElementById('logs');
            const time = new Date().toLocaleTimeString('pt-BR');
            const logClass = 'log-' + type;
            logs.innerHTML = `<div class="log-line ${logClass}">[${time}] ${message}</div>` + logs.innerHTML;
        }
        
        function clearLogs() {
            document.getElementById('logs').innerHTML = '<span class="log-info">[Sistema] Logs limpos</span>';
        }
        
        function setStatus(status, text) {
            const badge = document.getElementById('status-badge');
            const statusText = document.getElementById('status-text');
            
            badge.className = 'status-badge status-' + status;
            statusText.textContent = text;
        }
        
        async function runTest() {
            const btn = document.getElementById('test-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> Testando...';
            setStatus('testing', 'Testando conexão...');
            addLog('Iniciando teste de conexão...', 'info');
            
            try {
                const response = await fetch('/api/test');
                const data = await response.json();
                
                if (data.success) {
                    setStatus('connected', 'Conectado ao Browserless ✓');
                    addLog('Conexão bem sucedida!', 'success');
                    
                    // Update IP info
                    document.getElementById('ip-address').textContent = data.ip || 'N/A';
                    document.getElementById('ip-city').textContent = data.city || 'N/A';
                    document.getElementById('ip-region').textContent = data.region || 'N/A';
                    document.getElementById('ip-country').textContent = data.country || 'N/A';
                    document.getElementById('ip-org').textContent = data.org || 'N/A';
                    
                    addLog(`IP: ${data.ip} (${data.city}, ${data.region}, ${data.country})`, 'success');
                } else {
                    setStatus('disconnected', 'Falha na conexão');
                    addLog('Falha: ' + (data.error || 'Erro desconhecido'), 'error');
                }
                
                updateStats();
            } catch (error) {
                setStatus('disconnected', 'Erro de conexão');
                addLog('Erro: ' + error.message, 'error');
            }
            
            btn.disabled = false;
            btn.innerHTML = '🧪 Testar Conexão';
        }
        
        async function runYoutubeTest() {
            addLog('Iniciando teste YouTube...', 'info');
            setStatus('testing', 'Acessando YouTube...');
            
            try {
                const response = await fetch('/api/test-youtube');
                const data = await response.json();
                
                if (data.success) {
                    setStatus('connected', 'YouTube acessado ✓');
                    
                    document.getElementById('yt-title').textContent = data.title || 'N/A';
                    document.getElementById('yt-url').textContent = data.url || 'N/A';
                    document.getElementById('yt-status').textContent = '✓ Carregado';
                    document.getElementById('yt-size').textContent = data.content_size || 'N/A';
                    
                    addLog(`YouTube carregado: ${data.title}`, 'success');
                } else {
                    document.getElementById('yt-status').textContent = '✗ Falhou';
                    addLog('Falha YouTube: ' + (data.error || 'Erro'), 'error');
                }
                
                updateStats();
            } catch (error) {
                addLog('Erro YouTube: ' + error.message, 'error');
            }
        }
        
        async function updateStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                document.getElementById('total-tests').textContent = data.tests_count || 0;
                document.getElementById('success-tests').textContent = data.success_count || 0;
                document.getElementById('fail-tests').textContent = data.fail_count || 0;
                document.getElementById('last-test').textContent = data.last_test || '-';
            } catch (error) {
                console.error('Stats error:', error);
            }
        }
        
        async function refreshData() {
            await updateStats();
            addLog('Dados atualizados', 'info');
        }
        
        function setUrl(url) {
            document.getElementById('custom-url').value = url;
            document.getElementById('custom-url').focus();
        }
        
        async function testCustomUrl() {
            const urlInput = document.getElementById('custom-url');
            let url = urlInput.value.trim();
            
            if (!url) {
                addLog('Por favor, insira uma URL', 'warning');
                urlInput.focus();
                return;
            }
            
            // Adiciona https:// se não tiver protocolo
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                url = 'https://' + url;
                urlInput.value = url;
            }
            
            const btn = document.getElementById('url-btn');
            const resultDiv = document.getElementById('url-result');
            
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span> Acessando...';
            setStatus('testing', 'Acessando ' + new URL(url).hostname + '...');
            addLog(`Iniciando acesso: ${url}`, 'info');
            
            const startTime = Date.now();
            
            try {
                const response = await fetch('/api/test-url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                
                const data = await response.json();
                const endTime = Date.now();
                const responseTime = ((endTime - startTime) / 1000).toFixed(2);
                
                resultDiv.classList.add('show');
                
                if (data.success) {
                    resultDiv.classList.remove('error');
                    resultDiv.classList.add('success');
                    
                    document.getElementById('result-icon').textContent = '✓';
                    document.getElementById('result-text').textContent = 'Acesso bem sucedido!';
                    document.getElementById('result-url').textContent = url;
                    document.getElementById('result-page-title').textContent = data.title || 'N/A';
                    document.getElementById('result-status').textContent = '✓ Carregado';
                    document.getElementById('result-size').textContent = data.content_size || 'N/A';
                    document.getElementById('result-time').textContent = responseTime + 's';
                    
                    setStatus('connected', 'Acesso bem sucedido ✓');
                    addLog(`✓ Sucesso: ${data.title || url}`, 'success');
                    addLog(`  Tamanho: ${data.content_size}`, 'success');
                } else {
                    resultDiv.classList.remove('success');
                    resultDiv.classList.add('error');
                    
                    document.getElementById('result-icon').textContent = '✗';
                    document.getElementById('result-text').textContent = 'Falha no acesso';
                    document.getElementById('result-url').textContent = url;
                    document.getElementById('result-page-title').textContent = 'Erro';
                    document.getElementById('result-status').textContent = '✗ ' + (data.error || 'Falhou');
                    document.getElementById('result-size').textContent = '-';
                    document.getElementById('result-time').textContent = responseTime + 's';
                    
                    setStatus('disconnected', 'Falha no acesso');
                    addLog(`✗ Falha: ${data.error || 'Erro desconhecido'}`, 'error');
                }
                
                updateStats();
            } catch (error) {
                resultDiv.classList.add('show', 'error');
                resultDiv.classList.remove('success');
                
                document.getElementById('result-icon').textContent = '✗';
                document.getElementById('result-text').textContent = 'Erro de conexão';
                document.getElementById('result-status').textContent = '✗ ' + error.message;
                
                setStatus('disconnected', 'Erro de conexão');
                addLog(`✗ Erro: ${error.message}`, 'error');
            }
            
            btn.disabled = false;
            btn.innerHTML = '🚀 Acessar';
        }
        
        // Auto refresh stats
        setInterval(updateStats, 10000);
    </script>
</body>
</html>
"""


def run_async(coro):
    """Helper para rodar coroutines."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def test_connection():
    """Testa conexão com Browserless e obtém IP."""
    url = f"{BROWSERLESS_REST_URL}/content?token={BROWSERLESS_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "url": "https://ipinfo.io/json",
                "waitForTimeout": 5000
            }
            
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    # Parse the JSON from the HTML
                    import re
                    json_match = re.search(r'\{[^}]+\}', content)
                    if json_match:
                        ip_data = json.loads(json_match.group())
                        return {
                            "success": True,
                            "ip": ip_data.get("ip"),
                            "city": ip_data.get("city"),
                            "region": ip_data.get("region"),
                            "country": ip_data.get("country"),
                            "org": ip_data.get("org")
                        }
                return {"success": False, "error": f"HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def test_youtube():
    """Testa acesso ao YouTube."""
    url = f"{BROWSERLESS_REST_URL}/content?token={BROWSERLESS_API_KEY}"
    youtube_url = "https://www.youtube.com/watch?v=3Hj4wZk97JM"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "url": youtube_url,
                "waitForTimeout": 10000,
                "gotoOptions": {"waitUntil": "domcontentloaded"}
            }
            
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    
                    # Extract title
                    title = "N/A"
                    if "<title>" in content:
                        start = content.find("<title>") + 7
                        end = content.find("</title>")
                        title = content[start:end] if end > start else "N/A"
                    
                    return {
                        "success": True,
                        "title": title[:100],
                        "url": youtube_url,
                        "content_size": f"{len(content):,} bytes"
                    }
                return {"success": False, "error": f"HTTP {resp.status}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def test_custom_url(target_url: str):
    """Testa acesso a uma URL personalizada."""
    url = f"{BROWSERLESS_REST_URL}/content?token={BROWSERLESS_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "url": target_url,
                "waitForTimeout": 15000,
                "gotoOptions": {"waitUntil": "domcontentloaded"}
            }
            
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    
                    # Extract title
                    title = "N/A"
                    if "<title>" in content:
                        start = content.find("<title>") + 7
                        end = content.find("</title>")
                        title = content[start:end] if end > start else "N/A"
                    
                    # Limpar título de caracteres estranhos
                    title = title.replace("\n", " ").replace("\r", " ").strip()[:150]
                    
                    return {
                        "success": True,
                        "title": title,
                        "url": target_url,
                        "content_size": f"{len(content):,} bytes"
                    }
                else:
                    error_text = await resp.text()
                    return {"success": False, "error": f"HTTP {resp.status}: {error_text[:100]}"}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout - página demorou para carregar"}
    except Exception as e:
        return {"success": False, "error": str(e)[:100]}


@app.route("/")
def index():
    masked_key = BROWSERLESS_API_KEY[:20] + "..." + BROWSERLESS_API_KEY[-8:]
    return render_template_string(HTML_TEMPLATE, api_key_masked=masked_key)


@app.route("/api/test")
def api_test():
    state["tests_count"] += 1
    result = run_async(test_connection())
    
    if result["success"]:
        state["success_count"] += 1
        state["ip_info"] = result
    else:
        state["fail_count"] += 1
    
    state["last_test"] = datetime.now().strftime("%H:%M:%S")
    state["connection_status"] = "conectado" if result["success"] else "desconectado"
    
    return jsonify(result)


@app.route("/api/test-youtube")
def api_test_youtube():
    state["tests_count"] += 1
    result = run_async(test_youtube())
    
    if result["success"]:
        state["success_count"] += 1
        state["youtube_test"] = result
    else:
        state["fail_count"] += 1
    
    state["last_test"] = datetime.now().strftime("%H:%M:%S")
    
    return jsonify(result)


@app.route("/api/test-url", methods=["POST"])
def api_test_url():
    """Testa acesso a uma URL personalizada."""
    data = request.get_json()
    target_url = data.get("url", "")
    
    if not target_url:
        return jsonify({"success": False, "error": "URL não fornecida"})
    
    # Validar URL básica
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url
    
    state["tests_count"] += 1
    result = run_async(test_custom_url(target_url))
    
    if result["success"]:
        state["success_count"] += 1
    else:
        state["fail_count"] += 1
    
    state["last_test"] = datetime.now().strftime("%H:%M:%S")
    
    return jsonify(result)


@app.route("/api/stats")
def api_stats():
    return jsonify({
        "tests_count": state["tests_count"],
        "success_count": state["success_count"],
        "fail_count": state["fail_count"],
        "last_test": state["last_test"],
        "connection_status": state["connection_status"]
    })


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🌐 BROWSERLESS DASHBOARD")
    print("=" * 60)
    print(f"🔑 API Key: {BROWSERLESS_API_KEY[:20]}...")
    print(f"🌐 Servidor: {BROWSERLESS_REST_URL}")
    print("=" * 60)
    print("\n🚀 Iniciando servidor...")
    print("📍 Acesse: http://localhost:5050")
    print("\n" + "=" * 60 + "\n")
    
    app.run(host="0.0.0.0", port=5050, debug=False)

