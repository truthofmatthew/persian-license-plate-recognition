import { plateKey, type PlateNumber } from '../lib';
import type { Resident, Status } from '../db';

export function lookup(residents: Resident[], plate: PlateNumber): { status: Status; resident?: Resident } {
  const key = plateKey(plate);
  const resident = residents.find((r) => r.plate === key);
  return { status: resident ? (resident.allowed ? 'allowed' : 'denied') : 'unknown', resident };
}

export const fmtNum = (n: number, lang: 'fa' | 'en', digits = 0) =>
  n.toLocaleString(lang === 'fa' ? 'fa-IR' : 'en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits });
