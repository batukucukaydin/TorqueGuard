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

## Temporal input extension — model 0.2.0

The event-schedule extension passes **22 automated tests**, including the original checks and eight trajectory/event contract tests. New checks cover exact-tick application, persistent and atomic input updates, sector-release recovery, event-order sensitivity, throttle interruption, delayed clutch engagement, computed SOC reserve crossing, event serialization and seeded temporal witness reproduction. Invalid and off-grid events, unknown signals, duplicate or reversed timestamps and an off-grid horizon are rejected.

| Profile | Seed | Trajectories | Scheduled events | Injected-fault failures | Corrected failures |
| --- | --- | ---: | ---: | ---: | ---: |
| Temporal | 2026 | 100 | 400 | 12 | 0 |
| Temporal | 2026 | 1,000 | 4,017 | 126 | 0 |

The 1,000-case report observes 31 of the 32 five-boolean input combinations within this sampled envelope. This does not establish numeric, state-space or event-order completeness. Earlier results above remain associated with model 0.1.0 and its boundary profile.

The temporal report has been replayed through the CLI and the browser counterexample action. A wet-sector preset produces a baseline violation before recovering at the 4.00 s sector exit. Editing its wet-on event to remain dry changes the baseline result to PASS. The corrected controller passes both sequences. The event editor's atomic grouping has been exercised through Apply timeline & compare.
