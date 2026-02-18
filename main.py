from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, CheckConstraint, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "sqlite:///./devices.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# -----------------------
# DATABASE MODELS
# -----------------------

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


Base.metadata.create_all(bind=engine)


DEVICE_TYPE_MODELS = {
    "pc": PC,
    # Add more types here later
}


# -----------------------
# TEMPLATES + STATIC
# -----------------------

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# -----------------------
# DEVICES API
# -----------------------

@app.get("/api/devices")
def get_devices(plano: str = Query(None)):
    db = SessionLocal()
    query = db.query(Device)
    if plano:
        query = query.filter(Device.plano == plano)
    devices = query.all()
    db.close()
    return devices

@app.post("/api/devices")
def create_or_update_device(device: dict):
    db = SessionLocal()
    device_id = device.get("id")
    print(device)

    try:
        device_type = device.get("type")

        if not device_type:
            return {"error": "Device type is required"}

        if device_type not in DEVICE_TYPE_MODELS:
            return {"error": f"Unsupported device type: {device_type}"}

        subtype_model = DEVICE_TYPE_MODELS[device_type]

        if device_id:
            # --------------------
            # UPDATE EXISTING
            # --------------------
            db_device = db.query(Device).get(device_id)
            if not db_device:
                raise HTTPException(status_code=404, detail="Device not found")

            # Update base fields
            base_columns = {c.name for c in Device.__table__.columns}
            for k, v in device.items():
                if k in base_columns:
                    print(k)
                    setattr(db_device, k, v)

            # Update subtype fields
            subtype_instance = db.query(subtype_model).filter_by(device_id=device_id).first()

            subtype_columns = {
                c.name for c in subtype_model.__table__.columns
                if c.name != "device_id"
            }

            subtype_data = {
                k: v for k, v in device.items()
                if k in subtype_columns
            }

            if subtype_instance:
                for k, v in subtype_data.items():
                    setattr(subtype_instance, k, v)
            else:
                # If subtype row doesn't exist, create it
                subtype_instance = subtype_model(
                    device_id=device_id,
                    **subtype_data
                )
                db.add(subtype_instance)

            db.commit()
            db.refresh(db_device)

            return {
                "message": "Device updated successfully",
                "device_id": db_device.id
            }
        else:
            # --------------------
            # CREATE NEW
            # --------------------
            base_columns = {c.name for c in Device.__table__.columns}

            base_data = {
                k: v for k, v in device.items()
                if k in base_columns
            }

            new_device = Device(**base_data)
            db.add(new_device)
            db.flush()  # get ID before commit

            subtype_columns = {
                c.name for c in subtype_model.__table__.columns
                if c.name != "device_id"
            }

            subtype_data = {
                k: v for k, v in device.items()
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

@app.delete("/api/devices/{device_id}")
def delete_device(device_id: int):
    db = SessionLocal()
    device = db.query(Device).get(device_id)
    if device:
        # delete connections
        db.query(DeviceConnection).filter(
            (DeviceConnection.from_device_id == device_id) |
            (DeviceConnection.to_device_id == device_id)
        ).delete(synchronize_session=False)
        db.delete(device)
        db.commit()
    db.close()
    return {"message": "deleted"}

# -----------------------
# CONNECTIONS API
# -----------------------

@app.get("/api/connections")
def get_connections(plano: str = None):
    db = SessionLocal()
    query = db.query(DeviceConnection)
    if plano:
        query = query.join(Device, Device.id == DeviceConnection.from_device_id)\
                     .filter(Device.plano == plano)
    connections = query.all()
    db.close()
    return connections

@app.post("/api/connections")
def create_connection(conn: dict):
    db = SessionLocal()
    new_conn = DeviceConnection(**conn)
    db.add(new_conn)
    db.commit()
    db.refresh(new_conn)
    db.close()
    return new_conn
