from datetime import datetime

from custom_components.octopus_spain import coordinator


def test_next_madrid_hour_aligns_to_next_whole_hour():
    result = coordinator.next_madrid_hour(datetime.fromisoformat("2026-05-04T13:15:30+02:00"))

    assert result.isoformat() == "2026-05-04T14:00:00+02:00"


def test_next_madrid_hour_moves_forward_when_already_on_boundary():
    result = coordinator.next_madrid_hour(datetime.fromisoformat("2026-05-04T14:00:00+02:00"))

    assert result.isoformat() == "2026-05-04T15:00:00+02:00"
