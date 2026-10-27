import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { DEFAULT_SETTINGS, listResidents, loadSettings, saveSettings, type Resident, type Settings } from './db';
import { Engine, type EngineState } from './engine';
import { DICTS, type Dict } from './i18n';
import { Live } from './ui/Live';
import { LogView } from './ui/Log';
import { Residents } from './ui/Residents';
import { SettingsView } from './ui/Settings';

const TABS = ['live', 'log', 'residents', 'settings'] as const;
type Tab = (typeof TABS)[number];
const tabFromHash = (): Tab => (TABS as readonly string[]).includes(location.hash.slice(1)) ? (location.hash.slice(1) as Tab) : 'live';

export interface AppCtx {
  t: Dict; settings: Settings; setSettings: (s: Settings) => void;
  residents: Resident[]; refreshResidents: () => Promise<void>;
  engine: Engine | null; engineState: EngineState; reloadEngine: () => void;
}
const Ctx = createContext<AppCtx | null>(null);
export const useApp = () => useContext(Ctx)!;

export function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [settings, setSettingsState] = useState<Settings | null>(null);
  const [residents, setResidents] = useState<Resident[]>([]);
  const [engine, setEngine] = useState<Engine | null>(null);
  const [engineState, setEngineState] = useState<EngineState>({ status: 'loading' });
  const [engineGen, setEngineGen] = useState(0);
  const [storageError, setStorageError] = useState(false);

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    addEventListener('hashchange', onHash);
    return () => removeEventListener('hashchange', onHash);
  }, []);

  const refreshResidents = useCallback(async () => setResidents(await listResidents()), []);
  useEffect(() => {
    loadSettings()
      .then(setSettingsState)
      .catch(() => { setStorageError(true); setSettingsState(DEFAULT_SETTINGS); });
    refreshResidents().catch(() => setStorageError(true));
  }, [refreshResidents]);

  // Engine survives tab switches; it restarts when the backend or precision changes, or on "Reload models".
  const backend = settings?.backend, precision = settings?.precision;
  useEffect(() => {
    if (!backend || !precision) return;
    const e = new Engine({ backend, precision }, setEngineState);
    setEngine(e);
    return () => e.dispose();
  }, [engineGen, backend, precision]);

  const lang = settings?.lang ?? 'fa', theme = settings?.theme ?? 'auto';
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === 'fa' ? 'rtl' : 'ltr';
    if (theme === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
  }, [lang, theme]);

  const setSettings = useCallback((s: Settings) => { setSettingsState(s); saveSettings(s).catch(() => setStorageError(true)); }, []);
  const ctx = useMemo<AppCtx | null>(
    () => settings && { t: DICTS[settings.lang], settings, setSettings, residents, refreshResidents, engine, engineState, reloadEngine: () => setEngineGen((g) => g + 1) },
    [settings, setSettings, residents, refreshResidents, engine, engineState],
  );
  if (!ctx) return null;
  const { t } = ctx;

  return (
    <Ctx.Provider value={ctx}>
      <header className="topbar">
        <span className="brand" dir="ltr">PLPR</span>
        <nav className="tabs" aria-label="PLPR">
          {TABS.map((k) => (
            <a key={k} href={`#${k}`} aria-current={tab === k ? 'page' : undefined}>{t[k]}</a>
          ))}
        </nav>
        <button type="button" className="ghost" lang={settings!.lang === 'fa' ? 'en' : 'fa'} aria-label={t.langSwitchLabel}
          onClick={() => setSettings({ ...settings!, lang: settings!.lang === 'fa' ? 'en' : 'fa' })}>
          {t.langSwitch}
        </button>
      </header>
      {storageError && <p className="banner error" role="alert">{t.storageError}</p>}
      <main>
        {tab === 'live' && <Live />}
        {tab === 'log' && <LogView />}
        {tab === 'residents' && <Residents />}
        {tab === 'settings' && <SettingsView />}
      </main>
    </Ctx.Provider>
  );
}
