"""tap-lexio: Singer tap for the Lexio Rent API, built with the Meltano Singer SDK."""
from __future__ import annotations

import sys

from singer_sdk import Tap
from singer_sdk import typing as th

from tap_lexio.streams import STREAM_TYPES, LexioStream

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override


class TapLexio(Tap):
    """Extract fleet, catalogue, customers, rentals, maintenance and rental events from Lexio Rent."""

    name = "tap-lexio"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "api_key",
            th.StringType,
            required=True,
            secret=True,
            title="API key",
            description="Lexio API key (lck_...), from Settings > Developer > API tokens. Business plan.",
        ),
        th.Property(
            "api_url",
            th.StringType,
            default="https://api.lexio.rent/api/external/v1",
            title="API URL",
            description="Base URL of the Lexio Rent API v1.",
        ),
        th.Property(
            "blocks_days_back",
            th.IntegerType,
            default=30,
            title="Vehicle blocks: days back",
            description="vehicle_blocks stream: first day of the window, in days before today.",
        ),
        th.Property(
            "blocks_days_ahead",
            th.IntegerType,
            default=180,
            title="Vehicle blocks: days ahead",
            description="vehicle_blocks stream: last day of the window, in days after today.",
        ),
    ).to_dict()

    @override
    def discover_streams(self) -> list[LexioStream]:
        return [stream_class(tap=self) for stream_class in STREAM_TYPES]


if __name__ == "__main__":
    TapLexio.cli()
