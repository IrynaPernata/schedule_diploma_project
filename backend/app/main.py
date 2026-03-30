from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, users, schedules, leaves

app = FastAPI(title="Shift Scheduler API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(leaves.router, prefix="/api/leaves", tags=["leaves"])

@app.get("/")
async def root():
    return {"status": "ok", "app": "Shift Scheduler"}