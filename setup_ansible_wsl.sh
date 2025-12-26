#!/bin/bash
# Script para instalar Ansible no WSL Ubuntu

echo "=========================================="
echo "  Instalando Ansible no WSL Ubuntu"
echo "=========================================="
echo ""

# Atualiza sistema
echo "[1/4] Atualizando sistema..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# Instala dependências
echo "[2/4] Instalando dependencias..."
sudo apt-get install -y -qq python3 python3-pip python3-venv software-properties-common

# Instala Ansible
echo "[3/4] Instalando Ansible..."
sudo pip3 install ansible

# Verifica instalação
echo "[4/4] Verificando instalacao..."
ansible --version

echo ""
echo "=========================================="
echo "  Ansible instalado com sucesso!"
echo "=========================================="



