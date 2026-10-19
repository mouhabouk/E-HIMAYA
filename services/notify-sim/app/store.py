# ┏━━ SIMULATION ━━ in-memory record of the pushes and SMS the simulator "delivered" (inspection only)
# ┃ PRODUCTION: no equivalent; real deliveries are visible on the devices, in the Firebase console and in the SMS
# ┃   provider's reports. Remove the notify-sim service; the API keeps its own delivery records.
# ┗━━━━━━━━━━━━━━━━
"""SIMULATION — ring buffer of the messages received by the simulator.

``seq`` is strictly increasing and starts from the start-up time in milliseconds, so a client that polls with
``after=<last_seq>`` keeps working across a restart of the simulator (new numbers are always larger).
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

Channel = Literal["push", "sms"]


@dataclass(frozen=True, slots=True)
class Item:
    seq: int
    id: str
    channel: Channel
    received_at: str
    token: str | None = None
    to: str | None = None
    title: str | None = None
    body: str | None = None
    text: str | None = None
    data: dict[str, str] | None = None
    android_channel: str | None = None
    priority: str | None = None
    segments: int | None = None
    encoding: str | None = None

    def as_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Page:
    items: list[Item]
    last_seq: int


@dataclass
class Store:
    capacity: int = 1000
    clock: Callable[[], float] = time.time
    _items: deque[Item] = field(init=False)
    _seq: int = field(init=False)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._items = deque(maxlen=self.capacity)
        self._seq = int(self.clock() * 1000)

    def add(self, channel: Channel, message_id: str, **fields: Any) -> Item:
        with self._lock:
            self._seq += 1
            received = datetime.fromtimestamp(self.clock(), UTC).isoformat(timespec="milliseconds")
            item = Item(seq=self._seq, id=message_id, channel=channel, received_at=received, **fields)
            self._items.append(item)
            return item

    def query(
        self,
        *,
        channel: Channel | None = None,
        token: str | None = None,
        to: str | None = None,
        after: int = 0,
        limit: int = 50,
    ) -> Page:
        """Items with ``seq > after`` matching every given filter, oldest first, at most ``limit``.

        ``last_seq`` is the value to pass as the next ``after``: the last returned item when the page is full,
        otherwise the newest sequence number (nothing matching is left between the two).
        """
        with self._lock:
            matching = [
                item
                for item in self._items
                if item.seq > after
                and (channel is None or item.channel == channel)
                and (token is None or item.token == token)
                and (to is None or item.to == to)
            ]
            head = self._seq
        page = matching[:limit]
        if len(matching) > limit:
            return Page(page, page[-1].seq)
        return Page(page, max(head, after))

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
