# Ecobee automation

Cloud-only Ecobee automation for the Dauphin Island beach house using:

- SmartThings cloud-to-cloud Ecobee integration
- GitHub Actions
- WeatherFlow Tempest
- Google Sheets rental schedule

## Current status

Phase 1 is in place: SmartThings discovery and manual thermostat test workflows.

Automatic Beach House control is intentionally disabled in `config.json` until SmartThings API control is verified against a Mandeville thermostat.

## Thermostats

- Kitchen n Living
- Bedrooms
- Beach House

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

Tempest device serial: `ST-00221346`

## Phase 1: SmartThings API proof

SmartThings Personal Access Tokens created now expire after 24 hours, so the PAT is only for initial testing. The permanent automation will use OAuth with refresh-token handling.

### 1. Create a temporary SmartThings PAT

Create a PAT in the SmartThings account portal and grant:

- Read devices
- Execute device commands

Do not commit the token to this repository.

### 2. Add the token as a GitHub Actions secret

Repository:

`Settings -> Secrets and variables -> Actions -> New repository secret`

Name:

`SMARTTHINGS_TOKEN`

Value:

the SmartThings PAT

### 3. Run device discovery

Open:

`Actions -> SmartThings - List thermostats -> Run workflow`

Expected thermostat labels:

- Kitchen n Living
- Bedrooms
- Beach House

### 4. Run a safe Mandeville test

Open:

`Actions -> Test Mandeville thermostat -> Run workflow`

Start with:

- Thermostat: Kitchen n Living or Bedrooms
- Mode: match the thermostat's current mode
- Temperature: choose a harmless nearby target
- Dry run: true

The log should show the matched SmartThings device ID and current thermostat state without sending a command.

Once the dry run looks correct, rerun with `dry_run = false` to prove SmartThings can actually change the Ecobee.

## Manual Beach House workflow

A separate manual workflow exists for the Beach House thermostat. Keep `dry_run = true` until the Mandeville API test succeeds.

## Safety

The client rejects requested setpoints outside 60-80 F.

Automatic Beach House control remains disabled until:

1. SmartThings control is verified.
2. Permanent SmartThings OAuth is configured.
3. Tempest data access is verified.
4. Rental spreadsheet access and date parsing are verified.
