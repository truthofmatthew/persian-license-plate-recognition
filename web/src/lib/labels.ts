// Mirrors plpr/labels.py. Each entry is [code, persian]; `code` is the Latin code used in DB keys.
export const CHAR_CLASSES: ReadonlyArray<readonly [string, string]> = [
  ['0', '۰'], ['1', '۱'], ['2', '۲'], ['3', '۳'], ['4', '۴'],
  ['5', '۵'], ['6', '۶'], ['7', '۷'], ['8', '۸'], ['9', '۹'],
  ['A', 'الف'], ['B', 'ب'], ['P', 'پ'], ['Taxi', 'ت'], ['ث', 'ث'],
  ['J', 'ج'], ['چ', 'چ'], ['ح', 'ح'], ['خ', 'خ'], ['D', 'د'],
  ['ذ', 'ذ'], ['ر', 'ر'], ['ز', 'ز'], ['ژ', 'ژ'], ['Sin', 'س'],
  ['ش', 'ش'], ['Sad', 'ص'], ['ض', 'ض'], ['T', 'ط'], ['ظ', 'ظ'],
  ['PuV', 'ع'], ['غ', 'غ'], ['ف', 'ف'], ['Gh', 'ق'], ['ک', 'ک'],
  ['گ', 'گ'], ['L', 'ل'], ['M', 'م'], ['N', 'ن'], ['H', 'ه'],
  ['V', 'و'], ['Y', 'ی'], ['PwD', 'ژ'], // PwD: disabled / veterans plate
];

export const CODE_TO_PERSIAN: Record<string, string> = Object.fromEntries(CHAR_CLASSES);

export const VALID_LETTERS = new Set(['A', 'B', 'P', 'Taxi', 'J', 'D', 'Sin', 'Sad', 'T', 'PuV', 'Gh', 'L', 'M', 'N', 'H', 'V', 'Y', 'PwD', 'ژ', 'ش', 'ک', 'ز']);

export const LETTER_TYPE: Record<string, string> = {
  Taxi: 'taxi', PuV: 'public', A: 'government', PwD: 'disabled',
  Sad: 'police', P: 'police', Sin: 'public', Gh: 'military', 'ش': 'military',
};

const FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹';
const AR_DIGITS = '٠١٢٣٤٥٦٧٨٩';

/** Persian and Arabic-Indic digits -> ASCII digits. */
export const toLatinDigits = (s: string): string =>
  s.replace(/[۰-۹٠-٩]/g, (d) => String(FA_DIGITS.includes(d) ? FA_DIGITS.indexOf(d) : AR_DIGITS.indexOf(d)));

export const toPersianDigits = (s: string): string => s.replace(/[0-9]/g, (d) => FA_DIGITS[+d]);

/** Arabic presentation letters -> Persian (ي->ی, ك->ک), strip ZWJ/ZWNJ. */
export const normalizePersian = (s: string): string => s.replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/[‍‌]/g, '');
