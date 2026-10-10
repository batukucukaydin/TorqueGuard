"""SI-unit, closed-loop longitudinal plant and deliberately synthetic controller fault."""

from dataclasses import dataclass, asdict
from enum import Enum
import math
from .signals import SignalEvent, Inputs, InputSchedule, normalize_events

DT = 0.02
MASS_KG = 800.0
WHEEL_RADIUS_M = 0.33
BATTERY_J = 4_000_000.0  # Model assumption, not homologated hardware data.
IDLE_RPM = 4000.0
GEAR_RATIO = 14.0
EFFICIENCY = 0.92
SOC_RESERVE = 0.10
RESPONSE_DEADLINE_S = 0.50


class State(str, Enum):
    COAST = "COAST"
    RECOVERY = "RECOVERY"
    WET_HOLD = "WET_HOLD"
    DEPLOY = "DEPLOY"
    ICE_ONLY = "ICE_ONLY"
    INHIBITED = "INHIBITED"


@dataclass(frozen=True)
class Scenario:
    name: str = "Wet concertina"
    initial_speed_kph: float = 18.0
    soc: float = 0.60
    grip: float = 0.35
    wet: bool = True
    restricted_sector: bool = True
    deployment_limit_kw: float = 250.0
    throttle: float = 0.85
    brake_overlap: bool = False
    clutch_engaged: bool = True
    engine_available: bool = True
    hold_s: float = 2.0
    duration_s: float = 6.0
    sector: int = 0
    events: tuple[SignalEvent, ...] = ()

    def __post_init__(self):
        ranges = {"initial_speed_kph": (0, 100), "soc": (0, 1), "grip": (0, 1),
                  "deployment_limit_kw": (0, 350), "throttle": (0, 1),
                  "hold_s": (0.5, 4), "duration_s": (1, 10)}
        for key, (low, high) in ranges.items():
            value = getattr(self, key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{key} must be a finite number between {low} and {high}")
        for key in ("wet", "restricted_sector", "brake_overlap", "clutch_engaged", "engine_available"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be boolean")
        if not isinstance(self.name, str) or not 1 <= len(self.name) <= 80:
            raise ValueError("name must contain 1–80 characters")
        if self.duration_s < self.hold_s + 1:
            raise ValueError("duration_s must allow at least 1 second after hold_s")
        if not math.isclose(self.duration_s / DT, round(self.duration_s / DT), abs_tol=1e-8, rel_tol=0):
            raise ValueError("duration_s must align to the 0.02 s sample grid")
        if type(self.sector) is not int or not 0 <= self.sector <= 99:
            raise ValueError("sector must be an integer in [0, 99]")
        object.__setattr__(self, "events", normalize_events(self.events, self.duration_s, DT))

    def to_dict(self):
        return {**asdict(self), "events": [event.to_dict() for event in self.events]}


PRESETS = {
    "wet_concertina": Scenario(),
    "dry_restart": Scenario(name="Dry restart", wet=False, grip=0.9, deployment_limit_kw=350),
    "unrestricted": Scenario(name="Unrestricted sector", restricted_sector=False),
    "depleted": Scenario(name="SOC reserve · ICE fallback", soc=0.10, initial_speed_kph=0),
    "brake_overlap": Scenario(name="Brake and throttle overlap", brake_overlap=True),
    "clutch_open": Scenario(name="Clutch disengaged", clutch_engaged=False),
    "wet_sector_release": Scenario(name="Wet entry · sector release", wet=False, restricted_sector=False,
        duration_s=8, events=(
            SignalEvent(1, "Rain / restricted sector", wet=True, restricted_sector=True, sector=1),
            SignalEvent(2, "Restart request", throttle=.85, brake=0),
            SignalEvent(3, "Throttle lift", throttle=0),
            SignalEvent(3.3, "Throttle reapplied", throttle=.85),
            SignalEvent(4, "Sector exit releases restriction", sector=2, restricted_sector=False, deployment_limit_kw=350))),
    "rain_onset": Scenario(name="Rain onset after dry restart", wet=False, restricted_sector=False,
        grip=.8, events=(
            SignalEvent(2.4, "Rain and wet grip", wet=True, grip=.35),
            SignalEvent(3, "Enter restricted sector", sector=1, restricted_sector=True, deployment_limit_kw=250),
            SignalEvent(4, "Throttle lift", throttle=0),
            SignalEvent(4.2, "Throttle reapplied", throttle=.85))),
    "clutch_sequence": Scenario(name="Clutch release · wet restriction", events=(
            SignalEvent(2, "Restart with clutch open", clutch_engaged=False, throttle=.85, brake=0),
            SignalEvent(2.6, "Clutch engagement", clutch_engaged=True),
            SignalEvent(4, "Wet restriction removed", wet=False))),
    "energy_boundary": Scenario(name="SOC reserve crossing · power cap change", initial_speed_kph=0,
        soc=.10015, wet=False, grip=.8, hold_s=1, events=(
            SignalEvent(2, "Electrical deployment disabled", deployment_limit_kw=0, sector=1),
            SignalEvent(3, "Electrical cap restored", deployment_limit_kw=250, sector=2))),
}


@dataclass(frozen=True)
class Sample:
    time_s: float
    speed_kph: float
    next_speed_kph: float
    engine_rpm: float
    throttle: float
    brake: float
    soc: float
    next_soc: float
    state: str
    reason: str
    wheel_torque_nm: float
    ice_wheel_torque_nm: float
    mgu_wheel_torque_nm: float
    mgu_power_kw: float  # Signed: positive propulsion, negative harvesting.
    recovery_power_kw: float
    deployment_limit_kw: float
    eligible: bool
    wet: bool
    restricted_sector: bool
    sector: int
    grip: float
    clutch_engaged: bool
    engine_available: bool


class Controller:
    def __init__(self, variant: str):
        if variant not in ("faulty", "corrected"):
            raise ValueError("variant must be faulty or corrected")
        self.variant = variant
        self.state = State.COAST

    def transition(self, s: Inputs, speed_kph: float, rpm: float, throttle: float, brake: float, soc: float):
        constrained = s.wet and s.restricted_sector
        demand = throttle > 0.05 and brake < 0.05 and s.clutch_engaged
        # Injected fault: the exit guard requires speed that blocked propulsion cannot produce.
        # This is a hypothesis inspired by the incident, NOT the FIA's disclosed algorithm.
        if self.variant == "faulty" and self.state == State.WET_HOLD and constrained and speed_kph < 5:
            self.state, reason = State.WET_HOLD, "Exit guard speed >= 5 km/h is false"
        elif not s.clutch_engaged:
            self.state, reason = State.INHIBITED, "Clutch is disengaged"
        elif brake >= 0.05:
            if constrained and speed_kph < 3 and rpm < 4500 and self.variant == "faulty":
                self.state, reason = State.WET_HOLD, "Wet restricted sector + low speed + low RPM"
            else:
                self.state, reason = State.RECOVERY, "Braking has priority"
        elif demand:
            if soc > SOC_RESERVE and s.deployment_limit_kw > 0:
                self.state, reason = State.DEPLOY, "Driver demand releases recovery; limits retained"
            else:
                self.state, reason = State.ICE_ONLY, "Electrical energy unavailable; ICE fallback"
        else:
            self.state, reason = State.COAST, "No propulsion request"
        return self.state, reason


def step(s: Scenario, controller: Controller, speed_mps: float, soc: float, t: float,
         inputs: Inputs | None = None) -> Sample:
    s = inputs if inputs is not None else InputSchedule(s).at(t)
    throttle, brake = s.throttle, s.brake
    rpm = max(IDLE_RPM, speed_mps / WHEEL_RADIUS_M * GEAR_RATIO * 60 / (2 * math.pi)) if s.engine_available else 0.0
    state, reason = controller.transition(s, speed_mps * 3.6, rpm, throttle, brake, soc)
    omega = speed_mps / WHEEL_RADIUS_M
    ice = throttle * 300.0 * GEAR_RATIO * EFFICIENCY if s.engine_available and s.clutch_engaged and brake < 0.05 else 0.0
    mgu = 0.0
    if state == State.WET_HOLD:
        # Synthetic torque arbitration fault: ICE output is absorbed by generation.
        # At standstill this generates no energy; never recharge from zero wheel power.
        headroom_w = max(0.0, (1 - soc) * BATTERY_J / (EFFICIENCY * DT))
        ice = min(ice, 100_000 / max(omega, 1.0), headroom_w / max(omega, 1.0))
        mgu = -ice
    elif state == State.DEPLOY:
        energy_power_w = max(0.0, (soc - SOC_RESERVE) * BATTERY_J * EFFICIENCY / DT)
        power_w = min(s.deployment_limit_kw * 1000, energy_power_w)
        mgu = min(throttle * 3500.0, power_w / max(omega, 1.0))
    elif state == State.RECOVERY and s.clutch_engaged:
        headroom_w = max(0.0, (1 - soc) * BATTERY_J / (EFFICIENCY * DT))
        mgu = -min(1800.0 * brake, 100_000 / max(omega, 1.0), headroom_w / max(omega, 1.0))

    grip_torque = s.grip * MASS_KG * 9.81 * WHEEL_RADIUS_M
    raw = ice + mgu
    # Combined axle torque is bounded by grip. No claim of production traction control.
    if raw > grip_torque and raw > 0:
        factor = grip_torque / raw
        ice, mgu = ice * factor, mgu * factor
    if state == State.RECOVERY:
        mgu = max(mgu, -grip_torque)
    wheel = ice + mgu
    power_w = mgu * omega
    battery_delta_j = -power_w * DT / EFFICIENCY if power_w >= 0 else -power_w * DT * EFFICIENCY
    next_soc = min(1.0, max(0.0, soc + battery_delta_j / BATTERY_J))
    brake_force = brake * s.grip * MASS_KG * 9.81
    resistance = (120.0 if speed_mps > 0 else 0.0) + 0.3 * speed_mps ** 2
    next_speed = max(0.0, speed_mps + (wheel / WHEEL_RADIUS_M - brake_force - resistance) / MASS_KG * DT)
    nominal_ice = throttle * 300.0 * GEAR_RATIO * EFFICIENCY if s.engine_available else 0.0
    nominal_mgu = min(throttle * 3500.0, s.deployment_limit_kw * 1000 / max(omega, 1.0),
                      max(0.0, (soc - SOC_RESERVE) * BATTERY_J * EFFICIENCY / DT) / max(omega, 1.0))
    available_torque = min(grip_torque, nominal_ice + nominal_mgu)
    eligible = (throttle >= 0.70 and brake < 0.05 and s.clutch_engaged and
                available_torque > 150.0 and (s.engine_available or (soc > SOC_RESERVE and s.deployment_limit_kw > 1.0)))
    return Sample(round(t, 4), speed_mps * 3.6, next_speed * 3.6, rpm, throttle, brake, soc, next_soc,
                  state.value, reason, wheel, ice, mgu, power_w / 1000, max(0.0, -power_w / 1000),
                  s.deployment_limit_kw, eligible, s.wet, s.restricted_sector, s.sector,
                  s.grip, s.clutch_engaged, s.engine_available)


class Monitor:
    """Bounded liveness + physical invariants; exemptions reset the demand timer."""
    def __init__(self):
        self.starvation_s = 0.0
        self.max_starvation_s = 0.0
        self.findings = {}

    def observe(self, x: Sample):
        starving = x.eligible and x.wheel_torque_nm < 100.0
        self.starvation_s = self.starvation_s + DT if starving else 0.0
        self.max_starvation_s = max(self.max_starvation_s, self.starvation_s)
        checks = {
            "TORQUE_LIVENESS": self.starvation_s + 1e-9 >= RESPONSE_DEADLINE_S,
            "DEPLOYMENT_LIMIT": x.mgu_power_kw > x.deployment_limit_kw + 1e-7,
            "SOC_BOUNDS": not 0 <= x.next_soc <= 1,
            "BRAKE_PRIORITY": x.brake >= 0.05 and x.wheel_torque_nm > 1e-6,
        }
        for code, failed in checks.items():
            if failed and code not in self.findings:
                self.findings[code] = {"code": code, "time_s": x.time_s, "state": x.state,
                                       "reason": x.reason, "sector": x.sector, "wet": x.wet,
                                       "demand_duration_s": round(self.starvation_s, 4)}


def simulate(s: Scenario, variant="faulty", retain_trace=True):
    controller, monitor = Controller(variant), Monitor()
    speed, soc = s.initial_speed_kph / 3.6, s.soc
    trace, transitions, states, edges = [], [], set(), set()
    previous_state = State.COAST.value
    schedule = InputSchedule(s)
    for i in range(round(s.duration_s / DT)):
        x = step(s, controller, speed, soc, i * DT, inputs=schedule.at(i * DT))
        monitor.observe(x)
        states.add(x.state)
        edges.add(f"{previous_state} → {x.state}")
        if x.state != previous_state:
            transitions.append({"time_s": x.time_s, "from": previous_state, "to": x.state, "reason": x.reason})
        previous_state = x.state
        if retain_trace:
            trace.append(asdict(x))
        speed, soc = x.next_speed_kph / 3.6, x.next_soc
    return {"variant": variant, "passed": not monitor.findings, "findings": list(monitor.findings.values()),
            "max_starvation_s": round(monitor.max_starvation_s, 4), "final_speed_kph": round(speed * 3.6, 4),
            "final_soc": soc, "states": sorted(states), "edges": sorted(edges),
            "transitions": transitions, "trace": trace}
