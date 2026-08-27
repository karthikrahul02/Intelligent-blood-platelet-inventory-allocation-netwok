def calculate_transfer(
    source_inventory: int,
    source_demand: int,
    destination_inventory: int,
    destination_demand: int
):
    source_surplus = max(
        0,
        source_inventory - source_demand
    )

    destination_shortage = max(
        0,
        destination_demand - destination_inventory
    )

    transfer_units = min(
        source_surplus,
        destination_shortage
    )

    if transfer_units == 0:
        return {
            "transfer_required": False,
            "units": 0
        }

    if destination_shortage >= 50:
        priority = "HIGH"
    elif destination_shortage >= 20:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "transfer_required": True,
        "units": transfer_units,
        "priority": priority
    }