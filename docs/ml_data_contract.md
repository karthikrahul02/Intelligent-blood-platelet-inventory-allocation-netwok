# ML/Data contract for backend integration

This is a proposed contract for the ML/Data component. Coordinate field names with the backend owner before integration.

## Forecast input fields
- `hospital_id` (string/category)
- `blood_group` (string/category)
- `date` (date)
- recent daily `daily_demand` history (non-negative units)
- optional `emergency_event` indicator if known at prediction time

## Forecast output
One row per hospital and blood group:
- `hospital_id`
- `blood_group`
- `forecast_date`
- `predicted_demand` (non-negative numeric estimate, not a guaranteed integer)

## Risk input/output concepts
The backend may combine `predicted_demand` with:
- current usable inventory
- confirmed incoming units and their arrival times
- batch expiry dates
- compatibility constraints
- transfer time and capacity

Projected shortage in its simplest form:
`current usable inventory + confirmed incoming units - predicted demand`

This calculation is only valid for a defined forecast horizon and should not count expired/unusable stock as available.

## Limitations
The current ML model is trained on synthetic records and is suitable for capstone demonstration only. It is not a validated clinical decision system.
