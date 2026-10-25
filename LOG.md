# Log

## 2026-10-25 — email-triage: Sorter dashboard rework (branch `t3/extract-email-ui-patterns-skill`)

**Status:** Done · **Iter:** 1 · **Project:** `projects/email-triage`

### What changed

1. **`GET /api/email-triage/distributions?threshold=`** (new, `email_triage.py`) —
   per-question distributions computed in SQLite: `noul` Yes/No at the cutoff,
   `choice` categories (taxonomy order, count desc), `score` bands. Returns
   `sample_size` / `total` / `uncategorized` / `synced_at` / `threshold` plus
   `questions[]` with `title`, `answered`, `buckets`, `average`, `scale`, `bands`.
   Per-question `bands` + `threshold` overrides added to `QUESTIONS_TAXONOMY`.
2. **`model_questions()`** — single strip point that keeps only
   `type`/`instructions`/`criteria` for the decision APIs. Fixes a live bug: Clef
   returned `422 Extra inputs are not permitted` for the new display metadata, so
   every run silently sorted 0 emails.
3. **`static/index.html` rebuilt as the Sorter shell** (1,251 → ~2,690 lines):
   top bar (tabs + spend + `Compare cost`), question rail (enable checkboxes,
   pencil title edits, `+ New`), recipe header (sample, freshness, 25/50/100,
   Refresh), run bar (status sentence, model, scope, `▶ Run`, run receipt),
   distribution cards driven by the payload (bars, `Show N more`, `Average X of Y`),
   drill-through filters into the item table (chip + active row + second-click
   clear), one column per question, CSV `Export`, cost modal (measured vs
   list-price, per-1,000, `Against Jev`), feedback pill.
4. **Safety/robustness fixes found by review + live E2E:** urgency drill filter now
   derives edges from the payload `bands`; `threshold` no longer re-buckets
   `action_required`; inline handlers use `jsAttr()` (JSON + HTML escape) because
   `escapeHtml()` is entity-decoded before inline JS runs; bucket rows are native
   `<button>`s; cost modal never prints a fabricated figure.

### Verification

- `python3 -m pytest tests/ -q` → **17 passed** (6 new: distributions contract,
  empty cache, shell markers, model-payload strip, per-question threshold, bands).
- `node --check` on the extracted inline script → OK.
- Live E2E in the browser at `/email-triage`: real `▶ Run` classified **47 emails
  in 26.6 sec** with Clef-Flash (after the 422 fix), receipt printed, cards showed
  48 answered, `Work & GitHub` drill → 27 rows → second click restored 50,
  `2. Medium` drill → exactly the 8 rows the card counted, cost modal opened with
  the honest "no published list prices" row, malicious-sender click-through
  delivered the raw string as one argument (no breakout). Console: no errors.

### Post-change pipeline

| Step | Result |
|---|---|
| `code-simplifier` | Folded into this pass: cost modal dead table → single honest row, duplicate band math removed (backend + frontend share payload edges) |
| `code-review` | CodeReviewer subagent on the diff → 3 findings (XSS in inline handlers, urgency band mismatch, global threshold), all fixed and re-verified above |
| `ocr-review` | Visual check via browser screenshots at 1280×800 — shell, cards, modal render correctly, no console errors |
| `pr` | Skipped — no PR requested for this change (work stays on the branch) |
| `repo-quality-orchestrator` | Skipped — TypeScript-repo audit; this project is Python + single-file HTML (covered by pytest + `node --check`) |
| `retro` | This entry; edge cases recorded in `LEARNINGS.md` |

### Next

- Onboarding a new source tab (YouTube/X/Support) now starts from
  `.opencode/skill/email-sorter-ui/SKILL.md` — taxonomy + payload contract, no
  `index.html` edits needed for a new question.
