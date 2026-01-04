# 🚀 Mindpulse

**Plataforma SaaS Multi-tenant para Gestão de Equipes**

Sistema completo para gerenciamento de treinamentos, checklists e feedback de colaboradores, com foco em gamificação e produtividade.

![Django](https://img.shields.io/badge/Django-5.1.4-092E20?style=for-the-badge&logo=django)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)

---

## 📋 Funcionalidades

### 🏢 Multi-tenancy
- Isolamento completo de dados por empresa (`company_id`)
- Cada empresa tem seus próprios usuários, treinamentos, checklists e feedbacks

### 👥 Níveis de Acesso
| Nível | Permissões |
|-------|------------|
| **Admin Master** | Acesso global a todas as empresas, gestão completa |
| **Gestor** | Gerencia conteúdo da sua unidade |
| **Colaborador** | Visualiza e executa tarefas da sua empresa |

### 🎬 Treinamentos
- Upload de vídeos com tracking de progresso
- Sistema de gamificação com pontos e badges
- Controle de conclusão automático (90% assistido)

### 📋 Checklists
- Frequências configuráveis: Diário, Semanal, Quinzenal, Mensal
- Sistema de `period_key` para controle de execução
- Pontuação por conclusão

### 💬 Feedback
- Seletor de sentimento com emojis
- Categorização (Sugestão, Problema, Elogio, etc.)
- Sistema de comentários e respostas

### 📊 Dashboards
- **Admin Master**: Visão comparativa global entre lojas
- **Gestor**: Ranking de colaboradores e status do dia
- **Colaborador**: Metas e progresso pessoal

---

## 🎨 Design

- **Dark Mode** com paleta oficial:
  - Background: `#1A1A1A`
  - Brand (Vermelho): `#F83531`
  - Texto: `#FFFFFF`
- UI moderna com Tailwind CSS
- Animações suaves e micro-interações

---

## 🛠️ Instalação

### Requisitos
- Python 3.11+
- pip

### Setup Rápido (Windows)

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/mindpulse.git
cd mindpulse

# Execute o setup automático
setup.bat
```

### Setup Manual

```bash
# Crie o ambiente virtual
python -m venv venv

# Ative o ambiente
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instale as dependências
pip install -r requirements.txt

# Crie o arquivo .env
cp env.example .env

# Execute as migrações
python manage.py migrate

# Crie um superusuário
python manage.py createsuperuser

# Inicie o servidor
python manage.py runserver
```

Acesse: http://127.0.0.1:8000

---

## 📁 Estrutura do Projeto

```
mindpulse/
├── apps/
│   ├── accounts/      # Autenticação e usuários
│   ├── checklists/    # Módulo de checklists
│   ├── core/          # Models base, middleware, decorators
│   ├── feedback/      # Sistema de feedback
│   └── trainings/     # Módulo de treinamentos
├── templates/         # Templates HTML
├── static/            # Arquivos estáticos
├── mindpulse/         # Configurações Django
└── requirements.txt   # Dependências
```

---

## 🔧 Configuração

### Variáveis de Ambiente (.env)

```env
DEBUG=True
SECRET_KEY=sua-chave-secreta
USE_SQLITE=True

# Para produção com PostgreSQL
# USE_SQLITE=False
# DB_NAME=mindpulse_db
# DB_USER=postgres
# DB_PASSWORD=sua-senha
# DB_HOST=localhost
# DB_PORT=5432

# Google Cloud Storage (opcional)
# USE_GCS=True
# GCS_BUCKET_NAME=seu-bucket
# GCS_PROJECT_ID=seu-projeto
```

---

## 🚀 Deploy

### Google Cloud Run (Recomendado)

1. Configure o Google Cloud SQL (PostgreSQL)
2. Configure o Google Cloud Storage para mídia
3. Use o Dockerfile incluído
4. Configure as variáveis de ambiente no Cloud Run

---

## 📝 Licença

Este projeto é proprietário. Todos os direitos reservados.

---

## 👨‍💻 Desenvolvido por

**Mindpulse Team** - 2024

---

*Gestão inteligente de equipes* ⚡

