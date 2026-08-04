import { createContext, useCallback, useEffect, useMemo, useReducer, useRef } from 'react';
import * as api from '../utils/apiClient.js';
import { validateImage } from '../utils/validateImage.js';
import { initialInspectionState, inspectionReducer } from './inspectionState.js';

export const InspectionContext = createContext(null);

export function InspectionProvider({ children }) {
  const [state, dispatch] = useReducer(inspectionReducer, initialInspectionState);
  const historyRequestId = useRef(0);
  const uploadRequestSequence = useRef(0);
  const uploadController = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    dispatch({ type: 'modelsLoading' });
    api.getModels({ signal: controller.signal })
      .then((models) => dispatch({ type: 'models', models: Array.isArray(models) ? models : [] }))
      .catch((err) => {
        if (err.name !== 'AbortError') {
          dispatch({ type: 'modelsError', error: err.message || 'Could not load detection models' });
        }
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const previewUrl = state.preview;
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [state.preview]);

  useEffect(() => () => {
    uploadRequestSequence.current += 1;
    uploadController.current?.abort();
  }, []);

  const runInspection = useCallback(async (file, modelId = state.selectedModelId) => {
    const invalid = validateImage(file);
    if (invalid) {
      dispatch({ type: 'error', error: invalid });
      return null;
    }
    const requestId = ++uploadRequestSequence.current;
    uploadController.current?.abort();
    const controller = new AbortController();
    uploadController.current = controller;
    dispatch({
      type: 'file',
      preview: URL.createObjectURL(file),
      meta: { name: file.name, size: file.size },
      requestId,
    });
    try {
      const record = await api.inspectImage(file, { modelId, signal: controller.signal });
      if (requestId !== uploadRequestSequence.current) return null;
      dispatch({ type: 'result', record, requestId });
      return record;
    } catch (err) {
      if (controller.signal.aborted || requestId !== uploadRequestSequence.current) return null;
      dispatch({
        type: 'error',
        error: err.message || 'Detection model error',
        requestId,
      });
      return null;
    } finally {
      if (uploadController.current === controller) uploadController.current = null;
    }
  }, [state.selectedModelId]);

  const loadHistory = useCallback(async (filters) => {
    const requestId = ++historyRequestId.current;
    dispatch({ type: 'historyLoading' });
    try {
      const records = await api.getHistory(filters);
      if (requestId === historyRequestId.current) {
        dispatch({ type: 'history', records: Array.isArray(records) ? records : records.items || [] });
      }
    } catch (err) {
      if (requestId === historyRequestId.current) {
        dispatch({ type: 'historyError', error: err.message || 'Could not load history' });
      }
    }
  }, []);

  const removeInspection = useCallback(async (id) => {
    await api.deleteInspection(id);
    dispatch({ type: 'history', records: state.history.filter((r) => r.inspectionId !== id) });
  }, [state.history]);

  const clearAll = useCallback(async () => {
    await api.clearHistory();
    dispatch({ type: 'history', records: [] });
  }, []);

  const cancelUpload = useCallback(() => {
    uploadRequestSequence.current += 1;
    uploadController.current?.abort();
    uploadController.current = null;
  }, []);
  const reset = useCallback(() => {
    cancelUpload();
    dispatch({ type: 'reset' });
  }, [cancelUpload]);
  const selectModel = useCallback((modelId) => {
    cancelUpload();
    dispatch({ type: 'selectModel', modelId });
  }, [cancelUpload]);

  const value = useMemo(
    () => ({ ...state, runInspection, loadHistory, removeInspection, clearAll, reset, selectModel }),
    [state, runInspection, loadHistory, removeInspection, clearAll, reset, selectModel],
  );

  return <InspectionContext.Provider value={value}>{children}</InspectionContext.Provider>;
}
