import os
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker, Session
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
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    comments:Mapped[list["Comment"]]=relationship(back_populates="ticket",cascade="all, delete-orphan",order_by="Comment.id")

class Comment(Base):
    __tablename__="ticket_comments"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    ticket_id:Mapped[int]=mapped_column(ForeignKey("tickets.id"))
    author_id:Mapped[int]=mapped_column(Integer)
    text:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    ticket:Mapped[Ticket]=relationship(back_populates="comments")

class Notice(Base):
    __tablename__="ticket_notices"
    id:Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id:Mapped[int]=mapped_column(Integer,index=True)
    kind:Mapped[str]=mapped_column(String(50))
    message:Mapped[str]=mapped_column(String(500))
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

Base.metadata.create_all(engine)
app=FastAPI(title="Tickets Service",version="1.1.0")

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()

class TicketInput(BaseModel):
    title:str=Field(min_length=4,max_length=180)
    description:str=Field(min_length=5,max_length=4000)
    priority:str="normal"
    asset_id:int|None=None
class TicketUpdate(BaseModel):
    status:str|None=None
    assigned_to:int|None=None
class CommentInput(BaseModel):
    text:str=Field(min_length=1,max_length=2000)

def serialize(t):
    return {"id":t.id,"title":t.title,"description":t.description,"status":t.status,"priority":t.priority,
            "requester_id":t.requester_id,"asset_id":t.asset_id,"assigned_to":t.assigned_to,
            "created_at":t.created_at.isoformat(),"comments":[{"id":c.id,"author_id":c.author_id,"text":c.text,"created_at":c.created_at.isoformat()} for c in t.comments]}

def notice(session,user_id,kind,message):
    session.add(Notice(user_id=user_id,kind=kind,message=message));session.commit()

async def check_reference(service,path,authorization):
    base=os.getenv(service)
    if not base: raise HTTPException(503,"Serviço dependente não configurado.")
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            response=await client.get(f"{base}{path}",headers={"Authorization":authorization} if authorization else {})
        if response.status_code==404: raise HTTPException(400,"Referência informada não existe.")
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401,403): raise HTTPException(e.response.status_code,"Acesso negado pelo serviço dependente.")
        raise HTTPException(503,"Não foi possível validar os dados no serviço dependente.")
    except httpx.HTTPError:
        raise HTTPException(503,"Não foi possível validar os dados no serviço dependente.")

@app.get("/health")
def health(): return {"service":"tickets","status":"ok"}

@app.post("/tickets",status_code=201)
async def create_ticket(data:TicketInput,current=Depends(get_current_user),authorization:str|None=Header(default=None),session:Session=Depends(db)):
    if data.priority not in {"low","normal","high","critical"}: raise HTTPException(422,"Prioridade inválida.")
    if data.asset_id is not None: await check_reference("INVENTORY_URL",f"/internal/assets/{data.asset_id}",authorization)
    t=Ticket(title=data.title,description=data.description,priority=data.priority,requester_id=current["id"],asset_id=data.asset_id)
    session.add(t);session.commit();session.refresh(t)
    notice(session,current["id"],"ticket_opened",f"Seu chamado #{t.id} foi aberto.")
    return serialize(t)

@app.get("/tickets")
def list_tickets(current=Depends(get_current_user),session:Session=Depends(db)):
    q=session.query(Ticket)
    if current["role"] not in {"admin","technician"}: q=q.filter(Ticket.requester_id==current["id"])
    return [serialize(t) for t in q.order_by(Ticket.id.desc()).all()]

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id:int,current=Depends(get_current_user),session:Session=Depends(db)):
    t=session.get(Ticket,ticket_id)
    if not t or (current["role"] not in {"admin","technician"} and t.requester_id!=current["id"]): raise HTTPException(404,"Chamado não encontrado.")
    return serialize(t)

@app.patch("/tickets/{ticket_id}")
async def update_ticket(ticket_id:int,data:TicketUpdate,current=Depends(require_roles("admin","technician")),authorization:str|None=Header(default=None),session:Session=Depends(db)):
    t=session.get(Ticket,ticket_id)
    if not t: raise HTTPException(404,"Chamado não encontrado.")
    values=data.model_dump(exclude_unset=True)
    if "status" in values:
        transitions={"open":{"in_progress"},"in_progress":{"resolved"},"resolved":{"closed","in_progress"},"closed":set()}
        if values["status"] not in transitions.get(t.status,set()): raise HTTPException(422,f"Transição inválida: {t.status} → {values['status']}.")
    if "assigned_to" in values and values["assigned_to"] is not None:
        await check_reference("USERS_URL",f"/internal/technicians/{values['assigned_to']}",authorization)
        if t.status=="open": t.status="in_progress"
    for key,value in values.items(): setattr(t,key,value)
    session.commit();session.refresh(t)
    if "status" in values and values["status"]=="resolved": notice(session,t.requester_id,"ticket_resolved",f"Seu chamado #{t.id} foi resolvido.")
    return serialize(t)

@app.post("/tickets/{ticket_id}/comments",status_code=201)
def add_comment(ticket_id:int,data:CommentInput,current=Depends(get_current_user),session:Session=Depends(db)):
    t=session.get(Ticket,ticket_id)
    if not t or (current["role"] not in {"admin","technician"} and t.requester_id!=current["id"]): raise HTTPException(404,"Chamado não encontrado.")
    if t.status=="closed": raise HTTPException(422,"Chamados fechados não recebem comentários.")
    c=Comment(ticket_id=t.id,author_id=current["id"],text=data.text);session.add(c);session.commit();session.refresh(c)
    return {"id":c.id,"author_id":c.author_id,"text":c.text,"created_at":c.created_at.isoformat()}

@app.get("/notifications")
def list_notifications(current=Depends(get_current_user),session:Session=Depends(db)):
    return [{"id":n.id,"kind":n.kind,"message":n.message,"created_at":n.created_at.isoformat()} for n in session.query(Notice).filter_by(user_id=current["id"]).order_by(Notice.id.desc()).limit(30).all()]
