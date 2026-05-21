"""Constants for A. O. Smith Tankless integration."""

DOMAIN = "aosmith_tankless"
MANUFACTURER = "A. O. Smith"

# Coordinator update interval (seconds)
UPDATE_INTERVAL = 30

# Min/max setpoint bounds (°F) — API enforces temperatureSetpointMaximum
MIN_TEMP = 100
MAX_TEMP = 140
