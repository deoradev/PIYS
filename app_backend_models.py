from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# User Models
class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(UserBase):
    id: Optional[str] = None
    hashed_password: str
    created_at: datetime

class UserResponse(UserBase):
    id: str
    access_token: Optional[str] = None
    token_type: Optional[str] = None

# Vehicle Models
class VehicleBase(BaseModel):
    license_plate: str
    make: str
    model: str
    color: str

class VehicleCreate(VehicleBase):
    pass

class Vehicle(VehicleBase):
    id: Optional[str] = None
    user_id: str
    created_at: datetime

class VehicleResponse(VehicleBase):
    id: str
    user_id: str
    created_at: datetime

# Parking Space Models
class ParkingSpaceBase(BaseModel):
    title: str
    address: str
    hourly_rate: float
    daily_rate: Optional[float] = None

class ParkingSpaceCreate(ParkingSpaceBase):
    pass

class ParkingSpace(ParkingSpaceBase):
    id: Optional[str] = None
    user_id: str
    available: bool = True
    created_at: datetime

class ParkingSpaceResponse(ParkingSpaceBase):
    id: str
    user_id: str
    available: bool
    created_at: datetime

# QR Code Models
class QRCodeBase(BaseModel):
    space_id: str

class QRCodeCreate(QRCodeBase):
    pass

class QRCode(QRCodeBase):
    id: Optional[str] = None
    user_id: str
    unique_code: str
    qr_data: str
    qr_image: str
    created_at: datetime

class QRCodeResponse(QRCodeBase):
    id: str
    user_id: str
    unique_code: str
    qr_data: str
    qr_image: str
    created_at: datetime

# Message Models
class MessageBase(BaseModel):
    content: str

class MessageCreate(MessageBase):
    recipient_id: str
    space_id: str

class Message(MessageBase):
    id: Optional[str] = None
    sender_id: str
    recipient_id: str
    space_id: str
    created_at: datetime

class MessageResponse(MessageBase):
    id: str
    sender_id: str
    recipient_id: str
    space_id: str
    created_at: datetime