"""
Dashboard em tempo real para o SerpAPI Browser Clicker
"""

from flask import Flask, render_template_string, jsonify
import threading
import time
from datetime import datetime

app = Flask(__name__)

# =====================================================
# ESTATÍSTICAS GLOBAIS (compartilhadas com o clicker)
# =====================================================
class StatsManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.inicio = None
        self.stats = {
            "rodadas": 0,
            "ads_encontrados": 0,
            "cliques_sucesso": 0,
            "cliques_falha": 0,
            "por_dominio": {},
            "por_regiao": {},  # Cliques por região
            "ultimos_cliques": [],
            "erros": [],
            "ads_por_palavra": {},
            "browsers_ativos": 0,
            "tracking_links": [],  # Lista de tracking links usados
            "ips_ativos": {},  # IPs por browser
        }
    
    def iniciar(self):
        self.inicio = time.time()
    
    def registrar_ad_encontrado(self, palavra, dominio, tracking_link, cidade=""):
        with self.lock:
            self.stats["ads_encontrados"] += 1
            if palavra not in self.stats["ads_por_palavra"]:
                self.stats["ads_por_palavra"][palavra] = []
            self.stats["ads_por_palavra"][palavra].append({
                "dominio": dominio,
                "tracking": tracking_link[:100] + "..." if len(tracking_link) > 100 else tracking_link,
                "cidade": cidade,
                "hora": datetime.now().strftime("%H:%M:%S")
            })
    
    def registrar_ip(self, browser_id, ip, cidade_ip="", estado_ip=""):
        with self.lock:
            self.stats["ips_ativos"][browser_id] = {
                "ip": ip,
                "cidade": cidade_ip,
                "estado": estado_ip,
                "hora": datetime.now().strftime("%H:%M:%S")
            }
    
    def registrar_clique(self, dominio, url_retorno, tracking_link="", cidade="", ip="", sucesso=True, erro=None):
        with self.lock:
            if sucesso:
                self.stats["cliques_sucesso"] += 1
                self.stats["por_dominio"][dominio] = self.stats["por_dominio"].get(dominio, 0) + 1
                
                # Registra por região
                if cidade:
                    self.stats["por_regiao"][cidade] = self.stats["por_regiao"].get(cidade, 0) + 1
                
                # Adiciona aos últimos cliques
                self.stats["ultimos_cliques"].insert(0, {
                    "dominio": dominio,
                    "url_retorno": url_retorno[:120] if url_retorno else "N/A",
                    "tracking_link": tracking_link[:120] if tracking_link else "N/A",
                    "cidade": cidade or "N/A",
                    "ip": ip or "N/A",
                    "hora": datetime.now().strftime("%H:%M:%S"),
                    "sucesso": True
                })
                self.stats["ultimos_cliques"] = self.stats["ultimos_cliques"][:100]
                
                # Registra tracking link
                self.stats["tracking_links"].insert(0, {
                    "tracking": tracking_link[:150] if tracking_link else "N/A",
                    "dominio": dominio,
                    "cidade": cidade,
                    "hora": datetime.now().strftime("%H:%M:%S")
                })
                self.stats["tracking_links"] = self.stats["tracking_links"][:50]
            else:
                self.stats["cliques_falha"] += 1
                self.stats["erros"].insert(0, {
                    "dominio": dominio,
                    "erro": str(erro)[:100] if erro else "Erro desconhecido",
                    "cidade": cidade or "N/A",
                    "hora": datetime.now().strftime("%H:%M:%S")
                })
                self.stats["erros"] = self.stats["erros"][:50]
    
    def incrementar_rodada(self):
        with self.lock:
            self.stats["rodadas"] += 1
    
    def set_browsers_ativos(self, qtd):
        with self.lock:
            self.stats["browsers_ativos"] = qtd
    
    def get_stats(self):
        with self.lock:
            elapsed = time.time() - self.inicio if self.inicio else 0
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            
            total = self.stats["cliques_sucesso"] + self.stats["cliques_falha"]
            taxa_sucesso = (self.stats["cliques_sucesso"] / total * 100) if total > 0 else 0
            cliques_por_min = self.stats["cliques_sucesso"] / (elapsed / 60) if elapsed > 60 else self.stats["cliques_sucesso"]
            
            return {
                **self.stats,
                "tempo_execucao": f"{mins}m {secs}s",
                "taxa_sucesso": round(taxa_sucesso, 1),
                "cliques_por_minuto": round(cliques_por_min, 1),
                "total_cliques": total,
            }

