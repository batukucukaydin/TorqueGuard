# Operating guide

Python 3.10+ is required. TorqueGuard has no runtime dependencies and runs directly from the repository root.

## Dashboard

```sh
python3 -m torqueguard serve
```

Open http://127.0.0.1:8765. Select a preset, adjust the base operating conditions and run a comparison. The event timeline lets you add, edit or remove timed input changes. Choose **Apply timeline & compare** to apply edits. Rows sharing a timestamp are grouped into one atomic event; their first row supplies the event label. The same signal cannot appear twice at the same timestamp.

Events override the base schedule for their own signal and persist until updated again. Setting a throttle event to zero keeps throttle zero until another throttle event re-enables demand. SOC and vehicle speed are calculated by the plant and cannot be overwritten by input events.

Scrub the trace cursor to inspect sector, weather, cap, brake, clutch, controller state and SOC. Vertical chart markers indicate scheduled events; hover a marker to see its label. The green background marks sustained high throttle with brake released and clutch engaged; it does not imply energy/grip eligibility for the liveness monitor.

Select **Temporal event sequences** in the campaign search profile to investigate input order and dwell time. A report can be exported or its first counterexample loaded into the event editor.

## CLI replay and export

```sh
python3 -m torqueguard replay --scenario wet_sector_release --output reports/sector-release.json --csv reports/sector-release.csv
python3 -m torqueguard replay --scenario energy_boundary --output reports/energy-boundary.json
```

Run reproducible campaigns:

```sh
python3 -m torqueguard campaign --profile boundary --cases 1000 --seed 2026 --output reports/boundary.json
python3 -m torqueguard campaign --profile temporal --cases 1000 --seed 2026 --output reports/temporal.json
python3 -m torqueguard replay --input reports/temporal.json --output reports/temporal-witness.json
```

Campaigns default to the boundary profile. Exit code 1 indicates that the corrected controller violated a monitored property. Use `--fail-on faulty` to check fault detection or `--fail-on none` for exploratory runs. Browser campaigns allow at most 10,000 cases; the CLI permits up to 1,000,000. Runs are sequential and CPU-bound.

## Scenario files

`replay --input` accepts a scenario JSON, exported replay JSON or a campaign report containing a counterexample. Missing scenario fields use their defaults.

```json
{
  "name": "Timed sector release",
  "duration_s": 6,
  "events": [
    {"time_s": 1, "label": "Wet sector entry", "wet": true, "restricted_sector": true, "sector": 1},
    {"time_s": 2, "label": "Restart request", "throttle": 0.85, "brake": 0},
    {"time_s": 4, "label": "Sector exit", "restricted_sector": false, "sector": 2, "deployment_limit_kw": 350}
  ]
}
```

An event requires a timestamp, an optional label and at least one supported signal. Event arrays are strictly ordered, contain at most 32 events and align to the 20 ms sample grid. Timestamps must be earlier than the simulation horizon. The horizon must also align to the 20 ms grid. Time-zero events change the initial external inputs. All changes at one timestamp belong in the same object.

Numeric signal ranges: throttle/brake/grip [0, 1], deployment cap [0, 350] kW, sector integer [0, 99]. Wet mode, sector restriction, clutch engagement and ICE availability are booleans. The dashboard presents throttle and brake as percentages; JSON uses normalized fractions.

The base driver schedule brakes at 80% until `hold_s` and then requests the scenario throttle. `brake_overlap` keeps braking active. An event overrides only its specified fields, so a sector event alone does not change driver inputs.

## Automated checks

```sh
python3 -m unittest discover -s tests -v
node --check torqueguard/web/app.js
```

The HTTP tests open a temporary loopback port. The dashboard serves only on 127.0.0.1. Stop it with Ctrl+C.
