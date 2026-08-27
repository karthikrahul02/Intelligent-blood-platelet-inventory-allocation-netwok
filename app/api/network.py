from fastapi import APIRouter

router = APIRouter(
    prefix="/network",
    tags=["Network"]
)


@router.get("/status")
def network_status():
    return {
        "status": "operational",
        "hospitals_connected": 2
    }