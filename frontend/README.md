# Inspect-Vision frontend

React 18, Vite and TanStack Router. Real FastAPI mode is the default; mock mode is explicit.

## Routes

- `/` — dashboard and quick upload
- `/inspect` — image/live inspection and Canvas overlay
- `/samples` — curated operator showcase
- `/history` — history filters and CSV
- `/details/:id` — inspection detail

## Samples

The Samples page consumes the 14-item backend operator catalog: Bottle, Capsule, Screw and Metal nut good/bad pairs for Bayes-PFL, plus three Steel Surface and three Concrete & Structural Cracks examples.

A sample supplies its category context but keeps the current selected model. `Use suggested model` is an explicit action. Sample inspection reuses the ordinary persisted inspect flow.

The twelve VisA files under `backend/samples/demo/` are separate demo/evidence assets and are not displayed as the operator Samples catalog.

## Client contract

The frontend uses the model, sample, inspect, stream, history and export API routes documented in `docs/api-contract.md`. The viewer renders the original image and a separate rescaled Canvas overlay. History filter choices come from currently exposed model classes.
