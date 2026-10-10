import unittest
from dataclasses import replace
from torqueguard.model import PRESETS, Scenario, simulate, SOC_RESERVE
from torqueguard.signals import SignalEvent, InputSchedule
from torqueguard.validation import campaign, compare


class TimelineTests(unittest.TestCase):
    def test_event_is_applied_at_exact_tick_and_persists(self):
        scenario = Scenario(events=(SignalEvent(1, wet=False, sector=2), SignalEvent(2, throttle=.7, brake=0)))
        schedule = InputSchedule(scenario)
        self.assertTrue(schedule.at(.98).wet)
        self.assertFalse(schedule.at(1).wet)
        self.assertFalse(schedule.at(3).wet)
        self.assertEqual(schedule.at(3).sector, 2)
        self.assertEqual(schedule.at(2).throttle, .7)
        self.assertEqual(schedule.at(2).brake, 0)

    def test_sector_exit_releases_fault_after_a_reported_violation(self):
        runs = compare(PRESETS["wet_sector_release"])["runs"]
        self.assertFalse(runs["faulty"]["passed"])
        self.assertTrue(runs["corrected"]["passed"])
        before = runs["faulty"]["trace"][199]
        after = runs["faulty"]["trace"][200]
        self.assertEqual(before["state"], "WET_HOLD")
        self.assertEqual(after["state"], "DEPLOY")
        self.assertEqual(after["sector"], 2)
        self.assertGreater(after["wheel_torque_nm"], 100)
        self.assertGreater(runs["faulty"]["final_speed_kph"], 0)

    def test_event_order_changes_reachability(self):
        s = Scenario(events=(SignalEvent(1.8, wet=False),))
        self.assertTrue(simulate(s)["passed"])
        later = replace(s, events=(SignalEvent(3, wet=False),))
        self.assertFalse(simulate(later)["passed"])
        self.assertEqual(simulate(later)["findings"][0]["time_s"], 2.48)

    def test_throttle_pulse_resets_response_clock(self):
        scenario = Scenario(events=(SignalEvent(2.3, throttle=0), SignalEvent(2.6, throttle=.85)))
        run = simulate(scenario)
        self.assertEqual(run["findings"][0]["time_s"], 3.08)

    def test_clutch_open_exempts_response_until_engagement(self):
        run = simulate(PRESETS["clutch_sequence"])
        self.assertEqual(run["findings"][0]["time_s"], 3.08)
        self.assertFalse(run["trace"][100]["eligible"])
        self.assertTrue(simulate(PRESETS["clutch_sequence"], "corrected")["passed"])

    def test_soc_crossing_is_computed_and_cap_changes_are_respected(self):
        run = simulate(PRESETS["energy_boundary"], "corrected")
        self.assertTrue(run["passed"])
        self.assertIn("DEPLOY", run["states"])
        self.assertIn("ICE_ONLY", run["states"])
        self.assertAlmostEqual(run["final_soc"], SOC_RESERVE)
        for x in run["trace"]:
            self.assertLessEqual(x["mgu_power_kw"], x["deployment_limit_kw"] + 1e-7)
            self.assertGreaterEqual(x["next_soc"], SOC_RESERVE - 1e-9)

    def test_timeline_round_trip_and_temporal_campaign_reproduction(self):
        s = PRESETS["wet_sector_release"]
        self.assertEqual(compare(s), compare(Scenario(**s.to_dict())))
        first = campaign(2026, 100, "temporal")
        self.assertEqual(first, campaign(2026, 100, "temporal"))
        self.assertGreater(first["scheduled_events"], 300)
        self.assertGreater(first["failures"]["faulty"], 0)
        self.assertEqual(first["failures"]["corrected"], 0)
        witness = first["first_counterexample"]
        self.assertFalse(simulate(Scenario(**witness["scenario"]))["passed"])

    def test_invalid_event_contracts_are_rejected(self):
        invalid = [None, [{"time_s":1}], [{"time_s":1,"wet":"yes"}],
                   [{"time_s":1,"soc":.5}], [{"time_s":1,"throttle":1.1}],
                   [{"time_s":float("nan"),"wet":True}], [{"time_s":.01,"wet":True}],
                   [{"time_s":6,"wet":True}], [{"time_s":1,"sector":True}],
                   [{"time_s":2,"wet":True},{"time_s":1,"wet":False}],
                   [{"time_s":1,"wet":True},{"time_s":1,"wet":False}]]
        for events in invalid:
            with self.assertRaises((ValueError, TypeError)):
                Scenario(events=events)
        with self.assertRaises(ValueError):
            campaign(profile="unknown")
        with self.assertRaises(ValueError):
            Scenario(duration_s=6.01)
