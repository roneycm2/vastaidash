#!/bin/bash
# Script para executar deploy via Ansible no WSL
# Usa screen e 2000 threads

echo "=========================================="
echo "  Deploy Ansible - WSL Ubuntu"
echo "  Screen + 2000 Threads"
echo "=========================================="
echo ""

# Verifica se está no WSL
if [ -z "$WSL_DISTRO_NAME" ]; then
    echo "[AVISO] Este script deve ser executado dentro do WSL"
    echo "Execute: wsl -d Ubuntu-24.04"
    exit 1
fi

# Verifica se Ansible está instalado
if ! command -v ansible-playbook &> /dev/null; then
    echo "[ERRO] Ansible nao encontrado. Execute primeiro:"
    echo "  bash setup_ansible_wsl.sh"
    exit 1
fi

# Copia arquivos do Windows para o WSL (se necessário)
WINDOWS_PATH="/mnt/c/Users/outros/liderbet"
CURRENT_DIR=$(pwd)

if [ ! -f "inventory.yml" ]; then
    if [ -f "$WINDOWS_PATH/inventory.yml" ]; then
        echo "[INFO] Copiando arquivos do Windows..."
        cp "$WINDOWS_PATH/inventory.yml" .
        cp "$WINDOWS_PATH/deploy_golang.yml" .
        cp "$WINDOWS_PATH/abrir_site_proxy.go" .
        cp "$WINDOWS_PATH/ansible.cfg" .
    else
        echo "[ERRO] Arquivos nao encontrados. Certifique-se de estar no diretorio correto."
        exit 1
    fi
fi

# Atualiza o playbook para usar 2000 threads e screen
echo "[INFO] Atualizando playbook para 2000 threads e screen..."

# Cria playbook atualizado
cat > deploy_golang_screen.yml << 'EOF'
---
- name: Instalar Go, compilar e executar abrir_site_proxy.go com screen
  hosts: all
  become: yes
  vars:
    go_version: "1.21.5"
    go_install_dir: "/usr/local"
    app_name: "abrir_site_proxy"
    app_dir: "/opt/{{ app_name }}"
    site_url: "7k.bet.br"
    num_threads: "2000"
  
  tasks:
    - name: Instalar screen
      apt:
        name: screen
        state: present
        update_cache: yes
      when: ansible_os_family == "Debian"
    
    - name: Instalar screen (RedHat)
      yum:
        name: screen
        state: present
      when: ansible_os_family == "RedHat"

    - name: Verificar se Go já está instalado
      command: which go
      register: go_check
      ignore_errors: yes
      changed_when: false

    - name: Baixar Go
      get_url:
        url: "https://go.dev/dl/go{{ go_version }}.linux-amd64.tar.gz"
        dest: "/tmp/go{{ go_version }}.linux-amd64.tar.gz"
      when: go_check.rc != 0

    - name: Remover instalação antiga do Go (se existir)
      file:
        path: "{{ go_install_dir }}/go"
        state: absent
      when: go_check.rc != 0

    - name: Extrair Go
      unarchive:
        src: "/tmp/go{{ go_version }}.linux-amd64.tar.gz"
        dest: "{{ go_install_dir }}"
        remote_src: yes
      when: go_check.rc != 0

    - name: Configurar variáveis de ambiente do Go
      lineinfile:
        path: /etc/profile.d/golang.sh
        line: "{{ item }}"
        create: yes
        mode: '0644'
      loop:
        - "export GOROOT={{ go_install_dir }}/go"
        - "export GOPATH=$HOME/go"
        - "export PATH=$PATH:{{ go_install_dir }}/go/bin:$GOPATH/bin"
      when: go_check.rc != 0

    - name: Criar diretório da aplicação
      file:
        path: "{{ app_dir }}"
        state: directory
        mode: '0755'

    - name: Copiar arquivo abrir_site_proxy.go
      copy:
        src: abrir_site_proxy.go
        dest: "{{ app_dir }}/abrir_site_proxy.go"
        mode: '0644'

    - name: Inicializar módulo Go
      command: go mod init {{ app_name }}
      args:
        chdir: "{{ app_dir }}"
        creates: "{{ app_dir }}/go.mod"
      environment:
        GOROOT: "{{ go_install_dir }}/go"
        GOPATH: "/root/go"
        PATH: "{{ ansible_env.PATH }}:{{ go_install_dir }}/go/bin"

    - name: Baixar dependências Go
      command: go get github.com/enetx/g github.com/enetx/surf
      args:
        chdir: "{{ app_dir }}"
      environment:
        GOROOT: "{{ go_install_dir }}/go"
        GOPATH: "/root/go"
        PATH: "{{ ansible_env.PATH }}:{{ go_install_dir }}/go/bin"

    - name: Compilar aplicação
      command: go build -o {{ app_name }} abrir_site_proxy.go
      args:
        chdir: "{{ app_dir }}"
      environment:
        GOROOT: "{{ go_install_dir }}/go"
        GOPATH: "/root/go"
        PATH: "{{ ansible_env.PATH }}:{{ go_install_dir }}/go/bin"
      register: build_result

    - name: Tornar executável
      file:
        path: "{{ app_dir }}/{{ app_name }}"
        mode: '0755'

    - name: Parar processo existente (se houver)
      shell: pkill -f "{{ app_name }}" || true
      ignore_errors: yes

    - name: Fechar screen antigo (se existir)
      shell: screen -X -S {{ app_name }} quit || true
      ignore_errors: yes

    - name: Executar aplicação em screen com 2000 threads
      shell: |
        cd {{ app_dir }}
        screen -dmS {{ app_name }} bash -c './{{ app_name }} {{ site_url }} {{ num_threads }} > output.log 2>&1'
        sleep 2
        screen -list | grep {{ app_name }} && echo "Executando em screen" || echo "Erro"
      environment:
        GOROOT: "{{ go_install_dir }}/go"
        GOPATH: "/root/go"
        PATH: "{{ ansible_env.PATH }}:{{ go_install_dir }}/go/bin"
      register: run_result

    - name: Verificar se processo está rodando
      shell: pgrep -f "{{ app_name }}"
      register: process_check
      ignore_errors: yes
      changed_when: false

    - name: Mostrar status
      debug:
        msg:
          - "✅ Aplicação compilada e executada com sucesso!"
          - "📁 Diretório: {{ app_dir }}"
          - "🚀 Processo PID: {{ process_check.stdout if process_check.rc == 0 else 'Não encontrado' }}"
          - "📋 Logs: {{ app_dir }}/output.log"
          - "🔧 Para ver screen: screen -r {{ app_name }}"
          - "📊 Para ver logs: tail -f {{ app_dir }}/output.log"
EOF

echo "[INFO] Executando playbook..."
ansible-playbook deploy_golang_screen.yml -i inventory.yml

echo ""
echo "=========================================="
echo "  Deploy concluido!"
echo "=========================================="



