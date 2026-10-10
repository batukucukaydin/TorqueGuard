# Modeling contract

## Units and assumptions

| Quantity | Value | Basis |
| --- | --- | --- |
| Integration step | 0.02 s | Fixed discrete-time assumption |
| Vehicle mass | 800 kg | Illustrative, no event calibration |
| Wheel radius | 0.33 m | Illustrative |
| Gear ratio | 14:1 | Fixed effective crank-to-wheel ratio |
| Mechanical/electrical efficiency | 0.92 | Lumped constant assumption |
| Battery energy capacity | 4,000,000 J | Illustrative usable capacity |
| Minimum running ICE RPM | 4,000 rpm | Simplified idle/clutch assumption |
| ICE torque map | 300 Nm × throttle | Simplified crank torque, not measured data |
| MGU-K axle torque request | 3,500 Nm × throttle | Illustrative near-zero-speed saturation |
| Electrical caps | 0–350 kW | Scenario setting; 350 kW contextualized by FIA 2026 material |
| Harvest cap | 100 kW | Model assumption |
| SOC deployment reserve | 0.10 | Model assumption |
| Fault entry / exit | <3 / ≥5 km/h | Synthetic injected fault thresholds |
| Fault RPM threshold | <4,500 rpm | Synthetic, not an FIA disclosed threshold |
| Response property | <100 Nm for ≥0.50 s | Demonstration requirement, not a certified hazard threshold |

The [FIA 2026 refinements](https://api.fia.com/news/refinements-2026-fia-formula-1-regulations-agreed-all-stakeholders) describe 350 kW in key acceleration zones and 250 kW elsewhere; this model does not implement their complete track-dependent rules. A single fixed `restricted_sector` flag expresses one hypothesis. A grip coefficient is a deterministic plant envelope, not real tyre data or a claim about legal traction control.

## Equations

- `wheel_omega = speed_mps / wheel_radius`
- `engine_rpm = max(idle_rpm, wheel_omega × ratio × 60 / (2π))` for an available ICE. This imposes idealized clutch/idle behavior; clutch slip dynamics are omitted.
- `ice_axle_torque = throttle × 300 × ratio × efficiency`
- `mgu_axle_torque = min(throttle × 3500, power_cap / max(wheel_omega, 1), available_battery_power / max(wheel_omega, 1))`
- `grip_axle_torque = grip × mass × g × wheel_radius`; positive combined torque is scaled to this limit.
- `mgu_power = mgu_axle_torque × wheel_omega`. The denominator floor used for torque saturation does not change actual power at zero speed.
- Deployment energy: `ΔE = -P × dt / efficiency`; harvesting energy: `ΔE = -P × dt × efficiency` for signed negative P.
- Available battery power and harvesting headroom are bounded before integration. SOC clipping remains a numerical guard; corrected-controller deployment cannot cross the reserve.
- In the injected fault, requested ICE torque is limited to generator headroom and canceled by negative MGU-K torque. Remaining ICE demand is gated. With a full battery both are zero; a full battery does not create an unlimited energy sink.
- `acceleration = (wheel_torque / radius - brake_force - resistance) / mass`; forward speed is clamped at zero.

The model applies rolling resistance only while moving. Brake force and regeneration are simplified; it is not a complete tyre friction-circle or brake blending model. No acceleration/thermal/voltage validation is implied.

## Temporal property and coverage

The torque-response clock runs only with sustained throttle ≥70%, brake <5%, engaged clutch and independently calculated nominal available axle torque >150 Nm. Nominal torque uses current SOC, cap, engine availability, speed and grip; it does not use the faulty controller output. Legitimate inhibitions reset the timer.

Detection occurs at the beginning of the 25th starving step (`t=2.48 s` for a `t=2.00 s` demand); that step completes the 0.50 s interval. This fixed-step convention has 20 ms resolution.

The campaign enumerates seeded samples from a small boundary-biased parameter set and runs full trajectories. It does **not** enumerate all continuous states, all event orderings or all thresholds. Boolean condition counts have a denominator of 32 for five flags, but do not establish coverage of all their numeric combinations. Witnesses are first failures with the complete scenario and zero-based case index. There is no automated minimization in this MVP.

The two controllers have independent plant feedback. This is a paired comparison of the same external driver schedule, not replaying identical measured speed and SOC through both controllers. Initial braking and wait duration are scripted. A future experiment should vary input order, sector transitions, dwell, clutch release and sample time, add mutation-based monitors and validate against recorded or HIL traces.
