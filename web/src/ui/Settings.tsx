import { useApp } from '../App';
import type { Settings } from '../db';
import { fmtNum } from './status';

export function SettingsView() {
  const { t, settings, setSettings, engineState, reloadEngine } = useApp();
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setSettings({ ...settings, [k]: v });
  const range = (k: 'plateConf' | 'charConf', label: string) => (
    <label className="field">
      <span>{label}: <output>{fmtNum(settings[k], settings.lang, 2)}</output></span>
      <input type="range" min={0.1} max={0.9} step={0.05} value={settings[k]} onChange={(e) => set(k, +e.target.value)} />
    </label>
  );
  const select = <K extends 'backend' | 'precision' | 'lang' | 'theme'>(k: K, label: string, opts: [Settings[K], string][]) => (
    <label className="field">
      <span>{label}</span>
      <select value={settings[k]} onChange={(e) => set(k, e.target.value as Settings[K])}>
        {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
  const int = (k: 'minHits' | 'everyN', label: string, max: number, hint?: string) => (
    <label className="field">
      <span>{label}</span>
      <input type="number" min={1} max={max} value={settings[k]} aria-describedby={hint ? `${k}-hint` : undefined}
        onChange={(e) => { const v = Math.round(+e.target.value); if (v >= 1 && v <= max) set(k, v); }} />
      {hint && <span id={`${k}-hint`} className="hint">{hint}</span>}
    </label>
  );

  return (
    <section className="page settings">
      <h1>{t.settings}</h1>
      <div className="privacy" role="note">
        <h2>{t.privacyTitle}</h2>
        <p>{t.privacy}</p>
      </div>
      <fieldset>
        <legend>{t.thresholds}</legend>
        {range('plateConf', t.plateConf)}
        {range('charConf', t.charConf)}
        {int('minHits', t.minHits, 10)}
        {int('everyN', t.everyN, 30, t.everyNHint)}
      </fieldset>
      <fieldset>
        <legend>{t.engine}</legend>
        {select('backend', t.backendChoice, [['auto', t.auto], ['webgpu', 'WebGPU'], ['wasm', 'WASM']])}
        {select('precision', t.precision, [['auto', t.auto], ['fp32', 'fp32'], ['fp16', 'fp16']])}
        <p className="hint">{t.backendHint}</p>
        <p className="engine-state" role="status">
          {engineState.status === 'ready' && <span dir="ltr">{engineState.backend === 'webgpu' ? 'WebGPU' : 'WASM'} · {engineState.precision} · {(engineState.loadMs / 1000).toFixed(1)} s</span>}
          {engineState.status === 'loading' && t.loadingModels}
          {engineState.status === 'error' && <span className="error-text" dir="ltr">{engineState.message}</span>}
        </p>
        <button type="button" onClick={reloadEngine}>{t.reload}</button>
      </fieldset>
      <fieldset>
        <legend>{t.appearance}</legend>
        {select('lang', t.language, [['fa', 'فارسی'], ['en', 'English']])}
        {select('theme', t.theme, [['auto', t.auto], ['light', t.light], ['dark', t.dark]])}
      </fieldset>
    </section>
  );
}
