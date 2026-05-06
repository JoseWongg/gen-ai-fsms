# Technology Stack – FSMS Onboarding System

## Languages

- **Python** – 3.12 – Main programming language

## Backend Framework & Libraries

- **FastAPI** – Web framework for REST API
- **Uvicorn** – ASGI server
- **SQLAlchemy** – ORM and database toolkit
- **Alembic** – Database migrations
- **Pydantic** – Data validation and settings management
- **PyMySQL** – MySQL database driver
- **python-dotenv** – Environment variable management
- **python-jose[cryptography]** – JWT creation and validation
- **passlib[bcrypt]** – Password hashing
- **email-validator** – Email format validation
- **requests** – HTTP client (for Mailgun API)
- **langgraph** – Stateful workflow orchestration (screening and approval flows)
- **langchain-core** – LLM integration helpers

## Frontend Framework & Libraries

- **Streamlit** – Web UI framework
- **httpx** – HTTP client (calls FastAPI backend)
- **pandas** – Data manipulation (test records)

## Database

- **MySQL** – 8.0 – Relational database (development, test, production)
- **JawsDB MySQL** – Heroku add‑on for production MySQL

## LLM & AI

- **OpenAI API (GPT‑4o mini)** – Answer clarification questions, interpret user answers during screening
- **LangGraph** – Workflow management (conversational flows)

## Email Service

- **Mailgun** – Transactional email (password reset)
- **SMTP** – Email transport (fallback)

## Infrastructure & Deployment

- **Heroku** – Cloud platform (hosts backend and frontend apps)
- **Cloudflare** – DNS management, SSL, domain (`ai-fsms.com`)
- **Git** – Version control
- **GitHub** – Remote repository
- **Heroku CLI** – Deployment and management

## Development Tools

- **VS Code** – IDE
- **Pylance** – Type checking and linting
- **Pytest** – Unit and integration testing
- **pytest-dotenv** – Environment loading for tests
- **SQLTools** – Database explorer (VS Code extension)
- **Mermaid** – Diagram generation

## Authentication & Security

- **JWT (JSON Web Tokens)** – Stateless authentication
- **bcrypt** – Password hashing
- **HTTPS / TLS** – Encrypted communication (Heroku + Cloudflare)
- **CORS** – Cross‑origin request control

## Monitoring & Logging

- **Heroku Logs** – Application log streaming
- **Sentry** – Error tracking on production (Heroku Add-on)
