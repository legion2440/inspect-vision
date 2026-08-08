import { selectInitialModel } from '../utils/models.js';

export const initialInspectionState = {
  current: null,
  preview: null,
  fileMeta: null,
  status: 'idle',
  error: null,
  uploadRequestId: null,
  history: [],
  historyStatus: 'idle',
  models: [],
  modelsStatus: 'idle',
  modelsError: null,
  selectedModelId: '',
  productName: '',
};

function withoutUploadResult(state) {
  return {
    ...state,
    current: null,
    preview: null,
    fileMeta: null,
    status: 'idle',
    error: null,
    uploadRequestId: null,
  };
}

export function inspectionReducer(state, action) {
  switch (action.type) {
    case 'file':
      return {
        ...state,
        preview: action.preview,
        fileMeta: action.meta,
        current: null,
        error: null,
        status: 'detecting',
        uploadRequestId: action.requestId,
      };
    case 'result':
      if (action.requestId !== state.uploadRequestId) return state;
      return {
        ...state,
        current: action.record,
        status: 'done',
        error: null,
        uploadRequestId: null,
      };
    case 'error':
      if (action.requestId != null && action.requestId !== state.uploadRequestId) return state;
      return {
        ...state,
        status: 'error',
        error: action.error,
        uploadRequestId: null,
      };
    case 'reset':
      return {
        ...initialInspectionState,
        history: state.history,
        historyStatus: state.historyStatus,
        models: state.models,
        modelsStatus: state.modelsStatus,
        modelsError: state.modelsError,
        selectedModelId: state.selectedModelId,
        productName: state.productName,
      };
    case 'history':
      return { ...state, history: action.records, historyStatus: 'done' };
    case 'historyLoading':
      return { ...state, historyStatus: 'loading' };
    case 'historyError':
      return { ...state, historyStatus: 'error', error: action.error };
    case 'modelsLoading':
      return { ...state, modelsStatus: 'loading', modelsError: null };
    case 'models': {
      const selectedStillInstalled = action.models.some(
        (model) => model.id === state.selectedModelId && model.installed,
      );
      return {
        ...state,
        models: action.models,
        modelsStatus: 'done',
        modelsError: null,
        selectedModelId: selectedStillInstalled
          ? state.selectedModelId
          : selectInitialModel(action.models),
      };
    }
    case 'modelsError':
      return { ...state, modelsStatus: 'error', modelsError: action.error };
    case 'selectModel':
      return {
        ...withoutUploadResult(state),
        selectedModelId: action.modelId,
      };
    case 'setProductName':
      return {
        ...withoutUploadResult(state),
        productName: action.productName,
      };
    default:
      return state;
  }
}
