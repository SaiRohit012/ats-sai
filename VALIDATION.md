# Validation and migration notes

Tested on 19 September 2026 with Python 3.12, Streamlit 1.64.0, Tectonic 0.17.0, PyMuPDF 1.28.2, pypdf 6.19.0 and pytest 9.1.1 on Windows.

## Results

- **53 tests passed**, including real PDF compilation tests and the JD-driven selection regression checks.
- Both PDFs have exactly **15 bullets**: three per employer and three per selected project. Project order is checked as problem/purpose, implementation/method, then outcome with available measurements. Tests reject one, two or four bullets and reordered project narratives; missing measurements are explicitly flagged. They also reject rewrites that remove required numerical evidence.
- **V1: one page. V2: one page.** No compiler overflow, page-target, missing-word or protected-content warnings.
- Both PDFs contain all three education entries, IIT Madras's Foundation credential, all three employers, six skills categories, and two selected projects.
- Employment dates reflect the user's confirmations: HSBC January–July 2026, Redwood August 2026–Present, Codinoverse February–April 2024.
- Both HSBC achievement sets were confirmed by the user and are available for tailoring in each master profile.
- Redwood outcome metrics are unavailable, as confirmed by the user. Its five-layer architecture is explicitly classified as scope. No numerical impact was invented. Generic preview projects are PayFlow and the Distributed Key-Value Store. They are not fixed or preferred for AI tailoring. Their correctness results are retained; missing numerical benchmarks are flagged.
- PDF text was checked using **two independent readers**, PyMuPDF and pypdf. All expected lexical tokens are present in both. The first attempt exposed an AWS/kerning extraction problem; explicit OpenType font settings without kerning/standard ligatures resolved it in Tectonic builds.
- Tests check that section and employer headings share the 0.6-inch left margin, visible text is at least 10.4pt (rounding tolerance for the 10.5pt body size), and text stays within page bounds.
- Final pages were rendered with **Poppler** and visually inspected. No overlaps, clipped content, orphaned headings, or unintended second pages were observed.
- An intentional long-content test verifies that overflow is reported without silently deleting content or shrinking type.
- The Streamlit server booted, its health endpoint returned `ok`, and browser interaction successfully generated and displayed a one-page PDF.
- Streamlit AppTest covers boot, version switching, editable-profile behavior, local build failure handling, saved-result isolation from later JD/profile changes, and invalid selections.
- Unit tests cover nested JSON schema failures, missing roles, unknown IDs, cross-entry IDs, duplicate selections, unbuilt projects, new numerical claims, removed qualifiers, LaTeX escaping, catalog failures, non-free/audio-model filtering, 401 fail-fast behavior including repair, bounded repair/fallback, rate limits, mixed errors, and compiler timeouts.
- Live OpenRouter catalog access succeeded. No live chat-completion call was made because an API key was not supplied. Provider responses and error handling were tested with mocks.
- `pip check` reports no broken requirements.

## JD-driven selection revision

- Removed the prompt preference for named projects. Every run evaluates all six projects independently against the supplied JD.
- Required a complete include/omit assessment of the library, validated against the actual selection. Keyword reports classify priorities and may cite only evidence retained in the resume.
- Added six mocked tailoring cases across both profiles (payments, analytics and distributed systems), checking the full catalog reaches the provider and returned selections are preserved. Added invalid-assessment and omitted-keyword-evidence rejection tests.
- Clearly separated generic/manual previews from JD-tailored drafts in the UI. The included PDF snapshots are unchanged generic examples, not a tailored result for an unspecified JD.
- All 53 tests passed in 33.86 seconds. These tests validate integration and safeguards, not the quality of a live model's ranking. The renderer still measures each customized PDF; long combinations may require concise reviewed wording before meeting the one-page target.

## What these checks do not prove

They do not certify a particular employer's ATS parser, predict a hiring outcome, externally verify employment/project metrics, or guarantee future LLM output. A future customized PDF must still be inspected. The app exposes its page count, extracted text and any warnings for that purpose.

The Tectonic compilation path was exercised. The `pdflatex` fallback and Streamlit Community Cloud deployment instructions/dependencies are provided, but those environments were not available for a live deployment test. No GitHub push or hosted deployment was performed.

## Baseline inspected

- GitHub repository: https://github.com/SaiRohit012/ats-resume
- Inspected commit: `515fa5e57cd324a8859102be768551e5b9ec9fa4`
- Supplied archive: `ats-resume-upgrade (1).zip`
- Both original GitHub resume strings and both supplied ZIP templates are retained in `sources/` for traceability.

The complete original app was retrieved locally, including its final UI code. This work does not depend on the earlier ZIP author's incomplete fetch of lines 1000–1159.

## Migration from the old app

Copy this project's files into your repository, replacing `app.py`, `requirements.txt`, and `README.md` and adding the other files/directories. Keep your Streamlit entry point as `app.py`. Include `packages.txt` when deploying to Community Cloud.

Resume content now lives in `profiles/resume_v1.json` and `profiles/resume_v2.json`. The generated `resumes/*.tex` files are portable snapshots, not the app's authoritative data store. Old session data and marker-format LLM results are not imported. A new app session starts from the JSON profiles.

The previous five upgrades were useful, but their presence alone did not resolve content loss, layout stability, one-page verification, ambiguous source facts, unsafe arbitrary LaTeX execution, incomplete schema validation, or history changing its comparison baseline. This implementation addresses those issues explicitly.
