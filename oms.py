from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

from sqlalchemy import Column, Integer, String, Float, create_engine, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = "sqlite:///./orders.db"

Base = declarative_base()
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="Order Management API with DB")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class OrderDB(Base):
    __tablename__ = "orders"

    sl_no = Column(Integer, unique=True, nullable=False)
    id = Column(String, primary_key=True, index=True)
    project_name = Column(String, index=True)
    architect_name = Column(String, index=True)
    total_amount = Column(Float)
    amount_paid = Column(Float)
    remaining_amount = Column(Float)
    paid_percent = Column(Float)
    remaining_percent = Column(Float)
    start_date = Column(String)
    last_invoice_date = Column(String)
    end_date = Column(String, nullable=True)
    created_at = Column(String)

Base.metadata.create_all(bind=engine)

def recalc(total_amount, amount_paid):
    try:
        total_amount = float(total_amount)
        amount_paid = float(amount_paid)
    except ValueError:
        total_amount, amount_paid = 0, 0
    remaining = total_amount - amount_paid
    paid_pct = round((amount_paid / total_amount)*100, 2) if total_amount > 0 else 0
    rem_pct = 100 - paid_pct
    return round(remaining, 2), paid_pct, rem_pct

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class OrderCreate(BaseModel):
    id: str = Field(..., description="Unique order ID, user must provide")
    project_name: str
    architect_name: str
    total_amount: float = Field(gt=0)
    amount_paid: float = Field(ge=0)

class PaymentUpdate(BaseModel):
    amount_paid: float = Field(gt=0)
    end_date: Optional[str] = None

class OrderOut(BaseModel):
    sl_no: int
    id: str
    project_name: str
    architect_name: str
    total_amount: float
    amount_paid: float
    remaining_amount: float
    paid_percent: float
    remaining_percent: float
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
    finally:
        db.close()

@app.post("/orders/", response_model=OrderOut)
def create_order(order: OrderCreate, db: Session = Depends(get_db)):
    if db.query(OrderDB).filter(OrderDB.id == order.id).first():
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
        total_amount=order.total_amount,
        amount_paid=order.amount_paid,
        remaining_amount=remaining,
        paid_percent=paid_pct,
        remaining_percent=rem_pct,
        start_date=start_date,
        last_invoice_date=now,
        end_date=None,
        created_at=now,
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@app.put("/orders/{order_id}/", response_model=OrderOut)
def update_order(order_id: str, upd: PaymentUpdate, db: Session = Depends(get_db)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
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
    db.commit()
    db.refresh(order)
    return order

@app.delete("/orders/{order_id}/", response_model=dict)
def delete_order(order_id: str, db: Session = Depends(get_db)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
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
    db: Session = Depends(get_db)
):
    query = db.query(OrderDB)
    if keyword:
        kw = f"%{keyword.lower()}%"
        query = query.filter(
            (OrderDB.id.ilike(kw)) |
            (OrderDB.project_name.ilike(kw)) |
            (OrderDB.architect_name.ilike(kw))
        )
    if percent is not None:
        query = query.filter(OrderDB.remaining_percent == percent)
    results = query.order_by(OrderDB.sl_no.asc()).all()
    return results

@app.get("/orders/filter/", response_model=List[OrderOut])
def filter_orders_by_remaining(percent: float, db: Session = Depends(get_db)):
    # Optional: you can remove this if using combined search endpoint
    return db.query(OrderDB).filter(OrderDB.remaining_percent == percent).order_by(OrderDB.sl_no.asc()).all()

@app.get("/orders/{order_id}/invoice_summary", response_model=Dict[str, Optional[str]])
def get_invoice_summary(order_id: str, db: Session = Depends(get_db)):
    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    return {
        "Start Date": order.start_date,
        "Last Invoice Date": order.last_invoice_date,
        "End Date": order.end_date,
    }

@app.get("/reports/collection/", response_model=Dict[str, float])
def get_collection_report(db: Session = Depends(get_db)):
    total_paid = db.query(func.sum(OrderDB.amount_paid)).scalar() or 0
    total_remaining = db.query(func.sum(OrderDB.remaining_amount)).scalar() or 0
    percent_paid = round(total_paid / (total_paid + total_remaining) * 100, 2) if (total_paid + total_remaining) else 0
    percent_remaining = 100 - percent_paid
    return {
        "Total Collected": total_paid,
        "Total Remaining": total_remaining,
        "Collected %": percent_paid,
        "Pending %": percent_remaining
    }
