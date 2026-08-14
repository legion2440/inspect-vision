# Inspect-Vision

Inspect-Vision — приложение для визуального контроля производственных объектов на React/Vite + FastAPI + OpenCV. Проект поддерживает несколько моделей детекции, историю SQLite, original/annotated media, live-инспекцию, quality score и CSV export.

· [English version](README.md)

## Быстрый старт

Windows Git Bash:

```bash
py -3.13 -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-api.txt
cp .env.example .env
npm --prefix frontend ci
```

PyTorch `2.12.1` / torchvision `0.27.1` устанавливаются отдельно под нужный compute backend (CUDA, CPU или macOS/MPS).

Default Bayes-PFL:

```bash
python scripts/install_models.py
```

Все exposed-модели:

```bash
python scripts/install_models.py --all
```

Запуск backend:

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Frontend во втором терминале:

```bash
npm --prefix frontend run dev
```

Приложение: `http://localhost:5173`

## Модели

| Модель | Роль | Нативный результат |
| --- | --- | --- |
| General Manufacturing (Bayes-PFL) | broad category-guided anomaly localizer | `anomaly` |
| Steel Surface | YOLOv8 specialist для стали | 6 классов дефектов стали |
| Concrete & Structural Cracks | YOLOv8 specialist | `crack` |

Bayes-PFL остаётся основной general-моделью и моделью по умолчанию. Для guided Bayes-PFL `DetectionRuntimeManager` кэширует один `DetectionService` на `modelId`, а product/category context меняется под per-model lock без загрузки новой копии Bayes-PFL + CLIP.

AnomalyCLIP adapter сохранён как experimental backend slot, но ни одна текущая exposed-модель его не использует.

## Samples / demo images

В проекте **один** набор operator/demo images: 14 файлов в `backend/samples/demo/`. Эти же изображения отображаются на `/samples` и они же закрывают требование задания `at least 10 demo images`.

| Группа | Локальные примеры | Suggested model |
| --- | --- | --- |
| MVTec AD | Bottle good / broken large; Capsule good / crack; Screw good / manipulated front; Metal nut good / bent | Bayes-PFL |
| Steel Surface | good, inclusion, scratch | Steel Surface |
| Concrete & Structural Cracks | transverse, longitudinal, diagonal | Concrete specialist |

Итого: **8 Bayes + 3 steel + 3 concrete**. Каталог определяется `backend/routes/sample_catalog.py`, а `/api/samples/{id}/image` отдаёт соответствующий локальный файл. Runtime network для страницы Samples не нужен.

Клик по sample подставляет product/category context, но не переключает выбранную модель автоматически. `Use suggested model` — отдельное явное действие. Инспекция sample идёт через обычный `/api/inspect` и сохраняется в history.

## API

| Метод | Путь | Назначение |
| --- | --- | --- |
| GET | `/api/models` | модели и capabilities |
| GET | `/api/samples` | 14 local operator/demo records |
| GET | `/api/samples/{id}/image` | local demo image по catalog ID |
| POST | `/api/inspect` | инспекция + persistence |
| POST | `/api/stream` | live frame без persistence |
| GET | `/api/history` | history + filters |
| GET | `/api/history/{id}` | detail |
| DELETE | `/api/history/{id}` | удалить запись |
| POST | `/api/history/clear` | очистить history |
| GET | `/api/export` | filtered CSV |

## Проверка

Каноническая проверка:

```bash
python scripts/validate.py
```

Отдельно:

```bash
python scripts/validate_demo_samples.py
python scripts/validate_architecture.py
python -m pytest
npm --prefix frontend test
npm --prefix frontend run build
```

Проверка реальных моделей:

```bash
python scripts/probe_models.py --device auto
```

Runtime evidence остаётся привязанным к source snapshot, который реально выполнялся. После detector-bound изменений нужен новый production-path probe; старое evidence не переписывается.

## Автор

- Nazar Yestayev (@nyestaye)
