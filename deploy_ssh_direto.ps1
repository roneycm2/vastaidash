# Deploy usando SSH direto (sem Ansible)
# Requer: ssh.exe no PATH (geralmente vem com Git ou OpenSSH)

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

$sshKey = "C:\Users\outros\.ssh\id_rsa"
$user = "root"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy via SSH Direto" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $sshKey)) {
    Write-Host "[ERRO] Chave SSH nao encontrada: $sshKey" -ForegroundColor Red
    exit 1
}

foreach ($server in $servers) {
    Write-Host "Processando $($server.name) ($($server.ip):$($server.port))..." -ForegroundColor Yellow
    
    # Testa conexão
    Write-Host "  [1/6] Testando conexao..." -ForegroundColor Gray
    $testResult = & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no -o ConnectTimeout=10 "$user@$($server.ip)" "echo conectado" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERRO] Nao foi possivel conectar: $testResult" -ForegroundColor Red
        Write-Host ""
        continue
    }
    Write-Host "  [OK] Conexao estabelecida" -ForegroundColor Green
    
    # Verifica Go
    Write-Host "  [2/6] Verificando Go..." -ForegroundColor Gray
    $goCheck = & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no "$user@$($server.ip)" "which go" 2>&1
    if ($goCheck -notmatch "/usr/local/go/bin/go") {
        Write-Host "  [INFO] Go nao encontrado, instalando..." -ForegroundColor Yellow
        & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no "$user@$($server.ip)" "cd /tmp && wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz && sudo rm -rf /usr/local/go && sudo tar -C /usr/local -xzf go1.21.5.linux-amd64.tar.gz && rm go1.21.5.linux-amd64.tar.gz && echo 'Go instalado'" 2>&1 | Out-Null
    }
    Write-Host "  [OK] Go verificado/instalado" -ForegroundColor Green
    
    # Cria diretório
    Write-Host "  [3/6] Criando diretorio..." -ForegroundColor Gray
    & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no "$user@$($server.ip)" "mkdir -p /opt/abrir_site_proxy && chmod 755 /opt/abrir_site_proxy" 2>&1 | Out-Null
    Write-Host "  [OK] Diretorio criado" -ForegroundColor Green
    
    # Copia arquivo via SCP
    Write-Host "  [4/6] Copiando arquivo..." -ForegroundColor Gray
    & scp.exe -i $sshKey -P $($server.port) -o StrictHostKeyChecking=no abrir_site_proxy.go "$user@$($server.ip):/opt/abrir_site_proxy/" 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Arquivo copiado" -ForegroundColor Green
    } else {
        Write-Host "  [ERRO] Falha ao copiar arquivo" -ForegroundColor Red
        Write-Host ""
        continue
    }
    
    # Compila e executa
    Write-Host "  [5/6] Compilando..." -ForegroundColor Gray
    $buildCmd = "cd /opt/abrir_site_proxy && export GOROOT=/usr/local/go && export GOPATH=/root/go && export PATH=`$PATH:/usr/local/go/bin:`$GOPATH/bin && go mod init abrir_site_proxy 2>/dev/null || true && go get github.com/enetx/g github.com/enetx/surf && go build -o abrir_site_proxy abrir_site_proxy.go && chmod +x abrir_site_proxy && echo 'Compilado'"
    $buildResult = & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no "$user@$($server.ip)" $buildCmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERRO] Falha na compilacao: $buildResult" -ForegroundColor Red
        Write-Host ""
        continue
    }
    Write-Host "  [OK] Compilado com sucesso" -ForegroundColor Green
    
    # Instala screen se necessário
    Write-Host "  [6/7] Verificando screen..." -ForegroundColor Gray
    $screenCheck = & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no "$user@$($server.ip)" "which screen || (apt-get update -qq 2>/dev/null && apt-get install -y -qq screen 2>/dev/null) || (yum install -y -q screen 2>/dev/null) || true" 2>&1
    Write-Host "  [OK] Screen verificado/instalado" -ForegroundColor Green
    
    # Para processo antigo se existir
    Write-Host "  [7/8] Parando processo antigo..." -ForegroundColor Gray
    & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no "$user@$($server.ip)" "pkill -f abrir_site_proxy || true; screen -X -S abrir_site_proxy quit || true" 2>&1 | Out-Null
    Start-Sleep -Milliseconds 500
    
    # Executa usando screen com 2000 threads
    Write-Host "  [8/8] Executando com screen (2000 threads)..." -ForegroundColor Gray
    $runCmd = "cd /opt/abrir_site_proxy && screen -dmS abrir_site_proxy bash -c './abrir_site_proxy 7k.bet.br 2000 > output.log 2>&1'"
    $runResult = & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no "$user@$($server.ip)" $runCmd 2>&1
    
    # Verifica se está rodando
    Start-Sleep -Seconds 2
    $checkCmd = "screen -list | grep abrir_site_proxy && pgrep -f abrir_site_proxy && echo 'OK'"
    $checkResult = & ssh.exe -i $sshKey -p $($server.port) -o StrictHostKeyChecking=no "$user@$($server.ip)" $checkCmd 2>&1
    
    if ($checkResult -match "OK") {
        Write-Host "  [OK] Programa rodando em screen com 2000 threads!" -ForegroundColor Green
    } else {
        Write-Host "  [AVISO] Verifique manualmente: screen -r abrir_site_proxy" -ForegroundColor Yellow
        Write-Host "  Output: $checkResult" -ForegroundColor Gray
    }
    
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Deploy concluido!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan

