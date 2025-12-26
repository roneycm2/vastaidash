# Script PowerShell para executar Ansible no WSL
# Instala Ansible se necessário e executa o deploy

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Ansible via WSL - Setup e Deploy" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verifica se WSL está disponível
$wslCheck = wsl --list --verbose 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERRO] WSL nao encontrado. Instalando..." -ForegroundColor Red
    Write-Host "Execute como Administrador: wsl --install" -ForegroundColor Yellow
    exit 1
}

Write-Host "[INFO] WSL encontrado" -ForegroundColor Green
Write-Host ""

# Verifica se Ubuntu está instalado
$ubuntuInstalled = $wslCheck -match "Ubuntu"
if (-not $ubuntuInstalled) {
    Write-Host "[INFO] Ubuntu nao encontrado. Tentando instalar..." -ForegroundColor Yellow
    wsl --install -d Ubuntu-24.04 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[AVISO] Ubuntu pode ja estar instalado ou houve erro na instalacao" -ForegroundColor Yellow
    }
}

# Usa Ubuntu-24.04 ou tenta Ubuntu
$distro = "Ubuntu-24.04"
$distroCheck = wsl -d $distro echo "test" 2>&1
if ($LASTEXITCODE -ne 0) {
    $distro = "Ubuntu"
    $distroCheck = wsl -d $distro echo "test" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] Nenhuma distribuicao Ubuntu encontrada" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[INFO] Usando distribuicao: $distro" -ForegroundColor Green
Write-Host ""

# Copia scripts para o WSL
Write-Host "[1/3] Preparando scripts no WSL..." -ForegroundColor Gray
$currentPath = (Get-Location).Path.Replace('\', '/').Replace('C:', '/mnt/c')
$wslPath = "/tmp/liderbet"

# Copia arquivos para o WSL
wsl -d $distro bash -c "mkdir -p $wslPath && cp -r $currentPath/* $wslPath/ 2>/dev/null || true && chmod +x $wslPath/*.sh 2>/dev/null || true"
Write-Host "[OK] Scripts copiados" -ForegroundColor Green

# Verifica se Ansible está instalado
Write-Host "[2/3] Verificando Ansible..." -ForegroundColor Gray
$ansibleCheck = wsl -d $distro bash -c "which ansible-playbook" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[INFO] Ansible nao encontrado. Instalando..." -ForegroundColor Yellow
    Write-Host "Isso pode levar alguns minutos..." -ForegroundColor Gray
    
    # Executa script de instalação
    wsl -d $distro bash -c "cd $wslPath && bash setup_ansible_wsl.sh"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERRO] Falha ao instalar Ansible" -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Ansible instalado" -ForegroundColor Green
} else {
    Write-Host "[OK] Ansible ja esta instalado" -ForegroundColor Green
}

# Executa deploy
Write-Host "[3/3] Executando deploy..." -ForegroundColor Gray
Write-Host ""

wsl -d $distro bash -c "cd $wslPath && bash deploy_wsl.sh"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Processo concluido!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

