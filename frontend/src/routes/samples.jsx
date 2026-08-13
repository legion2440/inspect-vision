import { useEffect, useMemo, useRef, useState } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import ModelSelector from '../components/ModelSelector.jsx';
import { useInspection } from '../hooks/useInspection.js';
import * as api from '../utils/apiClient.js';
import {
  groupSamplesByDomain,
  inspectShowcaseSample,
  recommendedModelFor,
} from '../utils/samples.js';

export const Route = createFileRoute('/samples')({ component: Samples });

function titleCase(value) {
  return String(value || '')
    .replaceAll('_', ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function sampleCardTitle(sample, domain) {
  const subject = sample.productName === 'Bottle'
    ? 'Bottle neck'
    : (sample.productName || domain);
  const state = sample.condition === 'good'
    ? 'No defect'
    : titleCase(sample.sourceLabels.join(' · '));
  return `${subject} — ${state}`;
}

function Samples() {
  const {
    models,
    modelsStatus,
    modelsError,
    selectedModelId,
    selectModel,
    runInspection,
    error: inspectionError,
    productName,
    setProductName,
  } = useInspection();
  const [catalog, setCatalog] = useState({ notice: '', datasets: [], samples: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busySampleId, setBusySampleId] = useState(null);
  const sampleRequestRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();
    api.getSamples({ signal: controller.signal })
      .then((data) => {
        setCatalog(data);
        setError(null);
      })
      .catch((requestError) => {
        if (requestError.name !== 'AbortError') {
          setError(requestError.message || 'Could not load inspection samples');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => () => sampleRequestRef.current?.abort(), []);

  const datasets = useMemo(
    () => new Map(catalog.datasets.map((dataset) => [dataset.id, dataset])),
    [catalog.datasets],
  );
  const groups = useMemo(() => groupSamplesByDomain(catalog.samples), [catalog.samples]);
  const selectedModel = models.find((model) => model.id === selectedModelId);
  const productReady = !selectedModel?.requiresProductName || Boolean(productName.trim());

  const cancelSampleRequest = () => {
    sampleRequestRef.current?.abort();
    sampleRequestRef.current = null;
    setBusySampleId(null);
  };

  const handleModelChange = (modelId) => {
    cancelSampleRequest();
    setError(null);
    selectModel(modelId);
  };

  const handleProductNameChange = (value) => {
    cancelSampleRequest();
    setError(null);
    setProductName(value);
  };

  const inspectSample = async (sample) => {
    cancelSampleRequest();
    const controller = new AbortController();
    sampleRequestRef.current = controller;
    setBusySampleId(sample.id);
    setError(null);
    const sampleProductName = sample.productName || productName;
    if (sample.productName) setProductName(sample.productName);
    try {
      const record = await inspectShowcaseSample({
        sample,
        selectedModelId,
        productName: sampleProductName,
        loadSample: api.getSampleImage,
        runInspection,
        navigate,
        signal: controller.signal,
      });
      if (!record) setError('Inspection did not complete. Check the selected model and try again.');
    } catch (requestError) {
      if (requestError.name !== 'AbortError') {
        setError(requestError.message || 'Could not inspect this sample');
      }
    } finally {
      if (sampleRequestRef.current === controller) {
        sampleRequestRef.current = null;
        setBusySampleId(null);
      }
    }
  };

  return (
    <main className="qc-main">
      <div className="qc-pagehead">
        <div>
          <h6 className="qc-kicker">Curated inspection showcase</h6>
          <h1>Inspection samples</h1>
          <p className="text-muted qc-lede">
            Checked Bayes-PFL product examples plus steel and concrete specialist cases. Model choice always stays explicit.
          </p>
        </div>
      </div>

      <ModelSelector
        models={models}
        value={selectedModelId}
        onChange={handleModelChange}
        loading={modelsStatus === 'loading'}
        error={modelsError}
        productName={productName}
        onProductNameChange={handleProductNameChange}
      />

      <div className="qc-sample-notice" role="note">
        <strong>{catalog.notice || 'Source labels describe dataset metadata, not model predictions.'}</strong>
        <span>
          Clicking a sample supplies its product/category context but keeps your current model selection, so the same source can be compared across general and specialist models.
        </span>
      </div>

      {loading && <p className="qc-mono text-muted">loading sample catalog…</p>}
      {(error || inspectionError) && <p className="qc-error">{error || inspectionError}</p>}
      {!productReady && <p className="qc-mono text-muted">Choose a category above or click a sample to use that sample&apos;s category.</p>}

      <div className="qc-sample-grid qc-sample-catalog-grid">
        {[...groups.entries()].map(([domain, samples]) => {
          const specialist = samples.every(
            (sample) => sample.recommendedModelId !== 'bayespfl-general-v1',
          );
          return (
            <section
              className={`qc-sample-domain${specialist ? ' is-specialist' : ''}`}
              aria-label={domain}
              key={domain}
            >
              {samples.map((sample) => {
                const dataset = datasets.get(sample.datasetId);
                const recommended = recommendedModelFor(sample, models);
                const recommendedAvailable = Boolean(recommended?.installed);
                const busy = busySampleId === sample.id;
                const canInspect = Boolean(selectedModelId) && (
                  !selectedModel?.requiresProductName || Boolean(sample.productName || productName.trim())
                );
                const sourceReference = sample.sourcePath || sample.sourceFile || sample.filename;
                return (
                  <article className="card qc-sample-card" key={sample.id}>
                    <div className="qc-sample-image-wrap">
                      <img
                        src={api.sampleImageUrl(sample)}
                        alt={`${domain}: ${sample.sourceLabels.join(', ')}`}
                        className="qc-sample-image"
                        loading="lazy"
                      />
                    </div>
                    <div className="qc-sample-copy">
                      <span className="card-kicker">{dataset?.name || sample.datasetId}</span>
                      <h3>{sampleCardTitle(sample, domain)}</h3>
                      <div className="qc-tags">
                        {sample.productName && <span className="tag tag-neutral">{sample.productName}</span>}
                        {sample.sourceLabels.map((label) => (
                          <span className="tag tag-neutral" key={label}>{label}</span>
                        ))}
                      </div>
                      <p className="card-body">
                        Suggested model: <strong>{recommended?.displayName || sample.recommendedModelId}</strong>
                        {!recommendedAvailable && ' — Not installed'}
                      </p>
                      <p className="qc-mono text-muted">Pinned source: {sourceReference}</p>
                      <div className="qc-sample-actions">
                        <button
                          type="button"
                          className="btn btn-primary"
                          disabled={busy || !canInspect}
                          onClick={() => inspectSample(sample)}
                        >
                          {busy ? 'Inspecting…' : 'Inspect sample'}
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          disabled={!recommendedAvailable || selectedModelId === sample.recommendedModelId}
                          onClick={() => handleModelChange(sample.recommendedModelId)}
                        >
                          Use suggested model
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </section>
          );
        })}
      </div>

      {!loading && (
        <section className="qc-attribution">
          <h2>Dataset attribution</h2>
          <div className="qc-attribution-grid">
            {catalog.datasets.map((dataset) => (
              <article className="card" key={dataset.id}>
                <h3>{dataset.name}</h3>
                <p className="card-body">{dataset.attribution}</p>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
