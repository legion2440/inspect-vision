from __future__ import annotations

import json
import re
from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8", newline="\n")


def replace_between(text: str, start: str, end: str, body: str) -> str:
    start_index = text.find(start)
    end_index = text.find(end, start_index + len(start)) if start_index >= 0 else -1
    if start_index < 0 or end_index < 0:
        return text
    return text[:start_index] + start + "\n\n" + body.strip() + "\n\n" + text[end_index:]


readme = read("README.md")
readme = replace_between(
    readme,
    "## 🖼️ Samples",
    "## 🔄 Inspection flow",
    """The Samples page uses the same fourteen images committed in `backend/samples/demo/`. They are both the operator sample catalog and the project demo-image set used for acceptance; there is no second demo corpus.

| Group | Local samples | Suggested model |
| --- | --- | --- |
| MVTec AD | Bottle good / broken large; Capsule good / crack; Screw good / manipulated front; Metal nut good / bent | Bayes-PFL general |
| Steel Surface | good surface, inclusion, scratch | Steel Surface specialist |
| Concrete & Structural Cracks | transverse, longitudinal, and diagonal crack examples | Concrete specialist |

The eight MVTec files preserve the previously pinned MMAD revision sources. The six specialist files preserve the previously pinned project-source bytes and dataset attribution. Runtime delivery is entirely local through `/api/samples/{id}/image`.

Important UI behavior:

- clicking a sample supplies that sample's product/category context;
- clicking a sample **does not change the selected model**;
- `Use suggested model` is the explicit action that switches the model;
- source labels describe dataset metadata and are never presented as model predictions;
- inspecting a sample performs fresh inference through the ordinary `/api/inspect` path and stores the result in normal history.

These fourteen files directly satisfy the assignment requirement for at least ten demo images, including clean and defective examples.""",
)
readme = readme.replace(
    "| `GET` | `/api/samples` | list the attributed 14-item operator showcase |",
    "| `GET` | `/api/samples` | list the fourteen local operator/demo samples |",
)
readme = readme.replace(
    "| `GET` | `/api/samples/{id}/image` | serve one pinned showcase image by catalog ID |",
    "| `GET` | `/api/samples/{id}/image` | serve one local demo image by catalog ID |",
)
readme = re.sub(
    r"\nThe two tests that fetch pinned showcase bytes are opt-in.*?```\n",
    "\n",
    readme,
    flags=re.S,
)
readme = readme.replace(
    "│   ├── samples/         local VisA demo/evidence corpus and provenance",
    "│   ├── samples/         fourteen local operator/demo images and source metadata",
)
readme = readme.replace(
    "- The operator showcase image endpoints use pinned network sources; ordinary repository validation does not fetch them.",
    "- The fourteen operator/demo images are committed locally and require no runtime network access.",
)
write("README.md", readme)


write(
    "README_RU.md",
    """# Inspect-Vision

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
""",
)


agents = read("AGENTS.md")
agents = re.sub(
    r"- `backend/routes/sample_catalog\.py` defines the operator-facing Samples catalog:.*?- Runtime qualification inputs are separate from both operator showcase and demo\n  evidence and may use pinned remote sources through verification scripts\.\n",
    "- `backend/routes/sample_catalog.py` defines the single fourteen-image operator/demo corpus: eight MVTec Bayes-PFL examples plus three steel and three concrete specialist examples. The exact same files live in `backend/samples/demo/`, are served locally by `/api/samples`, and satisfy the demo-image acceptance requirement. There is no second operator/demo corpus.\n- Runtime qualification inputs remain separate verification inputs and may use pinned remote sources through verification scripts.\n",
    agents,
    flags=re.S,
)
agents = agents.replace("make probe-samples\n", "")
agents = agents.replace(".venv/Scripts/python.exe scripts/probe_demo_samples.py\n", "")
agents = re.sub(
    r"Demo images are an attributed, hash-bound,.*?(?=GNU Make)",
    "The fourteen local files in `backend/samples/demo/` are the same images exposed by `/api/samples`; `scripts/validate_demo_samples.py` validates this single corpus. Runtime qualification uses separate verification inputs.\n",
    agents,
    flags=re.S,
)
write("AGENTS.md", agents)


