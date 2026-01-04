@echo off
chcp 65001 > nul

echo =============================================
echo    MINDPULSE - INICIANDO SERVIDOR LOCAL
echo =============================================

echo [1/3] Ativando ambiente virtual...
call venv\Scripts\activate.bat

echo [2/3] Verificando configuracoes...
python -c "import django; print(f'Django {django.get_version()} OK!')" 2>nul
if errorlevel 1 (
    echo Django nao encontrado! Instalando dependencias...
    pip install -r requirements.txt
)

echo [3/3] Iniciando servidor local...
echo.
echo =============================================
echo    SERVIDOR RODANDO!
echo    Acesse: http://127.0.0.1:8000
echo    ou: http://localhost:8000
echo    Pressione Ctrl+C para parar
echo =============================================
echo.
python manage.py runserver 127.0.0.1:8000

