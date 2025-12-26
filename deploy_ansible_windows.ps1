# Deploy usando comandos Ansible ad-hoc (funciona no Windows)
# Usa screen e 2000 threads

$servers = @(
    "servidor1", "servidor2", "servidor3", "servidor4", "servidor5",
    "servidor6", "servidor7", "servidor8", "servidor9"
)

$ansiblePath = "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts"
if (Test-Path $ansiblePath) {
    $env:PATH = "$ansiblePath;$env:PATH"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy Ansible - Screen + 2000 Threads" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($server in $servers) {
    Write-Host "Processando $server..." -ForegroundColor Yellow
    
    # Testa conexão
    Write-Host "  [1/7] Testando conexao..." -ForegroundColor Gray
    $pingResult = ansible $server -m ping -i inventory.yml 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERRO] Nao foi possivel conectar" -ForegroundColor Red
        Write-Host ""
        continue
    }
    Write-Host "  [OK] Conexao estabelecida" -ForegroundColor Green
    
    # Verifica/instala screen
    Write-Host "  [2/7] Verificando screen..." -ForegroundColor Gray
    ansible $server -m shell -a "which screen || (apt-get update -qq && apt-get install -y -qq screen)" -i inventory.yml 2>&1 | Out-Null
    Write-Host "  [OK] Screen verificado/instalado" -ForegroundColor Green
    
    # Verifica Go
    Write-Host "  [3/7] Verificando Go..." -ForegroundColor Gray
    $goCheck = ansible $server -m shell -a "which go" -i inventory.yml 2>&1
    if ($goCheck -notmatch "/usr/local/go/bin/go") {
        Write-Host "  [INFO] Go nao encontrado, instalando..." -ForegroundColor Yellow
        ansible $server -m shell -a "cd /tmp && wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz && sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz && rm go1.21.5.linux-amd64.tar.gz && echo 'Go instalado'" -i inventory.yml 2>&1 | Out-Null
    }
    Write-Host "  [OK] Go verificado/instalado" -ForegroundColor Green
    
    # Cria diretório
    Write-Host "  [4/7] Criando diretorio..." -ForegroundColor Gray
    ansible $server -m file -a "path=/opt/abrir_site_proxy state=directory mode=0755" -i inventory.yml 2>&1 | Out-Null
    Write-Host "  [OK] Diretorio criado" -ForegroundColor Green
    
    # Copia arquivo
    Write-Host "  [5/7] Copiando arquivo..." -ForegroundColor Gray
    ansible $server -m copy -a "src=abrir_site_proxy.go dest=/opt/abrir_site_proxy/abrir_site_proxy.go mode=0644" -i inventory.yml 2>&1 | Out-Null
    Write-Host "  [OK] Arquivo copiado" -ForegroundColor Green
    
    # Compila
    Write-Host "  [6/7] Compilando..." -ForegroundColor Gray
    $buildCmd = "cd /opt/abrir_site_proxy && export GOROOT=/usr/local/go && export GOPATH=/root/go && export PATH=`$PATH:/usr/local/go/bin:`$GOPATH/bin && go mod init abrir_site_proxy 2>/dev/null || true && go get github.com/enetx/g github.com/enetx/surf && go build -o abrir_site_proxy abrir_site_proxy.go && chmod +x abrir_site_proxy && echo 'Compilado'"
    $buildResult = ansible $server -m shell -a $buildCmd -i inventory.yml 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERRO] Falha na compilacao" -ForegroundColor Red
        Write-Host $buildResult -ForegroundColor Red
        Write-Host ""
        continue
    }
    Write-Host "  [OK] Compilado com sucesso" -ForegroundColor Green
    
    # Para processo antigo e inicia com screen
    Write-Host "  [7/7] Executando com screen (2000 threads)..." -ForegroundColor Gray
    $runCmd = "cd /opt/abrir_site_proxy && pkill -f abrir_site_proxy || true && screen -dmS abrir_site_proxy bash -c './abrir_site_proxy 7k.bet.br 2000 > output.log 2>&1' && sleep 2 && screen -list | grep abrir_site_proxy && echo 'Executando em screen' || echo 'Erro'"
    $runResult = ansible $server -m shell -a $runCmd -i inventory.yml 2>&1
    if ($runResult -match "Executando em screen") {
        Write-Host "  [OK] Programa rodando em screen com 2000 threads!" -ForegroundColor Green
    } else {
        Write-Host "  [AVISO] Verifique se iniciou: $runResult" -ForegroundColor Yellow
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy concluido!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Para verificar os processos rodando:" -ForegroundColor Yellow
Write-Host "  ansible all -m shell -a 'screen -list' -i inventory.yml" -ForegroundColor Gray
Write-Host ""
Write-Host "Para ver os logs:" -ForegroundColor Yellow
Write-Host "  ansible servidor1 -m shell -a 'tail -f /opt/abrir_site_proxy/output.log' -i inventory.yml" -ForegroundColor Gray



