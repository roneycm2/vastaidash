#!/usr/bin/env python3
"""
Deploy & Control Solver via SSH para Vast.ai
=============================================
Este script:
1. Busca máquinas ativas na Vast.ai
2. Conecta via SSH em cada uma
3. Envia o solver e executa
4. Monitora logs em tempo real
5. Pode matar processos em todas as máquinas

Uso:
    # Deploy e executa solver
    python deploy_solver_ssh.py --tabs 3
    python deploy_solver_ssh.py --machine 142.170.89.112:22 --tabs 5
    
    # Mata processos em todas as máquinas
    python deploy_solver_ssh.py --kill
    
    # Status dos processos
    python deploy_solver_ssh.py --status
    
    # Lista máquinas
    python deploy_solver_ssh.py --list
"""

import os
import sys
import json
import time
import subprocess
import threading
import argparse
import requests
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Vast.ai API
VAST_API_KEY = "e8f9118afe31f8aa7e23e0a5e7a29d9f7dc716c82e2d2c3f09a4f4fcf17be8f0"
VAST_API_URL = "https://console.vast.ai/api/v0"

# Arquivo do solver
SOLVER_FILE = "turnstile_remote_solver.py"

# SSH timeout
SSH_TIMEOUT = 30


def log(msg: str, level: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"info": "ℹ️", "ok": "✅", "err": "❌", "warn": "⚠️", "run": "🚀"}
    print(f"[{ts}] {icons.get(level, '•')} {msg}")


def get_vast_instances():
    """Busca instâncias ativas na Vast.ai"""
    log("Buscando instâncias na Vast.ai...")
    
    try:
        headers = {"Authorization": f"Bearer {VAST_API_KEY}"}
        resp = requests.get(f"{VAST_API_URL}/instances", headers=headers, params={"owner": "me"})
        
        if resp.status_code != 200:
            log(f"Erro API: {resp.status_code}", "err")
            return []
        
        data = resp.json()
        instances = data.get("instances", [])
        
        # Filtra running
        running = [i for i in instances if i.get("actual_status") == "running"]
        
        log(f"Encontradas {len(running)} instâncias rodando", "ok")
        
        result = []
        for inst in running:
            ssh_host = inst.get("ssh_host")
            ssh_port = inst.get("ssh_port")
            if ssh_host and ssh_port:
                result.append({
                    "id": inst.get("id"),
                    "host": ssh_host,
                    "port": ssh_port,
                    "gpu": inst.get("gpu_name", "Unknown"),
                    "ram": inst.get("cpu_ram", 0) / 1024  # GB
                })
        
        return result
        
    except Exception as e:
        log(f"Erro ao buscar Vast.ai: {e}", "err")
        return []


def check_ssh_available():
    """Verifica se SSH está disponível"""
    try:
        result = subprocess.run(["ssh", "-V"], capture_output=True, timeout=5)
        return True
    except:
        return False


