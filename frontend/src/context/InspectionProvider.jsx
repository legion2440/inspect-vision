import { createContext, useCallback, useMemo, useReducer, useRef } from 'react';
import * as api from '../utils/apiClient.js';
import { validateImage } from '../utils/validateImage.js';

export const InspectionContext = createContext(null);

const initial = {
  current: null,      // the inspection being viewed on /inspect
  preview: null,      // object URL of the uploaded file, shown before results land
  fileMeta: null,     // { name, size, width, height }
  status: 'idle',     // idle | uploading | detecting | done | error
  error: null,
  history: [],
  historyStatus: 'idle',
};

function reducer(state, action) {
  switch (action.type) {
    case 'file':
      return { ...state, preview: action.preview, fileMeta: action.meta, current: null, error: null, status: 'detecting' };
    case 'result':
      return { ...state, current: action.record, status: 'done', error: null };
    case 'error':
      return { ...state, status: 'error', error: action.error };
    case 'reset':
      return { ...initial, history: state.history, historyStatus: state.historyStatus };
    case 'history':
      return { ...state, history: action.records, historyStatus: 'done' };
    case 'historyLoading':
      return { ...state, historyStatus: 'loading' };
    case 'historyError':
      return { ...state, historyStatus: 'error', error: action.error };
    default:
      return state;
  }
}

export function InspectionProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initial);
  const historyRequestId = useRef(0);

  const runInspection = useCallback(async (file) => {
    const invalid = validateImage(file);
    if (invalid) {
      dispatch({ type: 'error', error: invalid });
      return null;
    }
    dispatch({
      type: 'file',
      preview: URL.createObjectURL(file),
      meta: { name: file.name, size: file.size },
    });
    try {
      const record = await api.inspectImage(file);
      dispatch({ type: 'result', record });
      return record;
    } catch (err) {
      dispatch({ type: 'error', error: err.message || 'Detection model error' });
      return null;
    }
  }, []);

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

  const value = useMemo(
    () => ({ ...state, runInspection, loadHistory, removeInspection, clearAll, reset: () => dispatch({ type: 'reset' }) }),
    [state, runInspection, loadHistory, removeInspection, clearAll],
  );

  return <InspectionContext.Provider value={value}>{children}</InspectionContext.Provider>;
}
