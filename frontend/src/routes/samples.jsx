import { useEffect, useMemo, useRef, useState } from 'react';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { ArrowRight, ExternalLink } from 'lucide-react';
import ModelSelector from '../components/ModelSelector.jsx';
import { useInspection } from '../hooks/useInspection.js';
import * as api from '../utils/apiClient.js';
import {
  groupSamplesByDomain,
  inspectShowcaseSample,
  recommendedModelFor,
} from '../utils/samples.js';

const TRANSFORM_LABELS = {
  cropped: 'cropped from source',
  downscaled: 'downscaled from source',
};

export const Route = createFileRoute('/samples')({ component: Samples });

function Samples() {
  const {
    models,
    modelsStatus,
    modelsError,
    selectedModelId,
    selectModel,
    runInspection,
    error: inspectionError,
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

  const inspectSample = async (sample) => {
    cancelSampleRequest();
    const controller = new AbortController();
    sampleRequestRef.current = controller;
    setBusySampleId(sample.id);
    setError(null);
    try {
      const record = await inspectShowcaseSample({
        sample,
        selectedModelId,
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
          <h6 className="qc-kicker">Model-aware showcase</h6>
          <h1>Inspection samples</h1>
          <p className="text-muted qc-lede">
            Licensed source images spanning PCB, steel, and structural crack inspection.
          </p>
        </div>
      </div>

      <ModelSelector
        models={models}
        value={selectedModelId}
        onChange={handleModelChange}
        loading={modelsStatus === 'loading'}
        error={modelsError}
      />

      <div className="qc-sample-notice" role="note">
        <strong>{catalog.notice || 'Source labels describe dataset metadata, not model predictions.'}</strong>
        <span>
          The selected model is always used. Running a sample sends it through <code>/api/inspect</code>
          {' '}and creates a normal inspection history record.
        </span>
      </div>

      {loading && <p className="qc-mono text-muted">loading sample catalog…</p>}
      {(error || inspectionError) && <p className="qc-error">{error || inspectionError}</p>}

      {[...groups.entries()].map(([domain, samples]) => (
        <section className="qc-sample-domain" key={domain}>
          <div className="qc-sectionrow">
            <h2>{domain}</h2>
            <span className="qc-mono text-muted">{samples.length} source images</span>
          </div>
          <div className="qc-sample-grid">
            {samples.map((sample) => {
              const dataset = datasets.get(sample.datasetId);
              const recommended = recommendedModelFor(sample, models);
              const recommendedAvailable = Boolean(recommended?.installed);
              const busy = busySampleId === sample.id;
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
                    <h3>{sample.sourceLabels.join(' · ')}</h3>
                    <div className="qc-tags">
                      {sample.sourceLabels.map((label) => (
                        <span className="tag tag-neutral" key={label}>{label}</span>
                      ))}
                    </div>
                    <p className="card-body">
                      Recommended: <strong>{recommended?.displayName || sample.recommendedModelId}</strong>
                      {!recommendedAvailable && ' — Not installed'}
                    </p>
                    <p className="qc-mono text-muted">
                      {sample.width}×{sample.height} · {dataset?.license?.name}
                    </p>
                    {TRANSFORM_LABELS[sample.assetTransform] && (
                      <p className="qc-mono text-muted">
                        Modified: {TRANSFORM_LABELS[sample.assetTransform]}
                      </p>
                    )}
                    <div className="qc-sample-actions">
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={busy || !selectedModelId}
                        onClick={() => inspectSample(sample)}
                      >
                        {busy ? 'Inspecting…' : 'Inspect sample'} <ArrowRight size={15} />
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        disabled={!recommendedAvailable || selectedModelId === sample.recommendedModelId}
                        onClick={() => handleModelChange(sample.recommendedModelId)}
                      >
                        Use recommended model
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      ))}

      {!loading && (
        <section className="qc-attribution">
          <h2>Dataset attribution</h2>
          <div className="qc-attribution-grid">
            {catalog.datasets.map((dataset) => (
              <article className="card" key={dataset.id}>
                <h3>{dataset.name}</h3>
                <p className="card-body">{dataset.attribution}</p>
                {catalog.samples.some(
                  (sample) => sample.datasetId === dataset.id && sample.assetTransform === 'downscaled',
                ) && (
                  <p className="qc-mono text-muted">
                    Modified from source; see the sample cards for the declared transform.
                  </p>
                )}
                <div className="qc-sample-links">
                  <a href={dataset.sourceUrl} target="_blank" rel="noreferrer">
                    Source <ExternalLink size={13} />
                  </a>
                  <a href={dataset.license.url} target="_blank" rel="noreferrer">
                    {dataset.license.name} <ExternalLink size={13} />
                  </a>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
