"""Tests for alarm model normalization."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any

_ALARM_MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "wake_up_alarm"
    / "alarm_model.py"
)

_SPEC = spec_from_file_location("alarm_model", _ALARM_MODEL_PATH)
assert _SPEC is not None  # noqa: S101
assert _SPEC.loader is not None  # noqa: S101
alarm_model = module_from_spec(_SPEC)
_SPEC.loader.exec_module(alarm_model)

ALARM_TYPE_ONE_TIME = alarm_model.ALARM_TYPE_ONE_TIME
ALARM_TYPE_RECURRING = alarm_model.ALARM_TYPE_RECURRING
calculate_next_recurring_run = alarm_model.calculate_next_recurring_run
create_one_time_alarm = alarm_model.create_one_time_alarm
create_recurring_alarm = alarm_model.create_recurring_alarm
normalize_alarm = alarm_model.normalize_alarm
serialize_alarm = alarm_model.serialize_alarm


class AlarmModelTest(unittest.TestCase):
    """Tests for alarm model normalization."""

    def test_normalize_legacy_one_time_alarm(self) -> None:
        """Legacy stored alarms are migrated to the normalized one-time shape."""
        alarm = normalize_alarm(
            {
                "number": 1,
                "datetime": "2026-05-22T08:30:00+02:00",
            },
        )

        expected: dict[str, Any] = {
            "number": 1,
            "name": "Alarm 1",
            "type": ALARM_TYPE_ONE_TIME,
            "enabled": True,
            "datetime_obj": datetime(2026, 5, 22, 6, 30, tzinfo=UTC),
            "time": None,
            "weekdays": [],
            "next_run": datetime(2026, 5, 22, 6, 30, tzinfo=UTC),
            "created_at": None,
            "skip_next": False,
        }

        if alarm != expected:
            err_msg = f"Expected {expected}, got {alarm}"
            raise AssertionError(err_msg)

    def test_serialize_one_time_alarm_uses_normalized_storage_keys(self) -> None:
        """Normalized one-time alarms persist using explicit type and next run."""
        alarm = {
            "number": 1,
            "name": "Dentist",
            "type": ALARM_TYPE_ONE_TIME,
            "enabled": True,
            "datetime_obj": datetime(2026, 5, 22, 6, 30, tzinfo=UTC),
            "time": None,
            "weekdays": [],
            "next_run": datetime(2026, 5, 22, 6, 30, tzinfo=UTC),
            "created_at": datetime(2026, 5, 19, 8, 0, tzinfo=UTC),
            "skip_next": False,
        }

        expected: dict[str, Any] = {
            "number": 1,
            "name": "Dentist",
            "type": ALARM_TYPE_ONE_TIME,
            "enabled": True,
            "datetime": "2026-05-22T06:30:00+00:00",
            "time": None,
            "weekdays": [],
            "next_run": "2026-05-22T06:30:00+00:00",
            "created_at": "2026-05-19T08:00:00+00:00",
            "skip_next": False,
        }

        if serialize_alarm(alarm) != expected:
            err_msg = f"Expected {expected}, got {serialize_alarm(alarm)}"
            raise AssertionError(err_msg)

    def test_create_one_time_alarm_uses_default_name_and_next_run(self) -> None:
        """One-time alarm creation returns normalized alarm data."""
        alarm_at = datetime(2026, 5, 22, 6, 30, tzinfo=UTC)
        created_at = datetime(2026, 5, 19, 8, 0, tzinfo=UTC)

        alarm = create_one_time_alarm(1, alarm_at, created_at=created_at)

        expected: dict[str, Any] = {
            "number": 1,
            "name": "Alarm 1",
            "type": ALARM_TYPE_ONE_TIME,
            "enabled": True,
            "datetime_obj": alarm_at,
            "time": None,
            "weekdays": [],
            "next_run": alarm_at,
            "created_at": created_at,
            "skip_next": False,
        }

        if alarm != expected:
            err_msg = f"Expected {expected}, got {alarm}"
            raise AssertionError(err_msg)

    def test_create_one_time_alarm_accepts_name_and_enabled(self) -> None:
        """One-time alarm creation supports optional name and enabled state."""
        alarm_at = datetime(2026, 5, 22, 6, 30, tzinfo=UTC)
        created_at = datetime(2026, 5, 19, 8, 0, tzinfo=UTC)

        alarm = create_one_time_alarm(
            1,
            alarm_at,
            name="Dentist",
            enabled=False,
            created_at=created_at,
        )

        if alarm["name"] != "Dentist":
            err_msg = f"Expected name 'Dentist', got {alarm['name']}"
            raise AssertionError(err_msg)

        if alarm["enabled"] is not False:
            err_msg = f"Expected enabled to be False, got {alarm['enabled']}"
            raise AssertionError(err_msg)

        if alarm["next_run"] != alarm_at:
            err_msg = f"Expected next_run to be {alarm_at}, got {alarm['next_run']}"
            raise AssertionError(err_msg)

    def test_calculate_recurring_alarm_today_when_time_is_future(self) -> None:
        """Recurring alarms can run later on the current selected day."""
        now = datetime.fromisoformat("2026-05-19T06:00:00+02:00")

        next_run = calculate_next_recurring_run(
            "07:00:00",
            ["mon", "tue", "wed", "thu", "fri"],
            now=now,
        )

        expected = datetime.fromisoformat("2026-05-19T07:00:00+02:00")
        if next_run != expected:
            err_msg = f"Expected next_run to be {expected}, got {next_run}"
            raise AssertionError(err_msg)

    def test_calculate_recurring_alarm_tomorrow_when_time_has_passed(self) -> None:
        """Recurring alarms skip today when the selected time is in the past."""
        now = datetime.fromisoformat("2026-05-19T08:00:00+02:00")

        next_run = calculate_next_recurring_run(
            "07:00:00",
            ["mon", "tue", "wed", "thu", "fri"],
            now=now,
        )

        expected = datetime.fromisoformat("2026-05-20T07:00:00+02:00")
        if next_run != expected:
            err_msg = f"Expected next_run to be {expected}, got {next_run}"
            raise AssertionError(err_msg)

    def test_calculate_recurring_alarm_rolls_over_to_next_week(self) -> None:
        """Recurring alarms roll over to next week when needed."""
        now = datetime.fromisoformat("2026-05-22T08:00:00+02:00")

        next_run = calculate_next_recurring_run(
            "07:00:00",
            ["mon", "tue", "wed", "thu", "fri"],
            now=now,
        )

        expected = datetime.fromisoformat("2026-05-25T07:00:00+02:00")
        if next_run != expected:
            err_msg = f"Expected next_run to be {expected}, got {next_run}"
            raise AssertionError(err_msg)

    def test_calculate_recurring_alarm_can_skip_current_next_run(self) -> None:
        """Skipping the current occurrence returns the following valid run."""
        now = datetime.fromisoformat("2026-05-19T06:00:00+02:00")

        next_run = calculate_next_recurring_run(
            "07:00:00",
            ["mon", "tue", "wed", "thu", "fri"],
            now=now,
            skip_current=True,
        )

        expected = datetime.fromisoformat("2026-05-20T07:00:00+02:00")
        if next_run != expected:
            err_msg = f"Expected next_run to be {expected}, got {next_run}"
            raise AssertionError(err_msg)

    def test_create_recurring_alarm_returns_normalized_data(self) -> None:
        """Recurring alarm creation returns normalized alarm data."""
        now = datetime.fromisoformat("2026-05-19T06:00:00+02:00")
        expected_number = 2

        alarm = create_recurring_alarm(
            expected_number,
            "07:00:00",
            ["mon", "tue", "wed", "thu", "fri"],
            name="Work alarm",
            created_at=now,
            now=now,
        )

        if alarm["number"] != expected_number:
            err_msg = f"Expected number to be {expected_number}, got {alarm['number']}"
            raise AssertionError(err_msg)

        if alarm["name"] != "Work alarm":
            err_msg = f"Expected name to be 'Work alarm', got {alarm['name']}"
            raise AssertionError(err_msg)

        if alarm["type"] != ALARM_TYPE_RECURRING:
            err_msg = f"Expected type to be {ALARM_TYPE_RECURRING}, got {alarm['type']}"
            raise AssertionError(err_msg)

        if not alarm["enabled"]:
            err_msg = "Expected enabled to be True"
            raise AssertionError(err_msg)

        if alarm["time"] != "07:00:00":
            err_msg = f"Expected time to be '07:00:00', got {alarm['time']}"
            raise AssertionError(err_msg)

        expected = ["mon", "tue", "wed", "thu", "fri"]
        if alarm["weekdays"] != expected:
            err_msg = f"Expected weekdays to be {expected}, got {alarm['weekdays']}"
            raise AssertionError(err_msg)

        expected = datetime.fromisoformat("2026-05-19T07:00:00+02:00")
        if alarm["next_run"] != expected:
            err_msg = f"Expected next_run to be {expected}, got {alarm['next_run']}"
            raise AssertionError(err_msg)

    def test_create_disabled_recurring_alarm_has_no_next_run(self) -> None:
        """Disabled recurring alarms are stored without a next run."""
        now = datetime.fromisoformat("2026-05-19T06:00:00+02:00")
        expected_number = 2

        alarm = create_recurring_alarm(
            expected_number,
            "07:00:00",
            ["mon", "tue"],
            enabled=False,
            created_at=now,
            now=now,
        )

        if alarm["number"] != expected_number:
            err_msg = f"Expected number to be {expected_number}, got {alarm['number']}"
            raise AssertionError(err_msg)

        if alarm["name"] != "":
            err_msg = f"Expected name to be '', got {alarm['name']}"
            raise AssertionError(err_msg)

        if alarm["enabled"]:
            err_msg = "Expected enabled to be False"
            raise AssertionError(err_msg)

        if alarm["next_run"] is not None:
            err_msg = "Expected next_run to be None"
            raise AssertionError(err_msg)

    def test_create_recurring_alarm_rejects_invalid_weekday(self) -> None:
        """Recurring alarms reject unsupported weekday values."""
        now = datetime.fromisoformat("2026-05-19T06:00:00+02:00")

        with self.assertRaises(ValueError):
            create_recurring_alarm(
                2,
                "07:00:00",
                ["monday"],
                created_at=now,
                now=now,
            )

    def test_calculate_skipped_single_weekday_moves_to_next_week(self) -> None:
        """Skipping a single-day recurring alarm moves to the following week."""
        now = datetime.fromisoformat("2026-05-19T06:00:00+02:00")

        next_run = calculate_next_recurring_run(
            "07:00:00",
            ["tue"],
            now=now,
            skip_current=True,
        )

        expected = datetime.fromisoformat("2026-05-26T07:00:00+02:00")
        if next_run != expected:
            err_msg = f"Expected next_run to be {expected}, got {next_run}"
            raise AssertionError(err_msg)


if __name__ == "__main__":
    unittest.main()
