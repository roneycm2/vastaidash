#!/bin/bash
# Script simples para instalar Ansible no WSL

echo "=========================================="
echo "  Instalando Ansible no WSL"
echo "=========================================="
echo ""

echo "[1/3] Atualizando sistema..."
sudo apt-get update -qq

echo "[2/3] Instalando Python e pip..."
sudo apt-get install -y -qq python3 python3-pip

echo "[3/3] Instalando Ansible..."
sudo pip3 install ansible

echo ""
echo "=========================================="
echo "  Verificando instalacao..."
echo "=========================================="
ansible --version

echo ""
echo "=========================================="
echo "  Ansible instalado com sucesso!"
echo "=========================================="



