# Instalação do Ansible no Windows

## Status da Instalação

✅ **Ansible-core 2.14.18 instalado com sucesso**

## Patches Aplicados

Foram aplicados os seguintes patches para compatibilidade com Windows:

1. **Patch em `ansible/cli/__init__.py`**:
   - Adicionada verificação para `os.get_blocking()` (não disponível no Windows)
   - Permitido encoding `cp1252` no Windows (padrão do Windows)

2. **Módulos stub criados**:
   - `fcntl.py` - Stub para funcionalidades de file locking
   - `termios.py` - Stub para controle de terminal

## Limitações Conhecidas

⚠️ **O Ansible no Windows tem limitações significativas:**

- Não suporta `fork()` (processo de criação de processos filhos)
- Alguns módulos podem não funcionar corretamente
- Recomendado para uso básico ou desenvolvimento

## Soluções Recomendadas

### Opção 1: Usar WSL (Recomendado)

1. Instale o WSL:
   ```powershell
   wsl --install
   ```

2. No WSL, instale o Ansible:
   ```bash
   sudo apt update
   sudo apt install ansible -y
   ```

3. Execute os playbooks do WSL:
   ```bash
   ansible-playbook deploy_golang.yml
   ```

### Opção 2: Executar em Servidor Linux Remoto

O playbook `deploy_golang.yml` foi criado para executar em servidores Linux remotos. Configure o `inventory.yml` com seus servidores e execute:

```powershell
ansible-playbook deploy_golang.yml
```

### Opção 3: Usar Ansible no Windows (Limitado)

Para uso básico no Windows:

1. Configure o PATH (execute `configurar_ansible_windows.ps1`):
   ```powershell
   .\configurar_ansible_windows.ps1
   ```

2. Teste a instalação:
   ```powershell
   ansible-playbook --version
   ```

3. Execute playbooks simples (que não usem fork):
   ```powershell
   ansible-playbook deploy_golang.yml
   ```

## Verificação

Para verificar se o Ansible está funcionando:

```powershell
# Adicionar ao PATH da sessão atual
$env:PATH = "$env:LOCALAPPDATA\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts;$env:PATH"

# Verificar versão
ansible-playbook --version
```

## Arquivos Criados

- `deploy_golang.yml` - Playbook para instalar Go e executar o programa
- `inventory.yml` - Inventário de servidores
- `ansible.cfg` - Configuração do Ansible
- `configurar_ansible_windows.ps1` - Script de configuração
- `ansible_wrapper.ps1` - Wrapper para executar Ansible

## Próximos Passos

1. Configure o `inventory.yml` com seus servidores
2. Execute o playbook:
   ```powershell
   ansible-playbook deploy_golang.yml -e "site_url=7k.bet.br num_threads=10"
   ```

## Troubleshooting

### Erro: "cannot find context for 'fork'"
- **Causa**: Windows não suporta fork()
- **Solução**: Use WSL ou execute em servidor Linux remoto

### Erro: "No module named 'fcntl'"
- **Causa**: Módulo stub não foi criado
- **Solução**: Verifique se `fcntl.py` existe em `site-packages`

### Erro: "locale encoding to be UTF-8"
- **Causa**: Encoding do Windows (cp1252)
- **Solução**: Patch já aplicado, mas pode precisar de ajustes

