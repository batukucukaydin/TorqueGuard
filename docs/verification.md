# Verification record — 10 October 2026

Model version: `0.1.0`. Python `3.10.5`. All cases are illustrative model trajectories.

## Automated checks

`python3 -m unittest discover -s tests -v`: **14 tests passed**.

Checks cover the fault and corrected response, dry/unrestricted controls, legitimate torque inhibitions, SOC fallback, finite zero-speed torque/zero power, signed energy integration, full-battery generator headroom, deployment and reserve limits, continuous demand timing, campaign determinism, witness reproduction, invalid inputs and HTTP contracts.

`node --check torqueguard/web/app.js`: passed.

## Campaign results

| Seed | Trajectories | Injected-fault failures | Corrected failures | Rescued cases |
| --- | ---: | ---: | ---: | ---: |
| 2026 | 100 | 18 | 0 | 18 |
| 2026 | 1,000 | 154 | 0 | 154 |
| 2026 | 10,000 | 1,595 | 0 | 1,595 |

The CLI retains JSON reports in `reports/`. The default replay also exports 600 paired telemetry rows to CSV. A campaign witness has been replayed using `--input`; no regenerated seed search is required to replay its scenario.

## Browser checks

Local HTTP dashboard tested with the in-app browser:

- Default wet concertina: baseline fails, corrected passes; 4.00 s maximum starvation and 47.0 km/h corrected final speed.
- Dry restart: both controllers pass.
- Brake overlap: liveness exemption avoids a false failure.
- SOC reserve: corrected ICE-only fallback preserves propulsion.
- Browser campaign: 100 cases, 18 baseline failures, 0 corrected failures; first counterexample loads its own schedule and horizon.
- Desktop 1440 × 1000 and mobile 390 × 844 inspected. Mobile document width equals viewport width (390 px), with no horizontal overflow.

## Interpretation

These checks validate implementation consistency within the documented model and sampled test envelope. They do not establish coverage of all continuous states, all temporal event orderings, actual ECU code, or full FIA regulatory compliance. Counterexample minimization, hardware-in-the-loop testing and actual multisector trajectories remain future work.
