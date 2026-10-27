import { useRef, useState } from 'react';
import { useApp } from '../App';
import { addResidents, deleteResident, saveResident, type Resident } from '../db';
import { download, parseCsv, toCsv } from '../csv';
import { fromKey, plateKey, type PlateNumber } from '../lib';
import { Plate } from './Plate';
import { PlateInput } from './PlateInput';

const EMPTY_PLATE: PlateNumber = { left: '', letter: 'B', middle: '', region: '' };
const blank = (): Resident => ({ name: '', unit: '', car: '', plate: '', allowed: true });

export function Residents() {
  const { t, residents, refreshResidents } = useApp();
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState<Resident>(blank);
  const [plate, setPlate] = useState<PlateNumber>(EMPTY_PLATE);
  const [notice, setNotice] = useState<{ ok: boolean; text: string } | null>(null);

  const open = (r: Resident) => {
    setDraft(r);
    setPlate(fromKey(r.plate) ?? EMPTY_PLATE);
    dialog.current?.showModal();
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const key = plateKey(plate);
    if (!fromKey(key)) return;
    await saveResident({ ...draft, plate: key });
    dialog.current?.close();
    await refreshResidents();
  };

  const importCsv = async (file?: File) => {
    if (!file) return;
    const rows = parseCsv(await file.text());
    const head = rows[0]?.map((h) => h.trim().toLowerCase()) ?? [];
    const col = (name: string, i: number) => (head.includes(name) ? head.indexOf(name) : i);
    const body = head.includes('plate') ? rows.slice(1) : rows;
    const idx = { name: col('name', 0), unit: col('unit', 1), car: col('car', 2), plate: col('plate', 3), allowed: col('allowed', 4) };
    const parsed = body.flatMap((r): Resident[] => {
      const p = fromKey(r[idx.plate] ?? '');
      if (!p) return [];
      const allowed = !/^(0|false|no|خیر|نه)$/i.test((r[idx.allowed] ?? '').trim());
      return [{ name: r[idx.name] ?? '', unit: r[idx.unit] ?? '', car: r[idx.car] ?? '', plate: plateKey(p), allowed }];
    });
    if (!parsed.length) { setNotice({ ok: false, text: t.importError }); return; }
    await addResidents(parsed);
    await refreshResidents();
    setNotice({ ok: true, text: t.imported(parsed.length) });
  };

  const exportCsv = () =>
    download('plpr-residents.csv', toCsv([['name', 'unit', 'car', 'plate', 'allowed'], ...residents.map((r) => [r.name, r.unit, r.car, r.plate, r.allowed])]));

  return (
    <section className="page">
      <div className="page-head">
        <h1>{t.residents}</h1>
        <div className="actions">
          <button type="button" className="primary" onClick={() => open(blank())}>{t.addResident}</button>
          <label className="button">
            {t.importCsv}
            <input className="visually-hidden" type="file" accept=".csv,text/csv" data-testid="csv-input"
              onChange={(e) => { void importCsv(e.target.files?.[0]); e.target.value = ''; }} />
          </label>
          <button type="button" disabled={!residents.length} onClick={exportCsv}>{t.exportCsv}</button>
        </div>
      </div>
      {notice && <p className={`banner ${notice.ok ? 'ok' : 'error'}`} role="status">{notice.text}</p>}
      {!residents.length ? <p className="empty">{t.emptyResidents}</p> : (
        <ul className="resident-list">
          {residents.map((r) => {
            const p = fromKey(r.plate);
            return (
              <li key={r.id} className="resident-row">
                <div className="resident-plate">{p ? <Plate plate={p} size="sm" /> : <span dir="ltr">{r.plate}</span>}</div>
                <div className="resident-info">
                  <strong>{r.name || '-'}</strong>
                  <span className="muted">{[r.unit && `${t.unit} ${r.unit}`, r.car].filter(Boolean).join(' · ')}</span>
                </div>
                <label className="switch">
                  <input type="checkbox" checked={r.allowed} onChange={(e) => void saveResident({ ...r, allowed: e.target.checked }).then(refreshResidents)} />
                  <span>{r.allowed ? t.allowed : t.denied}</span>
                </label>
                <div className="row-actions">
                  <button type="button" onClick={() => open(r)}>{t.edit}</button>
                  <button type="button" className="danger" onClick={() => { if (confirm(t.confirmDelete)) void deleteResident(r.id!).then(refreshResidents); }}>{t.del}</button>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      <dialog ref={dialog} aria-labelledby="resident-title">
        <form onSubmit={(e) => void submit(e)} className="resident-form">
          <h2 id="resident-title">{draft.id ? t.editResident : t.addResident}</h2>
          <label>{t.name}<input required value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
          <div className="two">
            <label>{t.unit}<input value={draft.unit} onChange={(e) => setDraft({ ...draft, unit: e.target.value })} /></label>
            <label>{t.car}<input value={draft.car} onChange={(e) => setDraft({ ...draft, car: e.target.value })} /></label>
          </div>
          <PlateInput value={plate} onChange={setPlate} />
          <label className="switch">
            <input type="checkbox" checked={draft.allowed} onChange={(e) => setDraft({ ...draft, allowed: e.target.checked })} />
            <span>{t.allowEntry}</span>
          </label>
          <div className="actions end">
            <button type="button" onClick={() => dialog.current?.close()}>{t.cancel}</button>
            <button className="primary">{t.save}</button>
          </div>
        </form>
      </dialog>
    </section>
  );
}
