import os
import bcrypt
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from security import create_access_token, get_current_user, require_roles

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="user")
Base.metadata.create_all(engine)
app = FastAPI(title="Users Service", version="1.0.0")

def db():
    session = SessionLocal()
    try: yield session
    finally: session.close()

class Register(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
class Login(BaseModel):
    email: EmailStr
    password: str
class AdminUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "technician"

class PublicUser(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str

@app.get("/health")
def health(): return {"service": "users", "status": "ok"}
@app.post("/auth/register", status_code=201)
def register(data: Register, session: Session = Depends(db)):
    email = str(data.email).lower()
    if session.query(User).filter_by(email=email).first():
        raise HTTPException(409, "E-mail já cadastrado.")
    user = User(name=data.name.strip(), email=email,
                password_hash=bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode())
    session.add(user); session.commit(); session.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
@app.post("/auth/login")
def login(data: Login, session: Session = Depends(db)):
    user = session.query(User).filter_by(email=str(data.email).lower()).first()
    if not user or not bcrypt.checkpw(data.password.encode(), user.password_hash.encode()):
        raise HTTPException(401, "E-mail ou senha inválidos.")
    return {"access_token": create_access_token(user.id, user.email, user.role), "token_type": "bearer"}
@app.get("/users/me")
def me(current=Depends(get_current_user), session: Session = Depends(db)):
    user = session.get(User, current["id"])
    if not user: raise HTTPException(404, "Usuário não encontrado.")
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
@app.get("/users", dependencies=[Depends(require_roles("admin"))])
def list_users(session: Session = Depends(db)):
    return [{"id": u.id, "name": u.name, "email": u.email, "role": u.role} for u in session.query(User).all()]
@app.get("/users/{user_id}")
def get_user(user_id: int, current=Depends(get_current_user), session: Session = Depends(db)):
    if current["role"] != "admin" and current["id"] != user_id:
        raise HTTPException(403, "Acesso negado.")
    user = session.get(User, user_id)
    if not user: raise HTTPException(404, "Usuário não encontrado.")
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}

@app.post("/users", status_code=201, dependencies=[Depends(require_roles("admin"))])
def create_user(data: AdminUserCreate, session: Session = Depends(db)):
    email = str(data.email).lower()
    if data.role not in {"user", "technician", "admin"}: raise HTTPException(422, "Perfil inválido.")
    if session.query(User).filter_by(email=email).first(): raise HTTPException(409, "E-mail já cadastrado.")
    user = User(name=data.name.strip(), email=email, role=data.role, password_hash=bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode())
    session.add(user); session.commit(); session.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}

@app.get("/internal/technicians/{user_id}")
def internal_technician(user_id: int, current=Depends(get_current_user), session: Session = Depends(db)):
    user = session.get(User, user_id)
    if not user or user.role != "technician": raise HTTPException(404, "Técnico não encontrado.")
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role}