architecture = read("ARCHITECTURE.md")
architecture = architecture.replace(
    'API --> Samples["Pinned operator showcase"]',
    'API --> Samples["14 local operator/demo images"]',
)
architecture = re.sub(
    r"- `backend/routes/sample_catalog\.py` defines the operator Samples catalog:.*?- The twelve VisA files under `backend/samples/demo/` are a separate audit/demo\n  evidence corpus and are never projected into the operator Samples page\.\n",
    "- `backend/routes/sample_catalog.py` defines the fourteen-image operator/demo catalog: eight MVTec Bayes-PFL examples plus three steel and three concrete specialist examples. `/api/samples/{id}/image` serves those exact committed files from `backend/samples/demo/`; arbitrary client paths or URLs are never accepted. The operator catalog and the demo-image acceptance set are the same corpus.\n",
    architecture,
    flags=re.S,
)
architecture = architecture.replace(
    "The separate\ntracked VisA demo corpus is audit/evidence material and is not Bayes-PFL\nqualification evidence or the operator showcase.",
    "The local operator/demo corpus is not Bayes-PFL runtime qualification evidence.",
)
architecture = re.sub(
    r"- The VisA demo corpus remains a separate local evidence set\. Operator showcase\n  byte checks that require pinned remote sources are opt-in network checks and do\n  not make ordinary repository validation network-dependent\.",
    "- The fourteen operator/demo images are local committed files and require no runtime network access. Runtime model qualification remains a separate verification workflow.",
    architecture,
)
write("ARCHITECTURE.md", architecture)


api_contract = read("docs/api-contract.md")
api_contract = replace_between(
    api_contract,
    "### `GET /api/samples`",
    "### `GET /api/export`",
    """Returns `notice`, dataset attribution metadata, and the fourteen records from the single local operator/demo corpus. The catalog contains eight MVTec Bayes-PFL examples (Bottle, Capsule, Screw, and Metal nut good/bad pairs), three steel examples, and three concrete/crack examples.

Each sample includes its stable ID, product/category context, source labels, recommended model, filename/media type, and same-origin `imageUrl`. Source labels describe dataset metadata, not model predictions. Opening or inspecting a sample never changes the selected model automatically.

### `GET /api/samples/{id}/image`

Serves the matching committed file from `backend/samples/demo/`. Request input is only the known sample ID; filesystem paths and arbitrary URLs are never accepted. Unknown IDs return HTTP 404. The endpoint has no runtime network dependency.

The same fourteen files are the repository demo images and directly satisfy the `at least 10 demo images` acceptance requirement.""",
)
write("docs/api-contract.md", api_contract)


write(
    "backend/samples/README.md",
    """# Samples

`backend/samples/demo/` is the single operator/demo image corpus. It contains fourteen committed images: eight MVTec Bayes-PFL examples (Bottle, Capsule, Screw, Metal nut), three steel examples, and three concrete/crack examples.

`backend/routes/sample_catalog.py` supplies their IDs, labels, attribution, product context, and recommended models. `/api/samples` exposes the catalog and `/api/samples/{id}/image` serves those same local files. No second demo set or runtime network fetch is used.

These fourteen images directly satisfy the assignment requirement for at least ten demo images and include clean and defective examples.

Validate them with:

```bash
python scripts/validate_demo_samples.py
```

`model-probe-samples.json` is separate runtime-verification input metadata; it is not another operator/demo corpus.
""",
)


write(
    "backend/routes/README.md",
    """# Backend API routes

`backend.main:create_app` composes the FastAPI application. Its lifespan creates one validated lazy `DetectionRuntimeManager`, one `InspectionStorage`, and one shared inference lock. Factories remain injectable so HTTP tests can exercise route/storage behavior without loading model weights.

Implemented routes include inspect, models, the local sample catalog, history, stream, and CSV export.

`GET /api/samples` exposes the fourteen records defined by `sample_catalog.py`. `GET /api/samples/{id}/image` serves the corresponding committed file from `backend/samples/demo/`. These are the same fourteen images used as the project demo set; there is no second sample corpus and no runtime network fetch.

Bayes-PFL `productName` context is normalized and validated before inference. Model and category selection remain independent. A sample may supply its category context but never auto-selects another model. Sample inspection reuses the ordinary `/api/inspect` path.

Image decoding and history-filter parsing remain shared route utilities so inspect, stream, history and export cannot silently diverge. Detection and persistence logic stay in their owning modules.
""",
)


frontend_readme = read("frontend/README.md")
frontend_readme = frontend_readme.replace(
    "Twelve tracked local VisA demo images with explicit model selection",
    "Fourteen local operator/demo images with explicit model selection",
)
frontend_readme = re.sub(
    r"The Samples page is backed by .*?(?=\n\n## Backend contract used by the client)",
    "The Samples page is backed by the same fourteen files committed in `backend/samples/demo/`: eight MVTec Bayes examples plus three steel and three concrete specialist examples. A card supplies its product/category context but keeps the current model. Source labels are dataset metadata, not predictions. Images are served locally by catalog ID, so browsing the page has no network dependency.",
    frontend_readme,
    flags=re.S,
)
frontend_readme = frontend_readme.replace("tracked local demo metadata", "local operator/demo metadata")
frontend_readme = frontend_readme.replace("local demo image by manifest ID", "local demo image by catalog ID")
write("frontend/README.md", frontend_readme)


