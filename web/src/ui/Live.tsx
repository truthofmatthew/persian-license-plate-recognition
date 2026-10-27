import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useApp } from '../App';
import { addLog, type Status } from '../db';
import { PlateTracker, plateKey, readCharConf, type PlateNumber, type Track } from '../lib';
import type { FrameResult } from '../engine';
import { Plate } from './Plate';
import { fmtNum, lookup } from './status';

type Mode = 'camera' | 'video' | 'image' | 'stream';
interface Current { plate: PlateNumber | null; conf: number; found: boolean }

async function toJpeg(bmp: ImageBitmap): Promise<Blob> {
  const c = new OffscreenCanvas(bmp.width, bmp.height);
  c.getContext('2d')!.drawImage(bmp, 0, 0);
  return c.convertToBlob({ type: 'image/jpeg', quality: 0.85 });
}

export function Live() {
  const { t, settings, residents, engine, engineState, reloadEngine } = useApp();
  const lang = settings.lang;
  const [mode, setMode] = useState<Mode>('camera');
  const [running, setRunning] = useState(false);
  const [hasFrame, setHasFrame] = useState(false);
  const [error, setError] = useState('');
  const [current, setCurrent] = useState<Current | null>(null);
  const [stats, setStats] = useState({ ms: 0, rps: 0 });
  const [streamUrl, setStreamUrl] = useState('');
  const [aspect, setAspect] = useState('16 / 9');

  const video = useRef<HTMLVideoElement>(null);
  const overlay = useRef<HTMLCanvasElement>(null);
  const still = useRef<ImageBitmap | null>(null);
  const loop = useRef({ raf: 0, busy: false, frame: 0, lastTime: -1, lastDone: 0, stream: null as MediaStream | null });
  const tracker = useRef(new PlateTracker(settings.minHits));
  const crops = useRef(new Map<number, ImageBitmap>());
  const live = useRef({ settings, residents, engine });
  live.current = { settings, residents, engine };
  tracker.current.minHits = settings.minHits;

  const ready = engineState.status === 'ready';

  const logTracks = useCallback(async (tracks: Track[]) => {
    for (const tr of tracks) {
      const plate = tr.best!;
      const { status, resident } = lookup(live.current.residents, plate);
      const crop = crops.current.get(tr.id);
      crops.current.delete(tr.id);
      await addLog({ time: Date.now(), plate: plateKey(plate), status, resident: resident?.name, conf: tr.agreement, crop: crop && (await toJpeg(crop)) });
      crop?.close();
    }
  }, []);

  const draw = useCallback((res: FrameResult | null) => {
    const c = overlay.current;
    if (!c) return;
    const ctx = c.getContext('2d')!;
    if (res && (c.width !== res.width || c.height !== res.height)) { c.width = res.width; c.height = res.height; }
    ctx.clearRect(0, 0, c.width, c.height);
    if (still.current) ctx.drawImage(still.current, 0, 0);
    const lw = Math.max(2, c.width / 320);
    for (const r of res?.reads ?? []) {
      const [x1, y1, x2, y2] = r.box;
      ctx.lineWidth = lw * 2;
      ctx.strokeStyle = '#000';
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.lineWidth = lw;
      ctx.strokeStyle = r.plate ? '#3d7bff' : '#ffbf2e';
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    }
  }, []);

  const handle = useCallback(async (res: FrameResult) => {
    const now = performance.now();
    const dt = now - loop.current.lastDone;
    loop.current.lastDone = now;
    setStats((s) => ({ ms: res.ms, rps: dt > 0 && dt < 5000 ? (s.rps ? s.rps * 0.8 + 200 / dt : 1000 / dt) : s.rps }));
    draw(res);
    const done = tracker.current.update(res.reads);
    for (const r of res.reads) {
      const tr = tracker.current.tracks.find((x) => x.box === r.box);
      if (tr && r.plate) { crops.current.get(tr.id)?.close(); crops.current.set(tr.id, r.crop); } else r.crop.close();
    }
    const best = [...res.reads].sort((a, b) => Number(!!b.plate) - Number(!!a.plate) || b.plateConf - a.plateConf)[0];
    const tr = best && tracker.current.tracks.find((x) => x.box === best.box);
    setCurrent(best ? { plate: tr?.best ?? best.plate, conf: readCharConf(best), found: true } : { plate: null, conf: 0, found: false });
    await logTracks(done);
  }, [draw, logTracks]);

  const process = useCallback(async (frame: ImageBitmap) => {
    const { engine: e, settings: s } = live.current;
    if (!e) { frame.close(); return; }
    try {
      await handle(await e.run(frame, s.plateConf, s.charConf));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [handle]);

  const stopLoop = useCallback(async () => {
    const l = loop.current;
    cancelAnimationFrame(l.raf);
    l.stream?.getTracks().forEach((tr) => tr.stop());
    l.stream = null;
    const v = video.current;
    if (v) { v.pause(); v.srcObject = null; if (v.src.startsWith('blob:')) URL.revokeObjectURL(v.src); v.removeAttribute('src'); v.load(); }
    setRunning(false);
    await logTracks(tracker.current.flush());
  }, [logTracks]);

  const startLoop = useCallback(() => {
    const l = loop.current;
    l.frame = 0; l.lastTime = -1; l.lastDone = performance.now();
    const tick = () => {
      l.raf = requestAnimationFrame(tick);
      const v = video.current;
      if (!v || v.readyState < 2 || v.currentTime === l.lastTime) return;
      l.lastTime = v.currentTime;
      // Skip frames while the worker is busy and honour the every-Nth setting: the effective rate adapts to the device.
      if (l.busy || l.frame++ % live.current.settings.everyN) return;
      l.busy = true;
      createImageBitmap(v).then(process).catch((e: unknown) => setError(String(e))).finally(() => (l.busy = false));
    };
    tick();
    setRunning(true);
  }, [process]);

  useEffect(() => () => { void stopLoop(); still.current?.close(); crops.current.forEach((b) => b.close()); }, [stopLoop]);

  const reset = async () => {
    await stopLoop();
    setError(''); setCurrent(null); setHasFrame(false);
    still.current?.close(); still.current = null;
    draw(null);
  };

  const playVideo = async (src: { stream?: MediaStream; url?: string }) => {
    const v = video.current!;
    v.crossOrigin = src.url && !src.url.startsWith('blob:') ? 'anonymous' : null; // a remote stream must send CORS headers, or frames cannot be read
    if (src.stream) v.srcObject = src.stream; else v.src = src.url!;
    await v.play();
    setAspect(`${v.videoWidth || 16} / ${v.videoHeight || 9}`);
    setHasFrame(true);
    startLoop();
  };

  const startCamera = async () => {
    await reset();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
      loop.current.stream = stream;
      await playVideo({ stream });
    } catch (e) {
      setError(`${t.cameraError}: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const openFile = async (file: File | undefined) => {
    if (!file) return;
    await reset();
    try {
      if (mode === 'image') {
        still.current = await createImageBitmap(file);
        setAspect(`${still.current.width} / ${still.current.height}`);
        setHasFrame(true);
        draw({ reads: [], ms: 0, width: still.current.width, height: still.current.height });
        setCurrent(null);
        await process(await createImageBitmap(file));
        await logTracks(tracker.current.flush());
      } else {
        await playVideo({ url: URL.createObjectURL(file) });
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const playStream = async () => {
    await reset();
    try { await playVideo({ url: streamUrl.trim() }); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  };

  const status = useMemo(() => (current?.plate ? lookup(residents, current.plate) : null), [current, residents]);
  const statusText: Record<Status, string> = { allowed: t.allowed, denied: t.denied, unknown: t.unknown };
  const isVideo = mode !== 'image';

  return (
    <div className="live">
      <section className="viewer-col" aria-label={t.live}>
        <div className="segmented" role="group" aria-label={t.live}>
          {(['camera', 'video', 'image', 'stream'] as const).map((m) => (
            <button key={m} type="button" data-testid={`mode-${m}`} aria-pressed={mode === m} onClick={() => { void reset(); setMode(m); }}>{t[m]}</button>
          ))}
        </div>

        <div className="source-row">
          {mode === 'camera' && (running
            ? <button type="button" onClick={() => void stopLoop()}>{t.stop}</button>
            : <button type="button" className="primary" disabled={!ready} onClick={() => void startCamera()}>{t.startCamera}</button>)}
          {(mode === 'video' || mode === 'image') && (
            <>
              <label className={`button primary${ready ? '' : ' disabled'}`}>
                {t.chooseFile}
                <input className="visually-hidden" type="file" accept={mode === 'image' ? 'image/*' : 'video/*'} disabled={!ready}
                  data-testid="file-input" onChange={(e) => { void openFile(e.target.files?.[0]); e.target.value = ''; }} />
              </label>
              {running && <button type="button" onClick={() => void stopLoop()}>{t.stop}</button>}
            </>
          )}
          {mode === 'stream' && (
            <form className="stream-form" onSubmit={(e) => { e.preventDefault(); void playStream(); }}>
              <label htmlFor="stream-url">{t.streamLabel}</label>
              <div className="stream-inputs">
                <input id="stream-url" type="url" dir="ltr" required value={streamUrl} placeholder="https://edge.local:1984/api/stream.m3u8?src=gate"
                  aria-describedby="stream-hint" onChange={(e) => setStreamUrl(e.target.value)} />
                {running ? <button type="button" onClick={() => void stopLoop()}>{t.stop}</button> : <button className="primary" disabled={!ready}>{t.play}</button>}
              </div>
              <p id="stream-hint" className="hint">{t.streamHint}</p>
            </form>
          )}
        </div>

        <div className="viewer" style={{ aspectRatio: aspect }}>
          <video ref={video} playsInline muted hidden={!isVideo || !hasFrame} onEnded={() => void stopLoop()} />
          <canvas ref={overlay} className={isVideo ? 'overlay' : 'still'} hidden={!hasFrame} />
          {!hasFrame && (
            <div className="viewer-empty">
              {engineState.status === 'loading' && <p role="status">{t.loadingModels}</p>}
              {engineState.status === 'ready' && <p>{t.pickSource}</p>}
              {engineState.status === 'error' && (
                <div role="alert">
                  <p><strong>{t.modelError}</strong>: <span dir="ltr">{engineState.message}</span></p>
                  <p>{t.modelErrorHint}</p>
                  <button type="button" onClick={reloadEngine}>{t.reload}</button>
                </div>
              )}
            </div>
          )}
        </div>
        {error && <p className="banner error" role="alert" dir="auto">{error}</p>}
      </section>

      <aside className="result" aria-live="polite" data-testid="result" data-key={current?.plate ? plateKey(current.plate) : ''}>
        {current?.plate ? (
          <>
            <Plate plate={current.plate} size="lg" />
            {status && (
              <p className={`status status-${status.status}`} data-testid="status">
                <span className="status-mark" aria-hidden="true">{status.status === 'allowed' ? '✓' : status.status === 'denied' ? '✕' : '?'}</span>
                <span>{statusText[status.status]}{status.resident && <span className="status-name"> · <bdi>{status.resident.name}</bdi>{status.resident.unit && <> · {t.unit} <bdi>{status.resident.unit}</bdi></>}</span>}</span>
              </p>
            )}
            <p className="conf">{t.conf}: {fmtNum(current.conf * 100, lang)}{lang === 'fa' ? '٪' : '%'}</p>
          </>
        ) : (
          <p className="result-empty">{current ? (current.found ? t.partialRead : t.noPlate) : hasFrame ? t.reading : ' '}</p>
        )}
        <dl className="stats">
          <div><dt>{t.backend}</dt><dd dir="ltr" data-testid="backend" data-load-ms={engineState.status === 'ready' ? engineState.loadMs : undefined}>{engineState.status === 'ready' ? `${engineState.backend === 'webgpu' ? 'WebGPU' : 'WASM'} · ${engineState.precision}` : '-'}</dd></div>
          <div><dt>{t.latency}</dt><dd data-testid="latency" data-ms={stats.ms.toFixed(1)}>{stats.ms ? `${fmtNum(stats.ms, lang)} ${t.ms}` : '-'}</dd></div>
          <div><dt>{t.fps}</dt><dd>{stats.rps && running ? fmtNum(stats.rps, lang, 1) : '-'}</dd></div>
        </dl>
      </aside>
    </div>
  );
}
