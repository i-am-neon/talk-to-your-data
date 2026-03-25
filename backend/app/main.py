from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes.query import router

app = FastAPI(title="Data Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
