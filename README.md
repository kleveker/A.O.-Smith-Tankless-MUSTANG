# A. O. Smith Tankless (MUSTANG)

A Home Assistant custom integration for A. O. Smith MUSTANG tankless water heaters (model ATHR-199X3 and similar) connected via the iCOMM Wi-Fi module.

## Requirements

- A. O. Smith MUSTANG tankless water heater (ATHR-199X3 or compatible)
- iCOMM Wi-Fi module installed and connected
- Active A. O. Smith iCOMM account
- Home Assistant 2024.1 or later

## Installation

1. Add this repository to HACS as a custom repository (category: Integration)
2. Download the integration from HACS
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration**
5. Search for **A. O. Smith Tankless (MUSTANG)**
6. Enter your iCOMM email and password

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| Tankless Water Heater | `water_heater` | Temperature setpoint control |
| Recirculation Timer 1 | `switch` | Enable/disable Timer 1 |
| Recirculation Timer 1 Start | `time` | Timer 1 start time |
| Recirculation Timer 1 End | `time` | Timer 1 end time |
| Recirculation Timer 2 | `switch` | Enable/disable Timer 2 |
| Recirculation Timer 2 Start | `time` | Timer 2 start time |
| Recirculation Timer 2 End | `time` | Timer 2 end time |
| Recirculation On-Demand | `switch` | Toggle on-demand recirculation |
| Online Status | `sensor` | Device connectivity status |
| Error Code | `sensor` | Active error code if any |
| Active Alerts | `sensor` | Number of active alerts |
| Firmware Version | `sensor` | Current firmware version |
| Max Setpoint | `sensor` | Maximum allowed temperature |

## Notes

- The integration polls the A. O. Smith cloud API every 60 seconds
- Timer start/end times connect directly to the A. O. Smith cloud — changes may take a few seconds to reflect
- Compatible with the A. O. Smith iCOMM app running alongside this integration
