from flask import Flask, render_template_string, jsonify, request
from patchright.sync_api import sync_playwright
import threading, time, re, logging, sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

app = Flask(__name__)

PROXY_BASE = {"server": "http://fb29d01db8530b99.shg.na.pyproxy.io:16666", "username": "liderbet1-zone-mob-region-br", "password": "Aa10203040"}
DEFAULT_URL = "https://7k.bet.br/"

class TabManager:
    def __init__(self):
        self.tabs = {}
        self.lock = threading.Lock()
        self.running = False
        self.browser = None
        self.playwright_instance = None
        self.stats = {"requests_total": 0, "requests_success": 0, "requests_error": 0, "start_time": None}
    def get_all_tabs(self):
        with self.lock:
            return [{"id": tid, "ip": info.get("ip", "..."), "status": info.get("status", "iniciando"), "url": info.get("url", ""), "requests": info.get("requests", 0)} for tid, info in self.tabs.items() if tid != 0]
    def update_tab(self, tab_id, **kwargs):
        with self.lock:
            if tab_id in self.tabs: self.tabs[tab_id].update(kwargs)
    def add_tab(self, tab_id, **kwargs):
        with self.lock:
            self.tabs[tab_id] = {"ip": "...", "status": "iniciando", "url": "", "requests": 0, "page": None, **kwargs}
    def get_page(self, tab_id):
        with self.lock:
            return self.tabs.get(tab_id, {}).get("page")

tab_manager = TabManager()

def get_public_ip(page):
    try:
        page.goto("https://api.ipify.org?format=json", timeout=15000)
        match = re.search(r'"ip":\s*"([^"]+)"', page.content())
        if match: return match.group(1)
    except: pass
    return "Erro"

def browser_manager(num_tabs, url, use_proxy=True):
    logger.info(f"[Browser] Iniciando {num_tabs} guias...")
    try:
        p = sync_playwright().start()
        tab_manager.playwright_instance = p
        browser = p.chromium.launch(headless=False, args=['--disable-blink-features=AutomationControlled'])
        tab_manager.browser = browser
        context_opts = {"viewport": {"width": 1200, "height": 700}}
        if use_proxy: context_opts["proxy"] = PROXY_BASE
        context = browser.new_context(**context_opts)
        first_page = context.new_page()
        tab_manager.add_tab(1, page=first_page, status="obtendo_ip")
        shared_ip = get_public_ip(first_page)
        logger.info(f"[Browser] IP: {shared_ip}")
        tab_manager.update_tab(1, ip=shared_ip, status="pronta")
        if url:
            try: first_page.goto(url, timeout=30000); tab_manager.update_tab(1, url=url)
            except: pass
        for tab_id in range(2, num_tabs + 1):
            if not tab_manager.running: break
            tab_manager.add_tab(tab_id)
            page = context.new_page()
            tab_manager.update_tab(tab_id, page=page, ip=shared_ip, status="pronta")
            if url:
                try: page.goto(url, timeout=30000); tab_manager.update_tab(tab_id, url=url)
                except: pass
            time.sleep(0.3)
        logger.info(f"[Browser] {num_tabs} guias criadas!")
        while tab_manager.running:
            time.sleep(0.5)
            for tab_id in list(tab_manager.tabs.keys()):
                if tab_id == 0 or not tab_manager.running: continue
                with tab_manager.lock:
                    pending = tab_manager.tabs.get(tab_id, {}).get("pending_request")
                if pending:
                    page = tab_manager.get_page(tab_id)
                    if page:
                        tab_manager.update_tab(tab_id, status="navegando", pending_request=None)
                        try:
                            page.goto(pending, timeout=30000)
                            with tab_manager.lock: tab_manager.tabs[tab_id]["requests"] += 1
                            tab_manager.update_tab(tab_id, url=pending, status="pronta")
                            tab_manager.stats["requests_success"] += 1
                        except:
                            tab_manager.update_tab(tab_id, status="erro")
                            tab_manager.stats["requests_error"] += 1
                        tab_manager.stats["requests_total"] += 1
        context.close(); browser.close(); p.stop()
    except Exception as e:
        logger.error(f"Erro: {e}")
    finally:
        tab_manager.tabs = {}; tab_manager.browser = None; tab_manager.running = False

