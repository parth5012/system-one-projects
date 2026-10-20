# 🧠 System One Projects

> Monorepo housing production applications and microservices built on **System One AI Decision Models** (TypeSafe Jev, Cloudflare Clef & Clef-Flash).

---

## 🎯 What is System One AI?

In cognitive psychology, **System 1** describes fast, instinctive, and calibrated emotional/intuitive judgments, contrasting with **System 2** which represents slow, deliberative, and analytical reasoning.

In modern AI engineering:
- **System Two (LLMs / Agents)**: Generates free-form natural language, reasons via Chain-of-Thought, plans steps, writes code. Latency: `1,000ms – 5,000ms+`. High cost per token.
- **System One (Decision Models)**: Evaluates structured application state against typed propositions to output calibrated probabilities and classifications with zero hallucination. Latency: `<40ms – 200ms`. Extremely low cost ($0.042/M tokens).

| Characteristic | System 2 (Generative LLMs) | System 1 (Decision Models: Jev / Clef) |
| :--- | :--- | :--- |
| **Output Type** | Prose, markdown, JSON-in-markdown | Calibrated probabilities, typed scalar scores, categorical choices |
| **Latency** | 1,000 ms – 5,000 ms | 35 ms – 200 ms |
| **Hallucination Risk** | Inherent in token generation | Zero (schema & probabilities mathematically bounded) |
| **Workflow Ownership** | Model attempts to steer | Deterministic code owns the workflow, model supplies fast judgments |
| **Cost** | $1.00 – $15.00+ / M tokens | $0.042 – $0.24 / M tokens |

---

## 🏛️ Monorepo Structure

```
system-one-projects/
├── README.md                          # Monorepo architecture & primer
├── pyproject.toml                     # Root package & pytest config
├── .gitignore                         # Standard ignores & secret protection
├── .github/
│   └── workflows/
│       └── ci.yml                     # Automated GitHub Actions test pipeline
├── projects/
│   └── email-triage/                  # 📬 Subproject: Email Triage Engine
│       ├── README.md                  # In-depth email triage documentation
│       ├── pyproject.toml             # Standalone Python package definition
│       ├── requirements.txt           # Subproject dependencies
│       ├── .env.example               # Environment variables template
│       ├── main.py                    # Standalone FastAPI server & runner
│       ├── email_triage.py            # Core engine, router, SQLite cache & allowlist
│       ├── decision_client.py         # Unified Jev & Clef decision model client
│       ├── static/                    # Modern responsive dashboard UI
│       │   └── index.html
│       └── tests/                     # Comprehensive test suite (100% pass)
│           └── test_email_triage.py
└── email-triage -> projects/email-triage # Root symlink convenience
```

---

## 📦 Subprojects

### 1. [`projects/email-triage`](projects/email-triage)
An autonomous email classification, spam filtration, and priority ranking engine.
- Multi-provider System One backends:
  - **Cloudflare Workers AI**: `@cf/cloudflare/clef-flash` (9B, ~38ms) & `@cf/cloudflare/clef` (27B multimodal)
  - **Vercel AI Gateway (Free Tier)**: `convaiinnovations/laya-free` (Convai Innovations Laya free-tier evaluation model) & `typesafe-ai/jev`
  - **OpenRouter / TypeSafe**: `typesafe/jev-1.13`
- Evaluates 4 decision propositions in parallel (`is_irrelevant`, `category`, `urgency`, `action_required`).
- Built-in SQLite caching, audit trails, and sender domain allowlists.
- Full interactive web dashboard with real-time multi-provider switching.

---

## ⚙️ Development & Testing

### Run Tests Across Monorepo
```bash
pytest
```

### Run Email Triage Standalone
```bash
cd projects/email-triage
pip install -r requirements.txt
cp .env.example .env  # Add your Cloudflare / OpenRouter keys
python main.py
```

Dashboard is served at:
`http://localhost:8085/email-triage`

---

## 📜 License

MIT License. Built by [Parth Chawla](https://github.com/parth5012) & Hermes Agent.
