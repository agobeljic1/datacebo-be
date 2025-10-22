from datetime import datetime, timezone

from app.routers.licenses import _to_aware_utc


def test_to_aware_utc_handles_none_and_naive_and_aware():
    assert _to_aware_utc(None) is None

    naive = datetime(2024, 1, 1, 0, 0, 0)
    aware = _to_aware_utc(naive)
    assert aware.tzinfo is not None
    assert aware.tzinfo == timezone.utc

    aware_in = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    aware_out = _to_aware_utc(aware_in)
    assert aware_out == aware_in


