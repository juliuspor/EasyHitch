"""The one place that picks implementations, from Settings.

Every builder is cached, so services, stores and data files are created once
per process: once per Lambda container, once per local server. Feature code
is imported inside the builders, so each Lambda loads only what its own
service needs. The Availability function never imports Pillow or the Jev
client.
"""

from functools import cache
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI

from occupancy.repository import InMemoryOccupancyRepository, OccupancyRepository
from settings import Settings
from stations.catalog import StationCatalog
from web import create_app

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer

    from availability.mcp_server import McpEndpoint
    from availability.service import AvailabilityService
    from cameras.camera import Camera
    from cameras.registry import CameraRegistry
    from classification.classifier import OccupancyClassifier
    from ingest.fingerprints import FingerprintStore
    from ingest.service import IngestService
    from simulation.simulator import OccupancySimulator

JEV_TIMEOUT_SECONDS = 20  # leaves room within the Ingest function's 30 s timeout


@cache
def settings() -> Settings:
    return Settings.from_environment()


@cache
def station_catalog() -> StationCatalog:
    return StationCatalog.load(settings().data_dir / "stations.json")


@cache
def occupancy_repository() -> OccupancyRepository:
    if settings().storage == "dynamodb":
        from occupancy.dynamodb import DynamoOccupancyRepository
        return DynamoOccupancyRepository(_dynamodb(), settings().occupancy_table)
    return InMemoryOccupancyRepository()


@cache
def cameras() -> "dict[str, Camera]":
    from cameras.camera import check_against, load_cameras

    found = load_cameras(settings().data_dir / "cameras")
    check_against(found, station_catalog())
    return found


@cache
def camera_registry() -> "CameraRegistry":
    from cameras.registry import CameraRegistry, parse_token_hashes, read_token_file, token_hashes_from_tokens

    config = settings()
    if config.cameras == "ssm":
        from ssm import read_secure_string
        hashes = parse_token_hashes(read_secure_string(config.camera_tokens_parameter), config.camera_tokens_parameter)
    else:
        hashes = token_hashes_from_tokens(read_token_file(config.data_dir / "local-cameras.json"))
    return CameraRegistry(cameras(), hashes)


@cache
def fingerprint_store() -> "FingerprintStore":
    if settings().storage == "dynamodb":
        from ingest.dynamodb import DynamoFingerprintStore
        return DynamoFingerprintStore(_dynamodb(), settings().fingerprint_table)
    from ingest.fingerprints import InMemoryFingerprintStore
    return InMemoryFingerprintStore()


@cache
def classifier() -> "OccupancyClassifier":
    config = settings()
    if config.classifier == "jev":
        import httpx

        from classification.jev import JevCropClassifier
        key = config.openrouter_api_key
        if key is None:
            from ssm import read_secure_string
            key = read_secure_string(config.openrouter_api_key_parameter)
        return JevCropClassifier(httpx.Client(timeout=JEV_TIMEOUT_SECONDS), key, config.jev_model, config.decisions_url)
    from classification.static import StaticClassifier
    static = StaticClassifier.load(config.data_dir / "static-readings.json")
    static.check_covers(cameras().values())
    return static


@cache
def ingest_service() -> "IngestService":
    from ingest.service import IngestService
    return IngestService(classifier(), occupancy_repository(), fingerprint_store())


@cache
def availability_service() -> "AvailabilityService":
    from availability.service import AvailabilityService
    return AvailabilityService(station_catalog(), occupancy_repository(), settings().stale_after,
                               settings().data_dir / "models")


@cache
def simulator() -> "OccupancySimulator":
    from simulation.simulator import OccupancySimulator
    return OccupancySimulator(station_catalog(), occupancy_repository(), settings().stale_after)


@cache
def mcp_server() -> "MCPServer":
    from availability.mcp_server import build_server
    return build_server(availability_service())


def ingest_app() -> FastAPI:
    return create_app("Easy+Hitch Ingest API", [_ingest_router()])


def availability_app() -> FastAPI:
    return create_app("Easy+Hitch Availability API", [_availability_router()], mcp=_mcp_endpoint())


def local_app() -> FastAPI:
    """Both APIs and the MCP server in one app, sharing one in-memory store."""
    return create_app("Easy+Hitch", [_ingest_router(), _availability_router()], mcp=_mcp_endpoint())


def _ingest_router() -> APIRouter:
    from ingest.api import create_router
    return create_router(ingest_service(), camera_registry())


def _availability_router() -> APIRouter:
    from availability.api import create_router
    return create_router(availability_service())


def _mcp_endpoint() -> "McpEndpoint":
    from availability.mcp_server import McpEndpoint
    return McpEndpoint(mcp_server())


@cache
def _dynamodb():
    import boto3
    return boto3.resource("dynamodb")
