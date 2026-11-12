"""Offline tests (always run) and the Singer SDK standard suite (needs LEXIO_API_KEY)."""
from __future__ import annotations

import datetime as dt
import json
import os

import pytest
import requests

from tap_lexio.streams import PAGE_SIZE, CursorPaginator, EventsStream, VehicleBlocksStream
from tap_lexio.tap import TapLexio

CONFIG = {"api_key": "lck_test"}


def _response(body: dict) -> requests.Response:
    resp = requests.Response()
    resp.status_code = 200
    resp._content = json.dumps(body).encode()
    return resp


def test_discovers_all_streams():
    names = {s.name for s in TapLexio(config=CONFIG, parse_env_config=False).discover_streams()}
    assert names == {
        "vehicles", "categories", "locations", "options", "deductibles", "deposits", "mileage_packages",
        "customers", "rentals", "vehicle_blocks", "maintenance_records", "events",
    }


def test_every_stream_has_id_and_schema():
    for stream in TapLexio(config=CONFIG, parse_env_config=False).discover_streams():
        assert stream.primary_keys == ["id"]
        assert "id" in stream.schema["properties"], stream.name


def test_bearer_auth_and_user_agent():
    stream = TapLexio(config=CONFIG, parse_env_config=False).streams["vehicles"]
    req = stream.prepare_request(context=None, next_page_token=None)
    assert req.headers["Authorization"] == "Bearer lck_test"
    assert req.headers["User-Agent"].startswith("tap-lexio/")
    assert req.url.startswith("https://api.lexio.rent/api/external/v1/vehicles?")
    assert "limit=100" in req.url


def test_paginator_stops_on_short_page():
    paginator = CursorPaginator(None)
    full = _response({"data": [{}] * PAGE_SIZE, "nextCursor": "c2"})
    short = _response({"data": [{}], "nextCursor": "c3"})  # the event feed never returns a null cursor
    assert paginator.get_next(full) == "c2"
    assert paginator.get_next(short) is None


def test_cursor_is_sent_on_next_pages():
    stream = TapLexio(config=CONFIG, parse_env_config=False).streams["rentals"]
    assert stream.get_url_params(None, "abc")["cursor"] == "abc"


def test_vehicle_block_partitions_respect_92_days():
    tap = TapLexio(config={**CONFIG, "blocks_days_back": 30, "blocks_days_ahead": 365}, parse_env_config=False)
    parts = tap.streams["vehicle_blocks"].partitions
    today = dt.date.today()
    assert parts[0]["from"] == (today - dt.timedelta(days=30)).isoformat()
    assert parts[-1]["to"] == (today + dt.timedelta(days=365)).isoformat()
    for part in parts:
        span = dt.date.fromisoformat(part["to"]) - dt.date.fromisoformat(part["from"])
        assert span.days <= VehicleBlocksStream.MAX_DAYS - 1
    for left, right in zip(parts, parts[1:]):
        assert dt.date.fromisoformat(right["from"]) == dt.date.fromisoformat(left["to"]) + dt.timedelta(days=1)


def test_vehicle_blocks_deduplicated_across_partitions():
    stream = TapLexio(config=CONFIG, parse_env_config=False).streams["vehicle_blocks"]
    assert stream.post_process({"id": "b1"}) == {"id": "b1"}
    assert stream.post_process({"id": "b1"}) is None


def test_events_start_earliest_then_follow_cursor():
    stream = TapLexio(config=CONFIG, parse_env_config=False).streams["events"]
    assert stream.get_url_params(None, None)["start"] == "EARLIEST"
    params = stream.get_url_params(None, "c9")
    assert params["cursor"] == "c9" and "start" not in params


def test_events_skip_bookmarked(monkeypatch):
    stream = TapLexio(config=CONFIG, parse_env_config=False).streams["events"]
    monkeypatch.setattr(EventsStream, "get_starting_replication_key_value", lambda self, ctx: "2026-11-10T10:00:00+01:00")
    assert stream.post_process({"id": "e1", "occurredAt": "2026-11-10T10:00:00+01:00"}) is None
    assert stream.post_process({"id": "e2", "occurredAt": "2026-11-11T09:00:00+01:00"}) is not None


if os.environ.get("LEXIO_API_KEY"):
    from singer_sdk.testing import SuiteConfig, get_tap_test_class

    # Organizations often have no stop locations or vehicle blocks: empty is valid.
    TestTapLexio = get_tap_test_class(
        TapLexio,
        config={"api_key": os.environ["LEXIO_API_KEY"]},
        suite_config=SuiteConfig(ignore_no_records_for_streams=["locations", "vehicle_blocks"]),
    )
else:
    @pytest.mark.skip(reason="set LEXIO_API_KEY to run the Singer SDK standard tests against a Lexio organization")
    def test_standard_suite():
        pass
