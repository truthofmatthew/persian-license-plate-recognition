import { CODE_TO_PERSIAN, plateKey, platePersian, toPersianDigits, type PlateNumber } from '../lib';

/** An Iranian plate as drawn on the car: blue I.R. IRAN strip, digits, letter, then the "ایران" region box. */
export function Plate({ plate, size = 'md' }: { plate: PlateNumber; size?: 'sm' | 'md' | 'lg' }) {
  return (
    <div className={`plate plate-${size}`} dir="ltr" role="img" aria-label={platePersian(plate)} data-key={plateKey(plate)}>
      <div className="plate-strip" aria-hidden="true">
        <span className="plate-flag"><i /><i /><i /></span>
        <span>I.R.</span>
        <span>IRAN</span>
      </div>
      <div className="plate-main" aria-hidden="true">
        <span>{toPersianDigits(plate.left)}</span>
        <span className="plate-letter">{CODE_TO_PERSIAN[plate.letter] ?? plate.letter}</span>
        <span>{toPersianDigits(plate.middle)}</span>
      </div>
      <div className="plate-region" aria-hidden="true">
        <span className="plate-iran">ایران</span>
        <span>{toPersianDigits(plate.region)}</span>
      </div>
    </div>
  );
}
