# 🚀 Dashboard Ansible - Monitoramento de Servidores

Dashboard web para monitorar o status dos servidores e o deploy do código via Ansible.

## 📋 Funcionalidades

- ✅ **Monitoramento de Conexão**: Verifica se consegue acessar cada servidor via SSH
- 📦 **Status de Deploy**: Verifica se o código foi copiado e compilado
- 🔄 **Status de Processo**: Verifica se o programa está rodando
- 📊 **Estatísticas em Tempo Real**: Mostra resumo de todos os servidores
- 🎯 **Execução de Playbook**: Botão para executar o deploy diretamente do dashboard

## 🚀 Como Usar

### 1. Iniciar o Dashboard

```powershell
python dashboard_ansible.py
```

Ou use o script batch:
```cmd
executar_dashboard_ansible.bat
```

### 2. Acessar o Dashboard

Abra seu navegador em:
```
http://localhost:5000
```

## 📊 O que o Dashboard Mostra

### Estatísticas Gerais
- **Total de Servidores**: Quantidade total configurada
- **Acessíveis**: Servidores com conexão SSH funcionando
- **Código Deployado**: Servidores onde o código foi copiado
- **Processos Rodando**: Servidores onde o programa está executando

### Cards dos Servidores
Cada servidor mostra:
- **Nome do Servidor**: Ex: servidor1, servidor2, etc.
- **IP e Porta**: Endereço e porta SSH
- **Status de Conexão**: ✅ Acessível ou ❌ Inacessível
- **Código Copiado**: ✅ Sim ou ❌ Não
- **Processo Rodando**: ✅ Sim ou ❌ Não
- **Última Verificação**: Timestamp da última checagem

## 🔄 Atualização Automática

O dashboard atualiza automaticamente:
- **Status dos servidores**: A cada 30 segundos
- **Interface web**: A cada 5 segundos

## 🎯 Botões de Ação

### 🔄 Atualizar
Força uma atualização imediata do status de todos os servidores.

### ▶️ Executar Deploy
Executa o playbook `deploy_golang.yml` em todos os servidores acessíveis.

## 📁 Arquivos Necessários

O dashboard precisa dos seguintes arquivos no mesmo diretório:
- `inventory.yml` - Configuração dos servidores
- `deploy_golang.yml` - Playbook Ansible
- `ansible.cfg` - Configuração do Ansible
- `abrir_site_proxy.go` - Código fonte a ser deployado

## 🔧 Requisitos

- Python 3.9+
- Flask (`pip install flask`)
- PyYAML (`pip install pyyaml`)
- Ansible instalado e configurado

## 🐛 Troubleshooting

### Dashboard não inicia
- Verifique se o Flask está instalado: `pip install flask`
- Verifique se o PyYAML está instalado: `pip install pyyaml`

### Servidores aparecem como inacessíveis
- Verifique se a chave SSH está configurada corretamente
- Teste a conexão manualmente: `ansible servidor1 -m ping`
- Verifique se as portas SSH estão corretas no `inventory.yml`

### Código não aparece como deployado
- Execute o playbook: `ansible-playbook deploy_golang.yml`
- Verifique se o playbook foi executado com sucesso
- Aguarde alguns segundos para o dashboard atualizar

## 📝 Notas

- O dashboard verifica o status automaticamente em background
- A primeira verificação pode demorar alguns segundos
- Servidores inacessíveis não terão verificação de código deployado

