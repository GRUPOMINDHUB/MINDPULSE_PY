# 🚀 Mindpulse - Plataforma de Gestão de Equipes

**Versão:** 1.0  
**Data de Release:** Janeiro 2026  
**Desenvolvido por:** GRUPOMINDHUB

Sistema completo de gestão de equipes, treinamentos, checklists e feedbacks com arquitetura **multi-tenant** robusta e interface moderna.

---

## 📚 Índice

- [Visão Geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades-principais)
- [Arquitetura](#-arquitetura-e-tecnologias)
- [Instalação](#-instalação)
- [Configuração](#-configuração)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Segurança Multi-Tenant](#-segurança-multi-tenant)
- [Desenvolvimento](#-desenvolvimento)
- [Deploy](#-deploy)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Visão Geral

O Mindpulse é uma plataforma SaaS multi-tenant desenvolvida em Django para gestão operacional de equipes, com foco em restaurantes e operações de varejo. O sistema oferece:

- **Gestão de Colaboradores** com sistema de ranking e gamificação
- **Treinamentos Interativos** com vídeos e quizzes
- **Checklists Operacionais** com frequências configuráveis
- **Sistema de Feedback** com análise de sentimento
- **Relatórios Executivos** em PDF (formato Landscape profissional)
- **Interface Responsiva** com Dark/Light Mode

---

## ✨ Funcionalidades Principais

### 👥 Gestão de Usuários e Empresas

- **Sistema Multi-Tenant:** Isolamento completo de dados por empresa
- **Três Níveis de Acesso:**
  - **Admin Master:** Controle total, visualiza todas as empresas
  - **Gestor:** Gerencia sua unidade/empresa
  - **Colaborador:** Acesso aos seus treinamentos e checklists
- **Onboarding Automático:** E-mails automáticos com credenciais ao cadastrar novo colaborador
- **Sistema de Advertências:** Disciplina com tipos (Oral, Escrita, Suspensão)
- **Geração Automática de Matrícula:** Formato `EMPRESA-ANO-SEQUENCIAL` (ex: `DLU-2026-0001`)

### 📚 Treinamentos

- Criação e gerenciamento de treinamentos com vídeos e quizzes
- Upload de vídeos com thumbnails automáticos
- Quizzes com múltipla escolha e pontuação
- Progresso individual por colaborador
- Sistema de recompensas (pontos e medalhas)
- Ordenação via drag-and-drop

### ✅ Checklists Operacionais

- Checklists com frequências: Diária, Semanal, Mensal
- Tarefas com pontos e prazos
- Atribuição individual ou coletiva
- Sistema de conclusão por período
- Alertas automáticos de atraso
- Lógica anti-false-positive: Checklist completo nunca aparece como atrasado

### 💬 Sistema de Feedback

- Tickets de feedback com thread de conversa contínua
- Análise de sentimento (Great, Good, Neutral, Bad, Sad)
- Feedback anônimo opcional
- Interface estilo chat para diálogo entre colaborador e gestor
- Histórico completo de mensagens

### 📊 Relatórios Inteligentes

#### Relatório Individual
- Perfil completo do colaborador
- Ranking e pontos
- Checklists (período e totais)
- Treinamentos (progresso detalhado)
- Quizzes (média e tentativas)
- Histórico de advertências

#### Relatório Coletivo (Geral da Loja)
- **KPIs Consolidados:** Médias de Checklists, Treinamentos, Quizzes, Advertências
- **Top 3 (Pódio):** Melhores colaboradores por pontos
- **Índice de Atenção:** Top 3 com mais problemas
- **Matriz de Performance:** Tabela completa com barras de progresso
- **PDF Executivo:** Exportação em A4 Landscape, design profissional

### 🎨 Interface Moderna

- **Design Responsivo:** Mobile-first, funciona perfeitamente em tablets e smartphones
- **Dual-Theme:** Dark Mode e Light Mode com persistência
- **Slim UI:** Interface limpa e executiva
- **Navegação Intuitiva:** Sidebar responsiva
- **Gráficos Interativos:** Chart.js para visualizações

---

## 🏗️ Arquitetura e Tecnologias

### Stack Tecnológico

- **Backend:** Django 5.1.4 (Python 3.10+)
- **Frontend:** Tailwind CSS 3.x (via CDN)
- **Banco de Dados:**
  - Desenvolvimento: SQLite
  - Produção: PostgreSQL (Google Cloud SQL)
- **PDF:** xhtml2pdf 0.2.17
- **Processamento de Mídia:** Pillow, moviepy
- **E-mail:** SMTP (Gmail, Outlook, SendGrid, Mailgun)
- **Storage:** Google Cloud Storage (opcional) ou local

### Princípios de Arquitetura

- **SOLID Principles:** Código modular e extensível
- **DRY (Don't Repeat Yourself):** Funções utilitárias reutilizáveis
- **Service Layer:** Lógicas complexas isoladas em `services.py`
- **Type Hints:** Tipagem estática para melhor DX
- **Multi-Tenant:** Isolamento de dados por empresa garantido em todas as views

---

## 📦 Instalação

### Pré-requisitos

- Python 3.10 ou superior
- pip
- Git
- (Opcional) PostgreSQL para produção

### Passo a Passo

#### 1. Clone o Repositório

```bash
git clone https://github.com/GRUPOMINDHUB/MINDPULSE_PY.git
cd MINDPULSE_PY
```

#### 2. Crie e Ative Ambiente Virtual

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### 3. Instale Dependências

```bash
pip install -r requirements.txt
```

#### 4. Configure Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto (baseado no `env.example`):

```env
# Django
SECRET_KEY=sua-chave-secreta-aqui
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite para desenvolvimento)
USE_SQLITE=True

# Database PostgreSQL (para produção)
# USE_SQLITE=False
# DB_NAME=mindpulse_db
# DB_USER=postgres
# DB_PASSWORD=sua-senha
# DB_HOST=127.0.0.1
# DB_PORT=5432

# E-mail SMTP
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=sua-senha-de-app
DEFAULT_FROM_EMAIL=Mindpulse <seu-email@gmail.com>
SITE_URL=http://localhost:8000

# Google Cloud Storage (opcional)
USE_GCS=False
# GCS_BUCKET_NAME=seu-bucket
# GCS_PROJECT_ID=seu-project-id
```

#### 5. Execute Migrações

```bash
python manage.py migrate
```

#### 6. Crie Superusuário

```bash
python manage.py createsuperuser
```

#### 7. Execute o Servidor

```bash
python manage.py runserver
```

#### 8. Acesse o Sistema

```
http://127.0.0.1:8000
```

---

## ⚙️ Configuração

### Variáveis de Ambiente Detalhadas

#### Django Core

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `SECRET_KEY` | Chave secreta do Django (gere com `python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`) | `django-insecure-dev-key-change-in-production` |
| `DEBUG` | Modo debug (False em produção) | `True` |
| `ALLOWED_HOSTS` | Hosts permitidos (separados por vírgula) | `localhost,127.0.0.1` |

#### Banco de Dados

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `USE_SQLITE` | Usar SQLite (True) ou PostgreSQL (False) | `True` |
| `DB_NAME` | Nome do banco PostgreSQL | `mindpulse_db` |
| `DB_USER` | Usuário do PostgreSQL | `postgres` |
| `DB_PASSWORD` | Senha do PostgreSQL | - |
| `DB_HOST` | Host do PostgreSQL | `127.0.0.1` |
| `DB_PORT` | Porta do PostgreSQL | `5432` |

#### E-mail SMTP

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `EMAIL_HOST` | Servidor SMTP | `smtp.gmail.com` |
| `EMAIL_PORT` | Porta SMTP (587 para TLS, 465 para SSL) | `587` |
| `EMAIL_USE_TLS` | Usar TLS (porta 587) | `True` |
| `EMAIL_USE_SSL` | Usar SSL (porta 465) | `False` |
| `EMAIL_HOST_USER` | E-mail do remetente | - |
| `EMAIL_HOST_PASSWORD` | Senha do e-mail (ou Senha de App para Gmail) | - |
| `DEFAULT_FROM_EMAIL` | E-mail padrão (deve usar mesmo domínio do EMAIL_HOST_USER) | `Mindpulse <noreply@mindpulse.com.br>` |
| `SITE_URL` | URL base do site (para links em e-mails) | `http://localhost:8000` |

**Importante para Gmail:**
1. Ative 2FA na sua conta Google
2. Gere uma "Senha de App": https://myaccount.google.com/apppasswords
3. Use essa senha (não a senha normal) no `EMAIL_HOST_PASSWORD`

#### Google Cloud Storage (Opcional)

| Variável | Descrição |
|----------|-----------|
| `USE_GCS` | Ativar Google Cloud Storage | `False` |
| `GCS_BUCKET_NAME` | Nome do bucket |
| `GCS_PROJECT_ID` | ID do projeto |
| `GOOGLE_APPLICATION_CREDENTIALS` | Caminho para credenciais JSON |

---

## 📁 Estrutura do Projeto

```
MINDPULSE_PY/
│
├── apps/                          # Apps Django
│   ├── accounts/                  # Autenticação, usuários, advertências
│   │   ├── management/
│   │   │   └── commands/          # Comandos Django customizados
│   │   │       └── test_email.py  # Teste de SMTP
│   │   ├── models.py              # User, UserCompany, Warning
│   │   ├── views.py               # Views de autenticação e gestão
│   │   ├── forms.py               # Formulários (Login, Collaborator, etc)
│   │   ├── services.py            # Serviços de e-mail
│   │   ├── signals.py             # Signals de onboarding
│   │   └── urls.py                # URLs de accounts
│   │
│   ├── checklists/                # Checklists e tarefas
│   │   ├── models.py              # Checklist, Task, TaskDone, ChecklistCompletion
│   │   ├── views.py               # Views de listagem e execução
│   │   └── templatetags/          # Template tags customizados
│   │
│   ├── core/                      # Core: empresas, relatórios, dashboards
│   │   ├── models.py              # Company, Role
│   │   ├── views.py               # Views de dashboard e gestão
│   │   ├── views_reports.py       # Views de relatórios (legado)
│   │   ├── reports.py             # Lógica de extração de dados de relatórios
│   │   ├── utils.py               # Funções utilitárias (sanitização, helpers)
│   │   ├── decorators.py          # Decorators de permissão
│   │   ├── middleware.py          # Middleware de company context
│   │   └── context_processors.py  # Context processor para templates
│   │
│   ├── feedback/                  # Sistema de feedback
│   │   ├── models.py              # FeedbackTicket, FeedbackComment
│   │   └── views.py               # Views de feedback e gestão
│   │
│   └── trainings/                 # Treinamentos, vídeos, quizzes
│       ├── models.py              # Training, Video, Quiz, UserProgress
│       └── views.py               # Views de treinamentos
│
├── templates/                     # Templates HTML
│   ├── base.html                  # Template base
│   ├── accounts/                  # Templates de autenticação
│   │   ├── emails/                # Templates de e-mail (HTML)
│   │   ├── password_reset*.html   # Fluxo de recuperação de senha
│   │   └── ...
│   ├── core/                      # Templates de dashboards e relatórios
│   │   ├── reports/               # Templates de relatórios (PDF)
│   │   └── ...
│   ├── checklists/                # Templates de checklists
│   ├── feedback/                  # Templates de feedback
│   └── trainings/                 # Templates de treinamentos
│
├── static/                        # Arquivos estáticos (CSS, JS, imagens)
├── media/                         # Uploads (vídeos, imagens, PDFs)
│
├── mindpulse/                     # Configurações Django
│   ├── settings.py                # Configurações principais
│   ├── urls.py                    # URLs raiz
│   └── wsgi.py                    # WSGI config
│
├── manage.py                      # Script de gerenciamento Django
├── requirements.txt               # Dependências Python
├── README.md                      # Este arquivo
├── EMAIL_DEBUG.md                 # Guia de diagnóstico de e-mail
├── test_email.py                  # Script de teste de SMTP
└── .env                           # Variáveis de ambiente (criar manualmente)
```

---

## 🔒 Segurança Multi-Tenant

### Isolamento de Dados

O Mindpulse implementa isolamento rígido de dados por empresa:

1. **Middleware de Company Context:** Todos os requests têm `request.current_company`
2. **Filtros Automáticos:** Todas as queries são filtradas por `company`
3. **Validação de Permissões:** Decorators garantem acesso apenas à empresa do usuário
4. **Proteção em Views:** Verificações explícitas de `company` em todas as operações

### Verificações de Segurança

Todas as views de gestão verificam:

```python
# Exemplo de padrão aplicado
@login_required
@gestor_required
def minha_view(request):
    company = request.current_company
    
    if not company:
        return render(request, 'core/no_company.html')
    
    # Query sempre filtrada por company
    objetos = Model.objects.filter(company=company)
```

### Decorators de Permissão

- `@login_required`: Usuário deve estar autenticado
- `@gestor_required`: Usuário deve ser gestor ou admin
- `@admin_master_required`: Apenas Admin Master

---

## 💻 Desenvolvimento

### Comandos Úteis

```bash
# Criar migrações
python manage.py makemigrations

# Aplicar migrações
python manage.py migrate

# Criar superusuário
python manage.py createsuperuser

# Testar e-mail SMTP
python manage.py test_email

# Shell do Django
python manage.py shell

# Coletar arquivos estáticos (produção)
python manage.py collectstatic --noinput
```

### Estrutura de Código

#### Type Hints

Todas as funções principais usam type hints:

```python
def minha_funcao(
    user: User,
    company: Company,
    data_inicio: Union[str, date]
) -> Dict[str, Any]:
    """Docstring explicando função."""
    pass
```

#### Sanitização de Dados

Use funções utilitárias de `apps.core.utils`:

```python
from apps.core.utils import safe_int, safe_float, safe_str

# Ao invés de: int(value)
valor = safe_int(value, default=0)

# Ao invés de: float(value)
valor = safe_float(value, default=0.0)

# Ao invés de: str(value) or '---'
texto = safe_str(value, default='---')
```

#### Queries Otimizadas

Sempre use `select_related` e `prefetch_related`:

```python
# ✅ Bom
users = User.objects.filter(company=company).select_related('role')
checklists = Checklist.objects.filter(company=company).prefetch_related('tasks')

# ❌ Evite (causa N+1 queries)
users = User.objects.filter(company=company)
for user in users:
    print(user.role.name)  # Query adicional para cada usuário
```

### Service Layer

Lógicas complexas devem estar em `services.py`:

```python
# ✅ Bom: Lógica em services.py
from apps.accounts.services import send_onboarding_email

# ✅ Bom: View magra
def criar_colaborador(request):
    user_company = form.save()
    # Signal cuida do e-mail
    return redirect('sucesso')
```

---

## 🚀 Deploy

### Checklist de Produção

- [ ] `DEBUG=False` no `.env`
- [ ] `SECRET_KEY` único e seguro
- [ ] `ALLOWED_HOSTS` configurado com domínio real
- [ ] Banco PostgreSQL configurado
- [ ] `USE_SQLITE=False`
- [ ] SMTP configurado e testado
- [ ] `SITE_URL` com domínio real
- [ ] `collectstatic` executado
- [ ] Migrações aplicadas
- [ ] Superusuário criado

### Variáveis de Ambiente (Produção)

```env
DEBUG=False
SECRET_KEY=chave-super-secreta-gerada
ALLOWED_HOSTS=seu-dominio.com,www.seu-dominio.com
USE_SQLITE=False
DB_NAME=mindpulse_prod
DB_USER=postgres
DB_PASSWORD=senha-forte
DB_HOST=127.0.0.1
SITE_URL=https://seu-dominio.com
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=seu-email@gmail.com
EMAIL_HOST_PASSWORD=senha-de-app
```

---

## 🐛 Troubleshooting

### E-mail não está sendo enviado

1. Execute o teste: `python manage.py test_email`
2. Verifique logs do servidor Django
3. Consulte `EMAIL_DEBUG.md` para diagnóstico detalhado
4. Verifique se SMTP está configurado no `.env`
5. Para Gmail, certifique-se de usar Senha de App

### Erro "NoneType" em relatórios

- Todos os valores são sanitizados automaticamente
- Se ainda ocorrer, verifique logs detalhados
- Funções em `apps/core/utils.py` garantem valores seguros

### Performance lenta

- Verifique uso de `select_related` e `prefetch_related`
- Ative Django Debug Toolbar para identificar queries N+1
- Use `python manage.py shell` para testar queries

### Erro de permissão

- Verifique se `@login_required` ou `@gestor_required` está aplicado
- Confirme que `request.current_company` está definido
- Verifique se usuário pertence à empresa (UserCompany)

---

## 📖 Documentação Adicional

- **EMAIL_DEBUG.md:** Guia completo de diagnóstico de e-mail SMTP
- **test_email.py:** Script standalone para testar configuração SMTP
- **Docstrings:** Todas as funções principais têm documentação inline

---

## 🔄 Fluxo de Dados

### Criação de Colaborador

```
1. Form (CollaboratorForm) → Valida dados
2. Form.save() → Cria User + UserCompany
3. Signal (post_save UserCompany) → Detecta criação
4. Signal → Chama send_onboarding_email()
5. Service → Envia e-mail com credenciais
```

### Geração de Relatório PDF

```
1. View (report_management) → Recebe request
2. View → Chama get_report_data() ou get_company_report_data()
3. reports.py → Extrai e sanitiza dados do banco
4. View → Renderiza template HTML (pdf_template.html ou pdf_collective.html)
5. xhtml2pdf → Converte HTML para PDF
6. View → Retorna PDF como HttpResponse
```

---

## 📄 Licença

Proprietário - GRUPOMINDHUB

---

## 📞 Suporte

Para suporte técnico, entre em contato com a equipe de desenvolvimento.

---

**Desenvolvido com ❤️ pela equipe Mindpulse**
