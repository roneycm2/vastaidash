# Script para iniciar o dashboard Ansible
Write-Host "Iniciando Ansible Dashboard..." -ForegroundColor Cyan

# Adiciona Python ao PATH se necessario
$pythonPath = "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts"
if (Test-Path $pythonPath) {
    $env:PATH = "$pythonPath;$env:PATH"
}

# Verifica se Flask esta instalado
Write-Host "Verificando dependencias..." -ForegroundColor Yellow
$flaskCheck = python -c "import flask; print('OK')" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Flask nao encontrado. Instalando..." -ForegroundColor Yellow
    pip install flask
}

# Inicia o dashboard
Write-Host "Iniciando servidor na porta 5000..." -ForegroundColor Green
Write-Host "Acesse: http://localhost:5000" -ForegroundColor Cyan
Write-Host "Pressione Ctrl+C para parar" -ForegroundColor Yellow
Write-Host ""

python dashboard_ansible.py

