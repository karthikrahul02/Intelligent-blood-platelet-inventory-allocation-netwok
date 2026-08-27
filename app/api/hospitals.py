from fastapi import APIRouter

router = APIRouter(
    prefix="/hospitals",
    tags=["Hospitals"]
)


@router.get("")
def get_hospitals():
    return [
        {
            "id": 1,
            "name": "City Hospital",
            "location": "Bengaluru"
        },
        {
            "id": 2,
            "name": "General Hospital",
            "location": "Electronic City"
        }
    ]