"""Streams of the Lexio Rent API v1."""
from __future__ import annotations

import datetime as dt
import json
import sys
import typing as t
from importlib import resources

from singer_sdk import RESTStream
from singer_sdk.authenticators import BearerTokenAuthenticator
from singer_sdk.pagination import BaseAPIPaginator

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if t.TYPE_CHECKING:
    import requests
    from singer_sdk.helpers.types import Context

PAGE_SIZE = 100
USER_AGENT = "tap-lexio/0.1.0 (+https://github.com/lexio-rent-git/tap-lexio)"


def load_schema(name: str) -> dict:
    return json.loads(resources.files("tap_lexio").joinpath("schemas", f"{name}.json").read_text(encoding="utf-8"))


class CursorPaginator(BaseAPIPaginator[t.Optional[str]]):
    """Follows ``nextCursor`` and stops on a short page.

    The event feed always returns a ``nextCursor``, even on an empty page, so a
    short page is the only reliable end signal.
    """

    @override
    def get_next(self, response: requests.Response) -> str | None:
        body = response.json()
        if len(body.get("data") or []) < PAGE_SIZE:
            return None
        return body.get("nextCursor")


class LexioStream(RESTStream):
    """Base stream: Bearer key, cursor pagination, ``data`` envelope."""

    records_jsonpath = "$.data[*]"
    primary_keys: t.ClassVar[list[str]] = ["id"]
    replication_key = None
    extra_params: t.ClassVar[dict[str, t.Any]] = {}

    @property
    @override
    def url_base(self) -> str:
        return self.config.get("api_url", "https://api.lexio.rent/api/external/v1").rstrip("/")

    @property
    @override
    def authenticator(self) -> BearerTokenAuthenticator:
        return BearerTokenAuthenticator(token=self.config["api_key"])

    @property
    @override
    def http_headers(self) -> dict:
        return {"User-Agent": USER_AGENT, "Accept": "application/json"}

    @override
    def get_new_paginator(self) -> CursorPaginator:
        return CursorPaginator(None)

    @override
    def get_url_params(self, context: Context | None, next_page_token: str | None) -> dict[str, t.Any]:
        params: dict[str, t.Any] = {"limit": PAGE_SIZE, **self.extra_params}
        if next_page_token:
            params["cursor"] = next_page_token
        return params


def _stream(name: str, path: str, **attrs: t.Any) -> type[LexioStream]:
    body = {"name": name, "path": path, "schema": load_schema(name), **attrs}
    return type(name.title().replace("_", "") + "Stream", (LexioStream,), body)


VehiclesStream = _stream("vehicles", "/vehicles")
CategoriesStream = _stream("categories", "/categories")
LocationsStream = _stream("locations", "/locations")
OptionsStream = _stream("options", "/options")
DeductiblesStream = _stream("deductibles", "/deductibles")
DepositsStream = _stream("deposits", "/deposits")
MileagePackagesStream = _stream("mileage_packages", "/mileage-packages")
CustomersStream = _stream("customers", "/customers")
RentalsStream = _stream("rentals", "/rentals")
MaintenanceRecordsStream = _stream("maintenance_records", "/maintenance-records")


class VehicleBlocksStream(LexioStream):
    """Vehicle unavailability periods (repair, cleaning, personal use...).

    The endpoint needs a ``from``/``to`` window of at most 92 days, so the
    window ``blocks_days_back`` .. ``blocks_days_ahead`` around today is split
    into 92-day partitions. Blocks overlapping two partitions are emitted once.
    """

    name = "vehicle_blocks"
    path = "/vehicle-blocks"
    schema = load_schema("vehicle_blocks")
    MAX_DAYS = 92

    @property
    @override
    def partitions(self) -> list[dict]:
        today = dt.date.today()
        start = today - dt.timedelta(days=int(self.config.get("blocks_days_back", 30)))
        end = today + dt.timedelta(days=int(self.config.get("blocks_days_ahead", 180)))
        out = []
        while start <= end:
            stop = min(start + dt.timedelta(days=self.MAX_DAYS - 1), end)
            out.append({"from": start.isoformat(), "to": stop.isoformat()})
            start = stop + dt.timedelta(days=1)
        return out

    @override
    def get_url_params(self, context: Context | None, next_page_token: str | None) -> dict[str, t.Any]:
        params = super().get_url_params(context, next_page_token)
        params.update({"from": context["from"], "to": context["to"]})
        return params

    @override
    def post_process(self, row: dict, context: Context | None = None) -> dict | None:
        seen = self.__dict__.setdefault("_seen_ids", set())
        if row.get("id") in seen:
            return None
        seen.add(row.get("id"))
        return row


class EventsStream(LexioStream):
    """Rental change feed (``rental.created``, ``updated``, ``cancelled``, ``deleted``).

    Incremental on ``occurredAt``. The feed keeps 29 days of history, so a
    first sync starts there; later syncs skip events already bookmarked.
    """

    name = "events"
    path = "/events"
    schema = load_schema("events")
    replication_key = "occurredAt"
    is_sorted = False

    @override
    def get_url_params(self, context: Context | None, next_page_token: str | None) -> dict[str, t.Any]:
        params = super().get_url_params(context, next_page_token)
        if not next_page_token:
            params["start"] = "EARLIEST"
        return params

    @override
    def post_process(self, row: dict, context: Context | None = None) -> dict | None:
        bookmark = self.get_starting_replication_key_value(context)
        if bookmark and row.get("occurredAt") and row["occurredAt"] <= bookmark:
            return None
        return row


STREAM_TYPES = [
    VehiclesStream,
    CategoriesStream,
    LocationsStream,
    OptionsStream,
    DeductiblesStream,
    DepositsStream,
    MileagePackagesStream,
    CustomersStream,
    RentalsStream,
    VehicleBlocksStream,
    MaintenanceRecordsStream,
    EventsStream,
]
