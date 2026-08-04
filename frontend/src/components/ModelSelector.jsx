import { installModelCommand, modelClassesLabel } from '../utils/models.js';

export default function ModelSelector({ models = [], value, onChange, loading, error, compact = false }) {
  const selected = models.find((model) => model.id === value);
  const uninstalled = models.filter((model) => !model.installed);
  return (
    <section className={`qc-model-selector${compact ? ' is-compact' : ''}`} aria-label="Detection model">
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
      {selected && (
        <div className="qc-model-copy">
          <strong>{selected.domain}</strong>
          <span>{selected.description}</span>
          <span className="qc-mono">{modelClassesLabel(selected)}</span>
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
