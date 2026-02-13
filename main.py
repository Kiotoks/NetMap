from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

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
    ip = Column(String)
    plano = Column(String)

    # PC-specific fields
    cpu = Column(String, nullable=True)
    ram = Column(Integer, nullable=True)
    gpu = Column(String, nullable=True)

class DeviceConnection(Base):
    __tablename__ = "connections"
    id = Column(Integer, primary_key=True, index=True)
    from_device_id = Column(Integer, ForeignKey("devices.id"))
    to_device_id = Column(Integer, ForeignKey("devices.id"))
    connection_type = Column(String, default="ethernet")

    from_device = relationship("Device", foreign_keys=[from_device_id])
    to_device = relationship("Device", foreign_keys=[to_device_id])

Base.metadata.create_all(bind=engine)

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

    if device_id:
        # update existing
        db_device = db.query(Device).get(device_id)
        if not db_device:
            db.close()
            raise HTTPException(status_code=404, detail="Device not found")
        for k, v in device.items():
            setattr(db_device, k, v)
    else:
        # new device
        db_device = Device(**device)
        db.add(db_device)

    db.commit()
    db.refresh(db_device)
    db.close()
    return db_device

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
