export function selectInitialModel(models = []) {
  const installedDefault = models.find((model) => model.isDefault && model.installed);
  if (installedDefault) return installedDefault.id;
  const installed = models.find((model) => model.installed);
  if (installed) return installed.id;
  return models.find((model) => model.isDefault)?.id || models[0]?.id || '';
}

export function appendModelId(form, modelId) {
  if (modelId) form.append('modelId', modelId);
  return form;
}

export function appendProductName(form, productName) {
  const value = String(productName || '').trim();
  if (value) form.append('productName', value);
  return form;
}

export function installModelCommand(modelId) {
  return `python scripts/install_models.py --model ${modelId}`;
}

export function modelClassesLabel(model, limit = 6) {
  const classes = model?.classes || [];
  const visible = classes.slice(0, limit).map((name) => name.replaceAll('_', ' ').replaceAll('-', ' '));
  return visible.join(' · ') + (classes.length > limit ? ` · +${classes.length - limit}` : '');
}

export function preprocessingLabel(model) {
  switch (model?.preprocessingProfile) {
    case 'steel-enhanced':
      return 'preprocess: letterbox 640² · grayscale · CLAHE';
    case 'standard-color':
      return 'preprocess: letterbox 640² · color';
    case 'anomalyclip-stretch':
      return 'preprocess: stretch 518² · CLIP normalization';
    case 'bayespfl-stretch':
      return 'preprocess: stretch 518² · CLIP normalization';
    default:
      return 'preprocess: model-defined';
  }
}
