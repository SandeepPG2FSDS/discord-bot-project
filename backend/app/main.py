import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.database import Base, engine
from app.routes import interactions, dashboard, servers

logging.basicConfig(level=logging.INFO)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Discord Slash-Command Bot")

# Dashboard is a separate frontend origin from the API. Set ALLOWED_ORIGINS
# to your deployed frontend URL in production; defaults to "*" for local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(interactions.router)
app.include_router(dashboard.router)
app.include_router(servers.router)
app.include_router(servers.servers_router)


@app.get("/health")
def health():
    return {"status": "ok"}
