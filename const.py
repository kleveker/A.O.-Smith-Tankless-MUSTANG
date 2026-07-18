"""Constants for A. O. Smith Tankless integration."""

DOMAIN = "aosmith_tankless"
MANUFACTURER = "A. O. Smith"

# Coordinator update interval (seconds)
UPDATE_INTERVAL = 30

# Consecutive failed polls tolerated (serving cached data) before
# entities are marked unavailable. The iCOMM cloud regularly drops
# single polls for 30s-2min; one blip should not flap ~20 entities.
FAILURE_TOLERANCE = 3

# Min/max setpoint bounds (°F) — API enforces temperatureSetpointMaximum
MIN_TEMP = 100
MAX_TEMP = 140
