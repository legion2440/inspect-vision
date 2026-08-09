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

test('dashboard quick upload and recent inspection content starts at the same height', () => {
  const dashboard = read('../src/routes/index.jsx');
  const css = read('../src/styles/ui-controls.css');

  assert.equal((dashboard.match(/qc-sectionrow qc-dash-sectionhead/g) || []).length, 2);
  assert.match(dashboard, /qc-dash-sectionhead[\s\S]*Quick upload/);
  assert.match(dashboard, /qc-dash-sectionhead[\s\S]*Recent inspections/);
  assert.match(css, /\.qc-dash-sectionhead[\s\S]*min-height: 36px/);
});

test('sample catalog keeps general flow but starts each specialist domain on a fresh row', () => {
  const route = read('../src/routes/samples.jsx');
  const appCss = read('../src/styles/app.css');
  const css = read('../src/styles/ui-controls.css');

  assert.match(route, /sample\.recommendedModelId !== 'bayespfl-general-v1'/);
  assert.match(route, /qc-sample-domain\$\{specialist \? ' is-specialist' : ''\}/);
  assert.doesNotMatch(route, /function groupLabel/);
  assert.doesNotMatch(route, /<h2>\{domain\}<\/h2>/);
  assert.match(route, /'Bottle neck'/);
  assert.match(route, /'No defect'/);
  assert.match(route, /sampleCardTitle\(sample, domain\)/);
  assert.match(appCss, /\.qc-sample-grid \{ display: grid; grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
  assert.match(css, /\.qc-sample-catalog-grid > \.qc-sample-domain:not\(\.is-specialist\) \{ display: contents; \}/);
  assert.match(css, /\.qc-sample-catalog-grid > \.qc-sample-domain\.is-specialist[\s\S]*grid-column: 1 \/ -1/);
  assert.match(css, /\.qc-sample-catalog-grid > \.qc-sample-domain\.is-specialist[\s\S]*grid-template-columns: repeat\(3, minmax\(0, 1fr\)\)/);
});

test('sample actions align at the bottom of equal-height cards', () => {
  const css = read('../src/styles/ui-controls.css');

  assert.match(css, /\.qc-sample-card[\s\S]*height: 100%/);
  assert.match(css, /\.qc-sample-copy[\s\S]*flex: 1/);
  assert.match(css, /\.qc-sample-copy \.card-body \{ margin-top: 0; \}/);
  assert.match(css, /\.qc-sample-actions \{ margin-top: auto; \}/);
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
