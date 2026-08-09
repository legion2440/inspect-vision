import { useEffect, useId, useMemo, useRef, useState } from 'react';
import Blueprint from './Blueprint.jsx';
import { installModelCommand, modelClassesLabel } from '../utils/models.js';

const EVIDENCE_LABELS = {
  local: 'locally checked',
  upstream: 'upstream MVTec example',
  comparison: 'comparison domain',
  general: 'general zero-shot prompt',
};

const OTHER_OBJECTS_PRESET = { value: 'Other objects', evidence: 'general' };

function ProductCombobox({ presets, value, onChange }) {
  const rootRef = useRef(null);
  const listId = `product-options-${useId().replaceAll(':', '')}`;
  const [open, setOpen] = useState(false);
  const [filtering, setFiltering] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const visiblePresets = useMemo(() => {
    if (!filtering) return presets;
    const query = value.trim().toLowerCase();
    if (!query) return presets;
    return presets.filter((preset) => {
      const label = EVIDENCE_LABELS[preset.evidence] || preset.evidence || '';
      return `${preset.value} ${label}`.toLowerCase().includes(query);
    });
  }, [filtering, presets, value]);

  useEffect(() => {
    const closeOnOutsidePointer = (event) => {
      if (!rootRef.current?.contains(event.target)) {
        setOpen(false);
        setActiveIndex(-1);
      }
    };
    document.addEventListener('pointerdown', closeOnOutsidePointer);
    return () => document.removeEventListener('pointerdown', closeOnOutsidePointer);
  }, []);

  useEffect(() => {
    if (activeIndex >= visiblePresets.length) {
      setActiveIndex(visiblePresets.length ? 0 : -1);
    }
  }, [activeIndex, visiblePresets.length]);

  const openAll = () => {
    setFiltering(false);
    setOpen(true);
    setActiveIndex(presets.length ? 0 : -1);
  };

  const choose = (preset) => {
    onChange(preset.value);
    setOpen(false);
    setFiltering(false);
    setActiveIndex(-1);
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      setOpen(false);
      setActiveIndex(-1);
      return;
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      if (!open) {
        openAll();
        return;
      }
      if (!visiblePresets.length) return;
      const delta = event.key === 'ArrowDown' ? 1 : -1;
      setActiveIndex((current) => {
        const start = current < 0 ? (delta > 0 ? -1 : 0) : current;
        return (start + delta + visiblePresets.length) % visiblePresets.length;
      });
      return;
    }
    if (event.key === 'Enter' && open && activeIndex >= 0) {
      event.preventDefault();
      choose(visiblePresets[activeIndex]);
    }
  };

  const activeOptionId = open && activeIndex >= 0
    ? `${listId}-${activeIndex}`
    : undefined;

  return (
    <div className="qc-combobox" ref={rootRef}>
      <div className="qc-combobox-inputrow">
        <input
          id="inspection-product-name"
          className="input qc-combobox-input"
          type="text"
          value={value}
          required
          minLength={2}
          maxLength={40}
          autoComplete="off"
          placeholder="Choose an example or type a custom category"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listId}
          aria-activedescendant={activeOptionId}
          onClick={openAll}
          onFocus={openAll}
          onKeyDown={handleKeyDown}
          onChange={(event) => {
            onChange(event.target.value);
            setFiltering(true);
            setOpen(true);
            setActiveIndex(0);
          }}
        />
        <button
          type="button"
          className="qc-combobox-toggle"
          aria-label="Show curated categories"
          aria-expanded={open}
          onClick={() => (open ? setOpen(false) : openAll())}
        >
          ▾
        </button>
      </div>
      {open && (
        <div className="qc-combobox-menu" id={listId} role="listbox">
          {visiblePresets.length ? visiblePresets.map((preset, index) => (
            <button
              type="button"
              id={`${listId}-${index}`}
              role="option"
              aria-selected={preset.value === value}
              className={`qc-combobox-option${index === activeIndex ? ' is-active' : ''}`}
              key={`${preset.evidence}:${preset.value}`}
              onMouseEnter={() => setActiveIndex(index)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => choose(preset)}
            >
              <span>{preset.value}</span>
              <span className="qc-mono text-muted">
                {EVIDENCE_LABELS[preset.evidence] || preset.evidence}
              </span>
            </button>
          )) : (
            <div className="qc-combobox-empty qc-mono text-muted">No curated match — custom value is allowed.</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ModelSelector({
  models = [],
  value,
  onChange,
  loading,
  error,
  compact = false,
  productName = '',
  onProductNameChange = () => {},
}) {
  const selected = models.find((model) => model.id === value);
  const uninstalled = models.filter((model) => !model.installed);
  const presets = selected?.requiresProductName
    ? [
        ...(selected.productNamePresets || []).filter((preset) => preset.value !== OTHER_OBJECTS_PRESET.value),
        OTHER_OBJECTS_PRESET,
      ]
    : [];

  return (
    <Blueprint as="section" className={`qc-model-selector${compact ? ' is-compact' : ''}`} aria-label="Detection model">
      <div className={`qc-model-controls${selected?.requiresProductName ? '' : ' has-single'}`}>
        <div className="field">
          <label htmlFor="inspection-model">Detection model</label>
          <select
            id="inspection-model"
            className="input"
            value={value}
            disabled={loading || !models.length}
            onChange={(event) => onChange(event.target.value)}
          >
            {!models.length && <option value="">{loading ? 'Loading models…' : 'No models available'}</option>}
            {models.map((model) => (
              <option key={model.id} value={model.id} disabled={!model.installed}>
                {model.displayName}{model.isDefault ? ' — Recommended' : ''}{model.installed ? '' : ' — Not installed'}
              </option>
            ))}
          </select>
        </div>

        {selected?.requiresProductName && (
          <div className="field">
            <label htmlFor="inspection-product-name">Product / category</label>
            <ProductCombobox
              presets={presets}
              value={productName}
              onChange={onProductNameChange}
            />
            <span className="qc-mono text-muted">
              Curated examples are suggestions, not a training-class whitelist. Custom values are allowed.
            </span>
          </div>
        )}
      </div>

      {selected && (
        <div className="qc-model-copy">
          <strong>{selected.domain}</strong>
          <span>{selected.description}</span>
          <span className="qc-mono">Native output: {modelClassesLabel(selected)}</span>
        </div>
      )}

      {uninstalled.length > 0 && (
        <div className="qc-model-install" role="note">
          <strong>Install unavailable models</strong>
          {uninstalled.map((model) => (
            <span key={model.id}>
              {model.displayName}: <code>{installModelCommand(model.id)}</code>
            </span>
          ))}
        </div>
      )}
      {error && <p className="qc-error">{error}</p>}
    </Blueprint>
  );
}
