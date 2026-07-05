import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import interactions, dashboard, servers

logging.basicConfig(level=logging.INFO)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Discord Slash-Command Bot")

# Dashboard is a separate frontend origin in dev; lock this down to your
# deployed frontend URL in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
