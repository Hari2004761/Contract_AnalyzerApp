from database import Session, User, SearchHistory
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Request
from fastapi.responses import FileResponse
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, field_validator
from passlib.context import CryptContext
import os
import uuid
import logging
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="Contract Risk Analyzer API", version="1.0")
app.state.limiter = limiter


async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many attempts. Please wait before trying again."}
    )


app.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    request.state.view_rate_limit = None
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def serve_frontend():
    return FileResponse("frontend.html")


load_dotenv()

os.environ["TOKENIZERS_PARALLELISM"] = "false"
from processpdf import process_pdf
import jwt
from datetime import datetime, timedelta, timezone

ANALYZED_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"application/pdf"}

logger = logging.getLogger(__name__)

password = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()


def get_ip_and_username(request: Request) -> str:
    ip = get_remote_address(request)
    try:
        import asyncio
        body = asyncio.get_event_loop().run_until_complete(
            request.json()
        )
        username = body.get("username", "unknown")
    except:
        username = "unknown"
    return f"{ip}:{username}"


class UserCreate(BaseModel):
    username: str
    password: str
    consent_given: bool

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        if not any(c in "!@#$%^&*" for c in v):
            raise ValueError("Password must contain at least one special character (!@#$%^&*)")
        return v


@app.post("/signup/")
@limiter.limit("10/hour")
def create_user(
        request: Request,
        user: UserCreate,
        db: Session = Depends(get_db)
):
    if not user.consent_given:
        raise HTTPException(status_code=400, detail="You must consent to data processing to create an account.")

    existing_user = db.query(User).filter(User.username == user.username).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken,choose a different one!")

    hashed_password = password.hash(user.password)

    new_user = User(
        username=user.username,
        password_hash=hashed_password,
        consent_given=True,
        consent_timestamp=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()

    db.refresh(new_user)

    return {"message": f"User {new_user.username} created successfully!", "user_id": new_user.id}


SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"


class UserLogin(BaseModel):
    username: str
    password: str


@app.post("/login")
@limiter.limit("5/minute", key_func=get_ip_and_username)
@limiter.limit("20/minute")
def login(request: Request, user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()

    # Check account lockout
    if db_user and db_user.locked_until:
        if db_user.locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=403,
                detail="Account locked due to too many failed attempts. Try again later."
            )

    # Verify credentials
    if not db_user or not password.verify(user.password, db_user.password_hash):
        if db_user:
            db_user.failed_login_attempts = (db_user.failed_login_attempts or 0) + 1
            if db_user.failed_login_attempts >= 5:
                db_user.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
                db_user.failed_login_attempts = 0
            db.commit()
        raise HTTPException(status_code=401, detail="Invalid Username or Password")

    # Successful login — reset lockout state
    db_user.failed_login_attempts = 0
    db_user.locked_until = None
    db.commit()

    badge_data = {
        "sub": db_user.username,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    access_token = jwt.encode(badge_data, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "bearer"}


security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        username: str = payload.get("sub")

        if username is None:
            raise HTTPException(status_code=401, detail="Badge is missing a username")

        return username

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Your token has expired,Please log in again!.")

    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid security token!")


@app.get("/download/{filename}")
def get_file(
        filename: str,
        background_tasks: BackgroundTasks,
        current_user: str = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    safe_name = os.path.basename(filename)
    full_path = os.path.join(ANALYZED_DIR, safe_name)

    if not full_path.startswith(ANALYZED_DIR):
        raise HTTPException(status_code=400, detail="Invalid filename")

    user_record = db.query(User).filter(User.username == current_user).first()
    if not user_record:
        raise HTTPException(status_code=401, detail="User not found")

    owned = db.query(SearchHistory).filter(
        SearchHistory.user_id == user_record.id,
        SearchHistory.download_url == safe_name
    ).first()

    if not owned:
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    background_tasks.add_task(os.remove, full_path)
    return FileResponse(full_path)


@app.post("/analyze/")
@limiter.limit("10/minute")
def analyze_contract(
        request: Request,
        file: UploadFile = File(...),
        current_user: str = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    unique_id = str(uuid.uuid4())[:8]
    output_pdf_name = f"analyzed_{unique_id}.pdf"
    temp_filepath = f"temp_{unique_id}.pdf"

    with open(temp_filepath, "wb") as buffer:
        size = 0
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                buffer.close()
                os.remove(temp_filepath)
                raise HTTPException(status_code=413, detail="File too large. Maximum size is 10MB")
            buffer.write(chunk)

    try:
        risks = process_pdf(temp_filepath, output_pdf_name)

        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)

        user_record = db.query(User).filter(User.username == current_user).first()
        if not user_record:
            raise HTTPException(status_code=401, detail="User not found")

        new_history = SearchHistory(
            user_id=user_record.id,
            filename=file.filename,
            risks=len(risks),
            download_url=output_pdf_name
        )
        db.add(new_history)
        db.commit()
        return {
            "status": "success",
            "total_risks": len(risks),
            "download_url": f"/download/{output_pdf_name}",
            "risks": risks,
            "saved_to_database": True
        }
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        if os.path.exists(output_pdf_name):
            os.remove(output_pdf_name)
        logger.error("Error processing file '%s': %s", file.filename, e, exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred while processing the file")


@app.get("/history/")
def get_user_history(
        current_user: str = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    user_record = db.query(User).filter(User.username == current_user).first()
    if not user_record:
        raise HTTPException(status_code=401, detail="User not found")

    past_searches = db.query(SearchHistory).filter(SearchHistory.user_id == user_record.id).all()

    return {
        "status": "success",
        "total_searches": len(past_searches),
        "history": past_searches
    }


@app.post("/logout")
def logout(
        current_user: str = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    user_record = db.query(User).filter(User.username == current_user).first()
    if not user_record:
        raise HTTPException(status_code=401, detail="User not found")

    pending = db.query(SearchHistory).filter(
        SearchHistory.user_id == user_record.id,
        SearchHistory.download_url.isnot(None)
    ).all()

    deleted = 0
    for record in pending:
        full_path = os.path.join(ANALYZED_DIR, record.download_url)
        if os.path.exists(full_path):
            os.remove(full_path)
            deleted += 1

    return {"message": "Logged out successfully", "files_deleted": deleted}
