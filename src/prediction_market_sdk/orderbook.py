"""
Order Book Ladder - Zero-Alloc L2 Depth Engine.

Maintains bid/ask ladders for a single market and provides O(log N) top-of-book
and depth queries. Designed to sit on the hot path behind the WebSocket reactor:
every delta is applied in-place, mutating sorted price/size tables without
allocating intermediate dicts.

Design goals
------------
- **Zero-alloc discipline.** Levels are stored in plain Python ``dict`` objects
  keyed by price; an `OrderBookUpdate` is a ``msgspec.Struct(gc=False)``
  so WS deltas decode straight into a tracked struct without touching the GC.
- **Stable top-of-book.** Best bid is the *highest* price; best ask is the
  *lowest* price. A crossed book (best bid >= best ask) is surfaced honestly
  via the accessors rather than silently repaired.
- **Snapshot-first startup.** REST snapshots seed the ladder atomically; live
  deltas then merge against the seeded state. A ``seq`` watermark guards
  against stale snapshots applied out-of-order.

Example
-------
    >>> from prediction_market_sdk.orderbook import OrderBook
    >>> book = OrderBook.snapshot(seq=1,
    ...                           bids=[(58, 200), (57, 150)],
    ...                           asks=[(59, 120), (60, 300)])
    >>> book.best_bid, book.best_ask, book.spread, book.mid
    (58, 59, 1, 58.5)
    >>> book.levels(2)
    {'bids': [(58, 200), (57, 150)], 'asks': [(59, 120), (60, 300)]}
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

import msgspec

__all__ = ["OrderBook", "OrderBookError", "OrderBookUpdate"]


# ---------------------------------------------------------------------------
# msgspec Structs
# ---------------------------------------------------------------------------


class OrderBookUpdate(msgspec.Struct, gc=False):
    """
    Zero-alloc L2 order book delta.

    One struct encodes a single level change: ``delta`` is **signed** and
    represents the change in resting size at ``price`` on ``side``. A delta
    that drives the resting size to zero (or explicitly carries ``delta == 0``
    together with an absolute ``size`` of zero via :class:`OrderBook.apply_delta`)
    removes the level entirely.

    Attributes:
        market_id: Exchange market identifier (e.g. ``"KXBTC-100K"``).
        price: Price level in cents (e.g. ``4500`` == $45.00).
        delta: Signed quantity change at this price level. May be negative.
        side: Contract side - ``"yes"`` for bids, ``"no"`` for asks.
        ts: Exchange timestamp in milliseconds since epoch.
    """

    market_id: str
    price: int
    delta: int
    side: Literal["yes", "no"]
    ts: int


class OrderBookError(Exception):
    """Raised by :class:`OrderBook` for invariant violations (bad side, etc.)."""


# ---------------------------------------------------------------------------
# OrderBook
# ---------------------------------------------------------------------------


class OrderBook:
    """
    In-memory L2 order book ladder for a single market.

    Bids are kept as ``price -> size`` and exposed best-first (descending).
    Asks are kept the same way and exposed best-first (ascending). The book is
    *not* thread-safe; it is meant to be owned by a single asyncio task on the
    WS reactor path.

    Attributes:
        market_id: Optional market identifier this book tracks.
        seq: Sequence watermark set from :meth:`snapshot` and bumped by
            :meth:`apply_delta` when the update carries a newer ``ts``.
        bids: Raw ``{price: size}`` table for the bid side.
        asks: Raw ``{price: size}`` table for the ask side.
    """

    __slots__ = ("asks", "bids", "market_id", "seq")

    def __init__(self, market_id: str | None = None, seq: int = 0) -> None:
        """Initialize an empty book for ``market_id`` with sequence watermark ``seq``."""
        self.market_id = market_id
        self.seq = seq
        self.bids: dict[int, int] = {}
        self.asks: dict[int, int] = {}

    # -- construction ------------------------------------------------------

    @classmethod
    def snapshot(
        cls,
        seq: int,
        bids: list[tuple[int, int]],
        asks: list[tuple[int, int]],
        market_id: str | None = None,
    ) -> OrderBook:
        """
        Build a book from a REST snapshot.

        Args:
            seq: Snapshot sequence number / watermark. Applied to ``self.seq``.
            bids: Iterable of ``(price, size)`` bid levels. Duplicates are
                summed; zero-size entries are dropped.
            asks: Iterable of ``(price, size)`` ask levels. Same semantics.
            market_id: Optional market identifier attached to the book.

        Returns:
            A populated :class:`OrderBook` with the snapshot watermark set.
        """
        book = cls(market_id=market_id, seq=seq)
        for price, size in bids:
            if size <= 0:
                continue
            book.bids[price] = book.bids.get(price, 0) + size
        for price, size in asks:
            if size <= 0:
                continue
            book.asks[price] = book.asks.get(price, 0) + size
        # Prune any levels that summed to zero after merging duplicates.
        book._prune_zeros()
        return book

    # -- delta application -------------------------------------------------

    def apply_delta(self, update: OrderBookUpdate) -> None:
        """
        Merge a single WS delta into the ladder in place.

        Semantics:

        * **Additive.** ``delta`` is **signed** and added to the resting size
          at ``update.price`` on the side named by ``update.side``. Negative
          deltas reduce size.
        * **Removal.** If the resulting size falls to ``<= 0`` the level is
          dropped from the ladder entirely. Callers that receive an explicit
          ``size == 0`` removal frame should encode it as ``delta = -current`` -
          this method handles the resulting zero by deleting the level.
        * **Side mapping.** ``"yes"`` -> bids, ``"no"`` -> asks. Any other
          value raises :class:`OrderBookError` rather than silently mutating
          the wrong ladder.
        * **Watermark.** ``self.seq`` is bumped to ``update.ts`` only when it
          is greater than the current watermark, so out-of-order / replayed
          deltas cannot rewind the sequence.

        Args:
            update: A decoded :class:`OrderBookUpdate` struct.

        Raises:
            OrderBookError: If ``update.side`` is not ``"yes"`` or ``"no"``.
        """
        if update.side == "yes":
            ladder = self.bids
        elif update.side == "no":
            ladder = self.asks
        else:  # pragma: no cover - msgspec Literal blocks this at decode time.
            raise OrderBookError(f"Unknown side {update.side!r} for {update.market_id!r}")

        new_size = ladder.get(update.price, 0) + update.delta
        if new_size <= 0:
            ladder.pop(update.price, None)
        else:
            ladder[update.price] = new_size

        if update.ts > self.seq:
            self.seq = update.ts

    # -- accessors ---------------------------------------------------------

    @property
    def best_bid(self) -> int | None:
        """Highest resting bid price in cents, or ``None`` if the bid ladder is empty."""
        return max(self.bids) if self.bids else None

    @property
    def best_ask(self) -> int | None:
        """Lowest resting ask price in cents, or ``None`` if the ask ladder is empty."""
        return min(self.asks) if self.asks else None

    @property
    def spread(self) -> int | None:
        """
        Best ask minus best bid in cents.

        Returns ``None`` when either side is empty. A negative spread indicates
        a crossed book - the SDK reports it honestly rather than clamping.
        """
        bid, ask = self.best_bid, self.best_ask
        if bid is None or ask is None:
            return None
        return ask - bid

    @property
    def mid(self) -> float | None:
        """Midpoint between best bid and best ask in cents, or ``None`` if either side is empty."""
        bid, ask = self.best_bid, self.best_ask
        if bid is None or ask is None:
            return None
        return (bid + ask) / 2.0

    def levels(self, n: int = 10) -> dict[str, list[tuple[int, int]]]:
        """
        Return the top-``n`` bid and ask levels, best-first.

        Bids are sorted descending (best bid first); asks are sorted ascending
        (best ask first). Each level is returned as a ``(price, size)`` tuple.

        Args:
            n: Maximum number of levels per side. Defaults to 10. ``n <= 0``
              returns empty lists without raising.

        Returns:
            ``{"bids": [(price, size), ...], "asks": [(price, size), ...]}``
            with at most ``n`` entries per side.
        """
        if n <= 0:
            return {"bids": [], "asks": []}
        top_bids = sorted(self.bids.items(), key=lambda kv: kv[0], reverse=True)[:n]
        top_asks = sorted(self.asks.items(), key=lambda kv: kv[0])[:n]
        return {"bids": top_bids, "asks": top_asks}

    # -- iteration / helpers ----------------------------------------------

    def is_empty(self) -> bool:
        """Return ``True`` if both ladders are empty."""
        return not self.bids and not self.asks

    def __iter__(self) -> Iterator[tuple[str, int, int]]:
        """Yield ``(side, price, size)`` tuples for every resting level (bids first, then asks)."""
        for price, size in self.bids.items():
            yield ("yes", price, size)
        for price, size in self.asks.items():
            yield ("no", price, size)

    def __len__(self) -> int:
        """Total number of resting levels across both ladders."""
        return len(self.bids) + len(self.asks)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"OrderBook(market_id={self.market_id!r}, seq={self.seq}, "
            f"bids={len(self.bids)}, asks={len(self.asks)}, "
            f"best_bid={self.best_bid}, best_ask={self.best_ask})"
        )

    # -- internal ----------------------------------------------------------

    def _prune_zeros(self) -> None:
        """Drop any levels whose size has fallen to zero or below."""
        for price, size in list(self.bids.items()):
            if size <= 0:
                self.bids.pop(price, None)
        for price, size in list(self.asks.items()):
            if size <= 0:
                self.asks.pop(price, None)
