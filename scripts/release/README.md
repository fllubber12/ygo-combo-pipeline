# Release Zip

Creates a clean, shareable zip without development artifacts.

## Usage
- Default (excludes reports/ and data_cache/):
  - `bash scripts/release/make_release_zip.sh`
- Include reports:
  - `bash scripts/release/make_release_zip.sh --include-reports`
- Include cached Konami HTML:
  - `bash scripts/release/make_release_zip.sh --include-cache`

Output is written to `dist/` with a timestamped filename.

## Setup
- `bash scripts/dev/bootstrap_venv.sh`

## QA
- `python scripts/qa/run_qa.py`
- If `python` is not on PATH, use `python3`.
