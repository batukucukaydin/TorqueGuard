# TorqueGuard

**Hybrid Power Unit State-Space Validator** — a local engineering laboratory that detects sustained torque starvation in a stateful, closed-loop hybrid powertrain model.

The project is inspired by the October 2026 Bahrain GP in Malaysia incident. It injects a **synthetic** controller fault; it does not reproduce, reverse engineer or certify actual FIA or team ECU software. A passing campaign means the defined properties passed on the sampled model trajectories, not that a real power unit is safe.

## Run locally

Python 3.10+; no runtime packages or installation required.

```sh
python3 -m torqueguard serve
```

Open http://127.0.0.1:8765. Compare controllers, change operating conditions, scrub telemetry, run a seeded campaign and export a replay or counterexample report. The English interface and reports are intended for a technical portfolio; the incident analysis is available in Turkish in [docs/incident-analysis.md](docs/incident-analysis.md).

```sh
python3 -m unittest discover -s tests -v
python3 -m torqueguard replay --output reports/wet-replay.json --csv reports/wet-trace.csv
python3 -m torqueguard campaign --cases 1000 --seed 2026 --output reports/campaign.json
python3 -m torqueguard replay --input reports/campaign.json --output reports/counterexample.json
```

Campaign commands fail with exit code 1 when the corrected controller violates a monitored property. Use `--fail-on faulty` to check fault detection or `--fail-on none` for exploratory runs. The browser limits campaigns to 10,000 trajectories; the CLI permits up to 1,000,000. Large runs are CPU-bound and execute sequentially. Reports retain only bounded first witnesses; replay regenerates full telemetry.

## What runs

`Scenario → driver schedule → controller → torque arbitration → plant → next state → monitor`

- Fixed 20 ms step. The vehicle brakes, waits at a near-standstill, then receives a sustained throttle request. Each controller owns its own vehicle speed and SOC trajectory.
- Controller modes: `COAST`, `RECOVERY`, `WET_HOLD`, `DEPLOY`, `ICE_ONLY`, `INHIBITED`.
- Injected fault: wet + restricted sector + speed below 3 km/h + engine RPM below 4,500 enters a recovery latch. Exit requires speed ≥ 5 km/h; generator torque cancels available ICE torque. This circular guard prevents the vehicle accelerating to the exit speed.
- Corrected policy: brake and clutch guards first, then driver demand releases recovery. Deployment remains capped; ICE fallback is available at the SOC reserve.
- Plant: wheel torque, grip envelope, vehicle acceleration, rolling/aero resistance, signed MGU-K power, battery energy integration. Torque at standstill is finite; wheel power at standstill is zero.
- Campaign: seeded sampling includes speed thresholds, SOC boundaries, throttle thresholds, wet/sector flags, grip, power caps, brake overlap, clutch and engine availability. Reports expose observed states, transitions and boolean condition combinations. These are **sampled coverage counts**, not exhaustive state-space coverage percentages.

## Properties

| Property | Condition |
| --- | --- |
| `TORQUE_LIVENESS` | Throttle ≥ 70%, brake < 5%, clutch engaged and modeled available torque > 150 Nm: wheel torque must not remain below 100 Nm for 0.50 s. |
| `DEPLOYMENT_LIMIT` | Positive MGU-K mechanical wheel power stays within the configured kW cap. |
| `SOC_BOUNDS` | SOC remains within [0, 1]. Reserve and energy integration are additionally regression-tested. |
| `BRAKE_PRIORITY` | Brake requests do not produce positive drive-axle torque. |

Exemptions reset the response timer. A single low-torque sample is not a fault. Negative MGU-K power denotes harvesting; positive denotes propulsion. Sample inputs (`speed_kph`, `soc`) belong to the beginning of the step; `next_speed_kph` and `next_soc` are the resulting values.

## Evidence and assumptions

The [FIA investigation, 8 October 2026](https://api.fia.com/news/fia-concludes-investigation-bahrain-gp-malaysia-formation-lap-software-bug) confirms low RPM and restricted sectors with unrecoverable power loss, and confirms earlier simulations and FP1 testing. The precise state transition and ICE/recharge interaction remain undisclosed. The model's 250 kW cap is a configurable assumption, not a complete transcription of the FIA statement's “250kW power reduction”.

All calibrated values, equations and scope limitations are listed in [docs/model.md](docs/model.md). A 4 MJ battery, 800 kg mass, grip factor and gearing are illustrative parameters. The model does not include a battery voltage/current/thermal model, clutch slip, tyre slip, gear selection, validated engine maps, full FIA energy-per-lap counters, a multisector track or hardware-in-the-loop integration.

## Project layout

```text
torqueguard/model.py       controller, plant and temporal monitor
torqueguard/validation.py  paired replay and seeded campaigns
torqueguard/server.py      loopback HTTP API and dashboard
torqueguard/web/           dependency-free telemetry interface
tests/                    model physics, fault/fix and HTTP boundary checks
docs/                     incident evidence and modeling contract
```

This MVP establishes a reviewable portfolio baseline: an observed symptom, an explicit fault hypothesis, a reproducible counterexample, a control change and regression evidence. Next steps are hypothesis-specific fault plugins, temporal input/sector generation, automated scenario minimization, a requirements-to-test traceability matrix and an FMI/Simulink or C-controller adapter. A team-facing presentation should describe it as a validation methodology demo, not as a recovered FIA bug or an exhaustive verifier.
