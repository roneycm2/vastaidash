"""
Dashboard Browserless v2 - Com 20 Máquinas Concorrentes + Proxy BR
"""
import asyncio
import json
import re
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import requests
from playwright.sync_api import sync_playwright

# Configurações
BROWSERLESS_API_KEY = "2TaPTUF5ZToCE9je1f1a9658278c6a24cd5b63fda97b64e72"
BROWSERLESS_REST_URL = "https://production-sfo.browserless.io"

# Proxy residencial Brasil (FUNCIONANDO!)
PROXY_CONFIG = {
    "host": "fb29d01db8530b99.shg.na.pyproxy.io",
    "port": 16666,
    "username": "liderbet1-zone-resi-region-br",
    "password": "Aa10203040",
    "full_url": "http://liderbet1-zone-resi-region-br:Aa10203040@fb29d01db8530b99.shg.na.pyproxy.io:16666"
}

USE_PROXY = False

app = Flask(__name__)

# Estado global
state = {
    "last_ip": None,
    "last_location": None,
    "tests_count": 0,
    "success_count": 0,
    "fail_count": 0,
    "active_workers": 0,
    "last_test": None,
    "last_url": None,
    "last_title": None,
    "max_concurrent": 20,
    "current_concurrent": 0,
    "queued": 0,
    "workers_results": []
}

