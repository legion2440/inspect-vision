import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const read = (relativePath) => readFileSync(new URL(relativePath, import.meta.url), 'utf8');

test('shared model selector uses blueprint framing and exposes Other objects', () => {
  const selector = read('../src/components/ModelSelector.jsx');

  assert.match(selector, /import Blueprint from '\.\/Blueprint\.jsx'/);
  assert.match(selector, /<Blueprint as="section" className=\{`qc-model-selector/);
  assert.match(selector, /value: 'Other objects'/);
  assert.match(selector, /general zero-shot prompt/);
  assert.match(selector, /Custom values are allowed/);
});

test('quick upload and model controls share the blueprint frame language', () => {
  const uploader = read('../src/components/ImageUploader.jsx');
  const css = read('../src/styles/ui-controls.css');

  assert.match(uploader, /<Blueprint[\s\S]*qc-drop/);
  assert.match(css, /\.qc-model-selector\.blueprint,[\s\S]*\.qc-drop\.blueprint/);
  assert.match(css, /border-style: solid/);
});

test('sample catalog keeps semantic groups while cards share a three-column grid', () => {
  const route = read('../src/routes/samples.jsx');
  const appCss = read('../src/styles/app.css');
  const css = read('../src/styles/ui-controls.css');

  assert.match(route, /<div className="qc-sample-grid qc-sample-catalog-grid">/);
  assert.match(route, /<section className="qc-sample-domain" aria-label=\{domain\}/);
  assert.doesNotMatch(route, /function groupLabel/);
  assert.doesNotMatch(route, /<h2>\{domain\}<\/h2>/);
  assert.match(route, /'Bottle neck'/);
  assert.match(route, /'No defect'/);
  assert.match(route, /sampleCardTitle\(sample, domain\)/);
  assert.match(appCss, /\.qc-sample-grid \{ display: grid; grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(appCss, /\.qc-sample-grid, \.qc-attribution-grid \{ grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(appCss, /\.qc-stats, \.qc-filters, \.qc-metagrid, \.qc-sample-grid, \.qc-attribution-grid \{ grid-template-columns: 1fr; \}/);
  assert.match(css, /\.qc-sample-catalog-grid > \.qc-sample-domain \{ display: contents; \}/);
});

test('sample preview preserves the complete source image instead of cropping it', () => {
  const css = read('../src/styles/ui-controls.css');

  assert.match(css, /\.qc-sample-image-wrap[\s\S]*aspect-ratio: 1 \/ 1/);
  assert.match(css, /\.qc-sample-image-wrap[\s\S]*overflow: visible/);
  assert.match(css, /\.qc-sample-image[\s\S]*width: auto/);
  assert.match(css, /\.qc-sample-image[\s\S]*height: auto/);
  assert.match(css, /\.qc-sample-image[\s\S]*max-width: 100%/);
  assert.match(css, /\.qc-sample-image[\s\S]*max-height: 100%/);
  assert.match(css, /\.qc-sample-image[\s\S]*object-fit: contain/);
});
