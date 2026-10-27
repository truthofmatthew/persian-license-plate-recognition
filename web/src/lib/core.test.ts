// Mirrors tests/test_core.py (the model test lives in e2e/read.spec.ts).
import { describe, expect, it } from 'vitest';
import { fromKey, parseCodes, plateKey, platePersian, plateType, plateValid } from './plate';
import { decode, type PlateRead } from './pipeline';
import { PlateTracker } from './tracker';

describe('plate', () => {
  it('parses and round-trips keys', () => {
    const p = parseCodes([...'34', 'D', ...'31966'])!;
    expect(plateKey(p)).toBe('34D31966');
    expect(plateValid(p)).toBe(true);
    expect(fromKey('۳۴D۳۱۹-۶۶')).toEqual(p);
    expect(parseCodes(['Sin', '4', 'D', '3', '1', '9', '6', '6'])).toBeNull();
    expect(parseCodes([...'3412'])).toBeNull();
    expect(platePersian(p)).toContain('ایران');
    expect(plateType(p)).toBe('private');
  });
});

describe('tracker', () => {
  it('votes and emits once', () => {
    const good = [...'12', 'B', ...'34567'];
    const noisy = [...'12', 'B', ...'34561'];
    const t = new PlateTracker(3);
    const out = [];
    for (const [codes, conf] of [[good, 0.9], [noisy, 0.4], [good, 0.8], [good, 0.9]] as const) {
      const r: PlateRead = { box: [10, 10, 110, 40], plateConf: 0.8, codes: [...codes], charConfs: Array(8).fill(conf), plate: parseCodes(codes) };
      out.push(...t.update([r]));
    }
    expect(out.map((tr) => plateKey(tr.best!))).toEqual(['12B34567']);
  });

  it('flush emits a single good read once', () => {
    const t = new PlateTracker(3);
    const codes = [...'34', 'D', ...'31966'];
    t.update([{ box: [0, 0, 50, 20], plateConf: 0.9, codes, charConfs: Array(8).fill(0.9), plate: parseCodes(codes) }]);
    expect(t.flush().map((tr) => plateKey(tr.best!))).toEqual(['34D31966']);
    expect(t.flush()).toEqual([]);
  });
});

describe('decode', () => {
  it('scores obj*cls and suppresses overlaps class-agnostically', () => {
    // rows: cx, cy, w, h, obj, cls0, cls1
    const rows = [
      [50, 50, 20, 20, 0.9, 0.1, 0.9], // score 0.81, cls 1
      [52, 50, 20, 20, 0.9, 0.8, 0.1], // overlaps the first, lower score: dropped
      [200, 50, 20, 20, 0.6, 0.9, 0.1], // 0.54, kept
      [300, 50, 20, 20, 0.6, 0.5, 0.5], // 0.3, below conf
    ];
    const det = decode(new Float32Array(rows.flat()), 4, 7, 0.5, 0.45);
    expect(det.map((d) => [d.cls, +d.score.toFixed(2), d.box[0]])).toEqual([[1, 0.81, 40], [0, 0.54, 190]]);
  });
});