# Lock para thread safety
state_lock = threading.Lock()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌐 Browserless Dashboard v2 - 20 Máquinas</title>
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
        }
        .workers-title { font-size: 1.2rem; font-weight: 600; }
        .workers-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 0.75rem;
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
        .worker-details { 
            font-size: 0.75rem; 
            color: #94a3b8; 
            font-family: 'JetBrains Mono', monospace;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
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
            max-height: 250px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
        }
        .log-line { padding: 0.25rem 0; border-bottom: 1px solid #1e293b; }
        .log-success { color: #22c55e; }
        .log-error { color: #ef4444; }
        .log-info { color: #38bdf8; }
        .log-warning { color: #f59e0b; }
        
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
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌐 Browserless Dashboard v2</h1>
            <p class="subtitle">Execute até 20 navegadores simultâneos na nuvem</p>
        </header>
        
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
                       value="https://www.google.com"
                       onkeypress="if(event.key === 'Enter') startWorkers()">
                <input type="number" class="workers-input" id="num-workers" 
                       value="20" min="1" max="50" 
                       title="Número de navegadores">
                <label class="checkbox-label">
                    <input type="checkbox" id="use-proxy">
                    <span>🌐 Proxy BR</span>
                </label>
                <button class="btn btn-primary" id="start-btn" onclick="startWorkers()">
                    🚀 Iniciar 20 Workers
                </button>
                <button class="btn btn-danger" id="stop-btn" onclick="stopWorkers()" style="display: none;">
                    ⏹️ Parar
                </button>
            </div>
            <div class="quick-links">
                <span style="color: #64748b; margin-right: 0.5rem;">Links rápidos:</span>
                <span class="quick-link" onclick="setUrl('https://www.google.com')">Google</span>
                <span class="quick-link" onclick="setUrl('https://www.youtube.com')">YouTube</span>
                <span class="quick-link" onclick="setUrl('https://www.bet365.com')">Bet365</span>
                <span class="quick-link" onclick="setUrl('https://ipinfo.io/json')">Verificar IP</span>
                <span class="quick-link" onclick="setUrl('https://httpbin.org/ip')">HTTPBin IP</span>
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
                <button class="btn btn-secondary" onclick="clearWorkers()" style="padding: 0.5rem 1rem;">🗑️ Limpar</button>
            </div>
            <div class="workers-grid" id="workers-grid">
                <div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: #64748b;">
                    Configure a URL e clique em "Iniciar" para começar
                </div>
            </div>
        </div>
        
        <!-- Logs -->
        <div class="logs-box">
            <div class="logs-header">
                <span class="logs-title">📋 Logs em Tempo Real</span>
                <button class="btn btn-secondary" onclick="clearLogs()" style="padding: 0.5rem 1rem;">🗑️</button>
            </div>
            <div class="logs-content" id="logs">
                <div class="log-line log-info">[Sistema] Dashboard pronto - configure os workers e inicie</div>
            </div>
        </div>
        
        <footer>🚀 Browserless BaaS v2 - 20 Máquinas Concorrentes | <a href="https://docs.browserless.io" target="_blank">Docs</a></footer>
    </div>
    
    <script>
        let isRunning = false;
        let startTime = null;
        let statusInterval = null;
        let workers = [];
        
        function setUrl(url) {
            document.getElementById('url-input').value = url;
        }
        
        function addLog(msg, type = 'info') {
            const logs = document.getElementById('logs');
            const time = new Date().toLocaleTimeString('pt-BR');
            logs.innerHTML = '<div class="log-line log-' + type + '">[' + time + '] ' + msg + '</div>' + logs.innerHTML;
            // Limitar logs
            while(logs.children.length > 100) {
                logs.removeChild(logs.lastChild);
            }
        }
        
        function clearLogs() {
            document.getElementById('logs').innerHTML = '<div class="log-line log-info">[Sistema] Logs limpos</div>';
        }
        
        function clearWorkers() {
            workers = [];
            document.getElementById('workers-grid').innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: #64748b;">Nenhum worker ainda</div>';
            document.getElementById('stat-total').textContent = '0';
            document.getElementById('stat-running').textContent = '0';
            document.getElementById('stat-success').textContent = '0';
            document.getElementById('stat-fail').textContent = '0';
            document.getElementById('progress-container').style.display = 'none';
        }
        
        function updateWorkerCard(id, status, details = '', ip = '') {
            const card = document.getElementById('worker-' + id);
            if (!card) return;
            
            card.className = 'worker-card ' + status;
            
            const statusEl = card.querySelector('.worker-status');
            const detailsEl = card.querySelector('.worker-details');
            const iconEl = card.querySelector('.worker-icon');
            
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
            
            statusEl.textContent = statusTexts[status] || status;
            iconEl.textContent = icons[status] || '❓';
            
            if (ip) {
                detailsEl.textContent = 'IP: ' + ip + (details ? ' | ' + details : '');
            } else if (details) {
                detailsEl.textContent = details;
            }
        }
        
        function createWorkerCards(numWorkers) {
            const grid = document.getElementById('workers-grid');
            grid.innerHTML = '';
            workers = [];
            
            for (let i = 1; i <= numWorkers; i++) {
                workers.push({ id: i, status: 'pending', ip: '', details: '' });
                
                const card = document.createElement('div');
                card.id = 'worker-' + i;
                card.className = 'worker-card pending';
                card.innerHTML = `
                    <div class="worker-number">#${i}</div>
                    <div class="worker-info">
                        <div class="worker-status">⏳ Aguardando</div>
                        <div class="worker-details">-</div>
                    </div>
                    <div class="worker-icon">⏳</div>
                `;
                grid.appendChild(card);
            }
            
            document.getElementById('stat-total').textContent = numWorkers;
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
        
        async function startWorkers() {
            let url = document.getElementById('url-input').value.trim();
            const numWorkers = parseInt(document.getElementById('num-workers').value) || 20;
            const useProxy = document.getElementById('use-proxy').checked;
            
            if (!url) {
                addLog('Digite uma URL!', 'error');
                return;
            }
            
            if (!url.startsWith('http://') && !url.startsWith('https://')) {
                url = 'https://' + url;
                document.getElementById('url-input').value = url;
            }
            
            isRunning = true;
            startTime = Date.now();
            
            // UI Updates
            document.getElementById('start-btn').style.display = 'none';
            document.getElementById('stop-btn').style.display = 'inline-flex';
            document.getElementById('progress-container').style.display = 'block';
            
            createWorkerCards(numWorkers);
            addLog('🚀 Iniciando ' + numWorkers + ' workers para: ' + url, 'info');
            
            // Atualizar stats a cada 500ms
            statusInterval = setInterval(updateStats, 500);
            
            try {
                const response = await fetch('/api/run-workers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        url: url, 
                        num_workers: numWorkers,
                        use_proxy: useProxy 
                    })
                });
                
                // Streaming response
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
                                addLog('Worker #' + data.worker_id + ' iniciado', 'info');
                            }
                            else if (data.type === 'worker_result') {
                                const w = workers.find(x => x.id === data.worker_id);
                                if (w) {
                                    w.status = data.success ? 'success' : 'error';
                                    w.ip = data.ip || '';
                                    w.details = data.details || '';
                                }
                                
                                const locInfo = data.location ? ' | ' + data.location : '';
                                const proxyIcon = data.proxy_used ? '🇧🇷 ' : '';
                                updateWorkerCard(
                                    data.worker_id, 
                                    data.success ? 'success' : 'error',
                                    proxyIcon + (data.details || data.error || '') + locInfo,
                                    data.ip || ''
                                );
                                
                                if (data.success) {
                                    const proxyTag = data.proxy_used ? '🇧🇷' : '☁️';
                                    const loc = data.location ? ' | ' + data.location : '';
                                    addLog(proxyTag + ' Worker #' + data.worker_id + ' OK | IP: ' + (data.ip || 'N/A') + loc + ' | ' + (data.title || '').substring(0, 25), 'success');
                                } else {
                                    addLog('❌ Worker #' + data.worker_id + ' FALHOU: ' + (data.error || 'Erro'), 'error');
                                }
                            }
                            else if (data.type === 'complete') {
                                addLog('🏁 Concluído! Sucesso: ' + data.success + ' | Falhas: ' + data.fail + ' | Tempo: ' + data.elapsed + 's', 'success');
                            }
                        } catch(e) {
                            // Ignorar linhas inválidas
                        }
                    }
                }
            } catch (error) {
                addLog('❌ Erro: ' + error.message, 'error');
            }
            
            finishExecution();
        }
        
        function finishExecution() {
            isRunning = false;
            if (statusInterval) {
                clearInterval(statusInterval);
                statusInterval = null;
            }
            updateStats();
            document.getElementById('start-btn').style.display = 'inline-flex';
            document.getElementById('stop-btn').style.display = 'none';
        }
        
        function stopWorkers() {
            fetch('/api/stop-workers', { method: 'POST' });
            addLog('⏹️ Parando workers...', 'warning');
            finishExecution();
        }
        
        // Update button text based on input
        document.getElementById('num-workers').addEventListener('change', function() {
            document.getElementById('start-btn').innerHTML = '🚀 Iniciar ' + this.value + ' Workers';
        });
    </script>