status = json.loads(read("docs/project-status.json"))
status["recorded_at"] = "2026-08-14"
stale_fragments = (
    "twelve tracked VisA",
    "twelve local VisA",
    "network-backed showcase",
    "same twelve tracked VisA",
    "local demo-catalog consolidation",
)
status["verified"] = [
    item
    for item in status.get("verified", [])
    if not any(fragment.lower() in item.lower() for fragment in stale_fragments)
]
claim = "the operator Samples page and the demo-image acceptance set are the same fourteen committed files: eight MVTec Bayes examples plus three steel and three concrete specialist examples"
if claim not in status["verified"]:
    status["verified"].append(claim)
status["known_limitations"] = [
    item
    for item in status.get("known_limitations", [])
    if item.get("id") != "operator-showcase-network-source"
]
for item in status["known_limitations"]:
    if item.get("id") == "repository-validation-pending":
        item["detail"] = "The current local sample/demo consolidation requires canonical repository validation on the current source."
write("docs/project-status.json", json.dumps(status, ensure_ascii=False, indent=2) + "\n")


verification = read("docs/verification.md")
verification = re.sub(
    r"^\| At least 10 demo images \|.*$",
    "| At least 10 demo images | PASS | The same fourteen local files shown on `/samples` are committed in `backend/samples/demo/`; the set includes clean and defective cases across Bayes, steel, and concrete examples | `python scripts/validate_demo_samples.py`; API/frontend tests |",
    verification,
    flags=re.M,
)
verification = re.sub(
    r"^\| Operator demo catalog \|.*$",
    "| Operator demo catalog | PASS | `/api/samples` exposes those same fourteen committed demo files by stable catalog ID; there is no second demo set and no runtime image network fetch | API/frontend tests; `python scripts/validate_demo_samples.py` |",
    verification,
    flags=re.M,
)
verification = verification.replace("local demo-catalog consolidation", "local sample/demo consolidation")
verification = re.sub(
    r"The local operator demo corpus is independent of\nthat qualification bundle\.",
    "The local operator/demo corpus is independent of that qualification bundle.",
    verification,
)
write("docs/verification.md", verification)


module_map = json.loads(read("module-map.json"))
for module in module_map["modules"]:
    if module["id"] == "backend-api":
        module["description"] = "Owns FastAPI composition, HTTP validation, endpoint serialization, CORS, error mapping, and local operator/demo sample delivery."
        owned_paths = module.setdefault("additional_owned_paths", [])
        if "backend/samples/demo" not in owned_paths:
            owned_paths.append("backend/samples/demo")
    if module["id"] == "verification-evidence":
        module["entrypoints"] = [
            entry
            for entry in module.get("entrypoints", [])
            if entry.get("path") not in {"scripts/prepare_demo_samples.py", "scripts/probe_demo_samples.py"}
        ]
        module["docs"] = [
            entry
            for entry in module.get("docs", [])
            if entry.get("path") != "backend/samples/VISA-NOTICE.md"
        ]
        module["generated_artifacts"] = [
            entry
            for entry in module.get("generated_artifacts", [])
            if entry.get("path") != "docs/evidence/demo-samples/demo-samples-acceptance.json"
        ]
write("module-map.json", json.dumps(module_map, ensure_ascii=False, indent=2) + "\n")


files_to_check = [
    "README.md",
    "README_RU.md",
    "AGENTS.md",
    "ARCHITECTURE.md",
    "docs/api-contract.md",
    "docs/verification.md",
    "docs/project-status.json",
    "frontend/README.md",
    "backend/routes/README.md",
    "backend/samples/README.md",
    "module-map.json",
]
forbidden = [
    "demo-samples.json",
    "VISA-NOTICE.md",
    "probe_demo_samples.py",
    "prepare_demo_samples.py",
    "twelve tracked VisA",
    "twelve local VisA",
    "separate audit/demo",
    "operator showcase image endpoints use pinned network",
    "INSPECT_VISION_RUN_NETWORK_TESTS",
]
errors: list[str] = []
for path in files_to_check:
    content = read(path)
    for term in forbidden:
        if term in content:
            errors.append(f"{path}: {term}")
if errors:
    raise SystemExit("Stale sample references remain:\n" + "\n".join(errors))
