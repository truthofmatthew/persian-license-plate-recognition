"""Track plates across frames and vote per character, so one passing car = one event.

Small IoU tracker on purpose: plates move slowly between frames at a gate, and this
avoids a ByteTrack dependency. web/src/tracker.ts mirrors this file.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .engine import PlateRead
from .plate import PlateNumber, parse_codes


def iou(a: tuple, b: tuple) -> float:
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


@dataclass
class Track:
    id: int
    box: tuple
    votes: list[Counter] = field(default_factory=lambda: [Counter() for _ in range(8)])
    hits: int = 0
    missed: int = 0
    plate_conf: float = 0.0
    emitted: bool = False

    def add(self, r: PlateRead) -> None:
        self.box, self.missed, self.hits = r.box, 0, self.hits + 1
        self.plate_conf = max(self.plate_conf, r.plate_conf)
        if r.plate:  # only well-formed reads vote, weighted by confidence
            for i, (code, c) in enumerate(zip(r.codes, r.char_confs)):
                self.votes[i][code] += c

    @property
    def best(self) -> PlateNumber | None:
        if not self.votes[0]:
            return None
        return parse_codes([v.most_common(1)[0][0] for v in self.votes])

    @property
    def agreement(self) -> float:
        """Share of vote weight held by the winning symbol, averaged over positions."""
        if not self.votes[0]:
            return 0.0
        return sum(v.most_common(1)[0][1] / sum(v.values()) for v in self.votes) / 8


class PlateTracker:
    """Feed reads per frame; get back a finished plate once per vehicle.

    A track emits when it has ``min_hits`` good reads, or when it disappears
    after at least one good read (car drove off fast).
    """

    def __init__(self, min_hits: int = 3, max_missed: int = 15, iou_thr: float = 0.2):
        self.min_hits, self.max_missed, self.iou_thr = min_hits, max_missed, iou_thr
        self.tracks: list[Track] = []
        self._next = 1

    def update(self, reads: list[PlateRead]) -> list[Track]:
        done: list[Track] = []
        free = list(self.tracks)
        for r in reads:
            best = max(free, key=lambda t: iou(t.box, r.box), default=None)
            if best and iou(best.box, r.box) >= self.iou_thr:
                free.remove(best)
            else:
                best = Track(self._next, r.box)
                self._next += 1
                self.tracks.append(best)
            best.add(r)
            if not best.emitted and best.best and best.hits >= self.min_hits:
                best.emitted = True
                done.append(best)
        for t in free:
            t.missed += 1
        for t in [t for t in self.tracks if t.missed > self.max_missed]:
            self.tracks.remove(t)
            if not t.emitted and t.best:
                t.emitted = True
                done.append(t)
        return done

    def flush(self) -> list[Track]:
        """End of input (video ended, camera stopped): finish every pending track that has a good read."""
        done = [t for t in self.tracks if not t.emitted and t.best]
        for t in done:
            t.emitted = True
        self.tracks.clear()
        return done
