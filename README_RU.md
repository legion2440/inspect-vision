# Inspect-Vision

Inspect-Vision — приложение для визуального контроля производственных объектов. В проекте используются React/Vite, FastAPI, OpenCV, несколько выбираемых моделей детекции дефектов, история в SQLite, сохранение оригинальных и размеченных изображений, обработка live-кадров, quality score и экспорт CSV.

Оператор может выбрать между одной широкой category-guided моделью локализации аномалий и двумя компактными узкими специалистами. Общая модель полезна, когда категории объектов меняются и нужно найти подозрительную область; специалисты предпочтительнее в своих доменах, когда важен конкретный тип дефекта.

· [English version](README.md)

## 📋 Содержание

- [🚀 Быстрый старт](#-быстрый-старт)
- [📝 О проекте](#-о-проекте)
- [🧠 Стратегия моделей](#-стратегия-моделей)
- [📦 Артефакты моделей](#-артефакты-моделей)
- [🧭 История отбора моделей](#-история-отбора-моделей)
- [🏷️ Контекст продукта / категории](#️-контекст-продукта--категории)
- [🖼️ Примеры](#️-примеры)
- [🔄 Поток инспекции](#-поток-инспекции)
- [🔌 API](#-api)
- [🎯 Quality score и дополнительные возможности](#-quality-score-и-дополнительные-возможности)
- [🧪 Тесты и проверка](#-тесты-и-проверка)
- [📁 Структура проекта](#-структура-проекта)
- [⚠️ Примечания](#️-примечания)
- [🧑‍💻 Автор](#-автор)

## 🚀 Быстрый старт

### Требования

- Git
- Python 3.13
- Node.js с npm
- достаточно места для Python-окружения, файлов моделей и медиа инспекций
- опционально NVIDIA CUDA или Apple MPS

### Клонирование

```bash
git clone https://01.tomorrow-school.ai/git/nyestaye/inspect-vision.git
cd inspect-vision
```

### Python-окружение

Windows Git Bash:

```bash
py -3.13 -m venv .venv
source .venv/Scripts/activate
```

Linux / macOS:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

Обновить pip:

```bash
python -m pip install --upgrade pip
```

### Выбор сборки PyTorch

Inspect-Vision фиксирует PyTorch `2.12.1` и torchvision `0.27.1`, но не навязывает CPU-only wheel. Сначала установи сборку под конкретную машину, затем остальные backend-зависимости.

Windows или Linux с NVIDIA CUDA 12.6:

```bash
python -m pip install torch==2.12.1 torchvision==0.27.1 \
  --index-url https://download.pytorch.org/whl/cu126
```

Windows или Linux, только CPU:

```bash
python -m pip install torch==2.12.1 torchvision==0.27.1 \
  --index-url https://download.pytorch.org/whl/cpu
```

macOS, включая Apple Silicon:

```bash
python -m pip install torch==2.12.1 torchvision==0.27.1
```

На macOS режим `auto` использует MPS, если он доступен. Опциональный fallback отдельных операций PyTorch на CPU:

```bash
export PYTORCH_ENABLE_MPS_FALLBACK=1
```

Установить остальные backend- и frontend-зависимости:

```bash
python -m pip install -r requirements-api.txt
cp .env.example .env
npm --prefix frontend ci
```

Проверить доступный compute backend:

```bash
python -c "import torch; print('torch:', torch.__version__); print('cuda:', torch.cuda.is_available()); print('mps:', bool(getattr(torch.backends, 'mps', None)) and torch.backends.mps.is_available())"
```

Политика runtime по умолчанию:

```text
INSPECT_VISION_MODEL_DEVICE=auto
```

`auto` выбирает `CUDA -> MPS -> CPU`. Также поддерживаются явные `cpu`, `cuda`, `cuda:N` и `mps`. Если явно выбран недоступный ускоритель, приложение завершает запуск с ошибкой вместо скрытого fallback.

### Установка моделей

Установить общую модель Bayes-PFL по умолчанию:

```bash
python scripts/install_models.py
```

Установить все модели, доступные оператору:

```bash
python scripts/install_models.py --all
```

Для лёгкой specialist-only установки можно не скачивать связку Bayes-PFL + CLIP объёмом около 1.04 GB:

```bash
python scripts/install_models.py --model neu-defect-yolov8
# или
python scripts/install_models.py --model concrete-crack-yolov8
```

Bayes-PFL можно добавить позже:

```bash
python scripts/install_models.py --model bayespfl-general-v1
```

Артефакты проверяются по ожидаемому размеру и SHA-256. Файлы моделей `.pt` и `.pth` намеренно игнорируются Git.

### Запуск

Backend:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend во втором окне Git Bash:

```bash
npm --prefix frontend run dev
```

Открыть `http://localhost:5173`. Документация FastAPI доступна по адресу `http://localhost:8000/docs`.

## 📝 О проекте

Приложение поддерживает:

- ручной выбор модели на Dashboard, Inspect, live stream и Samples;
- category-guided локализацию общих аномалий;
- отдельных специалистов по стали и трещинам в бетонных/строительных поверхностях;
- сохраняемую историю инспекций с оригинальными и размеченными изображениями;
- bounding boxes в координатах исходного изображения;
- backend-authoritative quality score;
- экспорт CSV;
- live-frame инспекцию без сохранения записи;
- атрибутированный каталог примеров для сравнения общей модели и специалистов.

По умолчанию frontend работает с реальным FastAPI backend. Mock inference включается только явно и не скрывает ошибки backend или модели.

## 🧠 Стратегия моделей

Три доступные оператору модели решают разные задачи. Большая модель не означает автоматически более полезную модель в узком домене.

| Модель | Роль | Область | Нативный результат | Примерный размер загрузки | Когда использовать |
| --- | --- | --- | --- | ---: | --- |
| General Manufacturing (Bayes-PFL) | широкая guided-модель | разные категории объектов с текстовым контекстом | `anomaly` | ~1.04 GB вместе с CLIP | найти подозрительную область, когда заранее нет подходящей узкой taxonomy дефектов |
| Steel Surface | специалист | стальные поверхности | шесть именованных классов дефектов стали | ~6.3 MB | получить конкретный класс дефекта стали в своём домене |
| Concrete & Structural Cracks | специалист | бетон, кладка, стены, полы | `crack` | ~22.5 MB | обнаружить видимые строительные трещины в своём домене |

Компромисс сделан намеренно:

- **Bayes-PFL широкая, но семантически общая.** Она может локализовать аномальную область на разных категориях объектов, но прикладной результат остаётся `anomaly`. Если модель видит повреждённую область, Inspect-Vision не выдумывает, будто модель знает, что это именно царапина, вмятина, включение, трещина или другой конкретный дефект.
- **Специалисты узкие, но семантически полезнее в своих доменах.** Стальная модель возвращает свои шесть checkpoint-native классов, а бетонная — `crack`.
- **Специалисты намного меньше.** Стальной checkpoint весит около 6.3 MB, бетонный около 22.5 MB, тогда как Bayes-PFL вместе с CLIP требует примерно 1.04 GB.
- **Если есть подходящий специалист, он предпочтителен для семантической детекции.** Bayes-PFL остаётся полезной как широкая модель локализации аномалий и для сравнения на том же исходном изображении.

Модель и категория выбираются независимо. Выбор `Steel surface` не переключает приложение на стального специалиста, а `Concrete surface` — на модель трещин.

### Почему `train_visa.pth` выбран намеренно

Bayes-PFL публикует cross-dataset checkpoints. В Inspect-Vision используется:

```text
checkpoint: train_visa.pth
auxiliary training domain: VisA
qualification / showcase domain: MVTec AD
protocol: held-out cross-dataset zero-shot
```

Примеры Bayes-PFL в интерфейсе относятся к MVTec AD, поэтому `train_visa.pth` сохраняет qualification domain отличным от auxiliary training domain checkpoint. Замена на `train_mvtec.pth` при сохранении MVTec как qualification domain нарушила бы этот протокол.

Связь также хранится в `backend/detection/model-selection.json`, а проверки репозитория не позволяют auxiliary training и qualification domain стать одинаковыми.

### Поведение runtime и ускорителя

`DetectionRuntimeManager` лениво загружает и кэширует один успешный `DetectionService` на модель. Для guided Bayes-PFL смена `Bottle`, `Capsule`, `Screw`, `Metal nut` или другой категории меняет prompt context без загрузки ещё одной полной копии Bayes-PFL/CLIP.

Поэтому работа с ускорителем состоит из двух фаз:

- первый запрос после запуска процесса может быть заметно медленнее из-за загрузки и инициализации модели;
- последующие прогретые запросы используют уже загруженную модель, и ускорение CUDA/MPS не теряется на повторном старте модели.

## 📦 Артефакты моделей

| Модель | Backend | Артефакт | Размер | SHA-256 | Домен / нативный результат |
| --- | --- | --- | ---: | --- | --- |
| General Manufacturing (Bayes-PFL) | Bayes-PFL | `train_visa.pth` | 109,523,051 B | `b3d89b6a6018679e44f413ce4cb0931626bedbd480829d6fba94f2176f270fc3` | cross-domain localization / `anomaly` |
| General Manufacturing (Bayes-PFL) | CLIP | `ViT-L-14-336px.pt` | 934,088,680 B | `3035c92b350959924f9f00213499208652fc7ea050643e8b385c2dac08641f02` | visual/text backbone |
| Steel Surface | Ultralytics YOLOv8 | `defect_neu_yolov8.pt` | 6,257,194 B | `635402c435786756c000694654271f1e6aee3eb039aa5e975bb8ec8e9ec0e34b` | NEU steel / шесть именованных классов |
| Concrete & Structural Cracks | Ultralytics YOLOv8 | `crack_detection.pt` | 22,522,595 B | `386155cae09bee6af1ce99608fc42a32cafd40a25362b80037b4fa54f6999719` | строительные поверхности / `crack` |

URL источников, revisions, thresholds, preprocessing, данные целостности артефактов и quality weights находятся в `backend/models/model-manifest.json`.

## 🧭 История отбора моделей

`backend/detection/model-selection.json` фиксирует решения по кандидатам, чтобы текущие три модели не выглядели случайным набором.

| Кандидат | Решение | Причина |
| --- | --- | --- |
| Bayes-PFL | **выбрана как general** | лучший вариант среди проверенных широких anomaly-localization кандидатов; требует осмысленного category context |
| NEU YOLOv8 | **выбран специалист** | компактная модель по стали с шестью checkpoint-native классами дефектов |
| Concrete crack YOLOv8 | **выбран специалист** | компактная модель для видимых строительных трещин |
| `factory-defect-guard-v6-mc` | **отклонена как general** | локальные cross-domain проверки показали ненадёжное покрытие и путаницу классов; checkpoint сохранён, но `exposed: false` |
| YOLO-World X | **отклонён кандидат** | локальные проверки показали слабую локализацию, слишком большие bounding boxes и false positives на чистых изображениях |
| AnomalyCLIP | **отклонён кандидат** | локальные cross-domain проверки дали смесь успешных случаев, пропусков, false positives и слишком широких anomaly regions |

Исторические runtime-материалы остаются историческими. Старый factory checkpoint сохранён для воспроизводимости, но consistency check не позволяет снова сделать отклонённую модель видимой оператору.

## 🏷️ Контекст продукта / категории

Bayes-PFL использует текст продукта/категории как CLIP prompt context. Это guidance для zero-shot локализации, а не whitelist классов, на которых объект обязательно должен был обучаться.

Текущие варианты:

| Уровень | Примеры продукта / категории |
| --- | --- |
| локально проверены | Bottle, Capsule, Screw, Metal nut |
| дополнительные upstream MVTec примеры | Hazelnut, Pill, Toothbrush, Tile, Wood, Carpet |
| general-vs-specialist comparison | Steel surface, Concrete surface |
| обычный вариант интерфейса | Other objects |

Разрешён и произвольный пользовательский текст. `Cable` и `Zipper` намеренно отсутствуют в curated suggestions, потому что локальные проверки были неудовлетворительными, хотя вручную их всё ещё можно ввести для эксперимента.

Сервер приводит категорию к lowercase, принимает `_` как backward-compatible разделитель пробела и требует 2-40 символов, латинские буквы/пробелы/дефисы и максимум три слова. Некорректный guided context возвращает HTTP 422.

## 🖼️ Примеры

На странице Samples находится 14 атрибутированных примеров:

| Группа | Примеры | Рекомендуемая модель |
| --- | --- | --- |
| MVTec AD | Bottle good / broken large; Capsule good / crack; Screw good / manipulated front; Metal nut good / bent | Bayes-PFL general |
| Steel Surface | good surface, inclusion, scratch | Steel Surface specialist |
| Concrete & Structural Cracks | transverse, longitudinal и diagonal crack examples | Concrete specialist |

Восемь примеров MVTec AD отдаются из зафиксированной MMAD mirror revision `e88b7bd615ad582b0a7e8238066a9fb293a072b4`. MVTec AD распространяется по CC BY-NC-SA 4.0.

Три steel и три concrete showcase-изображения связаны с отслеживаемым provenance и зафиксированной исторической revision репозитория. Attribution датасетов показывается на странице Samples.

Важное поведение интерфейса:

- клик по sample подставляет product/category context этого примера;
- клик по sample **не меняет выбранную модель**;
- `Use suggested model` — отдельное явное действие для переключения на рекомендованную general/specialist модель;
- source labels описывают metadata датасета и никогда не выдаются за предсказание модели.

Так один и тот же исходник можно сначала прогнать через Bayes-PFL, а затем через подходящего специалиста, не скрывая от оператора выбор модели.

## 🔄 Поток инспекции

```text
JPEG/PNG bytes
-> content validation и OpenCV decode
-> выбранная модель + optional guided product context
-> model-specific inference и восстановление геометрии
-> native detections в координатах исходного изображения
-> annotated image + quality score + verdict
-> SQLite metadata + original/annotated media
```

Ultralytics-специалисты используют общий square-letterbox path. Bayes-PFL самостоятельно выполняет `518x518` stretch, CLIP normalization, anomaly-map postprocessing и восстановление координат исходного изображения.

Зафиксированные исходники Bayes-PFL остаются byte-exact. Device-specific проблемы upstream allocations адаптируются только в памяти, чтобы CPU, CUDA, indexed CUDA и MPS tensors оставались на выбранном устройстве.

## 🔌 API

| Метод | Путь | Назначение |
| --- | --- | --- |
| `GET` | `/api/models` | список доступных моделей, curated guided categories и installed/default state |
| `GET` | `/api/samples` | список атрибутированного showcase-каталога |
| `GET` | `/api/samples/{id}/image` | получить одно зафиксированное showcase-изображение |
| `POST` | `/api/inspect` | выполнить инспекцию и сохранить результат |
| `POST` | `/api/stream` | проверить один JPEG-кадр без сохранения |
| `GET` | `/api/history` | список/фильтрация инспекций |
| `GET` | `/api/history/{id}` | одна инспекция с image data URLs |
| `DELETE` | `/api/history/{id}` | удалить инспекцию и её media |
| `POST` | `/api/history/clear` | очистить историю и принадлежащие ей media |
| `GET` | `/api/export` | экспортировать отфильтрованную историю в CSV |

Пример Bayes-PFL:

```bash
curl -sS -X POST http://localhost:8000/api/inspect \
  -F "modelId=bayespfl-general-v1" \
  -F "productName=Capsule" \
  -F "image=@path/to/capsule.png;type=image/png"
```

Полный request/response contract находится в `docs/api-contract.md`.

## 🎯 Quality score и дополнительные возможности

Backend возвращает целочисленный `qualityScore` от 0 до 100. Чем выше значение, тем лучше качество. Это прикладная эвристика на основе класса дефекта, confidence, количества и площади bbox; это не калиброванная метрология и не safety measurement.

Также реализованы:

- live frame inspection через `POST /api/stream`;
- backend-authoritative quality scoring;
- серверный filtered CSV export;
- оригинальные и размеченные inspection media;
- model-aware history и type filters.

## 🧪 Тесты и проверка

Каноническая проверка репозитория из активированного окружения:

```bash
python scripts/validate.py
```

Полезные отдельные команды:

```bash
python scripts/validate_showcase_samples.py
python scripts/validate_architecture.py
python -m pytest
npm --prefix frontend test
npm --prefix frontend run build
```

Проверка реальных моделей выполняется отдельно от static/unit checks:

```bash
python scripts/probe_models.py --device auto
```

Есть и hardware-specific варианты:

```bash
python scripts/probe_models.py --device cuda
python scripts/probe_models.py --device mps
python scripts/probe_models.py --device cpu
```

Runtime evidence привязывается к исходникам, которые действительно выполнялись. Изменение detector-bound source не переписывает старую runtime-запись так, будто она относится к новой версии; для этого нужен новый production-path probe.

Правила навигации и ownership находятся в `AGENTS.md`. Текущий capability status — в `docs/project-status.json`, mapping требований к проверкам — в `docs/verification.md`.

## 📁 Структура проекта

```text
inspect-vision/
├── backend/
│   ├── detection/       adapters моделей, selection metadata, prompt validation
│   ├── models/          manifest моделей и игнорируемые локальные артефакты
│   ├── routes/          FastAPI boundaries
│   ├── samples/         каталоги, provenance и showcase assets
│   └── storage/         SQLite и lifecycle media
├── frontend/
│   ├── src/             React routes, components, context, API client и styles
│   └── tests/           frontend checks
├── docs/                contracts, status и runtime evidence
├── scripts/             установка, validation и runtime probes
├── tests/               Python unit и integration tests
├── AGENTS.md
├── ARCHITECTURE.md
├── README.md
└── README_RU.md
```

## ⚠️ Примечания

- Bayes-PFL — anomaly localizer, а не semantic defect classifier.
- Специалисты намеренно узкие; их семантическое преимущество относится к своим обученным доменам.
- Веса моделей игнорируются Git и устанавливаются отдельно.
- Для MVTec showcase нужен доступ в сеть, потому что исходные изображения отдаются из зафиксированной mirror revision.
- Source labels в Samples — metadata датасета, а не сохранённый или выдуманный результат модели.
- По умолчанию frontend использует реальный backend.
- Исторический runtime evidence не изменяется, чтобы приписать ему выполнение более новых исходников.

## 🧑‍💻 Автор

- Nazar Yestayev (@nyestaye)