</body>
</html>
'''


def access_url_single(target_url: str, worker_id: int, use_proxy: bool = False):
    """Acessa uma URL via Browserless com proxy BR usando BrowserQL."""
    
    result = {
        "worker_id": worker_id,
        "success": False, 
        "ip": None, 
        "location": None, 
        "title": None, 
        "content_size": None, 
        "error": None,
        "details": "",
        "duration": 0,
        "proxy_used": use_proxy
    }
    
    start = time.time()
    
    # Se usar proxy, usa Playwright CDP com proxy BR
    # Documentação: https://docs.browserless.io/baas/features/proxies#using-proxies-with-playwright
    if use_proxy:
        ws_endpoint = f"wss://production-sfo.browserless.io?token={BROWSERLESS_API_KEY}"
        proxy_config = {
            "server": f"http://{PROXY_CONFIG['host']}:{PROXY_CONFIG['port']}",
            "username": PROXY_CONFIG["username"],
            "password": PROXY_CONFIG["password"]
        }
        
        try:
            with sync_playwright() as p:
                # Conectar ao Browserless via CDP
                browser = p.chromium.connect_over_cdp(ws_endpoint)
                
                # Criar contexto COM PROXY
                context = browser.new_context(proxy=proxy_config)
                page = context.new_page()
                
                # Primeiro, pegar IP para confirmar proxy BR
                page.goto("https://ipinfo.io/json", timeout=30000)
                ip_content = page.content()
                
                ip_match = re.search(r'"ip":\s*"([^"]+)"', ip_content)
                city_match = re.search(r'"city":\s*"([^"]+)"', ip_content)
                region_match = re.search(r'"region":\s*"([^"]+)"', ip_content)
                country_match = re.search(r'"country":\s*"([^"]+)"', ip_content)
                
                if ip_match:
                    result["ip"] = ip_match.group(1)
                if city_match and country_match:
                    city = city_match.group(1)
                    region = region_match.group(1) if region_match else ""
                    country = country_match.group(1)
                    result["location"] = f"{city}, {region}, {country}".replace(", ,", ",").strip(", ")
                
                # Acessar URL alvo
                page.goto(target_url, timeout=45000)
                content = page.content()
                title = page.title()
                
                result["title"] = title[:60] if title else None
                result["content_size"] = len(content)
                result["success"] = True
                
                # Flag baseado no país
                detected_country = result["location"].split(", ")[-1] if result["location"] else ""
                flag = "🇧🇷" if detected_country == "BR" else "🌍"
                result["details"] = f"{flag} {len(content):,} bytes"
                
                browser.close()
                
        except Exception as e:
            result["error"] = str(e)[:60]
            result["details"] = str(e)[:50]
    
    else:
        # Sem proxy - usa endpoint /content simples
        api_url = f"{BROWSERLESS_REST_URL}/content?token={BROWSERLESS_API_KEY}"
        
        try:
            # Primeiro, pegar o IP
            ip_resp = requests.post(api_url, json={
                "url": "https://ipinfo.io/json", 
                "waitForTimeout": 5000
            }, timeout=30)
            
            if ip_resp.status_code == 200:
                ip_match = re.search(r'"ip":\s*"([^"]+)"', ip_resp.text)
                city_match = re.search(r'"city":\s*"([^"]+)"', ip_resp.text)
                country_match = re.search(r'"country":\s*"([^"]+)"', ip_resp.text)
                
                if ip_match:
                    result["ip"] = ip_match.group(1)
                if city_match and country_match:
                    result["location"] = f"{city_match.group(1)}, {country_match.group(1)}"
            
            # Depois, acessar a URL real
            url_resp = requests.post(api_url, json={
                "url": target_url,
                "waitForTimeout": 10000,
                "gotoOptions": {"waitUntil": "domcontentloaded"}
            }, timeout=60)
            
            if url_resp.status_code == 200:
                content = url_resp.text
                title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.IGNORECASE)
                if title_match:
                    result["title"] = title_match.group(1).strip()[:60]
                result["content_size"] = len(content)
                result["success"] = True
                result["details"] = f"{len(content):,} bytes"
            else:
                result["error"] = f"HTTP {url_resp.status_code}"
                result["details"] = f"Erro HTTP {url_resp.status_code}"
                
        except requests.Timeout:
            result["error"] = "Timeout"
            result["details"] = "Timeout na conexão"
        except Exception as e:
            result["error"] = str(e)[:50]
            result["details"] = str(e)[:50]
    
    result["duration"] = round(time.time() - start, 2)
    return result


def run_workers_thread(url: str, num_workers: int, use_proxy: bool, results_queue):
    """Executa workers em threads paralelas."""
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=min(num_workers, 20)) as executor:
        futures = {}
        
        # Submeter todos os workers
        for i in range(1, num_workers + 1):
            # Notificar início
            results_queue.append({"type": "worker_start", "worker_id": i})
            future = executor.submit(access_url_single, url, i, use_proxy)
            futures[future] = i
        
        # Coletar resultados conforme terminam
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
                    "proxy_used": result.get("proxy_used", False)
                })
            except Exception as e:
                results_queue.append({
                    "type": "worker_result",
                    "worker_id": worker_id,
                    "success": False,
                    "error": str(e),
                    "details": str(e)[:50],
                    "proxy_used": use_proxy
                })
    
    # Calcular totais
    success_count = sum(1 for r in results_queue if r.get("type") == "worker_result" and r.get("success"))
    fail_count = sum(1 for r in results_queue if r.get("type") == "worker_result" and not r.get("success"))
    elapsed = round(time.time() - start_time, 1)
    
    results_queue.append({
        "type": "complete",
        "success": success_count,
        "fail": fail_count,
        "elapsed": elapsed
    })


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/run-workers", methods=["POST"])
def api_run_workers():
    """Executa múltiplos workers e retorna resultados via streaming."""
    data = request.get_json()
    target_url = data.get("url", "https://www.google.com")
    num_workers = min(int(data.get("num_workers", 20)), 50)
    use_proxy = data.get("use_proxy", False)
    
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url
    
    results_queue = []
    
    # Iniciar thread de execução
    thread = threading.Thread(
        target=run_workers_thread, 
        args=(target_url, num_workers, use_proxy, results_queue)
    )
    thread.start()
    
    def generate():
        sent_count = 0
        while thread.is_alive() or sent_count < len(results_queue):
            while sent_count < len(results_queue):
                yield json.dumps(results_queue[sent_count]) + "\n"
                sent_count += 1
            time.sleep(0.1)
        
        # Enviar qualquer resultado restante
        while sent_count < len(results_queue):
            yield json.dumps(results_queue[sent_count]) + "\n"
            sent_count += 1
    
    return app.response_class(generate(), mimetype='application/x-ndjson')


@app.route("/api/stop-workers", methods=["POST"])
def api_stop_workers():
    """Para os workers (não implementado - workers já em execução não podem ser parados)."""
    return jsonify({"status": "requested"})


@app.route("/api/stats")
def api_stats():
    return jsonify(state)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🌐 BROWSERLESS DASHBOARD v2 - 20 MÁQUINAS CONCORRENTES")
    print("=" * 60)
    print(f"🔑 API Key: {BROWSERLESS_API_KEY[:20]}...")
    print("📍 Acesse: http://localhost:5070")
    print("=" * 60 + "\n")
    
    app.run(host="0.0.0.0", port=5080, debug=False, threaded=True)
