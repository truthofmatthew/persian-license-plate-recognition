// Everything the app stores lives in this IndexedDB database. Nothing is uploaded.
export interface Resident { id?: number; name: string; unit: string; car: string; plate: string; allowed: boolean }
export type Status = 'allowed' | 'denied' | 'unknown';
export interface LogEntry { id?: number; time: number; plate: string; status: Status; resident?: string; conf: number; crop?: Blob }
export interface Settings {
  plateConf: number; charConf: number; minHits: number; everyN: number;
  backend: 'auto' | 'webgpu' | 'wasm'; precision: 'auto' | 'fp32' | 'fp16';
  lang: 'fa' | 'en'; theme: 'auto' | 'light' | 'dark';
}
export const DEFAULT_SETTINGS: Settings = { plateConf: 0.5, charConf: 0.5, minHits: 3, everyN: 2, backend: 'auto', precision: 'auto', lang: 'fa', theme: 'auto' };

type Store = 'residents' | 'log' | 'kv';
let dbp: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  return (dbp ??= new Promise((resolve, reject) => {
    const req = indexedDB.open('plpr', 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      db.createObjectStore('residents', { keyPath: 'id', autoIncrement: true }).createIndex('plate', 'plate');
      db.createObjectStore('log', { keyPath: 'id', autoIncrement: true });
      db.createObjectStore('kv');
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  }));
}

async function tx<T>(store: Store, mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T> | void): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const req = fn(t.objectStore(store));
    t.oncomplete = () => resolve(req ? req.result : (undefined as T));
    t.onerror = () => reject(t.error);
  });
}

export const listResidents = () => tx<Resident[]>('residents', 'readonly', (s) => s.getAll());
export const saveResident = (r: Resident) => tx('residents', 'readwrite', (s) => s.put(r));
export const deleteResident = (id: number) => tx('residents', 'readwrite', (s) => s.delete(id));
export const addResidents = (rs: Resident[]) => tx('residents', 'readwrite', (s) => void rs.forEach((r) => s.add(r)));

export const listLog = async () => (await tx<LogEntry[]>('log', 'readonly', (s) => s.getAll())).reverse();
export const addLog = (e: LogEntry) => tx('log', 'readwrite', (s) => s.add(e));
export const clearLog = () => tx('log', 'readwrite', (s) => s.clear());

export const loadSettings = async (): Promise<Settings> => ({ ...DEFAULT_SETTINGS, ...(await tx<Partial<Settings> | undefined>('kv', 'readonly', (s) => s.get('settings'))) });
export const saveSettings = (v: Settings) => tx('kv', 'readwrite', (s) => s.put(v, 'settings'));
