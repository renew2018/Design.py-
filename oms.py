from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import logging

logging.basicConfig(level=logging.DEBUG)

DATABASE_URL = "sqlite:///./orders.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Order Management with Project Progress and Invoice")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_STAGES = [
    ("Design Review", 5),
    ("Concept MEP Design", 15),
    ("Detailed Design & Drawings", 30),
    ("Coordination & Clash Resolution", 45),
    ("Approvals", 55),
    ("Procurement", 65),
    ("Installation/Execution", 85),
    ("Testing & Commissioning", 95),
    ("Handover", 100),
]

class OrderDB(Base):
    __tablename__ = "orders"
    sl_no = Column(Integer, unique=True, nullable=False)
    id = Column(String, primary_key=True, index=True)
    project_name = Column(String, index=True)
    architect_name = Column(String, index=True)
    client_name = Column(String, nullable=True)
    client_phone = Column(String, nullable=True)
    client_address = Column(String, nullable=True)
    client_gst = Column(String, nullable=True)
    total_amount = Column(Float)
    amount_paid = Column(Float)
    remaining_amount = Column(Float)
    paid_percent = Column(Float)
    remaining_percent = Column(Float)
    progress_stage_index = Column(Integer, default=0)
    progress_percent = Column(Float, default=PROJECT_STAGES[0][1])
    draft_invoice_amount = Column(Float, default=0.0)
    start_date = Column(String)
    last_invoice_date = Column(String)
    end_date = Column(String, nullable=True)
    created_at = Column(String)

Base.metadata.create_all(bind=engine)

def recalc(total_amount, amount_paid):
    try:
        total_amount = float(total_amount)
        amount_paid = float(amount_paid)
    except Exception as e:
        logging.error(f"Error in recalc: {e}")
        total_amount, amount_paid = 0, 0
    remaining = total_amount - amount_paid
    paid_pct = round((amount_paid / total_amount)*100, 2) if total_amount > 0 else 0
    rem_pct = 100 - paid_pct
    return round(remaining, 2), paid_pct, rem_pct

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def update_draft_invoice(order: OrderDB):
    total_due = order.total_amount * (order.progress_percent / 100)
    due_invoice = total_due - order.amount_paid
    order.draft_invoice_amount = max(0, round(due_invoice, 2))

class OrderCreate(BaseModel):
    id: str = Field(..., description="Unique order ID, user must provide")
    project_name: str
    architect_name: str
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_address: Optional[str] = None
    client_gst: Optional[str] = None
    total_amount: float = Field(gt=0)
    amount_paid: float = Field(ge=0)

class PaymentUpdate(BaseModel):
    amount_paid: Optional[float] = None
    end_date: Optional[str] = None
    progress_stage_index: Optional[int] = None

class OrderOut(BaseModel):
    sl_no: int
    id: str
    project_name: str
    architect_name: str
    client_name: Optional[str]
    client_phone: Optional[str]
    client_address: Optional[str]
    client_gst: Optional[str]
    total_amount: float
    amount_paid: float
    remaining_amount: float
    paid_percent: float
    remaining_percent: float
    progress_stage_index: int
    progress_percent: float
    draft_invoice_amount: float
    start_date: str
    last_invoice_date: str
    end_date: Optional[str]
    created_at: str

    class Config:
        orm_mode = True

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logging.error(f"DB session error: {e}")
    finally:
        db.close()

@app.post("/orders/", response_model=OrderOut)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    logging.debug(f"Creating order: {order.id}")
    if db.query(OrderDB).filter(OrderDB.id == order.id).first():
        logging.error(f"Order ID {order.id} already exists")
        raise HTTPException(400, "Order ID already exists")
    max_sl = db.query(func.max(OrderDB.sl_no)).scalar()
    next_sl = (max_sl or 0) + 1
    remaining, paid_pct, rem_pct = recalc(order.total_amount, order.amount_paid)
    now = now_ts()
    start_date = date.today().isoformat()
    db_order = OrderDB(
        sl_no=next_sl,
        id=order.id,
        project_name=order.project_name,
        architect_name=order.architect_name,
        client_name=order.client_name,
        client_phone=order.client_phone,
        client_address=order.client_address,
        client_gst=order.client_gst,
        total_amount=order.total_amount,
        amount_paid=order.amount_paid,
        remaining_amount=remaining,
        paid_percent=paid_pct,
        remaining_percent=rem_pct,
        progress_stage_index=0,
        progress_percent=PROJECT_STAGES[0][1],
        start_date=start_date,
        last_invoice_date=now,
        end_date=None,
        created_at=now,
    )
    update_draft_invoice(db_order)
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@app.put("/orders/{order_id}/", response_model=OrderOut)
def update_order(order_id: str, upd: PaymentUpdate, db: Session = Depends(get_db)):
    logging.debug(f"Updating order: {order_id} with {upd}")
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        logging.error(f"Order {order_id} not found")
        raise HTTPException(404, "Order not found")
    if upd.amount_paid is not None:
        new_total_paid = order.amount_paid + upd.amount_paid
        remaining, paid_pct, rem_pct = recalc(order.total_amount, new_total_paid)
        order.amount_paid = new_total_paid
        order.remaining_amount = remaining
        order.paid_percent = paid_pct
        order.remaining_percent = rem_pct
        order.last_invoice_date = now_ts()
        if remaining <= 0:
            order.end_date = now_ts()
        elif upd.end_date:
            order.end_date = upd.end_date
    if upd.progress_stage_index is not None:
        if 0 <= upd.progress_stage_index < len(PROJECT_STAGES):
            order.progress_stage_index = upd.progress_stage_index
            order.progress_percent = PROJECT_STAGES[upd.progress_stage_index][1]
    update_draft_invoice(order)
    db.commit()
    db.refresh(order)
    return order

