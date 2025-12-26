"""
Deploy usando Ansible via Python - Funciona no Windows
Usa subprocess para executar comandos ansible ad-hoc
"""

import subprocess
import sys
import yaml
import time
import os
import io
from pathlib import Path

# Configura encoding UTF-8 para Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configurações
INVENTORY_FILE = "inventory.yml"
SSH_KEY = r"C:\Users\outros\.ssh\id_rsa"
THREADS = 2000
SITE_URL = "7k.bet.br"

def get_ansible_path():
    """Encontra o caminho do ansible"""
    python_scripts = Path.home() / "AppData" / "Local" / "Packages" / "PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0" / "LocalCache" / "local-packages" / "Python311" / "Scripts"
    ansible_exe = python_scripts / "ansible.exe"
    if ansible_exe.exists():
        return str(ansible_exe)
    
    # Tenta encontrar no PATH
    try:
        result = subprocess.run(["where", "ansible"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
    except:
        pass
    
    return "ansible"

def load_inventory():
    """Carrega o inventory.yml"""
    try:
        with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Erro ao carregar inventory: {e}")
        return None

def run_ansible_command(hostname, module, args, inventory_file=INVENTORY_FILE):
    """Executa um comando ansible ad-hoc"""
    ansible_exe = get_ansible_path()
    
    cmd = [
        ansible_exe,
        hostname,
        "-m", module,
        "-a", args,
        "-i", inventory_file
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            encoding='utf-8',
            errors='replace'
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def deploy_to_server(hostname):
    """Faz deploy completo em um servidor"""
    print(f"\n{'='*50}")
    print(f"Processando {hostname}...")
    print(f"{'='*50}")
    
    # 1. Testa conexão
    print("[1/8] Testando conexão...", end=" ", flush=True)
    success, stdout, stderr = run_ansible_command(hostname, "ping", "")
    if not success:
        print("[ERRO] Nao foi possivel conectar")
        print(f"   Erro: {stderr}")
        return False
    print("[OK]")
    
    # 2. Verifica/instala screen
    print("[2/8] Verificando screen...", end=" ", flush=True)
    screen_cmd = "which screen || (apt-get update -qq 2>/dev/null && apt-get install -y -qq screen 2>/dev/null) || (yum install -y -q screen 2>/dev/null) || true"
    success, stdout, stderr = run_ansible_command(hostname, "shell", screen_cmd)
    print("[OK]")
    
    # 3. Verifica Go
    print("[3/8] Verificando Go...", end=" ", flush=True)
    success, stdout, stderr = run_ansible_command(hostname, "shell", "which go")
    if "go" not in stdout.lower():
        print("\n   Instalando Go...", end=" ", flush=True)
        go_cmd = "cd /tmp && wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz && sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz && rm go1.21.5.linux-amd64.tar.gz && echo 'Go instalado'"
        success, stdout, stderr = run_ansible_command(hostname, "shell", go_cmd)
        print("[OK]")
    
    # 4. Cria diretório
    print("[4/8] Criando diretório...", end=" ", flush=True)
    success, stdout, stderr = run_ansible_command(hostname, "file", "path=/opt/abrir_site_proxy state=directory mode=0755")
    if not success:
        print("[ERRO]")
        return False
    print("[OK]")
    
    # 5. Copia arquivo
    print("[5/8] Copiando arquivo...", end=" ", flush=True)
    copy_cmd = f"src=abrir_site_proxy.go dest=/opt/abrir_site_proxy/abrir_site_proxy.go mode=0644"
    success, stdout, stderr = run_ansible_command(hostname, "copy", copy_cmd)
    if not success:
        print("[ERRO]")
        print(f"   Erro: {stderr}")
        return False
    print("[OK]")
    
    # 6. Compila
    print("[6/8] Compilando...", end=" ", flush=True)
    build_cmd = "cd /opt/abrir_site_proxy && export GOROOT=/usr/local/go && export GOPATH=/root/go && export PATH=$PATH:/usr/local/go/bin:$GOPATH/bin && go mod init abrir_site_proxy 2>/dev/null || true && go get github.com/enetx/g github.com/enetx/surf && go build -o abrir_site_proxy abrir_site_proxy.go && chmod +x abrir_site_proxy && echo 'Compilado'"
    success, stdout, stderr = run_ansible_command(hostname, "shell", build_cmd)
    if not success or "Compilado" not in stdout:
        print("[ERRO]")
        print(f"   Erro: {stderr}")
        return False
    print("[OK]")
    
    # 7. Para processo antigo
    print("[7/8] Parando processo antigo...", end=" ", flush=True)
    stop_cmd = "pkill -f abrir_site_proxy || true; screen -X -S abrir_site_proxy quit || true"
    run_ansible_command(hostname, "shell", stop_cmd)
    time.sleep(1)
    print("[OK]")
    
    # 8. Executa com screen e 2000 threads
    print(f"[8/8] Executando com screen ({THREADS} threads)...", end=" ", flush=True)
    run_cmd = f"cd /opt/abrir_site_proxy && screen -dmS abrir_site_proxy bash -c './abrir_site_proxy {SITE_URL} {THREADS} > output.log 2>&1'"
    success, stdout, stderr = run_ansible_command(hostname, "shell", run_cmd)
    
    # Verifica se está rodando
    time.sleep(2)
    check_cmd = "screen -list | grep abrir_site_proxy && pgrep -f abrir_site_proxy && echo 'OK'"
    success_check, stdout_check, stderr_check = run_ansible_command(hostname, "shell", check_cmd)
    
    if success_check and "OK" in stdout_check:
        print("[OK] Programa rodando em screen!")
        return True
    else:
        print("[AVISO] Verifique manualmente")
        print(f"   Output: {stdout_check}")
        return False

def main():
    """Função principal"""
    print("="*60)
    print("  Deploy Ansible via Python - Screen + 2000 Threads")
    print("="*60)
    
    # Carrega inventory
    inventory = load_inventory()
    if not inventory:
        print("[ERRO] Nao foi possivel carregar inventory.yml")
        return
    
    hosts = inventory.get('all', {}).get('hosts', {})
    if not hosts:
        print("[ERRO] Nenhum host encontrado no inventory")
        return
    
    print(f"\nEncontrados {len(hosts)} servidores\n")
    
    # Processa cada servidor
    success_count = 0
    failed_count = 0
    
    for hostname in hosts.keys():
        if deploy_to_server(hostname):
            success_count += 1
        else:
            failed_count += 1
    
    # Resumo
    print("\n" + "="*60)
    print("  RESUMO DO DEPLOY")
    print("="*60)
    print(f"[OK] Sucesso: {success_count}")
    print(f"[ERRO] Falhas: {failed_count}")
    print(f"Total: {len(hosts)}")
    print("="*60)
    
    if success_count > 0:
        print("\nComandos uteis:")
        print("   Verificar screens:")
        print(f"   ansible all -m shell -a 'screen -list' -i {INVENTORY_FILE}")
        print("\n   Ver logs:")
        print(f"   ansible servidor1 -m shell -a 'tail -20 /opt/abrir_site_proxy/output.log' -i {INVENTORY_FILE}")
        print("\n   Conectar ao screen:")
        print(f"   ansible servidor1 -m shell -a 'screen -r abrir_site_proxy' -i {INVENTORY_FILE}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[AVISO] Interrompido pelo usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO]: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

