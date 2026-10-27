import { expect, it } from 'vitest';
import { parseCsv, toCsv } from './csv';

it('round-trips quotes, commas and newlines', () => {
  const rows = [['name', 'unit'], ['Resident "A", 1', 'line1\nline2'], ['ساکن', '12']];
  expect(parseCsv(toCsv(rows))).toEqual(rows);
  expect(parseCsv('a,b\r\n\r\nc,d')).toEqual([['a', 'b'], ['c', 'd']]);
});
