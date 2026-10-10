import math
import unittest
from dataclasses import replace
from torqueguard.model import (PRESETS, Scenario, simulate, step, Controller, DT,
                              BATTERY_J, EFFICIENCY, SOC_RESERVE, Monitor)
from torqueguard.validation import campaign, compare


class ModelTests(unittest.TestCase):
    def test_wet_restart_exposes_latch_and_corrected_controller_recovers(self):
        paired = compare(PRESETS["wet_concertina"])["runs"]
        self.assertEqual([f["code"] for f in paired["faulty"]["findings"]], ["TORQUE_LIVENESS"])
        self.assertAlmostEqual(paired["faulty"]["findings"][0]["time_s"], 2.48)
        self.assertAlmostEqual(paired["faulty"]["final_speed_kph"], 0)
        self.assertTrue(paired["corrected"]["passed"])
        self.assertGreater(paired["corrected"]["final_speed_kph"], 30)
        first = next(x for x in paired["corrected"]["trace"] if x["time_s"] >= 2)
        self.assertEqual(first["state"], "DEPLOY")
        self.assertGreater(first["wheel_torque_nm"], 100)

    def test_dry_and_unrestricted_controls_do_not_enter_fault(self):
        for key in ("dry_restart", "unrestricted"):
            run = simulate(PRESETS[key])
            self.assertTrue(run["passed"])
            self.assertNotIn("WET_HOLD", run["states"])

    def test_legitimate_inhibitions_do_not_trigger_liveness(self):
        for s in (PRESETS["brake_overlap"], PRESETS["clutch_open"],
                  Scenario(grip=0), Scenario(engine_available=False, soc=0),
                  Scenario(throttle=0.69), Scenario(engine_available=False, deployment_limit_kw=0)):
            for variant in ("faulty", "corrected"):
                run = simulate(s, variant)
                self.assertTrue(run["passed"], (s, run["findings"]))

    def test_soc_reserve_keeps_ice_fallback(self):
        run = simulate(PRESETS["depleted"], "corrected")
        self.assertTrue(run["passed"])
        self.assertIn("ICE_ONLY", run["states"])
        self.assertGreater(run["final_speed_kph"], 20)

    def test_zero_speed_has_finite_torque_but_zero_power(self):
        s = Scenario()
        x = step(s, Controller("corrected"), 0, .6, 2)
        self.assertGreater(x.wheel_torque_nm, 100)
        self.assertEqual(x.mgu_power_kw, 0)
        self.assertEqual(x.soc, x.next_soc)
        self.assertTrue(all(math.isfinite(v) for v in (x.wheel_torque_nm, x.mgu_power_kw, x.next_speed_kph)))

    def test_energy_integration_matches_signed_wheel_power(self):
        for variant in ("faulty", "corrected"):
            run = simulate(Scenario(initial_speed_kph=45), variant)
            for x in run["trace"]:
                power = x["mgu_power_kw"] * 1000
                delta = -power * DT / EFFICIENCY if power >= 0 else -power * DT * EFFICIENCY
                expected = max(0, min(1, x["soc"] + delta / BATTERY_J))
                self.assertAlmostEqual(x["next_soc"], expected)

    def test_faulty_recovery_respects_full_battery_headroom(self):
        c = Controller("faulty")
        step(Scenario(soc=1), c, .5, 1, 0)
        x = step(Scenario(soc=1), c, .5, 1, 2)
        self.assertEqual(x.state, "WET_HOLD")
        self.assertEqual(x.mgu_power_kw, 0)
        self.assertEqual(x.wheel_torque_nm, 0)
        self.assertEqual(x.next_soc, 1)

    def test_limits_and_reserve_on_boundary_trajectories(self):
        for cap in (0, 1.1, 100, 250, 350):
            for soc in (0, .1, .100001, .6, 1):
                run = simulate(Scenario(soc=soc, deployment_limit_kw=cap), "corrected")
                self.assertTrue(run["passed"])
                for x in run["trace"]:
                    self.assertLessEqual(x["mgu_power_kw"], cap + 1e-7)
                    self.assertTrue(0 <= x["next_soc"] <= 1)
                    if x["mgu_power_kw"] > 0:
                        self.assertGreaterEqual(x["next_soc"], SOC_RESERVE - 1e-9)

    def test_monitor_requires_continuous_demand(self):
        x = step(Scenario(), Controller("faulty"), 0, .6, 2)
        starving = replace(x, eligible=True, wheel_torque_nm=0)
        monitor = Monitor()
        for _ in range(24):
            monitor.observe(starving)
        self.assertFalse(monitor.findings)
        monitor.observe(replace(starving, eligible=False))
        for _ in range(24):
            monitor.observe(starving)
        self.assertFalse(monitor.findings)
        monitor.observe(starving)
        self.assertIn("TORQUE_LIVENESS", monitor.findings)

    def test_seeded_campaign_reproduces_and_fixed_regression_is_clean(self):
        first = campaign(2026, 100)
        self.assertEqual(first, campaign(2026, 100))
        self.assertGreater(first["failures"]["faulty"], 0)
        self.assertEqual(first["failures"]["corrected"], 0)
        witness = first["first_counterexample"]
        self.assertFalse(simulate(Scenario(**witness["scenario"]))["passed"])

    def test_invalid_input_is_rejected(self):
        for kwargs in ({"soc":float("nan")}, {"soc":1.01}, {"wet":"false"},
                       {"deployment_limit_kw":351}, {"duration_s":2}, {"throttle":True}):
            with self.assertRaises(ValueError):
                Scenario(**kwargs)
        for seed, cases in ((True, 5), (1, False), (-1, 5), (1, 0)):
            with self.assertRaises(ValueError):
                campaign(seed, cases)


if __name__ == "__main__":
    unittest.main()
