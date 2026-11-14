// Fails when the tracked bundle is not what `npm run build` makes from src.
//
// Home Assistant serves custom_components/home_stock/panel/home-stock-panel.js,
// not frontend/src: a source change merged without a rebuild, or a bundle
// edited by hand, ships something no test has looked at. This builds the
// bundle IN MEMORY with the very rollup.config.mjs that `npm run build` uses
// (rollup's JS API, `bundle.generate`, never `bundle.write`), so it never
// touches the tracked file, and compares it byte for byte.
//
// The build is reproducible: two builds from a clean `npm ci` were measured
// byte-identical before this check was added, so a difference is a real one.
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { rollup } from 'rollup';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
process.chdir(root);

const { default: config } = await import(resolve(root, 'rollup.config.mjs'));
const tracked = resolve(root, config.output.file);

const bundle = await rollup(config);
let output;
try {
  ({ output } = await bundle.generate(config.output));
} finally {
  await bundle.close();
}
const chunks = output.filter((item) => item.type === 'chunk');
if (chunks.length !== 1) {
  console.error(`Expected one chunk, rollup produced ${chunks.length}.`);
  process.exit(1);
}
const built = chunks[0].code;
const current = await readFile(tracked, 'utf8');

if (built !== current) {
  console.error(
    `${config.output.file} is not the build of src/ (${current.length} characters tracked, `
    + `${built.length} built). Run \`npm run build\` and commit the result.`,
  );
  process.exit(1);
}
console.log(`${config.output.file} matches the build of src/ (${built.length} characters).`);
