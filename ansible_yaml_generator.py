"""
Dashboard para gerar arquivos YAML de inventário Ansible
"""

from flask import Flask, render_template_string, request, send_file
import io
import re

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ansible Inventory Generator v2</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-tertiary: #1f2937;
            --accent: #10b981;
            --accent-hover: #059669;
            --accent-glow: rgba(16, 185, 129, 0.3);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --border: #374151;
            --danger: #ef4444;
            --warning: #f59e0b;
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
                radial-gradient(ellipse at 20% 20%, rgba(16, 185, 129, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
                linear-gradient(180deg, var(--bg-primary) 0%, #0f172a 100%);
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        header {
            text-align: center;
            margin-bottom: 3rem;
            padding: 2rem 0;
        }
        
        h1 {
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent) 0%, #3b82f6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.5rem;
            letter-spacing: -0.02em;
        }
        
        .subtitle {
            color: var(--text-secondary);
            font-size: 1.1rem;
        }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }
        
        @media (max-width: 1024px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .card {
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.5rem;
            transition: all 0.3s ease;
        }
        
        .card:hover {
            border-color: var(--accent);
            box-shadow: 0 0 30px var(--accent-glow);
        }
        
        .card-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 1.25rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }
        
        .card-icon {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent) 0%, #059669 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }
        
        .card-title {
            font-size: 1.25rem;
            font-weight: 600;
        }
        
        .form-group {
            margin-bottom: 1.25rem;
        }
        
        label {
            display: block;
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }
        
        input[type="text"],
        input[type="number"],
        textarea {
            width: 100%;
            padding: 0.875rem 1rem;
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 10px;
            color: var(--text-primary);
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }
        
        input:focus,
        textarea:focus {
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }
        
        textarea {
            min-height: 400px;
            resize: vertical;
            line-height: 1.6;
        }
        
        .input-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        
        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 1rem 2rem;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1rem;
            font-weight: 600;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent) 0%, #059669 100%);
            color: white;
            width: 100%;
            margin-top: 1rem;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px var(--accent-glow);
        }
        
        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border);
        }
        
        .btn-secondary:hover {
            border-color: var(--accent);
        }
        
        .output-area {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 1rem;
            min-height: 400px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            line-height: 1.6;
            overflow-x: auto;
            white-space: pre-wrap;
            color: var(--text-secondary);
        }
        
        .stats-bar {
            display: flex;
            gap: 1.5rem;
            margin-bottom: 1rem;
            padding: 1rem;
            background: var(--bg-tertiary);
            border-radius: 10px;
        }
        
        .stat {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--accent);
        }
        
        .stat-label {
            font-size: 0.875rem;
            color: var(--text-muted);
        }
        
        .actions {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }
        
        .actions .btn {
            flex: 1;
        }
        
        .filename-input {
            display: flex;
            gap: 0.5rem;
            align-items: center;
        }
        
        .filename-input input {
            flex: 1;
        }
        
        .filename-input span {
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            padding: 1rem 1.5rem;
            background: var(--accent);
            color: white;
            border-radius: 10px;
            font-weight: 500;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 1000;
        }
        
        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }
        
        .help-text {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
        }
        
        .preview-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .preview-header .btn-secondary {
            padding: 0.5rem 1rem;
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⚡ Ansible Inventory Generator</h1>
            <p class="subtitle">Converta IP:PORTA para formato YAML de inventário Ansible</p>
        </header>
        
        <div class="main-grid">
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📝</div>
                    <h2 class="card-title">Entrada de Dados</h2>
                </div>
                
                <form id="generatorForm">
                    <div class="form-group">
                        <label for="hosts">Lista de IP:PORTA (um por linha)</label>
                        <textarea id="hosts" name="hosts" placeholder="217.171.200.22:34340&#10;37.41.28.10:40416&#10;184.191.105.145:22906"></textarea>
                        <p class="help-text">Formato: IP:PORTA ou HOST:PORTA (ex: fiber1.kmidata.es:24844)</p>
                    </div>
                    
                    <div class="input-row">
                        <div class="form-group">
                            <label for="site_url">Site URL</label>
                            <input type="text" id="site_url" name="site_url" value="7k.bet.br" placeholder="7k.bet.br">
                        </div>
                        <div class="form-group">
                            <label for="num_threads">Número de Threads</label>
                            <input type="text" id="num_threads" name="num_threads" value="50" placeholder="50">
                        </div>
                    </div>
                    
                    <div class="input-row">
                        <div class="form-group">
                            <label for="ansible_user">Usuário SSH</label>
                            <input type="text" id="ansible_user" name="ansible_user" value="root" placeholder="root">
                        </div>
                        <div class="form-group">
                            <label for="ssh_key">Caminho Chave SSH</label>
                            <input type="text" id="ssh_key" name="ssh_key" value="/root/.ssh/id_rsa" placeholder="/root/.ssh/id_rsa">
                        </div>
                    </div>
                    
                    <div class="form-group">
                        <label>Nome do Arquivo</label>
                        <div class="filename-input">
                            <input type="text" id="filename" name="filename" value="01" placeholder="01">
                            <span>.yml</span>
                        </div>
                    </div>
                    
                    <button type="submit" class="btn btn-primary">
                        ⚡ Gerar YAML
                    </button>
                </form>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <div class="card-icon">📄</div>
                    <h2 class="card-title">Preview do YAML</h2>
                </div>
                
                <div class="stats-bar">
                    <div class="stat">
                        <span class="stat-value" id="hostCount">0</span>
                        <span class="stat-label">hosts</span>
                    </div>
                    <div class="stat">
                        <span class="stat-value" id="validCount">0</span>
                        <span class="stat-label">válidos</span>
                    </div>
                    <div class="stat">
                        <span class="stat-value" id="duplicateCount">0</span>
                        <span class="stat-label">duplicados</span>
                    </div>
                    <div class="stat">
                        <span class="stat-value" id="invalidCount">0</span>
                        <span class="stat-label">inválidos</span>
                    </div>
                </div>
                
                <div class="preview-header">
                    <span style="color: var(--text-muted); font-size: 0.875rem;">Arquivo: <span id="previewFilename">01.yml</span></span>
                    <button type="button" class="btn btn-secondary" onclick="copyToClipboard()">📋 Copiar</button>
                </div>
                
                <div class="output-area" id="yamlOutput">O YAML gerado aparecerá aqui...</div>
                
                <div class="actions">
                    <button type="button" class="btn btn-primary" onclick="downloadYaml()">
                        💾 Baixar YAML
                    </button>
                </div>
            </div>
        </div>
    </div>
    
    <div class="toast" id="toast"></div>
    
    <script>
        let currentYaml = '';
        
        function showToast(message) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.classList.add('show');
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
        
        function updatePreviewFilename() {
            const filename = document.getElementById('filename').value || '01';
            document.getElementById('previewFilename').textContent = filename + '.yml';
        }
        
        document.getElementById('filename').addEventListener('input', updatePreviewFilename);
        
        function parseHosts(text) {
            const lines = text.trim().split('\\n');
            const hosts = [];
            const invalid = [];
            const seen = new Set();
            let duplicates = 0;
            
            lines.forEach((line, index) => {
                line = line.trim();
                if (!line) return;
                
                // Match IP:PORT or HOSTNAME:PORT
                const match = line.match(/^([\\w\\.-]+):(\\d+)$/);
                if (match) {
                    const key = `${match[1]}:${match[2]}`;
                    if (!seen.has(key)) {
                        seen.add(key);
                        hosts.push({
                            host: match[1],
                            port: parseInt(match[2])
                        });
                    } else {
                        duplicates++;
                    }
                } else {
                    invalid.push(line);
                }
            });
            
            return { hosts, invalid, duplicates };
        }
        
        function generateYaml(hosts, siteUrl, numThreads, ansibleUser, sshKey) {
            let yaml = 'all:\\n';
            yaml += '  hosts:\\n';
            
            hosts.forEach((h, index) => {
                yaml += `    servidor${index + 1}:\\n`;
                yaml += `      ansible_host: ${h.host}\\n`;
                yaml += `      ansible_port: ${h.port}\\n`;
                yaml += `      ansible_user: ${ansibleUser}\\n`;
                yaml += `      ansible_ssh_private_key_file: ${sshKey}\\n`;
            });
            
            yaml += '\\n  vars:\\n';
            yaml += `    site_url: ${siteUrl}\\n`;
            yaml += `    num_threads: '${numThreads}'\\n`;
            
            return yaml;
        }
        
        document.getElementById('generatorForm').addEventListener('submit', function(e) {
            e.preventDefault();
            
            const hostsText = document.getElementById('hosts').value;
            const siteUrl = document.getElementById('site_url').value || '7k.bet.br';
            const numThreads = document.getElementById('num_threads').value || '50';
            const ansibleUser = document.getElementById('ansible_user').value || 'root';
            const sshKey = document.getElementById('ssh_key').value || '/root/.ssh/id_rsa';
            
            const { hosts, invalid, duplicates } = parseHosts(hostsText);
            
            document.getElementById('hostCount').textContent = hosts.length + invalid.length + duplicates;
            document.getElementById('validCount').textContent = hosts.length;
            document.getElementById('duplicateCount').textContent = duplicates;
            document.getElementById('invalidCount').textContent = invalid.length;
            
            if (hosts.length === 0) {
                document.getElementById('yamlOutput').textContent = 'Nenhum host válido encontrado.\\nFormato esperado: IP:PORTA ou HOSTNAME:PORTA';
                currentYaml = '';
                return;
            }
            
            currentYaml = generateYaml(hosts, siteUrl, numThreads, ansibleUser, sshKey);
            document.getElementById('yamlOutput').textContent = currentYaml;
            
            showToast(`✅ ${hosts.length} hosts processados com sucesso!`);
        });
        
        function copyToClipboard() {
            if (!currentYaml) {
                showToast('⚠️ Gere o YAML primeiro!');
                return;
            }
            
            navigator.clipboard.writeText(currentYaml).then(() => {
                showToast('📋 YAML copiado para a área de transferência!');
            });
        }
        
        function downloadYaml() {
            if (!currentYaml) {
                showToast('⚠️ Gere o YAML primeiro!');
                return;
            }
            
            const filename = document.getElementById('filename').value || '01';
            const blob = new Blob([currentYaml], { type: 'text/yaml' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename + '.yml';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            showToast(`💾 ${filename}.yml baixado com sucesso!`);
        }
        
        // Auto-generate on paste
        document.getElementById('hosts').addEventListener('paste', function() {
            setTimeout(() => {
                document.getElementById('generatorForm').dispatchEvent(new Event('submit'));
            }, 100);
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    hosts_text = data.get('hosts', '')
    site_url = data.get('site_url', '7k.bet.br')
    num_threads = data.get('num_threads', '50')
    ansible_user = data.get('ansible_user', 'root')
    ssh_key = data.get('ssh_key', '/root/.ssh/id_rsa')
    filename = data.get('filename', '01')
    
    # Parse hosts (removing duplicates)
    hosts = []
    seen = set()
    lines = hosts_text.strip().split('\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^([\w\.-]+):(\d+)$', line)
        if match:
            key = f"{match.group(1)}:{match.group(2)}"
            if key not in seen:
                seen.add(key)
                hosts.append({
                    'host': match.group(1),
                    'port': int(match.group(2))
                })
    
    # Generate YAML
    yaml_content = "all:\n"
    yaml_content += "  hosts:\n"
    
    for i, h in enumerate(hosts, 1):
        yaml_content += f"    servidor{i}:\n"
        yaml_content += f"      ansible_host: {h['host']}\n"
        yaml_content += f"      ansible_port: {h['port']}\n"
        yaml_content += f"      ansible_user: {ansible_user}\n"
        yaml_content += f"      ansible_ssh_private_key_file: {ssh_key}\n"
    
    yaml_content += "\n  vars:\n"
    yaml_content += f"    site_url: {site_url}\n"
    yaml_content += f"    num_threads: '{num_threads}'\n"
    
    return {
        'yaml': yaml_content,
        'count': len(hosts),
        'filename': f"{filename}.yml"
    }

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    yaml_content = data.get('yaml', '')
    filename = data.get('filename', '01.yml')
    
    buffer = io.BytesIO()
    buffer.write(yaml_content.encode('utf-8'))
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='text/yaml'
    )

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Ansible Inventory Generator")
    print("="*50)
    print("\n📌 Acesse: http://localhost:5050")
    print("📌 Pressione Ctrl+C para encerrar\n")
    app.run(host='0.0.0.0', port=5050, debug=False)

