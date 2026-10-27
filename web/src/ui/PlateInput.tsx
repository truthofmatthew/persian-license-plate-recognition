import { useId } from 'react';
import { CHAR_CLASSES, toLatinDigits, type PlateNumber } from '../lib';
import { useApp } from '../App';

const LETTERS = CHAR_CLASSES.slice(10).map(([code, fa]) => ({ code, label: code === 'PwD' ? `${fa} (معلولین)` : fa }));
const digits = (v: string, n: number) => toLatinDigits(v).replace(/\D/g, '').slice(0, n);

/** Plate entry laid out like the plate itself: 2 digits, letter, 3 digits, region. */
export function PlateInput({ value, onChange }: { value: PlateNumber; onChange: (p: PlateNumber) => void }) {
  const { t } = useApp();
  const id = useId();
  const field = (k: 'left' | 'middle' | 'region', n: number, label: string) => (
    <label className="plate-field">
      <span className="visually-hidden">{label}</span>
      <input inputMode="numeric" pattern={`[0-9]{${n}}`} required size={n} maxLength={n} value={value[k]} placeholder={'0'.repeat(n)}
        aria-describedby={`${id}-hint`} onChange={(e) => onChange({ ...value, [k]: digits(e.target.value, n) })} />
    </label>
  );
  return (
    <fieldset className="plate-input" dir="ltr">
      <legend>{t.plate}</legend>
      <div className="plate-input-row">
        {field('left', 2, t.plateDigits2)}
        <label className="plate-field">
          <span className="visually-hidden">{t.plateLetter}</span>
          <select value={value.letter} onChange={(e) => onChange({ ...value, letter: e.target.value })} lang="fa">
            {LETTERS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
          </select>
        </label>
        {field('middle', 3, t.plateDigits3)}
        <span className="plate-input-sep" aria-hidden="true">ایران</span>
        {field('region', 2, t.plateRegion)}
      </div>
      <p id={`${id}-hint`} className="hint">{t.plateInvalid}</p>
    </fieldset>
  );
}
