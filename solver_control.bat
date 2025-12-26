@echo off
:: Solver Control - Comandos rápidos
:: ==================================

if "%1"=="" goto help
if "%1"=="deploy" goto deploy
if "%1"=="kill" goto kill
if "%1"=="status" goto status
if "%1"=="fetch" goto fetch
if "%1"=="list" goto list
if "%1"=="local" goto local

:help
echo.
echo ============================================
echo   SOLVER CONTROL - Comandos Rapidos
echo ============================================
echo.
echo Uso: solver_control.bat [comando] [opcoes]
echo.
echo Comandos:
echo   deploy [tabs]  - Deploy solver em todas as maquinas (default: 3 tabs)
echo   kill           - Mata solver em todas as maquinas
echo   status         - Mostra status de todas as maquinas
echo   fetch          - Baixa tokens de todas as maquinas
echo   list           - Lista maquinas disponiveis
echo   local [tabs]   - Roda solver local (default: 5 tabs)
echo.
echo Exemplos:
echo   solver_control.bat deploy 5
echo   solver_control.bat kill
echo   solver_control.bat local 3
echo.
goto end

:deploy
set TABS=3
if not "%2"=="" set TABS=%2
echo Iniciando deploy com %TABS% tabs por maquina...
python deploy_solver_ssh.py --tabs %TABS%
goto end

:kill
echo Matando processos em todas as maquinas...
python deploy_solver_ssh.py --kill
goto end

:status
echo Verificando status...
python deploy_solver_ssh.py --status
goto end

:fetch
echo Baixando tokens...
python deploy_solver_ssh.py --fetch
goto end

:list
echo Listando maquinas...
python deploy_solver_ssh.py --list
goto end

:local
set TABS=5
if not "%2"=="" set TABS=%2
echo Iniciando solver local com %TABS% tabs...
python turnstile_remote_solver.py --tabs %TABS% --visible --skip-install
goto end

:end










