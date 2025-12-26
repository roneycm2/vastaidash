@echo off
echo ========================================
echo   Ansible Dashboard - Iniciando...
echo ========================================
echo.

REM Adiciona o diretorio de scripts do Python ao PATH
set PATH=%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scripts;%PATH%

REM Executa o dashboard
python dashboard_ansible.py

pause

