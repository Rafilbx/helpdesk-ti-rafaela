import os
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from security import get_current_user, require_roles

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inventory.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
class Base(DeclarativeBase): pass
class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    asset_tag: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="available")
    assigned_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
Base.metadata.create_all(engine)
app = FastAPI(title="Inventory Service", version="1.0.0")
def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()
class AssetInput(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    asset_tag: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=2, max_length=100)
    status: str = "available"
    assigned_to: int | None = None
    description: str | None = None
def serialize(a):
    return {"id":a.id,"name":a.name,"asset_tag":a.asset_tag,"category":a.category,"status":a.status,"assigned_to":a.assigned_to,"description":a.description}
@app.get("/health")
def health(): return {"service":"inventory","status":"ok"}
@app.get("/internal/assets/{asset_id}")
def internal_asset(asset_id:int, current=Depends(get_current_user), session:Session=Depends(db)):
    a=session.get(Asset,asset_id)
    if not a: raise HTTPException(404,"Ativo não encontrado.")
    return serialize(a)
@app.get("/assets")
def list_assets(current=Depends(get_current_user), session:Session=Depends(db)):
    return [serialize(a) for a in session.query(Asset).all()]
@app.post("/assets",status_code=201)
def create_asset(data:AssetInput,current=Depends(require_roles("admin")),session:Session=Depends(db)):
    if session.query(Asset).filter_by(asset_tag=data.asset_tag).first(): raise HTTPException(409,"Patrimônio já cadastrado.")
    a=Asset(**data.model_dump()); session.add(a); session.commit(); session.refresh(a); return serialize(a)
@app.get("/assets/{asset_id}")
def get_asset(asset_id:int,current=Depends(get_current_user),session:Session=Depends(db)):
    a=session.get(Asset,asset_id)
    if not a: raise HTTPException(404,"Ativo não encontrado.")
    return serialize(a)
@app.patch("/assets/{asset_id}")
def update_asset(asset_id:int,data:AssetInput,current=Depends(require_roles("admin")),session:Session=Depends(db)):
    a=session.get(Asset,asset_id)
    if not a: raise HTTPException(404,"Ativo não encontrado.")
    for key,value in data.model_dump().items(): setattr(a,key,value)
    session.commit(); session.refresh(a); return serialize(a)
@app.delete("/assets/{asset_id}",status_code=204)
def delete_asset(asset_id:int,current=Depends(require_roles("admin")),session:Session=Depends(db)):
    a=session.get(Asset,asset_id)
    if not a: raise HTTPException(404,"Ativo não encontrado.")
    session.delete(a); session.commit()