@app.get("/orders/{order_id}/invoice_pdf")
def get_order_invoice_pdf(order_id: str, db: Session = Depends(get_db)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        logging.error(f"Invoice PDF request for non-existing order: {order_id}")
        raise HTTPException(404, "Order not found")
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.drawString(50, 800, f"Invoice for Order ID: {order.id}")
    p.drawString(50, 780, f"Client Name: {order.client_name or 'N/A'}")
    p.drawString(50, 760, f"Phone: {order.client_phone or 'N/A'}")
    p.drawString(50, 740, f"Address: {order.client_address or 'N/A'}")
    p.drawString(50, 720, f"GST No: {order.client_gst or 'N/A'}")
    p.drawString(50, 680, f"Progress: {order.progress_percent:.2f}%")
    p.drawString(50, 700, f"Total Amount: ₹{order.total_amount:.2f}")
    p.drawString(50, 660, f"Payable Amount for Work Done: ₹{order.draft_invoice_amount:.2f}")
    p.drawString(50, 640, f"Amount Paid: ₹{order.amount_paid:.2f}")
    p.drawString(50, 620, f"Remaining Amount: ₹{order.remaining_amount:.2f}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Invoice_{order.id}.pdf"},
    )

@app.get("/orders/{order_id}/invoice_json")
def get_invoice_json(order_id: str, db: Session = Depends(get_db)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        logging.error(f"Invoice JSON request for non-existing order: {order_id}")
        raise HTTPException(404, "Order not found")
    return {
        "id": order.id,
        "project_name": order.project_name,
        "client_name": order.client_name,
        "client_phone": order.client_phone,
        "client_address": order.client_address,
        "client_gst": order.client_gst,
        "progress_percent": order.progress_percent,
        "total_amount": order.total_amount,
        "amount_paid": order.amount_paid,
        "remaining_amount": order.remaining_amount,
        "draft_invoice_amount": order.draft_invoice_amount,
    }

@app.delete("/orders/{order_id}/", response_model=dict)
def delete_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        logging.error(f"Delete request for non-existing order: {order_id}")
        raise HTTPException(404, "Order not found")
    db.delete(order)
    db.commit()
    return {"message": f"Order {order_id} deleted"}

@app.get("/orders/", response_model=List[OrderOut])
def list_all_orders(db: Session = Depends(get_db)):
    return db.query(OrderDB).order_by(OrderDB.sl_no.asc()).all()

@app.get("/orders/search/", response_model=List[OrderOut])
def search_orders(
    keyword: Optional[str] = None,
    percent: Optional[float] = Query(None, ge=0, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(OrderDB)
    if keyword:
        # Split keyword into words for combined search
        words = keyword.lower().split()
        filters = []
        for w in words:
            kw = f"%{w}%"
            filters.append(
                (OrderDB.id.ilike(kw)) | (OrderDB.project_name.ilike(kw)) | (OrderDB.architect_name.ilike(kw)) | (OrderDB.client_name.ilike(kw))
            )
        from sqlalchemy import and_
        query = query.filter(and_(*filters))
    if percent is not None:
        query = query.filter(OrderDB.remaining_percent == percent)
    results = query.order_by(OrderDB.sl_no.asc()).all()
    return results

@app.get("/orders/filter/", response_model=List[OrderOut])
def filter_orders_by_remaining(percent: float, db: Session = Depends(get_db)):
    return (
        db.query(OrderDB)
        .filter(OrderDB.remaining_percent == percent)
        .order_by(OrderDB.sl_no.asc())
        .all()
    )
