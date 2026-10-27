import { useEffect, useMemo, useState } from 'react';
import { useApp } from '../App';
import { clearLog, listLog, type LogEntry, type Status } from '../db';
import { download, toCsv } from '../csv';
import { fromKey, platePersian } from '../lib';
import { Plate } from './Plate';

export const jalali = (lang: 'fa' | 'en') =>
  new Intl.DateTimeFormat(lang === 'fa' ? 'fa-IR-u-ca-persian' : 'en-US-u-ca-persian', { dateStyle: 'medium', timeStyle: 'short' });

function Thumb({ blob, alt }: { blob?: Blob; alt: string }) {
  const url = useMemo(() => (blob ? URL.createObjectURL(blob) : ''), [blob]);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  return url ? <img className="thumb" src={url} alt={alt} /> : <span className="thumb thumb-none" />;
}

export function LogView() {
  const { t, settings } = useApp();
  const [rows, setRows] = useState<LogEntry[] | null>(null);
  const [error, setError] = useState('');
  const [q, setQ] = useState('');

  const load = () => listLog().then(setRows).catch((e: unknown) => setError(String(e)));
  useEffect(() => { void load(); }, []);

  const fmt = jalali(settings.lang);
  const statusText: Record<Status, string> = { allowed: t.allowed, denied: t.denied, unknown: t.unknown };
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!rows || !needle) return rows ?? [];
    return rows.filter((r) => {
      const p = fromKey(r.plate);
      return [r.plate, p ? platePersian(p) : '', r.resident ?? ''].some((s) => s.toLowerCase().includes(needle));
    });
  }, [rows, q]);

  const exportCsv = () => {
    const iso = new Date().toISOString().slice(0, 10);
    download(`plpr-log-${iso}.csv`, toCsv([
      ['time_iso', 'time_jalali', 'plate', 'status', 'resident', 'agreement'],
      ...(rows ?? []).map((r) => [new Date(r.time).toISOString(), jalali('fa').format(r.time), r.plate, r.status, r.resident ?? '', r.conf.toFixed(3)]),
    ]));
  };

  return (
    <section className="page">
      <div className="page-head">
        <h1>{t.log}</h1>
        <div className="actions">
          <button type="button" disabled={!rows?.length} onClick={exportCsv}>{t.exportCsv}</button>
          <button type="button" className="danger" disabled={!rows?.length}
            onClick={() => { if (confirm(t.confirmClear)) void clearLog().then(load); }}>{t.clearLog}</button>
        </div>
      </div>
      <label className="search">
        <span className="visually-hidden">{t.search}</span>
        <input type="search" placeholder={t.search} value={q} onChange={(e) => setQ(e.target.value)} />
      </label>
      {error && <p className="banner error" role="alert">{error}</p>}
      {!rows && !error && <p role="status" className="muted">{t.reading}</p>}
      {rows && !rows.length && <p className="empty">{t.emptyLog}</p>}
      {rows && rows.length > 0 && !shown.length && <p className="empty">{t.noMatches}</p>}
      {shown.length > 0 && (
        <ul className="log-list">
          {shown.map((r) => {
            const p = fromKey(r.plate);
            return (
              <li key={r.id} className="log-row">
                <Thumb blob={r.crop} alt={`${t.photo} ${r.plate}`} />
                <div className="log-plate">{p ? <Plate plate={p} size="sm" /> : <span dir="ltr">{r.plate}</span>}</div>
                <div className="log-meta">
                  <span className={`status status-${r.status} status-sm`}>
                    <span className="status-mark" aria-hidden="true">{r.status === 'allowed' ? '✓' : r.status === 'denied' ? '✕' : '?'}</span>
                    {statusText[r.status]}{r.resident && <> · <bdi>{r.resident}</bdi></>}
                  </span>
                  <time dateTime={new Date(r.time).toISOString()}>{fmt.format(r.time)}</time>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
