# Script para fazer deploy manual nos servidores
# Executa os comandos do playbook individualmente

$servers = @(
    @{name="servidor1"; ip="184.191.105.145"; port="21503"},
    @{name="servidor2"; ip="77.104.167.149"; port="48172"},
    @{name="servidor3"; ip="199.68.217.31"; port="20320"},
    @{name="servidor4"; ip="69.48.204.144"; port="41744"},
    @{name="servidor5"; ip="24.124.32.70"; port="48267"},
    @{name="servidor6"; ip="142.170.89.112"; port="23633"},
    @{name="servidor7"; ip="199.68.217.31"; port="16090"},
    @{name="servidor8"; ip="83.108.94.163"; port="41689"},
    @{name="servidor9"; ip="77.104.167.148"; port="41108"}
)

$ansiblePath = "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts"
if (Test-Path $ansiblePath) {
    $env:PATH = "$ansiblePath;$env:PATH"
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy Manual - Servidores Ansible" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

foreach ($server in $servers) {
    Write-Host "Processando $($server.name) ($($server.ip):$($server.port))..." -ForegroundColor Yellow
    
    # Testa conexão
    Write-Host "  [1/6] Testando conexao..." -ForegroundColor Gray
    $pingResult = ansible $server.name -m ping -i inventory.yml 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERRO] Nao foi possivel conectar ao servidor" -ForegroundColor Red
        Write-Host ""
        continue
    }
    Write-Host "  [OK] Conexao estabelecida" -ForegroundColor Green
    
    # Verifica se Go está instalado
    Write-Host "  [2/6] Verificando Go..." -ForegroundColor Gray
    $goCheck = ansible $server.name -m shell -a "which go" -i inventory.yml 2>&1
    if ($goCheck -notmatch "/usr/local/go/bin/go") {
        Write-Host "  [INFO] Go nao encontrado, sera instalado no proximo passo" -ForegroundColor Yellow
    } else {
        Write-Host "  [OK] Go ja esta instalado" -ForegroundColor Green
    }
    
    # Instala Go (se necessário)
    Write-Host "  [3/6] Instalando/Atualizando Go..." -ForegroundColor Gray
    $goInstall = ansible $server.name -m shell -a "cd /tmp && wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz && sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz && rm go1.21.5.linux-amd64.tar.gz && echo 'Go instalado'" -i inventory.yml 2>&1
    Write-Host "  [OK] Go instalado/atualizado" -ForegroundColor Green
    
    # Cria diretório
    Write-Host "  [4/6] Criando diretorio da aplicacao..." -ForegroundColor Gray
    ansible $server.name -m file -a "path=/opt/abrir_site_proxy state=directory mode=0755" -i inventory.yml | Out-Null
    Write-Host "  [OK] Diretorio criado" -ForegroundColor Green
    
    # Copia arquivo
    Write-Host "  [5/6] Copiando arquivo abrir_site_proxy.go..." -ForegroundColor Gray
    ansible $server.name -m copy -a "src=abrir_site_proxy.go dest=/opt/abrir_site_proxy/abrir_site_proxy.go mode=0644" -i inventory.yml | Out-Null
    Write-Host "  [OK] Arquivo copiado" -ForegroundColor Green
    
    # Compila e executa
    Write-Host "  [6/6] Compilando e executando..." -ForegroundColor Gray
    $deployCmd = 'cd /opt/abrir_site_proxy && export GOROOT=/usr/local/go && export GOPATH=/root/go && export PATH=$PATH:/usr/local/go/bin:$GOPATH/bin && go mod init abrir_site_proxy 2>/dev/null || true && go get github.com/enetx/g github.com/enetx/surf && go build -o abrir_site_proxy abrir_site_proxy.go && chmod +x abrir_site_proxy && pkill -f abrir_site_proxy || true && nohup ./abrir_site_proxy 7k.bet.br 5 > output.log 2>&1 & echo "Deploy concluido"'
    
    $deployResult = ansible $server.name -m shell -a $deployCmd -i inventory.yml 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Deploy concluido com sucesso!" -ForegroundColor Green
    } else {
        Write-Host "  [ERRO] Falha no deploy" -ForegroundColor Red
        Write-Host $deployResult -ForegroundColor Red
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy concluido!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

