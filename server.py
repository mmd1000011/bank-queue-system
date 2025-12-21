from flask import Flask, jsonify, request, render_template
from datetime import datetime
from enum import Enum
import threading
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

app = Flask(__name__)

# -----------------------------
#  تنظیم دیتابیس (SQLite)
# -----------------------------
engine = create_engine("sqlite:///tickets.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class TicketStatus(str, Enum):
    NEW = "New"
    READY = "Ready"
    WAITING = "Waiting"
    CALLED = "Called"
    SERVING = "Serving"
    MISSED = "Missed"
    DONE = "Done"
    CANCELLED = "Cancelled"


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True, index=True)
    status = Column(String(20))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)


Base.metadata.create_all(bind=engine)

lock = threading.Lock()


def create_new_ticket():
    """صدور نوبت جدید و قرار دادن در وضعیت Waiting."""
    with lock:
        db = SessionLocal()
        try:
            last = db.query(Ticket).order_by(Ticket.number.desc()).first()
            next_number = (last.number + 1) if last else 1

            now = datetime.utcnow()
            t = Ticket(
                number=next_number,
                status=TicketStatus.WAITING.value,
                created_at=now,
                updated_at=now,
            )
            db.add(t)
            db.commit()
            db.refresh(t)
            return t
        finally:
            db.close()


def get_next_waiting_ticket():
    """اولین تیکت با وضعیت Waiting را برگردان."""
    db = SessionLocal()
    try:
        t = (
            db.query(Ticket)
            .filter(Ticket.status == TicketStatus.WAITING.value)
            .order_by(Ticket.number.asc())
            .first()
        )
        return t, db
    except:
        db.close()
        raise


# -----------------------------
#   API ها (برای Postman / سرویس‌ها)
# -----------------------------


@app.route("/api/ticket/new", methods=["POST"])
def api_new_ticket():
    t = create_new_ticket()
    return jsonify({
        "message": "New ticket issued",
        "ticket": {
            "id": t.id,
            "number": t.number,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
    }), 201


@app.route("/api/ticket/next", methods=["POST"])
def api_call_next_ticket():
    t, db = get_next_waiting_ticket()
    if t is None:
        db.close()
        return jsonify({"message": "No waiting tickets"}), 200

    t.status = TicketStatus.SERVING.value
    t.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(t)
    db.close()

    return jsonify({
        "message": "Next ticket called",
        "ticket": {
            "id": t.id,
            "number": t.number,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        }
    }), 200


@app.route("/api/ticket/<int:number>/done", methods=["POST"])
def api_ticket_done(number):
    db = SessionLocal()
    try:
        t = db.query(Ticket).filter(Ticket.number == number).first()
        if t is None:
            return jsonify({"error": "Ticket not found"}), 404

        if t.status != TicketStatus.SERVING.value:
            return jsonify({"error": "Ticket is not in Serving state"}), 400

        t.status = TicketStatus.DONE.value
        t.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(t)

        return jsonify({
            "message": "Ticket service finished",
            "ticket": {
                "id": t.id,
                "number": t.number,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
        }), 200
    finally:
        db.close()


@app.route("/api/tickets", methods=["GET"])
def api_list_tickets():
    db = SessionLocal()
    try:
        ts = db.query(Ticket).order_by(Ticket.number.asc()).all()
        return jsonify([
            {
                "id": t.id,
                "number": t.number,
                "status": t.status,
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in ts
        ])
    finally:
        db.close()


# -----------------------------
#   صفحه وب (UI)
# -----------------------------


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
