@echo off
echo.
echo =========================================================
echo   SOLVER DEPLOY DASHBOARD
echo =========================================================
echo.
echo Iniciando dashboard...
echo Acesse: http://localhost:5020
echo.
echo Pressione Ctrl+C para encerrar
echo.
echo =========================================================
echo.

cd /d "%~dp0"
python dashboard_solver_deploy.py

pause










