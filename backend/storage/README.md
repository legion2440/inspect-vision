# Inspection history

This module owns SQLite inspection metadata and the original/annotated media
lifecycle. Runtime databases and media directories remain ignored.

`SQLiteInspectionRepository` persists UTC timestamps, sanitized source filename
metadata, dimensions, defect JSON, totals, score, verdict, model ID, media type,
and relative media paths. History filtering is performed in SQL and combines
inclusive `from`/`to` dates, exact defect type through SQLite `json_each`, and a
case-insensitive ID/filename query. Results are newest first.

`InspectionStorage` coordinates the repository with `MediaStore`:

- new pairs are written to staging before a database transaction;
- stable final names use the inspection ID;
- failed writes or commits remove staged/promoted files;
- delete and clear move media to quarantine until the database commit succeeds;
- startup reconciliation restores referenced quarantined files and removes stale
  staging, quarantine, and unreferenced final files.

This layer stores bytes but does not create data URLs or HTTP responses. CSV
projection remains deferred with `/api/export`.
