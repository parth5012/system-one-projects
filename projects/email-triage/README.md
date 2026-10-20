# 📬 Email Triage Engine (System One Decision Models)

> Deterministic, ultra-low-latency email triage, classification, and allowlist protection powered by **TypeSafe Jev** and **Cloudflare Clef / Clef-Flash** System One decision models.

---

## ⚡ Overview

Traditional LLM classification prompts suffer from latency (1,000–3,000ms), hallucinations, markdown formatting parsing failures, and unpredictable token output costs.

The **Email Triage Engine** replaces generative LLMs with **System One decision models**:
- **TypeSafe Jev** (via OpenRouter or TypeSafe native endpoint)
- **Cloudflare Clef** (27B multimodal) and **Clef-Flash** (9B ultra-low latency, ~38ms)

Code owns the workflow and state transitions while the decision model supplies calibrated probabilities for boolean checks, discrete category choice, and continuous urgency scoring.

---

## 🏗️ Architecture

```
                                  ┌─────────────────────────────┐
                                  │   Himalaya CLI (IMAP/TLS)   │
                                  └──────────────┬──────────────┘
                                                 │ Envelope & Body Read
                                                 ▼
┌───────────────────────┐         ┌─────────────────────────────┐
│  Modern Web Dashboard │ ◄─────► │     FastAPI Backend App     │
│   (index.html)        │         └──────────────┬──────────────┘
└───────────────────────┘                        │
                                                 ├──────────────────────────────┐
                                                 ▼                              ▼
                                  ┌─────────────────────────────┐  ┌────────────────────────┐
                                  │  Allowlist & SQLite Cache   │  │  System One Engine     │
                                  │  - bypass protection        │  │  - Clef-Flash (9B)     │
                                  │  - audit trail & state      │  │  - Clef (27B)          │
                                  └─────────────────────────────┘  │  - Jev 1.13            │
                                                                   └────────────────────────┘
```

### Core Decision Primitives Evaluated Per Email

1. **`is_irrelevant` (`noul`)**:
   Binary proposition (0.0 to 1.0 probability) determining whether an email is pure marketing spam, cold pitch, or discount noise safe to archive.
2. **`category` (`choice`)**:
   Discrete taxonomy categorization:
   - `work`: Engineering, GitHub PRs/issues, CI/CD, internship.
   - `freelance`: Freelance inquiries, Truelancer/Upwork gigs, contract opportunities.
   - `personal`: 1-on-1 conversations, professors, university academics.
   - `newsletter`: High-signal technical digests, Substack, AI publications.
   - `transactional`: Order receipts, OTPs, invoices, banking, security alerts.
   - `irrelevant`: Promotional sales, cold outreach, coupon blasts.
3. **`urgency` (`score`)**:
   Continuous scalar (0.0 to 10.0 scale) evaluating response priority and time sensitivity.
4. **`action_required` (`noul`)**:
   Probability that direct action or reply is needed from the user.

---

## 🛡️ Allowlist Protection

Emails matching verified sender domains or handles (e.g. `flyrank.ai`, `github.com`, `truelancer.com`) automatically bypass `is_irrelevant` scoring and cannot be auto-archived. Users can add or remove allowlist rules directly from the web dashboard or REST API.

---

## 🚀 Quickstart

### 1. Prerequisites
- Python 3.10+
- Himalaya CLI configured with IMAP/SMTP (`which himalaya`)
- API credentials for Cloudflare Workers AI or OpenRouter

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
Copy `.env.example` to `.env` and configure:
```bash
cp .env.example .env
```
Fill in:
- `CLOUDFLARE_API_TOKEN` & `CLOUDFLARE_ACCOUNT_ID` (for Clef)
- `OPENROUTER_API_KEY` (for Jev)

### 4. Run the Standalone Server
```bash
python main.py
# Or with uvicorn:
uvicorn main:app --host 0.0.0.0 --port 8085 --reload
```

Open your browser at:
`http://localhost:8085/email-triage` (or your remote Tailscale MagicDNS host).

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

All endpoints, Himalaya parsing mocks, allowlist CRUD, and Cloudflare Clef Workers AI formats are covered.

---

## 📡 API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/health` | `GET` | Health check & engine status |
| `/email-triage` | `GET` | Interactive Web Dashboard |
| `/api/email-triage/emails` | `GET` | List recent envelopes with cache & allowlist status |
| `/api/email-triage/categorize` | `POST` | Execute System One classification (Clef/Jev) |
| `/api/email-triage/archive` | `POST` | Move selected message IDs to Gmail Archive via Himalaya |
| `/api/email-triage/email/{id}/body` | `GET` | Fetch parsed plain text / HTML email snippet |
| `/api/email-triage/allowlist` | `GET` | Retrieve active bypass allowlist rules |
| `/api/email-triage/allowlist` | `POST` | Add a domain / pattern to allowlist |
| `/api/email-triage/allowlist/{id}` | `DELETE` | Delete domain from allowlist |
