// Track plates across frames and vote per character, so one passing car = one event.
// Mirrors plpr/tracking.py; flush() is web-only (image upload / end of video).
import { parseCodes, type PlateNumber } from './plate';
import type { Box, PlateRead } from './pipeline';

export function iou(a: Box, b: Box): number {
  const ix = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const iy = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const inter = ix * iy;
  const union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
  return union > 0 ? inter / union : 0;
}

// Map keeps insertion order, so ties resolve to the first-seen symbol like Counter.most_common.
function top(votes: Map<string, number>): [string, number] {
  let best: [string, number] = ['', -Infinity];
  for (const e of votes) if (e[1] > best[1]) best = e;
  return best;
}

export class Track {
  votes: Map<string, number>[] = Array.from({ length: 8 }, () => new Map());
  hits = 0;
  missed = 0;
  plateConf = 0;
  emitted = false;
  constructor(public id: number, public box: Box) {}

  add(r: PlateRead): void {
    this.box = r.box;
    this.missed = 0;
    this.hits += 1;
    this.plateConf = Math.max(this.plateConf, r.plateConf);
    if (r.plate) r.codes.forEach((code, i) => this.votes[i].set(code, (this.votes[i].get(code) ?? 0) + r.charConfs[i]));
  }

  get best(): PlateNumber | null {
    return this.votes[0].size ? parseCodes(this.votes.map((v) => top(v)[0])) : null;
  }

  /** Share of vote weight held by the winning symbol, averaged over positions. */
  get agreement(): number {
    if (!this.votes[0].size) return 0;
    return this.votes.reduce((s, v) => s + top(v)[1] / [...v.values()].reduce((a, b) => a + b, 0), 0) / 8;
  }
}

/** Feed reads per frame; get back a finished plate once per vehicle. */
export class PlateTracker {
  tracks: Track[] = [];
  private next = 1;
  constructor(public minHits = 3, public maxMissed = 15, public iouThr = 0.2) {}

  update(reads: readonly PlateRead[]): Track[] {
    const done: Track[] = [];
    const free = [...this.tracks];
    for (const r of reads) {
      let best: Track | undefined;
      for (const t of free) if (!best || iou(t.box, r.box) > iou(best.box, r.box)) best = t;
      if (best && iou(best.box, r.box) >= this.iouThr) {
        free.splice(free.indexOf(best), 1);
      } else {
        best = new Track(this.next++, r.box);
        this.tracks.push(best);
      }
      best.add(r);
      if (!best.emitted && best.best && best.hits >= this.minHits) {
        best.emitted = true;
        done.push(best);
      }
    }
    for (const t of free) t.missed += 1;
    for (const t of this.tracks.filter((t) => t.missed > this.maxMissed)) {
      this.tracks.splice(this.tracks.indexOf(t), 1);
      if (!t.emitted && t.best) {
        t.emitted = true;
        done.push(t);
      }
    }
    return done;
  }

  /** End of stream: emit every track that has a good read but has not been emitted yet. */
  flush(): Track[] {
    const done = this.tracks.filter((t) => !t.emitted && t.best);
    done.forEach((t) => (t.emitted = true));
    this.tracks = [];
    return done;
  }
}
