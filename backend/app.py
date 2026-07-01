import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .routes import router
from .database import engine, Base
from .config import settings

# Create required directories
os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
os.makedirs(settings.OUTPUTS_DIR, exist_ok=True)
os.makedirs(settings.LOGS_DIR, exist_ok=True)

# Setup logging
log_level = logging.DEBUG if settings.DEBUG else logging.INFO
logging.basicConfig(
    filename=os.path.join(settings.LOGS_DIR, "app.log"),
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Also log to console
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
logging.getLogger().addHandler(console_handler)

# Init Database Models
Base.metadata.create_all(bind=engine)

app = FastAPI(title="RunPod API Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Mount static files at the root (must be placed after other routes to not override them)
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
