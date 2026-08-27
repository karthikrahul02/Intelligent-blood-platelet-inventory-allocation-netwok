from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.hospitals import router as hospitals_router
from app.api.inventory import router as inventory_router
from app.api.network import router as network_router
from app.database.connection import engine
from app.database.base import Base
from app.api.transfer import router as transfers_router 



app = FastAPI(
    title="Hospital Inventory Optimization API",
    description="Backend API for hospital inventory and transfer optimization",
    version="1.0.0",
)


app.include_router(health_router)
app.include_router(hospitals_router)
app.include_router(inventory_router)


@app.get("/")
def root():
    return {
        "message": "Hospital Inventory Optimization API",
        "status": "running"
    }
app.include_router(network_router)

Base.metadata.create_all(bind=engine)

app.include_router(transfers_router)