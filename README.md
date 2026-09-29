# Ecobee automation

Cloud-only Ecobee automation for the Dauphin Island beach house using:

- SmartThings cloud-to-cloud Ecobee integration
- GitHub Actions
- WeatherFlow Tempest
- Google Sheets rental schedule

## Current status

SmartThings discovery was successfully verified on September 29, 2026.

All three Ecobee thermostats are visible to GitHub Actions through SmartThings:

- Kitchen n Living Room
- Bedrooms
- Beach House

SmartThings read access and live thermostat control have both been verified against the Mandeville Bedrooms Ecobee. A live cooling-setpoint change was accepted by SmartThings and independently verified from the thermostat state within 2 seconds.

Automatic Beach House control is intentionally disabled in `config.json` until the complete control path and data sources are verified.

## Beach House targets

| State | Cooling | Heating |
|---|---:|---:|
| Occupied | 71 F | 68 F |
| Vacant / economy | 74 F | 64 F |

Mode logic:

- Tempest outdoor temperature > 70 F: cooling
- Tempest outdoor temperature < 65 F: heating
- 65-70 F: keep current HVAC mode

Rental timing:

- Check-in: 4:00 PM local
- Check-out: 10:00 AM local
- Time zone: America/Chicago (handles CST/CDT automatically)

Tempest device serial: `ST-00221346`

## SmartThings API test setup

SmartThings Personal Access Tokens created now expire after 24 hours, so the PAT is only for initial testing. The permanent automation will use OAuth with refresh-token handling.

### GitHub Actions secret

Repository:

`Settings -> Secrets and variables -> Actions`

Required secret:

`SMARTTHINGS_TOKEN`

Never commit the token to the repository.

### Device discovery

Workflow:

`Actions -> SmartThings - List thermostats -> Run workflow`

This has already been verified successfully.

### Safe Mandeville test

Workflow:

`Actions -> Test Mandeville thermostat -> Run workflow`

Start with:

- Thermostat: Kitchen n Living Room or Bedrooms
- Mode: match the thermostat's current mode
- Temperature: choose a harmless nearby target
- Dry run: true

The dry run reads and prints the thermostat state but sends no command.

After the dry run is verified, rerun with `dry_run = false` for one controlled live test.

## Manual Beach House workflow

A separate `Manual Beach House thermostat` workflow exists.

Keep `dry_run = true` until the Mandeville live-control test succeeds.

## Command safety and verification

The SmartThings client:

- Requires a complete thermostat device profile.
- Matches thermostats by exact SmartThings label.
- Rejects requested setpoints outside 60-80 F.
- Refuses a live setpoint change unless SmartThings reports the relevant setpoint in Fahrenheit.
- Checks that the requested heat/cool mode is supported when SmartThings reports supported modes.
- Uses SmartThings `setThermostatMode`, `setCoolingSetpoint`, and `setHeatingSetpoint` commands.
- Sends mode and setpoint together in one SmartThings command request.
- Requires every SmartThings command result to be `ACCEPTED`.
- Polls the thermostat after a live command and verifies that the requested mode/setpoint actually appear.
- Masks most of the SmartThings device ID in new workflow logs.
- Serializes thermostat-control workflows so two manual/control jobs cannot change a thermostat at the same time.

## Automatic-control gate

Automatic Beach House control remains disabled until:

1. ~~Mandeville dry-run inspection succeeds.~~ Verified 2026-09-29.
2. ~~One Mandeville live-control test succeeds.~~ Verified 2026-09-29.
3. Permanent SmartThings OAuth is configured.
4. Tempest data access is verified.
5. Rental spreadsheet access and date parsing are verified.
6. Arrival preconditioning logic is tested in dry-run mode.
