"""Shape checks on the Tuya datapoint table.

DP_CODES is hand-transcribed from the app, and a wrong entry is silent: the
feeder simply ignores a command, or accepts a portion outside the range the
hardware can dispense. These assertions are cheap and catch a bad edit.
"""

from __future__ import annotations

import pytest

from petsseries.dp_codes import DP_CODES

ENTRIES = sorted(DP_CODES.items())
IDS = [code for code, _ in ENTRIES]


class TestTableShape:
    """Every entry has to be usable without a special case."""

    @pytest.mark.parametrize(("code", "entry"), ENTRIES, ids=IDS)
    def test_the_key_is_a_numeric_datapoint_id(self, code: str, entry: dict) -> None:
        assert code.isdigit()

    @pytest.mark.parametrize(("code", "entry"), ENTRIES, ids=IDS)
    def test_every_entry_names_its_dp_code(self, code: str, entry: dict) -> None:
        assert entry["dpCode"]
        assert isinstance(entry["dpCode"], str)

    @pytest.mark.parametrize(("code", "entry"), ENTRIES, ids=IDS)
    def test_every_entry_declares_a_known_type(self, code: str, entry: dict) -> None:
        assert entry["standardType"] in ("Boolean", "Integer", "Enum", "String")

    def test_the_dp_codes_are_unique(self) -> None:
        # Two ids mapping to one name means one of them is a transcription slip.
        names = [entry["dpCode"] for entry in DP_CODES.values()]
        assert len(names) == len(set(names))


class TestIntegerRanges:
    """An Integer datapoint without a range cannot be validated by a caller."""

    INTEGERS = sorted((c, e) for c, e in DP_CODES.items() if e["standardType"] == "Integer")

    @pytest.mark.parametrize(("code", "entry"), INTEGERS, ids=[c for c, _ in INTEGERS])
    def test_it_carries_a_min_and_a_max(self, code: str, entry: dict) -> None:
        properties = entry["properties"]
        assert "min" in properties
        assert "max" in properties

    @pytest.mark.parametrize(("code", "entry"), INTEGERS, ids=[c for c, _ in INTEGERS])
    def test_the_range_is_the_right_way_round(self, code: str, entry: dict) -> None:
        assert entry["properties"]["min"] < entry["properties"]["max"]

    def test_the_portion_count_tops_out_at_the_hardware_limit(self) -> None:
        # feed_num is portions per dispense. The hopper takes 20.
        assert DP_CODES["201"]["dpCode"] == "feed_num"
        assert DP_CODES["201"]["properties"]["max"] == 20

    def test_the_volume_range_starts_at_one_not_zero(self) -> None:
        # 0 is not mute here; the datapoint simply does not accept it.
        assert DP_CODES["231"]["dpCode"] == "device_volume"
        assert DP_CODES["231"]["properties"]["min"] == 1


class TestEnumRanges:
    """An Enum datapoint without its values cannot be set safely."""

    ENUMS = sorted((c, e) for c, e in DP_CODES.items() if e["standardType"] == "Enum")

    @pytest.mark.parametrize(("code", "entry"), ENUMS, ids=[c for c, _ in ENUMS])
    def test_it_carries_a_non_empty_value_range(self, code: str, entry: dict) -> None:
        assert entry["valueRange"]

    @pytest.mark.parametrize(("code", "entry"), ENUMS, ids=[c for c, _ in ENUMS])
    def test_the_values_are_strings(self, code: str, entry: dict) -> None:
        # Tuya sends enum values as strings; sending an int is rejected.
        assert all(isinstance(v, str) for v in entry["valueRange"])


class TestKnownDatapoints:
    """The four the integration reads by number, pinned by name."""

    @pytest.mark.parametrize(
        ("code", "name"),
        [("232", None), ("208", None), ("250", None), ("207", "schedule")],
    )
    def test_the_documented_ids_behave_as_expected(self, code: str, name: str | None) -> None:
        if name is None:
            # 232, 208 and 250 are used by the integration but are not in the
            # transcribed table. Absence here is the current state, not a bug;
            # this pins it so a future addition is a deliberate edit.
            assert code not in DP_CODES
        else:
            assert DP_CODES[code]["dpCode"] == name
