from fastapi import APIRouter

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
)


@router.get("")
def get_inventory():
    return [
        {
            "hospital_id": 1,
            "item_name": "Paracetamol",
            "quantity": 500,
            "expiry_date": "2026-12-31"
        },
        {
            "hospital_id": 2,
            "item_name": "Paracetamol",
            "quantity": 100,
            "expiry_date": "2027-02-28"
        }
    ]