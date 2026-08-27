
from fastapi import APIRouter
from app.services.optimization_service import calculate_transfer



router = APIRouter(
    prefix="/transfers",
    tags=["Transfers"]
)


@router.get("/recommendations")
def get_transfer_recommendation():

    result = calculate_transfer(
        source_inventory=100,
        source_demand=40,
        destination_inventory=10,
        destination_demand=70
    )

    return {
        "source_hospital": "Hospital A",
        "destination_hospital": "Hospital B",
        "item": "Paracetamol",
        "units": result["units"],
        "priority": result.get("priority"),
        "recommendation": result
    }