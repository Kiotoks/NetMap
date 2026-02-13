from fastapi import FastAPI, Request
from fastapi import Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import (
    create_engine, Column, Integer, String,
    ForeignKey, DateTime, Text, CheckConstraint
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# DATABASE SETUP
# =========================

DATABASE_URL = "sqlite:///./devices.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# =========================
# MODELS
# =========================

class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    type = Column(String)

    x = Column(Integer)
    y = Column(Integer)

    status = Column(String)
    plano = Column(String)
    ip = Column(String)
    usuario = Column(String)
    descripcion = Column(Text)

    last_update = Column(DateTime, default=datetime.utcnow)
    place_name = Column(String)

    # Relationships
    pc = relationship("PC", back_populates="device", uselist=False)

    connections_from = relationship(
        "DeviceConnection",
        foreign_keys="DeviceConnection.from_device_id",
        back_populates="from_device",
        cascade="all, delete"
    )

    connections_to = relationship(
        "DeviceConnection",
        foreign_keys="DeviceConnection.to_device_id",
        back_populates="to_device",
        cascade="all, delete"
    )


class PC(Base):
    __tablename__ = "pcs"

    device_id = Column(Integer, ForeignKey("devices.id"), primary_key=True)

    user = Column(String)
    cpu_benchmark = Column(String)
    cpu = Column(String)
    ram = Column(Integer)
    office = Column(String)
    antivirus = Column(String)
    motherboard = Column(String)
    disks = Column(String)
    ram_ddr = Column(String)
    gpu = Column(String)
    gpu_memory = Column(String)

    device = relationship("Device", back_populates="pc")


class DeviceConnection(Base):
    __tablename__ = "device_connections"

    id = Column(Integer, primary_key=True)

    from_device_id = Column(Integer, ForeignKey("devices.id"))
    to_device_id = Column(Integer, ForeignKey("devices.id"))

    connection_type = Column(String)  # ethernet, fiber
    description = Column(String)

    __table_args__ = (
        CheckConstraint(
            'from_device_id != to_device_id',
            name='no_self_connection'
        ),
    )

    from_device = relationship(
        "Device",
        foreign_keys=[from_device_id],
        back_populates="connections_from"
    )

    to_device = relationship(
        "Device",
        foreign_keys=[to_device_id],
        back_populates="connections_to"
    )


# =========================
# DEVICE TYPE REGISTRY
# =========================

DEVICE_TYPE_MODELS = {
    "pc": PC,
    # Add more types here later
}


# Create tables
Base.metadata.create_all(bind=engine)


# =========================
# STATIC + TEMPLATES
# =========================

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# =========================
# ROUTES
# =========================

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# =========================
# CREATE DEVICE (POLYMORPHIC)
# =========================

@app.post("/api/devices")
def create_device(payload: dict):
    db = SessionLocal()

    try:
        device_type = payload.get("type")

        if not device_type:
            return {"error": "Device type is required"}

        if device_type not in DEVICE_TYPE_MODELS:
            return {"error": f"Unsupported device type: {device_type}"}

        # Extract base fields automatically
        base_columns = {c.name for c in Device.__table__.columns}

        base_data = {
            k: v for k, v in payload.items()
            if k in base_columns
        }

        new_device = Device(**base_data)
        db.add(new_device)
        db.flush()  # Get ID before commit

        # Dynamically create subtype
        subtype_model = DEVICE_TYPE_MODELS[device_type]

        subtype_columns = {
            c.name for c in subtype_model.__table__.columns
            if c.name != "device_id"
        }

        subtype_data = {
            k: v for k, v in payload.items()
            if k in subtype_columns
        }

        subtype_instance = subtype_model(
            device_id=new_device.id,
            **subtype_data
        )

        db.add(subtype_instance)

        db.commit()
        db.refresh(new_device)

        return {
            "message": "Device created successfully",
            "device_id": new_device.id
        }

    except Exception as e:
        db.rollback()
        return {"error": str(e)}

    finally:
        db.close()


# =========================
# GET DEVICES
# =========================

@app.get("/api/devices")
def get_devices(plano: str = Query(None)):
    db = SessionLocal()

    query = db.query(Device)

    if plano:
        query = query.filter(Device.plano == plano)

    devices = query.all()
    db.close()
    return devices


# =========================
# CREATE CONNECTION
# =========================

@app.post("/api/connections")
def create_connection(connection: dict):
    db = SessionLocal()

    try:
        new_connection = DeviceConnection(**connection)
        db.add(new_connection)
        db.commit()
        db.refresh(new_connection)
        return new_connection

    except Exception as e:
        db.rollback()
        return {"error": str(e)}

    finally:
        db.close()