def deploy_to_machine(machine: dict, solver_content: str, num_tabs: int):
    """Deploy e executa solver em uma máquina"""
    host = machine["host"]
    port = machine["port"]
    machine_id = machine.get("id", "unknown")
    
    log(f"[{host}:{port}] Conectando...")
    
    try:
        # Cria script temporário que inclui o solver
        remote_script = f'''
#!/bin/bash
cd /tmp

# Salva solver
cat > turnstile_solver.py << 'SOLVER_EOF'
{solver_content}
SOLVER_EOF

# Executa
python3 turnstile_solver.py --tabs {num_tabs} --skip-install 2>&1
'''
        
        # Executa via SSH
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=30",
            "-o", "ServerAliveInterval=30",
            "-p", str(port),
            f"root@{host}",
            "bash -s"
        ]
        
        log(f"[{host}:{port}] Executando solver com {num_tabs} tabs...", "run")
        
        # Inicia processo
        process = subprocess.Popen(
            ssh_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Envia script
        process.stdin.write(remote_script)
        process.stdin.close()
        
        # Lê output em tempo real
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                print(f"[{host}] {line.rstrip()}")
        
        return_code = process.wait()
        
        if return_code == 0:
            log(f"[{host}:{port}] Finalizado com sucesso", "ok")
        else:
            log(f"[{host}:{port}] Finalizado com código {return_code}", "warn")
        
        return True
        
    except subprocess.TimeoutExpired:
        log(f"[{host}:{port}] Timeout", "err")
        return False
    except Exception as e:
        log(f"[{host}:{port}] Erro: {e}", "err")
        return False


def run_deploy(machines: list, num_tabs: int = 3):
    """Executa deploy em múltiplas máquinas"""
    
    if not machines:
        log("Nenhuma máquina para deploy", "err")
        return
    
    # Lê conteúdo do solver
    solver_path = Path(__file__).parent / SOLVER_FILE
    if not solver_path.exists():
        log(f"Arquivo {SOLVER_FILE} não encontrado", "err")
        return
    
    with open(solver_path, "r", encoding="utf-8") as f:
        solver_content = f.read()
    
    log(f"Solver carregado: {len(solver_content)} bytes")
    
    print()
    print("=" * 60)
    print("🚀 DEPLOY SOLVER VIA SSH")
    print("=" * 60)
    print(f"Máquinas: {len(machines)}")
    print(f"Tabs por máquina: {num_tabs}")
    print("=" * 60)
    print()
    
    # Deploy em paralelo
    with ThreadPoolExecutor(max_workers=min(len(machines), 5)) as executor:
        futures = {
            executor.submit(deploy_to_machine, m, solver_content, num_tabs): m 
            for m in machines
        }
        
        try:
            for future in as_completed(futures):
                machine = futures[future]
                try:
                    future.result()
                except Exception as e:
                    log(f"[{machine['host']}] Erro: {e}", "err")
                    
        except KeyboardInterrupt:
            log("Deploy interrompido", "warn")


def run_ssh_command(machine: dict, command: str, timeout: int = 30) -> tuple:
    """Executa um comando SSH e retorna (success, output)"""
    host = machine["host"]
    port = machine["port"]
    
    try:
        ssh_cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "ConnectTimeout=10",
            "-p", str(port),
            f"root@{host}",
            command
        ]
        
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        return result.returncode == 0, result.stdout + result.stderr
        
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)


def kill_solver_on_machine(machine: dict) -> bool:
    """Mata o processo do solver em uma máquina"""
    host = machine["host"]
    port = machine["port"]
    
    log(f"[{host}:{port}] Matando processos...")
    
    # Comandos para matar o solver
    kill_commands = [
        "pkill -f turnstile_solver",
        "pkill -f turnstile_remote",
        "pkill -f patchright",
        "pkill -f chromium",
        "killall python3 2>/dev/null || true"
    ]
    
    success, output = run_ssh_command(machine, " ; ".join(kill_commands))
    
    if success:
        log(f"[{host}:{port}] Processos finalizados", "ok")
    else:
        log(f"[{host}:{port}] Possível erro: {output[:50]}", "warn")
    
    return success


def get_solver_status(machine: dict) -> dict:
    """Verifica status do solver em uma máquina"""
    host = machine["host"]
    port = machine["port"]
    
    # Verifica processos rodando
    success, output = run_ssh_command(machine, "ps aux | grep -E 'turnstile|patchright' | grep -v grep | wc -l")
    
    process_count = 0
    if success:
        try:
            process_count = int(output.strip())
        except:
            pass
    
    # Conta tokens salvos
    success2, output2 = run_ssh_command(machine, "wc -l < /tmp/turnstile_tokens.jsonl 2>/dev/null || echo 0")
    
    token_count = 0
    if success2:
        try:
            token_count = int(output2.strip())
        except:
            pass
    
    return {
        "host": host,
        "port": port,
        "running": process_count > 0,
        "processes": process_count,
        "tokens": token_count
    }


def kill_all(machines: list):
    """Mata solver em todas as máquinas"""
    print()
    print("=" * 60)
    print("🛑 KILL ALL - Matando processos em todas as máquinas")
    print("=" * 60)
    print()
    
    with ThreadPoolExecutor(max_workers=min(len(machines), 10)) as executor:
        futures = {executor.submit(kill_solver_on_machine, m): m for m in machines}
        
        for future in as_completed(futures):
            machine = futures[future]
            try:
                future.result()
            except Exception as e:
                log(f"[{machine['host']}] Erro: {e}", "err")
    
    print()
    log("Todos os processos foram finalizados", "ok")


