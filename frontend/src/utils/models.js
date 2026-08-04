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

export function installModelCommand(modelId) {
  return `python scripts/install_models.py --model ${modelId}`;
}

export function modelClassesLabel(model, limit = 6) {
  const classes = model?.classes || [];
  const visible = classes.slice(0, limit).map((name) => name.replaceAll('_', ' ').replaceAll('-', ' '));
  return visible.join(' · ') + (classes.length > limit ? ` · +${classes.length - limit}` : '');
}
