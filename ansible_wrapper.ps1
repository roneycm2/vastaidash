# Wrapper script para executar Ansible no Windows
# Adiciona o diretório de scripts do Python ao PATH temporariamente

$pythonScriptsPath = "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts"

if (Test-Path $pythonScriptsPath) {
    $env:PATH = "$pythonScriptsPath;$env:PATH"
    
    # Executa o comando passado como argumento
    if ($args.Count -gt 0) {
        & $args[0] $args[1..($args.Count-1)]
    } else {
        Write-Host "Uso: .\ansible_wrapper.ps1 <comando> [argumentos]"
        Write-Host "Exemplo: .\ansible_wrapper.ps1 ansible-playbook deploy_golang.yml"
    }
} else {
    Write-Host "Erro: Diretório de scripts do Python não encontrado!"
    Write-Host "Caminho esperado: $pythonScriptsPath"
}

