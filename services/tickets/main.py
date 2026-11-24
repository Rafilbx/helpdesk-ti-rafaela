import os
import httpx
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from security import get_current_user, require_roles

DATABASE_URL=os.getenv("DATABASE_URL","sqlite:///./tickets.db")
engine=create_engine(DATABASE_URL,connect_args={"check_same_thread":False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal=sessionmaker(bind=engine,autoflush=False)
class Base(DeclarativeBase): pass
class Ticket(Base):
    __tablename__="tickets"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    title:Mapped[str]=mapped_column(String(180))
    description:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(30),default="open")
    priority:Mapped[str]=mapped_column(String(20),default="normal")
    requester_id:Mapped[int]=mapped_column(Integer,index=True)
    asset_id:Mapped[int|None]=mapped_column(Integer,nullable=True)
    assigned_to:Mapped[int|None]=mapped_column(Integer,nullable=True)
Base.metadata.create_all(engine)
app=FastAPI(title="Tickets Service",version="1.0.0")
def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()
class TicketInput(BaseModel):
    title:str=Field(min_length=4,max_length=180)
    description:str=Field(min_length=5)
    priority:str="normal"
    asset_id:int|None=None
class TicketUpdate(BaseModel):
    status:str|None=None
    assigned_to:int|None=None
def serialize(t):
    return {"id":t.id,"title":t.title,"description":t.description,"status":t.status,"priority":t.priority,"requester_id":t.requester_id,"asset_id":t.asset_id,"assigned_to":t.assigned_to}
async def check_reference(service:str,path:str):
    base=os.getenv(service)
    if not base: raise HTTPException(503,"Serviço dependente não configurado.")
    try:
        async with httpx.AsyncClient(timeout=4) as client: response=await client.get(f"{base}{path}")
        if response.status_code==404: raise HTTPException(400,"Referência informada não existe.")
        response.raise_for_status()
    except httpx.HTTPError: raise HTTPException(503,"Não foi possível validar os dados no serviço dependente.")
@app.get("/health")
def health(): return {"service":"tickets","status":"ok"}
@app.post("/tickets",status_code=201)
async def create_ticket(data:TicketInput,current=Depends(get_current_user),session:Session=Depends(db)):
    if data.asset_id is not None: await check_reference("INVENTORY_URL",f"/internal/assets/{data.asset_id}")
    t=Ticket(title=data.title,description=data.description,priority=data.priority,requester_id=current["id"],asset_id=data.asset_id)
    session.add(t);session.commit();session.refresh(t);return serialize(t)
@app.get("/tickets")
def list_tickets(current=Depends(get_current_user),session:Session=Depends(db)):
    query=session.query(Ticket)
    if current["role"]!="admin": query=query.filter(Ticket.requester_id==current["id"])
    return [serialize(t) for t in query.order_by(Ticket.id.desc()).all()]
@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id:int,current=Depends(get_current_user),session:Session=Depends(db)):
    t=session.get(Ticket,ticket_id)
    if not t: raise HTTPException(404,"Chamado não encontrado.")
    if current["role"]!="admin" and t.requester_id!=current["id"]: raise HTTPException(403,"Acesso negado.")
    return serialize(t)
@app.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id:int,data:TicketUpdate,current=Depends(require_roles("admin")),session:Session=Depends(db)):
    t=session.get(Ticket,ticket_id)
    if not t: raise HTTPException(404,"Chamado não encontrado.")
    values=data.model_dump(exclude_unset=True)
    if "status" in values and values["status"] not in {"open","in_progress","resolved","closed"}: raise HTTPException(422,"Status inválido.")
    for key,value in values.items(): setattr(t,key,value)
    session.commit();session.refresh(t);return serialize(t)
