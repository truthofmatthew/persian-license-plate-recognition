// Copies the ONNX models and labels from ../model/onnx into public/models (gitignored).
import { cpSync, mkdirSync, readdirSync } from 'node:fs';

const src = new URL('../../model/onnx/', import.meta.url);
const dst = new URL('../public/models/', import.meta.url);
mkdirSync(dst, { recursive: true });
const files = readdirSync(src).filter((f) => f.endsWith('.onnx') || f === 'labels.json');
if (!files.length) throw new Error('No models in model/onnx. Run scripts/export_onnx.py first.');
for (const f of files) cpSync(new URL(f, src), new URL(f, dst));
console.log(`copied ${files.join(', ')} -> public/models/`);
