from fastapi import FastAPI

from app.database import engine, Base
from app.routers import router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Training Signup API", version="1.0.0")

app.include_router(router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