def status_all(machines: list):
    """Verifica status em todas as máquinas"""
    print()
    print("=" * 60)
    print("📊 STATUS - Verificando todas as máquinas")
    print("=" * 60)
    print()
    
    results = []
    
    with ThreadPoolExecutor(max_workers=min(len(machines), 10)) as executor:
        futures = {executor.submit(get_solver_status, m): m for m in machines}
        
        for future in as_completed(futures):
            try:
                status = future.result()
                results.append(status)
            except Exception as e:
                log(f"Erro ao verificar: {e}", "err")
    
    # Mostra resultados
    print()
    print(f"{'HOST':<25} {'PORTA':<8} {'STATUS':<12} {'PROCS':<8} {'TOKENS':<10}")
    print("-" * 70)
    
    total_tokens = 0
    running_count = 0
    
    for r in results:
        status_icon = "🟢 Running" if r["running"] else "🔴 Stopped"
        print(f"{r['host']:<25} {r['port']:<8} {status_icon:<12} {r['processes']:<8} {r['tokens']:<10}")
        total_tokens += r["tokens"]
        if r["running"]:
            running_count += 1
    
    print("-" * 70)
    print(f"{'TOTAL':<25} {'':<8} {f'{running_count}/{len(results)}':<12} {'':<8} {total_tokens:<10}")
    print()


def fetch_tokens(machines: list, output_file: str = "all_tokens.jsonl"):
    """Baixa tokens de todas as máquinas"""
    print()
    print("=" * 60)
    print("📥 FETCH TOKENS - Baixando tokens de todas as máquinas")
    print("=" * 60)
    print()
    
    all_tokens = []
    
    for machine in machines:
        host = machine["host"]
        port = machine["port"]
        
        log(f"[{host}:{port}] Buscando tokens...")
        
        success, output = run_ssh_command(machine, "cat /tmp/turnstile_tokens.jsonl 2>/dev/null || echo ''", timeout=60)
        
        if success and output.strip():
            lines = output.strip().split("\n")
            for line in lines:
                try:
                    token_data = json.loads(line)
                    token_data["source_host"] = host
                    all_tokens.append(token_data)
                except:
                    pass
            log(f"[{host}:{port}] {len(lines)} tokens", "ok")
        else:
            log(f"[{host}:{port}] Nenhum token", "warn")
    
    # Salva todos
    if all_tokens:
        with open(output_file, "w") as f:
            for t in all_tokens:
                f.write(json.dumps(t) + "\n")
        
        log(f"Total: {len(all_tokens)} tokens salvos em {output_file}", "ok")
    else:
        log("Nenhum token encontrado", "warn")
    
    return all_tokens


def main():
    parser = argparse.ArgumentParser(description="Deploy & Control Solver via SSH")
    parser.add_argument("--tabs", "-t", type=int, default=3, help="Tabs por máquina")
    parser.add_argument("--machine", "-m", help="Máquina específica (host:port)")
    parser.add_argument("--list", "-l", action="store_true", help="Listar máquinas")
    parser.add_argument("--kill", "-k", action="store_true", help="Mata solver em todas as máquinas")
    parser.add_argument("--status", "-s", action="store_true", help="Status de todas as máquinas")
    parser.add_argument("--fetch", "-f", action="store_true", help="Baixa tokens de todas as máquinas")
    
    args = parser.parse_args()
    
    # Verifica SSH
    if not check_ssh_available():
        log("SSH não disponível. Instale OpenSSH.", "err")
        sys.exit(1)
    
    # Busca máquinas
    if args.machine:
        # Máquina específica
        parts = args.machine.split(":")
        if len(parts) == 2:
            machines = [{"host": parts[0], "port": int(parts[1]), "id": "manual"}]
        else:
            log("Formato inválido. Use host:port", "err")
            sys.exit(1)
    else:
        # Busca na Vast.ai
        machines = get_vast_instances()
    
    if not machines:
        log("Nenhuma máquina encontrada", "err")
        sys.exit(1)
    
    # Operações
    if args.kill:
        kill_all(machines)
        return
    
    if args.status:
        status_all(machines)
        return
    
    if args.fetch:
        fetch_tokens(machines)
        return
    
    # Lista máquinas
    print()
    print("Máquinas disponíveis:")
    for m in machines:
        print(f"  • {m['host']}:{m['port']} (ID: {m.get('id', 'N/A')})")
    print()
    
    if args.list:
        return
    
    # Confirma deploy
    input("Pressione Enter para iniciar deploy ou Ctrl+C para cancelar...")
    
    # Deploy
    run_deploy(machines, args.tabs)


if __name__ == "__main__":
    main()

