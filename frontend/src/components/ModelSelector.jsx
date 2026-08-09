import { installModelCommand, modelClassesLabel } from '../utils/models.js';

const EVIDENCE_LABELS = {
  local: 'locally checked',
  upstream: 'upstream MVTec example',
  comparison: 'comparison domain',
};

export default function ModelSelector({
  models = [],
  value,
  onChange,
  loading,
  error,
  compact = false,
  productName = '',
  onProductNameChange = () => {},
  alignControlsTop = false,
}) {
  const selected = models.find((model) => model.id === value);
  const uninstalled = models.filter((model) => !model.installed);
  const presets = selected?.productNamePresets || [];

  return (
    <section className={`qc-model-selector${compact ? ' is-compact' : ''}`} aria-label="Detection model">
      <div
        className={`qc-model-controls${selected?.requiresProductName ? '' : ' has-single'}`}
        style={alignControlsTop ? { alignItems: 'start' } : undefined}
      >
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
            <input
              id="inspection-product-name"
              className="input"
              type="text"
              list="inspection-product-presets"
              value={productName}
              required
              minLength={2}
              maxLength={40}
              autoComplete="off"
              placeholder="Choose an example or type a custom category"
              onChange={(event) => onProductNameChange(event.target.value)}
            />
            <datalist id="inspection-product-presets">
              {presets.map((preset) => (
                <option
                  key={`${preset.evidence}:${preset.value}`}
                  value={preset.value}
                  label={`${preset.value} — ${EVIDENCE_LABELS[preset.evidence] || preset.evidence}`}
                />
              ))}
            </datalist>
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
    </section>
  );
}
