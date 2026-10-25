# Learnings

## email-triage

### Display metadata must be stripped before it reaches the decision model
`QUESTIONS_TAXONOMY` now carries dashboard-only fields (`title`, `labels`, `scale`,
`bands`, `threshold`). Cloudflare Clef rejects any extra question field with
`422 … Extra inputs are not permitted`, which failed *every* classification while
returning HTTP 200 with `categorized_count: 0`. All model call sites go through
`model_questions()`, which keeps only `type` / `instructions` / `criteria`. New
display field? No code change needed — the strip point already exists, and
`test_model_payload_excludes_display_metadata` guards it.

### Live runs find what mocked tests can't
The 422 above was invisible to pytest: `classify_single_email` was mocked and the
taxonomy never reached the wire. The first real `▶ Run` surfaced it in seconds.
Always exercise the actual provider once before calling a UI change done.

### Score buckets need the model's real range, not the documented one
README documents urgency on 0–10, but Clef's observed output over 48 real emails
spans 0.07–2.06. Equal quarters of 0–10 put all 48 rows in `1. Low` (useless
card), and once the backend used explicit `bands: [1.0, 2.5, 5.0]` the *frontend*
drill filter still used quarters — card said 8, filtered table said 0. Rules:

- Bucket edges live in the taxonomy (`bands`), are echoed in the payload, and the
  frontend derives membership from them (`inScoreBucket`) — never re-derive edges
  in two places.
- Keep `bands` aligned with the table badge thresholds so card and badge agree.

### `threshold` is per question, not global
The irrelevance slider (`?threshold=0.7`) must only re-bucket `is_irrelevant`.
Applied to every `noul`, it moved `Needs a reply` while `getActionBadge` stayed at
0.50. Fixed cutoffs belong on the taxonomy entry (`action_required: threshold 0.5`).

### `escapeHtml()` is not safe inside inline event handlers
The HTML parser decodes entities *before* running inline JS, so
`onclick="fn('${escapeHtml(x)}')"` still breaks out on a value containing `'`
(e.g. an email address `a'b@x.com');alert(1);//`). Use `jsAttr()` —
JSON-quote then HTML-escape — for anything interpolated into `onclick`/`onchange`.
Proven in the browser: the malicious sender arrives as a single string argument.

### Drilling rows are buttons
`<button type="button" class="bucket-row">` (with `:focus-visible` ring) instead of
a clickable `<div>` — keyboard operable, appears in the a11y tree, no `role` patching.
Bar track/fill inside become `<span>` + `display:block` since `<button>` only accepts
phrasing content.

### Honest cost beats a wall of dashes
No price for a model can be substantiated from README/env, so `MODEL_PRICES` stays
`null`: the receipt prints time only, the `Against Jev` column computes only when
both sides have a figure, and the list-price table collapses to one sentence saying
prices aren't published (footnote hidden).
