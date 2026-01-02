@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo =============================================
echo    MINDPULSE - SETUP AUTOMATICO
echo =============================================
echo.

echo [1/7] Removendo venv antigo...
if exist venv rmdir /s /q venv

echo [2/7] Criando arquivo .env...
(
echo SECRET_KEY=django-insecure-mindpulse-dev-key-2024
echo DEBUG=True
echo ALLOWED_HOSTS=localhost,127.0.0.1
echo USE_SQLITE=True
echo USE_GCS=False
) > .env

echo [3/7] Criando novo ambiente virtual...
python -m venv venv

echo [4/7] Ativando venv...
call venv\Scripts\activate.bat

echo [5/7] Instalando dependencias...
pip install -r requirements.txt

echo [6/7] Criando migracoes...
python manage.py makemigrations core accounts trainings checklists feedback

echo [7/7] Aplicando migracoes...
python manage.py migrate

echo.
echo =============================================
echo    INSTALACAO CONCLUIDA COM SUCESSO!
echo =============================================
echo.
echo Agora vamos criar o superusuario...
echo.
python manage.py createsuperuser

echo.
echo =============================================
echo    INICIANDO SERVIDOR...
echo =============================================
echo.
echo Acesse: http://127.0.0.1:8000
echo.
python manage.py runserver
