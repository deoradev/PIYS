from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import motor.motor_asyncio
import jwt
import bcrypt
import qrcode
import io
import base64
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, List
import os
from dotenv import load_dotenv
from models import (
    User, Vehicle, Message, ParkingSpace, QRCode as QRCodeModel, 
    UserCreate, UserLogin, VehicleCreate, MessageCreate, 
    ParkingSpaceCreate, QRCodeCreate, UserResponse, VehicleResponse,
    MessageResponse, ParkingSpaceResponse, QRCodeResponse
)

load_dotenv()

app = FastAPI(title="PIYS API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL)
database = client.piys_db

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        
        user = await database.users.find_one({"email": email})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        
        return User(**user)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def generate_qr_code(data: str) -> str:
    """Generate QR code and return as base64 string"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def generate_unique_code(length: int = 8) -> str:
    """Generate unique alphanumeric code"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "PIYS API is running!"}

@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate):
    """Register new user"""
    # Check if user already exists
    existing_user = await database.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password
    hashed_password = hash_password(user_data.password)
    
    # Create user
    user = User(
        email=user_data.email,
        name=user_data.name,
        phone=user_data.phone,
        hashed_password=hashed_password,
        created_at=datetime.utcnow()
    )
    
    result = await database.users.insert_one(user.dict())
    user.id = str(result.inserted_id)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        phone=user.phone,
        access_token=access_token,
        token_type="bearer"
    )

@app.post("/auth/login", response_model=UserResponse)
async def login(user_data: UserLogin):
    """Login user"""
    user = await database.users.find_one({"email": user_data.email})
    if not user or not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return UserResponse(
        id=str(user["_id"]),
        email=user["email"],
        name=user["name"],
        phone=user["phone"],
        access_token=access_token,
        token_type="bearer"
    )

@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        phone=current_user.phone
    )

@app.post("/vehicles", response_model=VehicleResponse)
async def add_vehicle(vehicle_data: VehicleCreate, current_user: User = Depends(get_current_user)):
    """Add new vehicle"""
    vehicle = Vehicle(
        user_id=current_user.id,
        license_plate=vehicle_data.license_plate,
        make=vehicle_data.make,
        model=vehicle_data.model,
        color=vehicle_data.color,
        created_at=datetime.utcnow()
    )
    
    result = await database.vehicles.insert_one(vehicle.dict())
    vehicle.id = str(result.inserted_id)
    
    return VehicleResponse(**vehicle.dict())

@app.get("/vehicles", response_model=List[VehicleResponse])
async def get_vehicles(current_user: User = Depends(get_current_user)):
    """Get user's vehicles"""
    vehicles = await database.vehicles.find({"user_id": current_user.id}).to_list(100)
    return [VehicleResponse(id=str(v["_id"]), **{k: v for k, v in v.items() if k != "_id"}) for v in vehicles]

@app.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: str, current_user: User = Depends(get_current_user)):
    """Delete vehicle"""
    result = await database.vehicles.delete_one({"_id": vehicle_id, "user_id": current_user.id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return {"message": "Vehicle deleted successfully"}

@app.post("/spaces", response_model=ParkingSpaceResponse)
async def add_parking_space(space_data: ParkingSpaceCreate, current_user: User = Depends(get_current_user)):
    """Add new parking space"""
    space = ParkingSpace(
        user_id=current_user.id,
        title=space_data.title,
        address=space_data.address,
        hourly_rate=space_data.hourly_rate,
        daily_rate=space_data.daily_rate,
        available=True,
        created_at=datetime.utcnow()
    )
    
    result = await database.parking_spaces.insert_one(space.dict())
    space.id = str(result.inserted_id)
    
    return ParkingSpaceResponse(**space.dict())

@app.get("/spaces", response_model=List[ParkingSpaceResponse])
async def get_parking_spaces():
    """Get all available parking spaces"""
    spaces = await database.parking_spaces.find({"available": True}).to_list(100)
    return [ParkingSpaceResponse(id=str(s["_id"]), **{k: v for k, v in s.items() if k != "_id"}) for s in spaces]

@app.get("/my-spaces", response_model=List[ParkingSpaceResponse])
async def get_my_parking_spaces(current_user: User = Depends(get_current_user)):
    """Get user's parking spaces"""
    spaces = await database.parking_spaces.find({"user_id": current_user.id}).to_list(100)
    return [ParkingSpaceResponse(id=str(s["_id"]), **{k: v for k, v in s.items() if k != "_id"}) for s in spaces]

@app.post("/qrcodes", response_model=QRCodeResponse)
async def generate_qr_code_endpoint(qr_data: QRCodeCreate, current_user: User = Depends(get_current_user)):
    """Generate QR code for parking space"""
    # Generate unique code
    unique_code = generate_unique_code()
    
    # Create QR code data
    qr_code_data = f"PIYS:{unique_code}:{qr_data.space_id}:{current_user.id}"
    qr_image = generate_qr_code(qr_code_data)
    
    # Save to database
    qr_code = QRCodeModel(
        user_id=current_user.id,
        space_id=qr_data.space_id,
        unique_code=unique_code,
        qr_data=qr_code_data,
        qr_image=qr_image,
        created_at=datetime.utcnow()
    )
    
    result = await database.qrcodes.insert_one(qr_code.dict())
    qr_code.id = str(result.inserted_id)
    
    return QRCodeResponse(**qr_code.dict())

@app.post("/scan/{unique_code}")
async def scan_qr_code(unique_code: str):
    """Scan QR code and get parking space info"""
    qr_code = await database.qrcodes.find_one({"unique_code": unique_code})
    if not qr_code:
        raise HTTPException(status_code=404, detail="Invalid QR code")
    
    space = await database.parking_spaces.find_one({"_id": qr_code["space_id"]})
    if not space:
        raise HTTPException(status_code=404, detail="Parking space not found")
    
    return {
        "space": ParkingSpaceResponse(id=str(space["_id"]), **{k: v for k, v in space.items() if k != "_id"}),
        "qr_code": QRCodeResponse(id=str(qr_code["_id"]), **{k: v for k, v in qr_code.items() if k != "_id"})
    }

@app.post("/messages", response_model=MessageResponse)
async def send_message(message_data: MessageCreate, current_user: User = Depends(get_current_user)):
    """Send message to space owner"""
    message = Message(
        sender_id=current_user.id,
        recipient_id=message_data.recipient_id,
        space_id=message_data.space_id,
        content=message_data.content,
        created_at=datetime.utcnow()
    )
    
    result = await database.messages.insert_one(message.dict())
    message.id = str(result.inserted_id)
    
    return MessageResponse(**message.dict())

@app.get("/messages", response_model=List[MessageResponse])
async def get_messages(current_user: User = Depends(get_current_user)):
    """Get user's messages"""
    messages = await database.messages.find({
        "$or": [
            {"sender_id": current_user.id},
            {"recipient_id": current_user.id}
        ]
    }).to_list(100)
    return [MessageResponse(id=str(m["_id"]), **{k: v for k, v in m.items() if k != "_id"}) for m in messages]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)