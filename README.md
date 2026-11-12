# tap-lexio

[![PyPI](https://img.shields.io/pypi/v/tap-lexio.svg)](https://pypi.org/project/tap-lexio/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`tap-lexio` is a [Singer](https://www.singer.io/) tap for the [Lexio Rent API](https://docs.lexio.rent), built with the [Meltano Singer SDK](https://sdk.meltano.com). It loads the data of a car, van or two-wheeler rental company into any Singer target (Postgres, Snowflake, BigQuery, DuckDB, CSV...).

<a href="https://lexio.rent/logiciel-location-voiture">Lexio Rent</a> is rental management software for professional rental companies: planning, contracts, check-in/check-out inspections, deposits and fleet maintenance.

## Streams

| Stream | Endpoint | Replication |
|---|---|---|
| `vehicles` | `GET /vehicles` | full table |
| `categories` | `GET /categories` | full table |
| `locations` | `GET /locations` | full table |
| `options` | `GET /options` | full table |
| `deductibles` | `GET /deductibles` | full table |
| `deposits` | `GET /deposits` | full table |
| `mileage_packages` | `GET /mileage-packages` | full table |
| `customers` | `GET /customers` | full table |
| `rentals` | `GET /rentals` | full table |
| `vehicle_blocks` | `GET /vehicle-blocks` | full table, over a window split into 92-day partitions |
| `maintenance_records` | `GET /maintenance-records` | full table |
| `events` | `GET /events` | incremental on `occurredAt` |

Schemas are generated from the published [OpenAPI specification](https://docs.lexio.rent/openapi.json) (version 1.0.5) by `scripts/gen_schemas.py`.

`events` is the rental change feed (`rental.created`, `rental.updated`, `rental.cancelled`, `rental.deleted`). The API keeps 29 days of history and has no webhooks: run the tap at least weekly and use the feed to know which rentals changed between two full loads.

## Installation

```bash
pip install tap-lexio
```

With Meltano:

```bash
meltano add extractor tap-lexio
meltano config tap-lexio set api_key lck_...
meltano run tap-lexio target-duckdb
```

## Settings

| Setting | Required | Default | Description |
|---|---|---|---|
| `api_key` | yes | | Lexio API key (`lck_...`), from **Settings → Developer → API tokens**. API access is part of the Business plan. |
| `api_url` | no | `https://api.lexio.rent/api/external/v1` | Base URL of the API. |
| `blocks_days_back` | no | `30` | `vehicle_blocks`: first day of the window, in days before today. |
| `blocks_days_ahead` | no | `180` | `vehicle_blocks`: last day of the window, in days after today. |

Settings can also come from the environment (`TAP_LEXIO_API_KEY`...) with `--config=ENV`. The SDK settings (`stream_maps`, `flattening_enabled`, `batch_config`...) are supported; run `tap-lexio --about` for the full list.

There is no sandbox: test against a dedicated Lexio organization.

## Usage without Meltano

```bash
echo '{"api_key": "lck_..."}' > config.json
tap-lexio --config config.json --discover > catalog.json
tap-lexio --config config.json --catalog catalog.json --state state.json | target-jsonl
```

## Development

```bash
pip install -e ".[test]"
pytest                               # offline tests
LEXIO_API_KEY=lck_... pytest         # adds the Singer SDK standard suite against your organization
python scripts/gen_schemas.py        # regenerate schemas after an API update
```

## About

This tap is maintained by the team behind <a href="https://lexio.rent/logiciel-location-voiture">Lexio Rent, car rental management software</a>. The `deductibles` and `deposits` streams carry the excess and deposit amounts set per vehicle category; to hand the same terms to customers, Lexio publishes a free <a href="https://lexio.rent/outils/franchise-garanties-location-vehicule">excess and cover summary sheet generator</a> (in French).

- API documentation: <https://docs.lexio.rent>
- Python client: <https://github.com/lexio-rent-git/lexio-python>
- Airflow provider: <https://github.com/lexio-rent-git/airflow-provider-lexio>
- Contact: contact@lexio.rent

MIT License.
