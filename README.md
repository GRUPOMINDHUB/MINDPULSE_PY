# 🚀 Mindpulse - Plataforma de Gestão de Equipes

Sistema completo de gestão de equipes, treinamentos, checklists e feedbacks com arquitetura multi-tenant.

## 📋 Versão 1.0

**Data de Release:** Janeiro 2026

### ✨ Funcionalidades Principais

#### 👥 Gestão de Usuários e Empresas
- Sistema multi-tenant com isolamento completo de dados
- Três níveis de acesso: Admin Master, Gestor e Colaborador
- Cadastro completo de colaboradores com dados pessoais e localização
- Geração automática de matrícula
- Sistema de advertências disciplinares (Oral, Escrita, Suspensão)

#### 📚 Treinamentos
- Criação e gerenciamento de treinamentos
- Upload de vídeos com thumbnails automáticos
- Sistema de quizzes com múltipla escolha
- Progresso individual por colaborador
- Sistema de recompensas e pontos
- Ordenação de conteúdo (vídeos e quizzes) via drag-and-drop

#### ✅ Checklists
- Checklists com frequências configuráveis (Diária, Semanal, Mensal)
- Tarefas com pontos e prazos
- Atribuição individual ou coletiva
- Sistema de conclusão por período
- Alertas de atraso

#### 💬 Feedback
- Sistema de tickets de feedback
- Análise de sentimento (Great, Good, Neutral, Bad, Sad)
- Respostas e acompanhamento
- Filtros por status e sentimento

#### 📊 Relatórios Inteligentes
- **Relatório Individual:** Perfil completo do colaborador com ranking, checklists, treinamentos, quizzes e advertências
- **Relatório Coletivo (Geral da Loja):**
  - KPIs consolidados (Checklists, Treinamentos, Disciplina)
  - Índice de Atenção (Top 3 colaboradores problemáticos)
  - O Pódio (Top 3 por pontos)
  - Tabela de performance completa por colaborador
  - Gráficos de comparação de performance
  - Exportação para PDF (A4 landscape)

#### 🎨 Interface Moderna
- Design responsivo (mobile-first)
- Dark Mode e Light Mode com persistência
- Tema customizável por empresa
- Navegação intuitiva com sidebar
- Gráficos interativos (Chart.js)

## 🛠️ Tecnologias

- **Backend:** Django 5.1.4
- **Frontend:** Tailwind CSS (via CDN)
- **Banco de Dados:** SQLite (desenvolvimento) / PostgreSQL (produção)
- **PDF:** xhtml2pdf 0.2.17
- **JavaScript:** Chart.js 4.4.0
- **Outras:** Pillow, moviepy, django-extensions

## 📦 Instalação

### Pré-requisitos
- Python 3.10 ou superior
- pip
- Git

### Passos

1. **Clone o repositório:**
```bash
git clone https://github.com/GRUPOMINDHUB/MINDPULSE_PY.git
cd MINDPULSE_PY
```

2. **Crie e ative um ambiente virtual:**
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. **Instale as dependências:**
```bash
pip install -r requirements.txt
```

4. **Configure o banco de dados:**
```bash
python manage.py migrate
```

5. **Crie um superusuário:**
```bash
python manage.py createsuperuser
```

6. **Execute o servidor:**
```bash
python manage.py runserver
```

7. **Acesse o sistema:**
```
http://127.0.0.1:8000
```

## 🚀 Início Rápido

### Windows
Execute o arquivo `iniciar_servidor.bat` ou `start.bat`

### Linux/Mac
```bash
chmod +x start.sh
./start.sh
```

## 👤 Níveis de Acesso

### Admin Master
- Acesso total ao sistema
- Gerenciamento de empresas
- Visualização de todas as empresas
- Criação de usuários administrativos

### Gestor
- Gerenciamento da sua unidade/empresa
- Criação de colaboradores
- Gerenciamento de treinamentos e checklists
- Visualização de relatórios coletivos e individuais
- Sistema de advertências

### Colaborador
- Visualização de treinamentos atribuídos
- Execução de checklists
- Envio de feedbacks
- Visualização do próprio perfil e progresso

## 📊 Relatórios

### Relatório Individual
Acesse: **Relatórios** → Selecione um colaborador → **Visualizar na Tela** ou **Baixar PDF**

**Conteúdo:**
- Perfil completo (nome, idade, telefone, cidade, bairro)
- Ranking e pontos
- Checklists (concluídos no período e totais)
- Treinamentos (progresso e status)
- Quizzes (média de notas e tentativas)
- Advertências (histórico completo)

### Relatório Coletivo (Geral da Loja)
Acesse: **Relatórios** → Deixe o colaborador em branco → **Visualizar na Tela** ou **Baixar PDF**

**Conteúdo:**
- **KPIs Consolidados:**
  - Média de Checklists (%)
  - Média de Treinamentos (%)
  - Total de Advertências por tipo
- **Índice de Atenção:** Top 3 colaboradores com mais problemas
- **O Pódio:** Top 3 colaboradores por pontos
- **Tabela de Performance:** Todos os colaboradores com KPIs detalhados
- **Gráficos:** Comparação visual de performance

## 🎨 Personalização

### Tema Dark/Light Mode
Acesse: **Configurações** → Alterne entre Dark e Light Mode

### Cores da Empresa
Admin Master pode configurar cores primárias por empresa no painel de administração.

## 📁 Estrutura do Projeto

```
MINDPULSE_PY/
├── apps/
│   ├── accounts/          # Usuários, autenticação, advertências
│   ├── checklists/        # Checklists e tarefas
│   ├── core/              # Empresas, roles, relatórios, dashboards
│   ├── feedback/          # Sistema de feedback
│   └── trainings/         # Treinamentos, vídeos, quizzes
├── templates/             # Templates HTML
├── static/                # Arquivos estáticos (CSS, JS)
├── media/                 # Uploads (vídeos, imagens)
├── mindpulse/            # Configurações do Django
├── requirements.txt      # Dependências Python
└── manage.py             # Script de gerenciamento Django
```

## 🔒 Segurança

- Isolamento completo de dados por empresa (multi-tenant)
- Autenticação obrigatória para todas as rotas
- Validação de permissões por nível de acesso
- CSRF protection ativado
- Sanitização de inputs

## 📝 Notas de Versão

### Versão 1.0 (Janeiro 2026)
- ✅ Sistema completo de gestão de equipes
- ✅ Treinamentos com vídeos e quizzes
- ✅ Checklists com frequências configuráveis
- ✅ Sistema de feedback com análise de sentimento
- ✅ Relatórios individuais e coletivos
- ✅ Exportação para PDF
- ✅ Dark/Light Mode
- ✅ Interface responsiva
- ✅ Sistema de advertências disciplinares
- ✅ Ranking e gamificação

## 🤝 Contribuindo

Este é um projeto privado do GRUPOMINDHUB. Para contribuições, entre em contato com a equipe de desenvolvimento.

## 📄 Licença

Proprietário - GRUPOMINDHUB

## 📞 Suporte

Para suporte técnico, entre em contato com a equipe de desenvolvimento.

---

**Desenvolvido com ❤️ pela equipe Mindpulse**
