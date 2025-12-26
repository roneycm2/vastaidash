# Script para configurar Ansible no Windows
# Adiciona o diretório de scripts do Python ao PATH permanentemente

$pythonScriptsPath = "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts"

Write-Host "Configurando Ansible no Windows..." -ForegroundColor Cyan

# Adicionar ao PATH do usuário
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$pythonScriptsPath*") {
    $newPath = "$currentPath;$pythonScriptsPath"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "OK: Diretorio de scripts do Python adicionado ao PATH do usuario" -ForegroundColor Green
} else {
    Write-Host "INFO: Diretorio de scripts do Python ja esta no PATH" -ForegroundColor Yellow
}

# Adicionar ao PATH da sessão atual
$env:PATH = "$pythonScriptsPath;$env:PATH"

Write-Host ""
Write-Host "Informacoes importantes:" -ForegroundColor Yellow
Write-Host "   - Ansible foi instalado com patches para Windows" -ForegroundColor White
Write-Host "   - O Ansible no Windows tem limitacoes (nao suporta 'fork')" -ForegroundColor White
Write-Host "   - Para uso completo, recomenda-se:" -ForegroundColor White
Write-Host "     * Usar WSL (Windows Subsystem for Linux)" -ForegroundColor Cyan
Write-Host "     * Ou executar playbooks em servidores Linux remotos" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para usar o Ansible, execute:" -ForegroundColor Green
Write-Host "   ansible-playbook deploy_golang.yml" -ForegroundColor White
Write-Host ""
Write-Host "NOTA: Alguns recursos podem nao funcionar no Windows nativo" -ForegroundColor Red

