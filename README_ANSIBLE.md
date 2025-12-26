# Deploy Ansible para abrir_site_proxy.go

Este playbook Ansible instala o Go, compila e executa o programa `abrir_site_proxy.go`.

## Pré-requisitos

1. Ansible instalado na máquina de controle:
   ```bash
   # Ubuntu/Debian
   sudo apt update && sudo apt install ansible -y
   
   # macOS
   brew install ansible
   
   # Windows (via WSL ou pip)
   pip install ansible
   ```

2. Acesso SSH ao servidor destino (chave SSH ou senha)

3. Python 3 instalado no servidor destino

## Configuração

1. **Edite o arquivo `inventory.yml`** com os dados do seu servidor:
   ```yaml
   servidor1:
     ansible_host: SEU_IP_AQUI
     ansible_user: seu_usuario
   ```

2. **Edite as variáveis no playbook** (`deploy_golang.yml`) se necessário:
   - `site_url`: URL do site (padrão: "7k.bet.br")
   - `num_threads`: Número de threads (padrão: "5")
   - `go_version`: Versão do Go (padrão: "1.21.5")

## Uso

### Executar o playbook completo:
```bash
ansible-playbook deploy_golang.yml
```

### Executar com variáveis customizadas:
```bash
ansible-playbook deploy_golang.yml -e "site_url=exemplo.com num_threads=10"
```

### Executar apenas para um host específico:
```bash
ansible-playbook deploy_golang.yml -l servidor1
```

### Verificar status sem executar (dry-run):
```bash
ansible-playbook deploy_golang.yml --check
```

## Verificar execução

Após o deploy, você pode verificar:

```bash
# Ver logs em tempo real
ansible servidor1 -a "tail -f /opt/abrir_site_proxy/output.log"

# Verificar se está rodando
ansible servidor1 -a "pgrep -f abrir_site_proxy"

# Parar a aplicação
ansible servidor1 -a "pkill -f abrir_site_proxy"
```

## Estrutura de arquivos no servidor

```
/opt/abrir_site_proxy/
├── abrir_site_proxy.go    # Código fonte
├── abrir_site_proxy        # Executável compilado
├── go.mod                  # Módulo Go
├── go.sum                  # Checksums das dependências
├── output.log              # Logs da execução
└── abrir_site_proxy.pid    # PID do processo
```

## Troubleshooting

### Erro de conexão SSH:
- Verifique se o servidor está acessível
- Teste a conexão: `ssh usuario@ip_servidor`
- Verifique as chaves SSH ou credenciais

### Erro ao baixar Go:
- Verifique conectividade com internet no servidor
- Verifique se a versão do Go especificada existe

### Erro ao compilar:
- Verifique se as dependências foram baixadas corretamente
- Execute manualmente: `cd /opt/abrir_site_proxy && go build abrir_site_proxy.go`

### Processo não inicia:
- Verifique os logs: `cat /opt/abrir_site_proxy/output.log`
- Verifique permissões: `ls -la /opt/abrir_site_proxy/abrir_site_proxy`

