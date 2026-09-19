# Resume Studio

A replacement for the supplied ATS Resume Optimizer, with two readable resume variants, structured source data, reviewable AI tailoring, and actual PDF checks.

## Start locally

Requires Python 3.11+ and either [Tectonic](https://tectonic-typesetting.github.io/book/latest/installation/) or TeX Live on PATH.

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
```

Use **Build resume preview** without an API key. To tailor to a job, enter your OpenRouter key, refresh the live model catalog, paste the job description, and choose **Tailor to this job with AI**. The first Tectonic run downloads its typesetting packages; if it times out, retry after packages have downloaded. TeX Live is an alternative without runtime downloads.

## Job-driven generation

Paste the actual job description and use **Tailor to this job with AI**. Both source variants expose their entire six-project library. The model ranks direct technology/domain overlap first, supported outcomes second, and complementary coverage third. PayFlow and the key-value store are candidates, not mandatory selections. Manual preview selections never restrict the AI library.

The response must account for every project with an include/omit rationale. The application rejects missing, duplicate or contradictory assessments. Job analysis shows these decisions alongside CRITICAL/IMPORTANT/BONUS keyword requirements and evidence from the selected resume. Unsupported requirements remain gaps. Optional unbuilt project suggestions remain outside the resume.

All three roles, all education, skills and contact details remain protected. Each included role/project retains exactly three bullets. Review proposed wording, rebuild, and inspect the measured PDF page count and warnings before applying. The ZIP's PDFs are generic examples; a specific final resume requires a JD and a successful tailoring run.

## What changed

- Education is compact, single-column text. IIT Madras appears in both variants as a **Foundation in Data Science and Programming**, not a degree.
- Headings are outside bullet lists and align with the left margin. Positive spacing separates headings, role subtitles, and bullets.
- Skills use full-width categories. The two-column skills table is removed. Source-backed skills and all education entries are protected from AI deletion.
- The actual body font is 10.5pt with a 13pt baseline. `article` does not support a `10.5pt` class option; the font size is explicitly set instead. There is no negative spacing or automatic type shrinking.
- V1 uses a serif font and V2 uses a sans serif font. Both have the same reading order and layout rules.
- The entire project catalog remains in `profiles/`. One-page drafts use two selected projects; the optional two-page mode permits up to three. Omitted projects are shown in the app and can be selected for another job.
- One-page drafts omit the generic summary and leadership section. Project technology stacks are visible beneath the titles. The layout fills the usable page with 0.6-inch top/side margins and a 0.55-inch bottom margin.
- The model selects existing evidence IDs and proposes wording in JSON. It cannot generate executable LaTeX or alter education, contact details, roles, dates, the skills list, or layout. Every experience and selected project must have **exactly three bullets** in either page mode.
- Project bullets follow **problem/purpose and what was built → implementation and method → outcome**. This sequence is validated from source metadata. Every role must retain a source-backed quantitative bullet. A rewrite cannot remove its numerical claims.
- Redwood has quantified scope (a five-layer architecture), not a measured improvement. The user confirmed that Redwood outcome metrics are not yet available; release numbers are not treated as achievement metrics.
- PayFlow, the key-value store and RideWise remain in the project library with three structured bullets, but lack numerical outcome measurements. Generic previews use PayFlow and the Distributed Key-Value Store. AI tailoring has no fixed project preference: it evaluates all six projects against each JD. The app flags missing numerical benchmarks and retains supported correctness outcomes. No invented measurements were added.
- Proposed rewrites require individual human review. New numeric claims and removed estimate/target qualifiers are rejected automatically; semantic truth still needs human judgment.
- Project ideas are labeled unbuilt and never inserted into a resume.
- A lexical **keyword coverage** check replaces the misleading ATS-score label. It includes nontechnical JD words, supports a few aliases, and is not a vendor ATS score, role-fit assessment, or hiring prediction.
- The app previews every PDF page, extracts its text, checks page count, flags compiler overflow, and checks protected content and missing words. It never declares a one-page fit without measuring it.
- A one-page target may overflow with your full education/skills and long source bullets. The app reports that honestly; select fewer projects or review concise rewrites while retaining three bullets per entry. It does not hide qualifications or shrink the text to force a fit.
- Model prices are checked against the live catalog at request time. Catalog failure stops the call instead of using unverified stale model IDs. Models are sorted by context capacity, not an asserted quality ranking.
- At most three models and one format-repair call per model are attempted. Authentication failures fail immediately, including during repair. Rate limits retain `Retry-After`; mixed failures are not mislabeled as all-rate-limited.
- History retains immutable source/JD/result snapshots. Editing a different resume or job description does not silently change an earlier result's diff or coverage.
- PDF compilation happens only on build, retry, or applying reviewed wording; tab interactions reuse the saved result.

## Files and editing

```text
app.py                   Streamlit interface and session history
core.py                  API, validation, coverage, PDF compilation and inspection
renderer.py              Fixed single-column LaTeX renderer
prompts.py               Structured selection/rewrite contract
profiles/resume_v1.json   V1 source facts and complete project catalog
profiles/resume_v2.json   V2 source facts and complete project catalog
resumes/resume_v1.tex     Generated editable LaTeX snapshot
resumes/resume_v2.tex     Generated editable LaTeX snapshot
sources/                 Original GitHub and ZIP resume snapshots for comparison
export_resumes.py         Generate matching .tex, .pdf and extracted .txt files
tests/                   Validation, API failure, content, rendering and UI tests
packages.txt             TeX Live dependencies for Streamlit Community Cloud
```

Edit the matching JSON profile to change permanent resume content. The app also offers an editor and JSON download for session edits; replace the repository file with that download to make it permanent. The generated `.tex` files can be edited in Overleaf, but future builds use the JSON profiles and renderer.

```bash
python export_resumes.py --output resumes
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Source facts and confirmations

1. **Employment dates confirmed:** you clarified HSBC was January–July 2026 and Redwood began in August 2026. Both profiles now use those dates.
2. **Both HSBC achievement sets confirmed:** you confirmed the vendor-analysis/complaint-triage set and the ML-accuracy/production-incident set are accurate. Both sets are available in each master profile. V1 uses vendor analysis, transaction analysis and complaint triage; V2 uses ML classification, BigQuery incident analysis and data-validation automation. Your confirmation is recorded in `confirmed_facts`; the app does not claim external verification.
3. **Codinoverse dates confirmed:** you clarified that the internship ended in April 2024. Both profiles use February–April 2024, resolving the March/April discrepancy between GitHub and the ZIP.
4. **Contact details:** V1 uses the BITS email and Hyderabad/Bengaluru; V2 uses the personal email and Hyderabad. Choose the current contact details.
5. **Education and metrics:** confirm the exact IIT credential name, current degree status/CGPAs, metrics, project completion, and release ownership. Foundation study is not represented as a completed IIT degree.

The delivered application resumes each contain **15 bullets on one page**: nine experience bullets and six project bullets. These are generic previews using PayFlow and the Distributed Key-Value Store, not final resumes for a particular JD. Tailored selections can differ for every job. All three education entries and skills categories remain visible. Existing quantitative claims were retained from the supplied sources, including claims needing verification. Original bullet wording is retained in `source_bullets`/`source_text`, and original resumes are in `sources/`. A source-backed claim is not necessarily a true claim. The app does not certify your work history, and no format can guarantee shortlisting or error-free LLM output.

When adding measurements to a project, replace its outcome bullet with an actual result, set `metric_kind` to `outcome`, and include that bullet's ID in `metric_bullet_ids`. Record the benchmark conditions and evidence in `metric_note`. Do not fill these fields with invented results. Preserve the `problem`, `implementation`, `outcome` kinds in that order.

## Deploy to Streamlit Community Cloud

Upload the complete project, select `app.py` as the entry point, and include both `requirements.txt` and `packages.txt`. `packages.txt` installs `pdflatex`, `titlesec`, `enumitem`, `needspace`, and Latin Modern fonts through the listed TeX Live packages. These include more than `texlive-latex-base`, which alone is insufficient for this template.

Keep API keys out of the repository. They live in the password field for the session. No key is included in history exports. The AI receives the selected profile's career evidence and job description; contact fields are excluded from its payload. Hosting administrators and model providers still control their respective environments. Use a trusted deployment for personal data.

LaTeX is generated only by the renderer with escaped text; arbitrary pasted or AI-written LaTeX is not compiled by the app. Tectonic uses untrusted mode. The `pdflatex` path disables shell escape and restricts file access. For a public, multiuser service, enforce resource limits and isolate compilation at the deployment level; these flags are not an operating-system sandbox.

## Why no education table?

A simple table can look compact to a recruiter, but parser behavior varies. Greenhouse lists complex tables and columned layouts among causes of unsuccessful or partial resume parsing. Two text lines per qualification preserve a predictable order without hiding IIT Madras. Harvard's guidance supports clear, consistent formatting, balanced whitespace, and fact-based bullets.

- [Greenhouse: unsuccessful resume parse](https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse)
- [Harvard: creating a strong resume](https://careerservices.fas.harvard.edu/resources/create-a-strong-resume/)
- [OpenRouter model catalog](https://openrouter.ai/docs/api/api-reference/models/get-models)
- [Streamlit deployment dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Tectonic compilation and untrusted mode](https://tectonic-typesetting.github.io/book/latest/v2cli/compile.html)

See `VALIDATION.md` for what was actually tested and the remaining limits.
