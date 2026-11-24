# Arquitetura de microsserviços

Esta implementação adiciona uma arquitetura distribuída ao HelpDesk TI, mantendo a aplicação original disponível. A nova composição é iniciada separadamente por `docker-compose.microservices.yml`.

## Serviços

| Serviço | Responsabilidade | Banco |
|---|---|---|
| Gateway | Entrada HTTP e roteamento | — |
| Users | Cadastro, autenticação e consulta de usuários | PostgreSQL próprio |
| Inventory | Cadastro e consulta de ativos de TI | PostgreSQL próprio |
| Tickets | Abertura, consulta e atualização de chamados | PostgreSQL próprio |

Os serviços não compartilham tabelas. O Tickets consulta o Inventory por HTTP para validar o ativo associado. O Gateway encaminha as requisições sem concentrar regras de negócio.

## Executar

1. Instale Docker e Docker Compose.
2. Copie `.env.microservices.example` para `.env`.
3. Defina uma senha forte em `DB_PASSWORD` e uma chave aleatória de no mínimo 32 caracteres em `JWT_SECRET_KEY`.
4. Execute:

```bash
docker compose --env-file .env -f docker-compose.microservices.yml up --build
```

A API fica disponível em `http://localhost:8000`. Documentação interativa: `http://localhost:8000/docs`.

## Rotas principais

- `POST /auth/register` — cria usuário.
- `POST /auth/login` — autentica e retorna JWT.
- `GET /users/me` — consulta o usuário autenticado.
- `GET /assets`, `POST /assets`, `GET /assets/{id}`, `PATCH /assets/{id}`, `DELETE /assets/{id}` — inventário.
- `POST /tickets`, `GET /tickets`, `GET /tickets/{id}`, `PATCH /tickets/{id}` — chamados.

Envie o token retornado pelo login no cabeçalho `Authorization: Bearer <token>`. Operações administrativas exigem papel `admin`. O cadastro público cria usuários comuns; a promoção inicial de um administrador deve ser feita por procedimento operacional seguro diretamente no banco de usuários.

## Separação e segurança

Cada domínio possui banco e credenciais de conexão isolados. Os bancos e serviços internos não publicam portas no host; somente o Gateway é exposto, limitado ao loopback. Senhas são armazenadas com bcrypt, tokens JWT têm expiração e a chave é fornecida por variável de ambiente. Não use valores de exemplo em produção.

## Limitações e evolução

Esta camada demonstra a decomposição dos domínios centrais e a comunicação HTTP. A migração dos registros já existentes deve ser executada como etapa controlada antes da substituição do monólito. Recursos acessórios do sistema legado, como notificações, comentários e histórico detalhado, precisam ser migrados para serviços/eventos próprios para equivalência funcional integral. O compose de microsserviços é independente do compose original para permitir comparação e transição gradual.

## Verificação

Após subir a composição, consulte `GET /health` no Gateway e nos serviços pela rede Docker. Faça o fluxo de cadastro, login, consulta de ativos e abertura de chamado usando o Swagger do Gateway.