# Instância global
stats_manager = StatsManager()

# =====================================================
# TEMPLATE HTML DO DASHBOARD
# =====================================================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 SerpAPI Clicker Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0f2847 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            padding: 25px;
            margin-bottom: 30px;
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 255, 136, 0.2);
        }
        
        .header h1 {
            font-size: 2.8em;
            background: linear-gradient(90deg, #00ff88, #00d9ff, #ff00ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 30px rgba(0, 255, 136, 0.3);
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 25px;
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            transition: all 0.3s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(0, 255, 136, 0.2);
        }
        
        .stat-card .icon { font-size: 2.2em; margin-bottom: 10px; }
        .stat-card .value { font-size: 2.8em; font-weight: bold; }
        .stat-card .label { color: #888; font-size: 0.85em; margin-top: 5px; text-transform: uppercase; }
        
        .stat-card.success .value { color: #00ff88; text-shadow: 0 0 20px rgba(0, 255, 136, 0.5); }
        .stat-card.error .value { color: #ff4757; text-shadow: 0 0 20px rgba(255, 71, 87, 0.5); }
        .stat-card.info .value { color: #00d9ff; text-shadow: 0 0 20px rgba(0, 217, 255, 0.5); }
        .stat-card.warning .value { color: #ffa502; text-shadow: 0 0 20px rgba(255, 165, 2, 0.5); }
        
        .section {
            background: rgba(255,255,255,0.03);
            border-radius: 20px;
            padding: 25px;
            margin-bottom: 25px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .section h2 {
            color: #00d9ff;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid rgba(0, 217, 255, 0.3);
            font-size: 1.3em;
        }
        
        .grid-2 {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
        }
        
        .table-container { overflow-x: auto; }
        
        table { width: 100%; border-collapse: collapse; }
        
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        
        th { color: #00d9ff; font-weight: 600; font-size: 0.9em; text-transform: uppercase; }
        tr:hover { background: rgba(0, 217, 255, 0.05); }
        
        .success-badge {
            background: linear-gradient(90deg, #00ff88, #00cc6a);
            color: #000;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: bold;
        }
        
        .error-badge {
            background: linear-gradient(90deg, #ff4757, #cc3a47);
            color: #fff;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75em;
        }
        
        .region-badge {
            background: linear-gradient(90deg, #9b59b6, #8e44ad);
            color: #fff;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 0.75em;
        }
        
        .domain-list { display: flex; flex-wrap: wrap; gap: 12px; }
        
        .domain-item {
            background: linear-gradient(135deg, rgba(0, 217, 255, 0.15), rgba(0, 255, 136, 0.1));
            padding: 12px 18px;
            border-radius: 15px;
            display: flex;
            align-items: center;
            gap: 12px;
            border: 1px solid rgba(0, 217, 255, 0.2);
        }
        
        .domain-item .count {
            background: linear-gradient(90deg, #00ff88, #00cc6a);
            color: #000;
            padding: 4px 10px;
            border-radius: 10px;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .region-list { display: flex; flex-wrap: wrap; gap: 12px; }
        
        .region-item {
            background: linear-gradient(135deg, rgba(155, 89, 182, 0.2), rgba(142, 68, 173, 0.15));
            padding: 12px 18px;
            border-radius: 15px;
            display: flex;
            align-items: center;
            gap: 12px;
            border: 1px solid rgba(155, 89, 182, 0.3);
        }
        
        .region-item .count {
            background: linear-gradient(90deg, #9b59b6, #8e44ad);
            color: #fff;
            padding: 4px 10px;
            border-radius: 10px;
            font-weight: bold;
        }
        
        .progress-bar {
            width: 100%;
            height: 12px;
            background: rgba(255,255,255,0.1);
            border-radius: 6px;
            overflow: hidden;
            margin-top: 10px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ff88, #00d9ff);
            transition: width 0.5s;
            box-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
        }
        
        .live-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            background: #00ff88;
            border-radius: 50%;
            animation: pulse 1.5s infinite;
            margin-right: 10px;
            box-shadow: 0 0 15px rgba(0, 255, 136, 0.8);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.9); }
        }
        
        .url-cell {
            max-width: 350px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-family: 'Consolas', monospace;
            font-size: 0.8em;
            color: #aaa;
        }
        
        .tracking-cell {
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            font-family: 'Consolas', monospace;
            font-size: 0.75em;
            color: #ff9f43;
        }
        
        .btn-proxy {
            background: linear-gradient(90deg, #9b59b6, #8e44ad);
            color: #fff;
            border: none;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.8em;
            font-weight: bold;
            transition: all 0.3s;
            white-space: nowrap;
        }
        
        .btn-proxy:hover {
            background: linear-gradient(90deg, #a66bbe, #9b59b6);
            transform: scale(1.05);
            box-shadow: 0 5px 20px rgba(155, 89, 182, 0.4);
        }
        
        .btn-proxy:active {
            transform: scale(0.95);
        }
        
        .btn-proxy.loading {
            opacity: 0.7;
            cursor: wait;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .tab {
            padding: 10px 20px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .tab:hover, .tab.active {
            background: rgba(0, 217, 255, 0.2);
            border-color: #00d9ff;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 SerpAPI Browser Clicker</h1>
        <p style="margin-top: 10px;"><span class="live-indicator"></span>Dashboard em Tempo Real - Atualização a cada 2s</p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card info">
            <div class="icon">⏱️</div>
            <div class="value" id="tempo">0m 0s</div>
            <div class="label">Tempo</div>
        </div>
        <div class="stat-card info">
            <div class="icon">🔄</div>
            <div class="value" id="rodadas">0</div>
            <div class="label">Rodadas</div>
        </div>
        <div class="stat-card warning">
            <div class="icon">🔍</div>
            <div class="value" id="encontrados">0</div>
            <div class="label">Ads Encontrados</div>
        </div>
        <div class="stat-card success">
            <div class="icon">✅</div>
            <div class="value" id="sucesso">0</div>
            <div class="label">Cliques OK</div>
        </div>
        <div class="stat-card error">
            <div class="icon">❌</div>
            <div class="value" id="falha">0</div>
            <div class="label">Falhas</div>
        </div>
        <div class="stat-card info">
            <div class="icon">⚡</div>
            <div class="value" id="rate">0</div>
            <div class="label">Cliques/min</div>
        </div>
    </div>
    
    <div class="section">
        <h2>📊 Taxa de Sucesso</h2>
        <div style="display: flex; align-items: center; gap: 20px;">
            <div class="progress-bar" style="flex: 1;">
                <div class="progress-fill" id="progress" style="width: 0%;"></div>
            </div>
            <span id="taxa" style="font-size: 2em; font-weight: bold; color: #00ff88;">0%</span>
        </div>
    </div>
    
    <div class="section">
        <h2>🌐 IPs Ativos dos Browsers</h2>
        <div class="domain-list" id="ips-ativos">
            <p style="color: #666;">Aguardando conexão...</p>
        </div>
    </div>
    
    <div class="grid-2">
        <div class="section">
            <h2>🎯 Cliques por Domínio</h2>
            <div class="domain-list" id="dominios">
                <p style="color: #666;">Aguardando dados...</p>
            </div>
        </div>
        
        <div class="section">
            <h2>📍 Cliques por Região</h2>
            <div class="region-list" id="regioes">
                <p style="color: #666;">Aguardando dados...</p>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>🔗 Últimos Cliques com Tracking Links</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Hora</th>
                        <th>IP</th>
                        <th>Região</th>
                        <th>Domínio</th>
                        <th>Tracking Link (Google Ads)</th>
                        <th>URL de Retorno</th>
                        <th>Status</th>
                        <th>Ação</th>
                    </tr>
                </thead>
                <tbody id="ultimos-cliques">
                    <tr><td colspan="8" style="color: #666;">Aguardando cliques...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="section">
        <h2>🔗 Tracking Links Utilizados</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Hora</th>
                        <th>Região</th>
                        <th>Domínio</th>
                        <th>Tracking Link Completo</th>
                        <th>Ação</th>
                    </tr>
                </thead>
                <tbody id="tracking-links">
                    <tr><td colspan="5" style="color: #666;">Aguardando dados...</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="section">
        <h2>⚠️ Últimos Erros</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Hora</th>
                        <th>Região</th>
                        <th>Domínio</th>
                        <th>Erro</th>
                    </tr>
                </thead>
                <tbody id="erros">
                    <tr><td colspan="4" style="color: #666;">Nenhum erro ainda</td></tr>
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        function atualizarDashboard() {
            fetch('/api/stats')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('tempo').textContent = data.tempo_execucao;
                    document.getElementById('rodadas').textContent = data.rodadas;
                    document.getElementById('encontrados').textContent = data.ads_encontrados;
                    document.getElementById('sucesso').textContent = data.cliques_sucesso;
                    document.getElementById('falha').textContent = data.cliques_falha;
                    document.getElementById('rate').textContent = data.cliques_por_minuto;
                    document.getElementById('taxa').textContent = data.taxa_sucesso + '%';
                    document.getElementById('progress').style.width = data.taxa_sucesso + '%';
                    
                    // Domínios
                    const dominiosDiv = document.getElementById('dominios');
                    if (Object.keys(data.por_dominio).length > 0) {
                        dominiosDiv.innerHTML = Object.entries(data.por_dominio)
                            .sort((a, b) => b[1] - a[1])
                            .map(([dom, count]) => 
                                `<div class="domain-item">
                                    <span>🔗 ${dom}</span>
                                    <span class="count">${count}</span>
                                </div>`
                            ).join('');
                    }
                    
                    // Regiões
                    const regioesDiv = document.getElementById('regioes');
                    if (Object.keys(data.por_regiao).length > 0) {
                        regioesDiv.innerHTML = Object.entries(data.por_regiao)
                            .sort((a, b) => b[1] - a[1])
                            .map(([reg, count]) => 
                                `<div class="region-item">
                                    <span>📍 ${reg}</span>
                                    <span class="count">${count}</span>
                                </div>`
                            ).join('');
                    }
                    
                    // IPs ativos
                    const ipsDiv = document.getElementById('ips-ativos');
                    if (data.ips_ativos && Object.keys(data.ips_ativos).length > 0) {
                        ipsDiv.innerHTML = Object.entries(data.ips_ativos)
                            .map(([browser, info]) => 
                                `<div class="domain-item" style="background: linear-gradient(135deg, rgba(46, 204, 113, 0.2), rgba(39, 174, 96, 0.15)); border-color: rgba(46, 204, 113, 0.3);">
                                    <span>🖥️ Browser ${browser}</span>
                                    <span style="color: #2ecc71; font-family: monospace;">${info.ip}</span>
                                    <span style="color: #aaa; font-size: 0.8em;">${info.cidade}, ${info.estado}</span>
                                </div>`
                            ).join('');
                    }
                    
                    // Últimos cliques
                    const cliquesBody = document.getElementById('ultimos-cliques');
                    if (data.ultimos_cliques.length > 0) {
                        cliquesBody.innerHTML = data.ultimos_cliques.slice(0, 30).map(c => 
                            `<tr>
                                <td>${c.hora}</td>
                                <td style="font-family: monospace; color: #2ecc71;">${c.ip || 'N/A'}</td>
                                <td><span class="region-badge">${c.cidade}</span></td>
                                <td><strong>${c.dominio}</strong></td>
                                <td class="tracking-cell" title="${c.tracking_link}">${c.tracking_link}</td>
                                <td class="url-cell" title="${c.url_retorno}">${c.url_retorno}</td>
                                <td><span class="success-badge">OK</span></td>
                                <td>
                                    <button onclick="abrirComProxy('${encodeURIComponent(c.tracking_link)}')" class="btn-proxy" style="padding: 5px 10px; font-size: 0.7em;">
                                        🚀 Abrir
                                    </button>
                                </td>
                            </tr>`
                        ).join('');
                    }
                    
                    // Tracking links
                    const trackingBody = document.getElementById('tracking-links');
                    if (data.tracking_links && data.tracking_links.length > 0) {
                        trackingBody.innerHTML = data.tracking_links.slice(0, 20).map(t => 
                            `<tr>
                                <td>${t.hora}</td>
                                <td><span class="region-badge">${t.cidade || 'N/A'}</span></td>
                                <td><strong>${t.dominio}</strong></td>
                                <td class="tracking-cell" title="${t.tracking}">${t.tracking}</td>
                                <td>
                                    <button onclick="abrirComProxy('${encodeURIComponent(t.tracking)}')" class="btn-proxy">
                                        🚀 Abrir com Proxy
                                    </button>
                                </td>
                            </tr>`
                        ).join('');
                    }
                    
                    // Erros
                    const errosBody = document.getElementById('erros');
                    if (data.erros.length > 0) {
                        errosBody.innerHTML = data.erros.slice(0, 20).map(e => 
                            `<tr>
                                <td>${e.hora}</td>
                                <td><span class="region-badge">${e.cidade}</span></td>
                                <td>${e.dominio}</td>
                                <td style="color: #ff4757;">${e.erro}</td>
                            </tr>`
                        ).join('');
                    }
                })
                .catch(err => console.error('Erro:', err));
        }
        
        function abrirComProxy(urlEncoded) {
            const url = decodeURIComponent(urlEncoded);
            const btn = event.target;
            btn.classList.add('loading');
            btn.textContent = '⏳ Abrindo...';
            
            fetch('/api/abrir_link?url=' + urlEncoded)
                .then(r => r.json())
                .then(data => {
                    btn.textContent = '✅ Aberto!';
                    btn.style.background = 'linear-gradient(90deg, #27ae60, #2ecc71)';
                    setTimeout(() => {
                        btn.textContent = '🚀 Abrir com Proxy';
                        btn.style.background = '';
                        btn.classList.remove('loading');
                    }, 3000);
                })
                .catch(err => {
                    btn.textContent = '❌ Erro';
                    btn.style.background = 'linear-gradient(90deg, #c0392b, #e74c3c)';
                    setTimeout(() => {
                        btn.textContent = '🚀 Abrir com Proxy';
                        btn.style.background = '';
                        btn.classList.remove('loading');
                    }, 3000);
                });
        }
        
        setInterval(atualizarDashboard, 2000);
        atualizarDashboard();
    </script>
</body>
</html>
"""

# =====================================================
# ROTAS
# =====================================================
@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/stats')
def api_stats():
    return jsonify(stats_manager.get_stats())

@app.route('/api/abrir_link')
def abrir_link():
    """Abre um tracking link usando navegador com proxy"""
    from flask import request
    import subprocess
    import threading
    
    url = request.args.get('url', '')
    if not url:
        return jsonify({"erro": "URL não fornecida"}), 400
    
    def abrir_browser_com_proxy(url):
        import asyncio
        import tempfile
        from patchright.async_api import async_playwright
        
        async def abrir():
            with tempfile.TemporaryDirectory() as user_data_dir:
                async with async_playwright() as p:
                    browser = await p.chromium.launch_persistent_context(
                        user_data_dir,
                        headless=False,
                        proxy={
                            "server": "http://fb29d01db8530b99.shg.na.pyproxy.io:16666",
                            "username": "liderbet1-zone-resi-region-br",
                            "password": "Aa10203040"
                        },
                    )
                    page = await browser.new_page()
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    # Mantém aberto por 60 segundos para visualização
                    await asyncio.sleep(60)
                    await browser.close()
        
        asyncio.run(abrir())
    
    # Executa em thread separada para não bloquear
    t = threading.Thread(target=abrir_browser_com_proxy, args=(url,), daemon=True)
    t.start()
    
    return jsonify({"status": "ok", "mensagem": "Abrindo navegador com proxy..."})

# =====================================================
# INICIAR DASHBOARD EM THREAD
# =====================================================
def iniciar_dashboard(port=5000):
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False, threaded=True)

def iniciar_dashboard_thread(port=5000):
    t = threading.Thread(target=iniciar_dashboard, args=(port,), daemon=True)
    t.start()
    return t

if __name__ == "__main__":
    print("🌐 Iniciando Dashboard...")
    print("📊 Acesse: http://localhost:5000")
    iniciar_dashboard()
