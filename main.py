from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "sqlite:///./devices.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class DeviceDB(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    type = Column(String)
    x = Column(Integer)
    y = Column(Integer)
    status = Column(String)
    ip = Column(String)


Base.metadata.create_all(bind=engine)


class Device(BaseModel):
    name: str
    type: str
    x: int
    y: int
    status: str
    ip: str


@app.get("/devices")
def get_devices():
    db = SessionLocal()
    devices = db.query(DeviceDB).all()
    return devices


@app.post("/devices")
def create_device(device: Device):
    db = SessionLocal()
    new_device = DeviceDB(**device.dict())
    db.add(new_device)
    db.commit()
    db.refresh(new_device)
    return new_device
