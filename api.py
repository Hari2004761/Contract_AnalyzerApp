from database import Session, User, SearchHistory
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from passlib.context import CryptContext
import os
import uuid
import logging
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Contract Risk Analyzer API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


class UserCreate(BaseModel):
    username: str
    password: str
    consent_given: bool


@app.post("/signup/")
def create_user(
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
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()

    if not db_user or not password.verify(user.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid Username or Password")

    # JWT Authentication
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
def analyze_contract(
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