DASHBOARD_HTML = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Dashboard Abas</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#1a1a2e;color:#eee;min-height:100vh;padding:20px}.container{max-width:1200px;margin:0 auto}header{text-align:center;padding:20px;margin-bottom:30px}h1{color:#00d4ff;font-size:2em}.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-bottom:30px}.stat-card{background:#252540;padding:20px;border-radius:10px;text-align:center}.stat-value{font-size:2em;font-weight:bold;color:#00d4ff}.stat-label{color:#888;font-size:0.9em;margin-top:5px}.controls{background:#252540;padding:20px;border-radius:10px;margin-bottom:30px}.control-row{display:flex;gap:15px;flex-wrap:wrap;align-items:flex-end}.input-group{flex:1;min-width:150px}.input-group label{display:block;margin-bottom:5px;color:#888}.input-group input{width:100%;padding:10px;border:1px solid #444;border-radius:5px;background:#1a1a2e;color:#eee}.btn{padding:10px 25px;border:none;border-radius:5px;cursor:pointer;font-weight:bold}.btn-primary{background:#00d4ff;color:#000}.btn-danger{background:#ff4444;color:#fff}.btn-secondary{background:#444;color:#fff}.btn:disabled{opacity:0.5;cursor:not-allowed}.tabs-panel{background:#252540;border-radius:10px;overflow:hidden}.tabs-header{padding:15px 20px;border-bottom:1px solid #444;display:flex;justify-content:space-between}.tabs-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:15px;padding:20px;max-height:400px;overflow-y:auto}.tab-card{background:#1a1a2e;border:1px solid #444;border-radius:8px;padding:15px}.tab-card.active{border-color:#00ff88}.tab-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}.tab-number{background:#00d4ff;color:#000;width:30px;height:30px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-weight:bold}.tab-status{padding:3px 8px;border-radius:4px;font-size:0.8em}.tab-status.pronta{background:rgba(0,255,136,0.2);color:#00ff88}.tab-status.navegando{background:rgba(0,212,255,0.2);color:#00d4ff}.tab-status.iniciando{background:rgba(255,255,255,0.1);color:#888}.tab-info{font-size:0.9em}.tab-row{display:flex;gap:8px;margin-bottom:5px}.tab-row .label{color:#888;min-width:30px}.tab-row .value{color:#eee}.tab-row .value.ip{color:#00d4ff}.empty-state{text-align:center;padding:40px;color:#888}.status-dot{width:10px;height:10px;border-radius:50%;background:#888;display:inline-block}.status-dot.active{background:#00ff88;animation:pulse 2s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}</style></head>
<body><div class="container"><header><h1>Dashboard de Abas</h1><p style="color:#888;margin-top:10px">1 Navegador - Multiplas Abas - Mesmo IP</p><div style="margin-top:15px"><span class="status-dot" id="status-dot"></span> <span id="status-text">Parado</span></div></header>
<div class="stats"><div class="stat-card"><div class="stat-value" id="total-tabs">0</div><div class="stat-label">Abas</div></div><div class="stat-card"><div class="stat-value" id="total-requests">0</div><div class="stat-label">Requests</div></div><div class="stat-card"><div class="stat-value" id="success-requests">0</div><div class="stat-label">Sucesso</div></div><div class="stat-card"><div class="stat-value" id="error-requests">0</div><div class="stat-label">Erros</div></div><div class="stat-card"><div class="stat-value" id="uptime">00:00:00</div><div class="stat-label">Tempo</div></div></div>
<div class="controls"><h2 style="margin-bottom:15px;color:#00d4ff">Controles</h2><div class="control-row"><div class="input-group"><label>Numero de Abas</label><input type="number" id="num-tabs" value="3" min="1" max="20"></div><div class="input-group" style="flex:2"><label>URL</label><input type="text" id="target-url" value="https://7k.bet.br/"></div><button class="btn btn-primary" id="btn-start" onclick="startTabs()">Iniciar</button><button class="btn btn-danger" id="btn-stop" onclick="stopTabs()" disabled>Parar</button><button class="btn btn-secondary" id="btn-request" onclick="sendRequest()" disabled>Request</button></div></div>
<div class="tabs-panel"><div class="tabs-header"><span>Abas Ativas</span><span id="tabs-counter">0 abas</span></div><div class="tabs-grid" id="tabs-container"><div class="empty-state">Clique em Iniciar para abrir abas</div></div></div></div>
<script>function fmt(s){const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60);return String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(sec).padStart(2,'0')}function update(){fetch('/api/status').then(r=>r.json()).then(d=>{document.getElementById('status-dot').className='status-dot'+(d.running?' active':'');document.getElementById('status-text').textContent=d.running?'Rodando':'Parado';document.getElementById('btn-start').disabled=d.running;document.getElementById('btn-stop').disabled=!d.running;document.getElementById('btn-request').disabled=!d.running||d.tabs.length===0;document.getElementById('total-tabs').textContent=d.tabs.length;document.getElementById('total-requests').textContent=d.stats.requests_total;document.getElementById('success-requests').textContent=d.stats.requests_success;document.getElementById('error-requests').textContent=d.stats.requests_error;if(d.stats.start_time)document.getElementById('uptime').textContent=fmt((Date.now()/1000)-d.stats.start_time);document.getElementById('tabs-counter').textContent=d.tabs.length+' abas';const c=document.getElementById('tabs-container');if(d.tabs.length===0){c.innerHTML='<div class="empty-state">Clique em Iniciar para abrir abas</div>';}else{c.innerHTML=d.tabs.map(t=>'<div class="tab-card '+(t.status==='pronta'?'active':'')+'"><div class="tab-header"><div class="tab-number">'+t.id+'</div><span class="tab-status '+t.status+'">'+t.status+'</span></div><div class="tab-info"><div class="tab-row"><span class="label">IP:</span><span class="value ip">'+t.ip+'</span></div><div class="tab-row"><span class="label">URL:</span><span class="value">'+(t.url||'...')+'</span></div><div class="tab-row"><span class="label">Req:</span><span class="value">'+t.requests+'</span></div></div></div>').join('');}}).catch(e=>console.error(e))}function startTabs(){fetch('/api/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({num_tabs:parseInt(document.getElementById('num-tabs').value)||3,url:document.getElementById('target-url').value||''})}).then(()=>update())}function stopTabs(){fetch('/api/stop',{method:'POST'}).then(()=>update())}function sendRequest(){fetch('/api/request',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.getElementById('target-url').value||'https://7k.bet.br/'})})}setInterval(update,1000);update();</script></body></html>'''

@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/status')
def api_status():
    return jsonify({"running": tab_manager.running, "tabs": tab_manager.get_all_tabs(), "stats": tab_manager.stats})

@app.route('/api/start', methods=['POST'])
def api_start():
    if tab_manager.running: return jsonify({"success": False})
    data = request.get_json() or {}
    num_tabs = data.get("num_tabs", 3)
    url = data.get("url", DEFAULT_URL)
    tab_manager.tabs = {}
    tab_manager.stats = {"requests_total": 0, "requests_success": 0, "requests_error": 0, "start_time": time.time()}
    tab_manager.running = True
    threading.Thread(target=browser_manager, args=(num_tabs, url, True), daemon=True).start()
    return jsonify({"success": True})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    tab_manager.running = False
    return jsonify({"success": True})

@app.route('/api/request', methods=['POST'])
def api_request():
    if not tab_manager.running: return jsonify({"success": False})
    data = request.get_json() or {}
    url = data.get("url", DEFAULT_URL)
    for tab_id in list(tab_manager.tabs.keys()):
        tab_manager.update_tab(tab_id, pending_request=url)
    return jsonify({"success": True})

if __name__ == '__main__':
    print("=" * 50)
    print("Dashboard de Abas")
    print("Acesse: http://localhost:5015")
    print("=" * 50)
    app.run(debug=False, host='0.0.0.0', port=5015, threaded=True)
