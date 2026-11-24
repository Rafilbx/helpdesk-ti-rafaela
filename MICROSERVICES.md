# HelpDesk TI — arquitetura de microsserviços

A versão de microsserviços separa o sistema em quatro aplicações independentes: Gateway, Usuários, Inventário e Chamados. O monólito original continua no repositório como referência da implementação anterior.

## Interface web

A aplicação possui uma interface web própria em `gateway/static`, servida pelo Gateway:

- Login e cadastro de solicitantes.
- Painel com totais de chamados por situação.
- Abertura e consulta de chamados, pesquisa e filtro.
- Atribuição de chamados a técnicos, transição de status e comentários.
- Cadastro, edição, consulta e exclusão de equipamentos (perfil administrador).
- Cadastro e consulta de usuários e perfis (perfil administrador).
- Notificações geradas pela abertura e resolução de chamados.

Acesse `http://localhost:8000/`. A documentação Swagger continua em `http://localhost:8000/docs`.

## Serviços e responsabilidades

| Serviço | Responsabilidade | Banco |
|---|---|---|
| Gateway | Interface web e roteamento de requisições | — |
| Users | Cadastro, login, perfis e consulta de técnicos | SQLite próprio no modo local / PostgreSQL no Compose |
| Inventory | Cadastro e gerenciamento de equipamentos | SQLite próprio no modo local / PostgreSQL no Compose |
| Tickets | Chamados, atribuição, status, comentários e notificações | SQLite próprio no modo local / PostgreSQL no Compose |

Os serviços não compartilham tabelas. O Tickets consulta Inventory para validar equipamentos e Users para validar técnicos, usando HTTP, timeout e o token JWT recebido na requisição. Cada serviço valida a autenticação localmente. O Gateway é o único ponto de entrada da interface.

## Executar localmente sem Docker (Windows / PowerShell)

Com Python instalado e as dependências já instaladas no ambiente virtual:

Abra quatro terminais PowerShell na raiz do projeto. Não feche os terminais enquanto estiver usando o HelpDesk.

**Terminal 1 — Usuários (porta 8001)**

```powershell
.\.venv\Scripts\Activate.ps1
$project = (Get-Location).Path
$env:PYTHONPATH="$project\services\shared"
$env:JWT_SECRET_KEY="chave-local-de-teste-com-mais-de-32-caracteres"
cd services/users
python -m uvicorn main:app --reload --port 8001
```

**Terminal 2 — Inventário (porta 8002)**

```powershell
.\.venv\Scripts\Activate.ps1
$project = (Get-Location).Path
$env:PYTHONPATH="$project\services\shared"
$env:JWT_SECRET_KEY="chave-local-de-teste-com-mais-de-32-caracteres"
cd services/inventory
python -m uvicorn main:app --reload --port 8002
```

**Terminal 3 — Chamados (porta 8003)**

```powershell
.\.venv\Scripts\Activate.ps1
$project = (Get-Location).Path
$env:PYTHONPATH="$project\services\shared"
$env:JWT_SECRET_KEY="chave-local-de-teste-com-mais-de-32-caracteres"
$env:INVENTORY_URL="http://127.0.0.1:8002"
$env:USERS_URL="http://127.0.0.1:8001"
cd services/tickets
python -m uvicorn main:app --reload --port 8003
```

**Terminal 4 — Gateway (porta 8000)**

```powershell
.\.venv\Scripts\Activate.ps1
$env:USERS_URL="http://127.0.0.1:8001"
$env:INVENTORY_URL="http://127.0.0.1:8002"
$env:TICKETS_URL="http://127.0.0.1:8003"
cd gateway
python -m uvicorn main:app --reload --port 8000
```

Abra `http://localhost:8000/`. Cada serviço também possui documentação própria nas portas 8001, 8002 e 8003.

### Primeiro administrador no modo local

O cadastro público cria solicitantes. Para habilitar a gestão de usuários e equipamentos, promova a conta de demonstração a administrador em um terminal separado, na raiz do projeto. Substitua o e-mail pelo usado no cadastro:

```powershell
python -c "import sqlite3; db=sqlite3.connect('services/users/users.db'); db.execute('UPDATE users SET role=? WHERE email=?', ('admin','rafaela@email.com')); db.commit(); db.close(); print('Perfil atualizado. Saia e entre novamente no HelpDesk.')"
```

Depois saia da interface e entre novamente para renovar o token com o perfil atualizado. Na tela Usuários, cadastre uma conta com perfil Técnico para testar a atribuição.

## Executar com Docker Compose

O Compose mantém três bancos PostgreSQL independentes e expõe somente o Gateway no host. Copie `.env.microservices.example` para `.env`, defina senha e chave JWT fortes e execute:

```bash
docker compose --env-file .env -f docker-compose.microservices.yml up --build
```

Docker não é necessário para o modo local descrito acima. O Compose ainda não foi executado/validado neste ambiente.

## Rotas principais

- `POST /auth/register` e `POST /auth/login`
- `GET /users/me`, `GET /users`, `POST /users`
- `GET /assets`, `POST /assets`, `PATCH /assets/{id}`, `DELETE /assets/{id}`
- `POST /tickets`, `GET /tickets`, `PATCH /tickets/{id}`
- `POST /tickets/{id}/comments`, `GET /notifications`
- `GET /health` e `GET /saude`

As operações administrativas exigem perfil `admin`; atribuição e atualização de chamados exigem `admin` ou `technician`. Solicitantes consultam apenas os próprios chamados.

## Observações e limites

A interface e os endpoints foram adicionados para demonstrar os fluxos centrais da aplicação. A migração de dados antigos não é automática. Recursos completos do monólito, como SLA avançado, histórico/auditoria detalhado e integração real de e-mail/SMS, ainda precisam de implementação antes de declarar equivalência funcional integral. O modo local usa SQLite separado por serviço; o Compose configura PostgreSQL separado por serviço.
