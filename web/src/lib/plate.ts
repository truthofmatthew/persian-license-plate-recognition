// Persian plate grammar: 2 digits, letter, 3 digits, 2-digit province code. Mirrors plpr/plate.py.
import { CODE_TO_PERSIAN, LETTER_TYPE, VALID_LETTERS, toLatinDigits, toPersianDigits } from './labels';

/** Plain object (not a class) so it survives postMessage between worker and page. */
export interface PlateNumber {
  left: string; // 2 digits
  letter: string; // Latin code, e.g. "B", "Sin", "Taxi"
  middle: string; // 3 digits
  region: string; // 2 digits (province code in the "ایران" box)
}

const KEY_RE = /^(\d{2})([A-Za-z]+|[؀-ۿ])(\d{3})(\d{2})$/;
const isDigit = (c: string) => /^\d$/.test(c);

/** Database key, same format as v1: `34D31966`. */
export const plateKey = (p: PlateNumber): string => `${p.left}${p.letter}${p.middle}${p.region}`;
export const plateLatin = (p: PlateNumber): string => `${p.left} ${p.letter} ${p.middle} - ${p.region}`;
export const platePersian = (p: PlateNumber): string =>
  toPersianDigits(`${p.left} ${CODE_TO_PERSIAN[p.letter] ?? p.letter} ${p.middle} - ایران ${p.region}`);
export const plateValid = (p: PlateNumber): boolean => VALID_LETTERS.has(p.letter) && p.region !== '00';
export const plateType = (p: PlateNumber): string => LETTER_TYPE[p.letter] ?? 'private';

export function fromKey(key: string): PlateNumber | null {
  const m = KEY_RE.exec(toLatinDigits(key.replace(/[ -]/g, '')));
  return m ? { left: m[1], letter: m[2], middle: m[3], region: m[4] } : null;
}

/** Left-to-right character codes -> plate, or null if the layout is not d d L d d d d d. */
export function parseCodes(codes: readonly string[]): PlateNumber | null {
  if (codes.length !== 8) return null;
  if (!codes.every((c, i) => i === 2 || isDigit(c)) || isDigit(codes[2])) return null;
  return { left: codes.slice(0, 2).join(''), letter: codes[2], middle: codes.slice(3, 6).join(''), region: codes.slice(6, 8).join('') };
}
