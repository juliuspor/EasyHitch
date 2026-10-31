"""Station occupancy in DynamoDB: one item per station, written only if nobody wrote it in between.

    {"station_id": "cmr-north-01", "version": 7,
     "slots": {"12": {"state": "taken", "confidence": 0.97, "changed_at": "...",
                      "reported_at": "...", "pending_taken": null, "simulated": false}}}
"""

import time
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from occupancy.model import SlotOccupancy, SlotState, StationOccupancy
from occupancy.repository import ConcurrentUpdate

BATCH_GET_LIMIT = 100  # DynamoDB's maximum keys per BatchGetItem


class DynamoOccupancyRepository:
    def __init__(self, dynamodb, table_name: str) -> None:
        """dynamodb is a boto3 DynamoDB service resource."""
        self._dynamodb = dynamodb
        self._table = dynamodb.Table(table_name)
        self._table_name = table_name

    def get(self, station_id: str) -> StationOccupancy | None:
        item = self._table.get_item(Key={"station_id": station_id}, ConsistentRead=True).get("Item")
        return _occupancy(item) if item else None

    def get_many(self, station_ids: Sequence[str]) -> list[StationOccupancy]:
        items = []
        for start in range(0, len(station_ids), BATCH_GET_LIMIT):
            request = {self._table_name: {
                "Keys": [{"station_id": station_id} for station_id in station_ids[start:start + BATCH_GET_LIMIT]],
                "ConsistentRead": True,
            }}
            delay = 0.05
            while request:
                response = self._dynamodb.batch_get_item(RequestItems=request)
                items.extend(response["Responses"].get(self._table_name, []))
                request = response.get("UnprocessedKeys") or {}
                if request:
                    time.sleep(delay)
                    delay *= 2
        by_station = {item["station_id"]: _occupancy(item) for item in items}
        return [by_station[station_id] for station_id in station_ids if station_id in by_station]

    def save(self, occupancy: StationOccupancy) -> None:
        expected = Attr("station_id").not_exists() if occupancy.version == 0 else Attr("version").eq(occupancy.version)
        try:
            self._table.put_item(Item=_item(occupancy, occupancy.version + 1), ConditionExpression=expected)
        except ClientError as error:
            if error.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ConcurrentUpdate(occupancy.station_id) from error
            raise


def _item(occupancy: StationOccupancy, version: int) -> dict:
    return {
        "station_id": occupancy.station_id,
        "version": version,
        "slots": {str(number): _slot_item(slot) for number, slot in occupancy.slots.items()},
    }


def _slot_item(slot: SlotOccupancy) -> dict:
    return {
        "state": slot.state.value,
        "confidence": None if slot.confidence is None else Decimal(str(round(slot.confidence, 4))),
        "changed_at": _text(slot.changed_at),
        "reported_at": _text(slot.reported_at),
        "pending_taken": slot.pending_taken,
        "simulated": slot.simulated,
    }


def _occupancy(item: dict) -> StationOccupancy:
    slots = {int(number): _slot(int(number), entry) for number, entry in item.get("slots", {}).items()}
    return StationOccupancy(station_id=item["station_id"], slots=slots, version=int(item["version"]))


def _slot(number: int, entry: dict) -> SlotOccupancy:
    confidence = entry.get("confidence")
    return SlotOccupancy(
        number=number,
        state=SlotState(entry["state"]),
        confidence=None if confidence is None else float(confidence),
        changed_at=_time(entry.get("changed_at")),
        reported_at=_time(entry.get("reported_at")),
        pending_taken=entry.get("pending_taken"),
        simulated=entry.get("simulated", False),  # items written before the simulator have none
    )


def _text(moment: datetime | None) -> str | None:
    return None if moment is None else moment.isoformat()


def _time(text: str | None) -> datetime | None:
    return None if text is None else datetime.fromisoformat(text)
