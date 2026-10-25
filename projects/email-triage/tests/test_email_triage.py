"""Tests for Email Triage standalone subproject in system-one-projects.
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from starlette.testclient import TestClient

project_dir = Path(__file__).resolve().parent.parent
if str(project_dir) not in sys.path:
    sys.path.insert(0, str(project_dir))

from main import app
import email_triage

client = TestClient(app)

MOCK_ENVELOPES = [
    {
        "id": "1001",
        "subject": "Re: [parth5012/warden] feat: LangGraph checkpointing foundation (PR #1)",
        "from": [{"name": "coderabbitai[bot]", "email": "notifications@github.com"}],
        "date": "2026-10-11T04:06:34-07:00",
        "size": 45599,
        "flags": ["*"]
    },
    {
        "id": "1002",
        "subject": "50% off autumn sneaker clearance sale",
        "from": [{"name": "SneakerOutlet", "email": "deals@sneakers.com"}],
        "date": "2026-10-11T03:00:00Z",
        "size": 12000,
        "flags": []
    }
]

def test_health_check():
    """Verify health endpoint."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["service"] == "email-triage"
    assert "vercel-ai-gateway" in data["providers"]

def test_email_triage_html_routes():
    """Verify that dashboard HTML endpoints render successfully."""
    for path in ["/", "/email-triage", "/triage", "/emails"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "Email Triage Engine" in res.text
        assert "TypeSafe Jev System One" in res.text

def test_api_list_emails_mocked():
    """Verify GET /api/email-triage/emails merges Himalaya envelopes with cache and allowlist."""
    with patch("email_triage.fetch_envelopes_from_himalaya", return_value=MOCK_ENVELOPES):
        res = client.get("/api/email-triage/emails?limit=2")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 2
        assert len(data["emails"]) == 2
        assert data["emails"][0]["id"] == "1001"
        assert data["emails"][0]["sender_name"] == "coderabbitai[bot]"
        assert data["emails"][0]["allowlisted"] is True, "notifications@github.com should match github.com allowlist"
        assert data["emails"][1]["id"] == "1002"
        assert data["emails"][1]["allowlisted"] is False

def test_api_categorize_mocked():
    """Verify POST /api/email-triage/categorize evaluates decision models and returns taxonomy."""
    mock_classified = {
        "message_id": "1002",
        "category": "irrelevant",
        "is_irrelevant_prob": 0.95,
        "urgency_score": 0.1,
        "action_required_prob": 0.02,
        "categorized_at": "2026-10-11T00:00:00Z"
    }
    
    with patch("email_triage.fetch_envelopes_from_himalaya", return_value=[MOCK_ENVELOPES[1]]):
        with patch("email_triage.classify_single_email", return_value=mock_classified):
            with patch.object(email_triage, "DEFAULT_PROVIDER", "openrouter"):
                with patch.object(email_triage, "OPENROUTER_API_KEY", "fake-key"):
                    res = client.post("/api/email-triage/categorize", json={"email_ids": ["1002"], "force_refresh": True})
                    assert res.status_code == 200
                    data = res.json()
                    assert data["categorized_count"] == 1
                    assert "1002" in data["results"]
                    assert data["results"]["1002"]["category"] == "irrelevant"
                    assert data["results"]["1002"]["is_irrelevant_prob"] == 0.95

def test_api_archive_mocked():
    """Verify POST /api/email-triage/archive calls Himalaya message move."""
    with patch("email_triage.move_messages_to_archive", return_value={"archived": ["1002"], "errors": []}):
        res = client.post("/api/email-triage/archive", json={"message_ids": ["1002"]})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["archived_count"] == 1
        assert data["message_ids"] == ["1002"]

def test_api_read_body_mocked():
    """Verify GET /api/email-triage/email/{id}/body returns parsed body."""
    mock_body = {
        "id": "1001",
        "subject": "PR Update",
        "sender": "bot@github.com",
        "body_text": "Here is the pull request review content.",
        "is_html": False
    }
    with patch("email_triage.extract_email_body_text", return_value=mock_body):
        res = client.get("/api/email-triage/email/1001/body")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "1001"
        assert "pull request review" in data["body_text"]

def test_api_allowlist_crud():
    """Verify CRUD operations on allowlist rules."""
    # 1. Fetch current list (should include seeded rules)
    res = client.get("/api/email-triage/allowlist")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    existing_patterns = [r["pattern"] for r in data["rules"]]
    assert "github.com" in existing_patterns

    # 2. Add new test pattern
    test_pattern = "pytest-unit-test-domain.io"
    add_res = client.post("/api/email-triage/allowlist", json={"pattern": test_pattern, "note": "Test rule"})
    assert add_res.status_code == 200
    rule = add_res.json()
    assert rule["pattern"] == test_pattern
    rule_id = rule["id"]

    # Duplicate check
    dup_res = client.post("/api/email-triage/allowlist", json={"pattern": test_pattern, "note": "Dup"})
    assert dup_res.status_code == 409

    # 3. Delete rule
    del_res = client.delete(f"/api/email-triage/allowlist/{rule_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted_id"] == rule_id

    # 4. Verify gone
    res_after = client.get("/api/email-triage/allowlist")
    patterns_after = [r["pattern"] for r in res_after.json()["rules"]]
    assert test_pattern not in patterns_after

@pytest.mark.asyncio
async def test_classify_clef_worker_ai_format():
    """Verify classify_single_email processes Cloudflare Workers AI Clef response correctly."""
    mock_cf_response = {
        "result": {
            "model": "clef-flash",
            "answers": {
                "is_irrelevant": {"type": "noul", "noul": 0.08},
                "category": {
                    "type": "choice",
                    "choice": "work",
                    "probabilities": {"work": 0.95, "irrelevant": 0.05}
                },
                "urgency": {"type": "score", "score": 0.45},
                "action_required": {"type": "noul", "noul": 0.25}
            }
        },
        "success": True,
        "errors": []
    }

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_cf_response
    mock_client.post = pytest.importorskip("unittest.mock").AsyncMock(return_value=mock_resp)

    res = await email_triage.classify_single_email(
        http_client=mock_client,
        email=MOCK_ENVELOPES[0],
        provider="cloudflare",
        model="@cf/cloudflare/clef-flash",
        cloudflare_token="fake-token",
        cloudflare_account_id="fake-account"
    )

    assert res["category"] == "work"
    assert res["is_irrelevant_prob"] == 0.0  # github.com is allowlisted
    assert res["urgency_score"] == 0.45
    assert res["provider"] == "cloudflare"
    assert res["model"] == "@cf/cloudflare/clef-flash"

def test_api_categorize_clef_provider_selection():
    """Verify POST /api/email-triage/categorize passes provider and model options."""
    mock_classified = {
        "message_id": "1002",
        "category": "personal",
        "is_irrelevant_prob": 0.1,
        "urgency_score": 0.5,
        "action_required_prob": 0.3,
        "categorized_at": "2026-10-11T00:00:00Z",
        "provider": "cloudflare",
        "model": "@cf/cloudflare/clef-flash"
    }

    with patch("email_triage.fetch_envelopes_from_himalaya", return_value=[MOCK_ENVELOPES[1]]):
        with patch("email_triage.classify_single_email", return_value=mock_classified) as mock_classify:
            with patch.object(email_triage, "CLOUDFLARE_API_TOKEN", "fake-token"):
                with patch.object(email_triage, "CLOUDFLARE_ACCOUNT_ID", "fake-account"):
                    res = client.post(
                        "/api/email-triage/categorize",
                        json={
                            "email_ids": ["1002"],
                            "force_refresh": True,
                            "provider": "cloudflare",
                            "model": "@cf/cloudflare/clef-flash"
                        }
                    )
                    assert res.status_code == 200
                    data = res.json()
                    assert data["categorized_count"] == 1
                    assert "1002" in data["results"]
                    assert data["results"]["1002"]["category"] == "personal"
                    mock_classify.assert_called_once()
                    _, kwargs = mock_classify.call_args
                    assert kwargs["provider"] == "cloudflare"
                    assert kwargs["model"] == "@cf/cloudflare/clef-flash"

@pytest.mark.asyncio
async def test_classify_vercel_laya_free_format():
    """Verify classify_single_email processes Vercel AI Gateway Laya Free response correctly."""
    mock_vercel_response = {
        "answers": {
            "is_irrelevant": {"type": "boolean", "probability": 0.05},
            "category": {
                "type": "choice",
                "choice": "work",
                "probabilities": {"work": 0.92, "irrelevant": 0.08}
            },
            "urgency": {"type": "score", "score": 0.35},
            "action_required": {"type": "boolean", "probability": 0.15}
        }
    }

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_vercel_response
    mock_client.post = pytest.importorskip("unittest.mock").AsyncMock(return_value=mock_resp)

    res = await email_triage.classify_single_email(
        http_client=mock_client,
        email=MOCK_ENVELOPES[0],
        provider="vercel",
        model="convaiinnovations/laya-free",
        vercel_token="fake-vercel-key"
    )

    assert res["category"] == "work"
    assert res["is_irrelevant_prob"] == 0.0  # allowlisted sender
    assert res["urgency_score"] == 0.35
    assert res["provider"] == "vercel"
    assert res["model"] == "convaiinnovations/laya-free"

def test_api_categorize_vercel_provider_selection():
    """Verify POST /api/email-triage/categorize passes Vercel AI Gateway options."""
    mock_classified = {
        "message_id": "1002",
        "category": "freelance",
        "is_irrelevant_prob": 0.02,
        "urgency_score": 0.8,
        "action_required_prob": 0.9,
        "categorized_at": "2026-10-11T00:00:00Z",
        "provider": "vercel",
        "model": "convaiinnovations/laya-free"
    }

    with patch("email_triage.fetch_envelopes_from_himalaya", return_value=[MOCK_ENVELOPES[1]]):
        with patch("email_triage.classify_single_email", return_value=mock_classified) as mock_classify:
            with patch.object(email_triage, "VERCEL_AI_GATEWAY_API_KEY", "fake-key"):
                res = client.post(
                    "/api/email-triage/categorize",
                    json={
                        "email_ids": ["1002"],
                        "force_refresh": True,
                        "provider": "vercel",
                        "model": "convaiinnovations/laya-free"
                    }
                )
                assert res.status_code == 200
                data = res.json()
                assert data["categorized_count"] == 1
                assert "1002" in data["results"]
                assert data["results"]["1002"]["category"] == "freelance"
                mock_classify.assert_called_once()
                _, kwargs = mock_classify.call_args
                assert kwargs["provider"] == "vercel"
                assert kwargs["model"] == "convaiinnovations/laya-free"


# ---------------------------------------------------------------------------
# Sorter dashboard contract (pattern spec: .opencode/skill/email-sorter-ui/SKILL.md)
# ---------------------------------------------------------------------------

# message_id, category, is_irrelevant_prob, urgency_score, action_required_prob
DIST_FIXTURE = [
    ("dist-fx-1", "irrelevant", 0.92, 2.0, 0.10),
    ("dist-fx-2", "newsletter", 0.85, 8.0, 0.80),
    ("dist-fx-3", "newsletter", 0.15, 5.0, 0.50),
    ("dist-fx-4", "work", 0.20, 9.5, 0.95),
]


def _seed_dist_fixture():
    with email_triage.get_db_connection() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO email_triage_cache ("
            "message_id, subject, sender_name, sender_email, date, size, "
            "category, is_irrelevant_prob, urgency_score, action_required_prob, "
            "summary, archived, categorized_at) "
            "VALUES (?, 'Fixture subject', 'Fixture', 'fixture@example.com', "
            "'2026-10-25T00:00:00+00:00', 1000, ?, ?, ?, ?, '', 0, "
            "'2026-10-25T09:27:00+00:00')",
            [(mid, cat, irr, urg, act) for mid, cat, irr, urg, act in DIST_FIXTURE],
        )
        conn.commit()


def test_api_distributions_contract(tmp_path):
    """Distribution payload feeds the Sorter card grid: buckets, averages, freshness."""
    with patch.object(email_triage, "DB_PATH", tmp_path / "dist.db"):
        email_triage.init_db()
        _seed_dist_fixture()

        res = client.get("/api/email-triage/distributions?threshold=0.5")
        assert res.status_code == 200
        data = res.json()

        assert data["threshold"] == 0.5
        assert data["sample_size"] == 4
        assert data["total"] == 4
        assert data["uncategorized"] == 0
        assert data["synced_at"] == "2026-10-25T09:27:00+00:00"

        questions = data["questions"]
        assert [q["question"] for q in questions] == [
            "is_irrelevant", "category", "urgency", "action_required"
        ]
        assert all(q["title"] for q in questions), "every question needs a display title"
        by_q = {q["question"]: q for q in questions}

        # noul -> Yes/No buckets split at the threshold
        irr = by_q["is_irrelevant"]
        assert irr["type"] == "noul"
        assert irr["answered"] == 4
        assert {b["key"]: b["count"] for b in irr["buckets"]} == {"yes": 2, "no": 2}
        assert [b["label"] for b in irr["buckets"]] == ["Yes", "No"]
        assert sum(b["count"] for b in irr["buckets"]) == irr["answered"]

        act = by_q["action_required"]
        assert {b["key"]: b["count"] for b in act["buckets"]} == {"yes": 3, "no": 1}

        # choice -> every taxonomy category, densest first, taxonomy order breaking ties
        cat = by_q["category"]
        assert cat["type"] == "choice"
        assert cat["answered"] == 4
        assert [b["key"] for b in cat["buckets"]] == [
            "newsletter", "work", "irrelevant", "freelance", "personal", "transactional"
        ]
        assert [b["count"] for b in cat["buckets"]] == [2, 1, 1, 0, 0, 0]
        assert all(b["label"] for b in cat["buckets"]), "category buckets need human labels"

        # score -> numbered level buckets over the scale plus an average
        urg = by_q["urgency"]
        assert urg["type"] == "score"
        assert urg["scale"] == 10
        assert urg["answered"] == 4
        assert [b["label"] for b in urg["buckets"]] == [
            "1. Low", "2. Medium", "3. High", "4. Critical"
        ]
        # banded by the taxonomy's explicit thresholds, not equal quarters of the
        # scale: Clef returns urgency in a 0-3-ish range, so quarters would collapse
        # every row into "Low". 2.0 -> Medium, 5.0 -> High, 8.0/9.5 -> Critical.
        assert [b["count"] for b in urg["buckets"]] == [0, 1, 1, 2]
        assert sum(b["count"] for b in urg["buckets"]) == urg["answered"]
        assert urg["average"] == 6.1


def test_api_distributions_empty_cache(tmp_path):
    """Empty cache still renders a full set of zeroed cards."""
    with patch.object(email_triage, "DB_PATH", tmp_path / "empty.db"):
        email_triage.init_db()

        res = client.get("/api/email-triage/distributions")
        assert res.status_code == 200
        data = res.json()
        assert data["sample_size"] == 0
        assert data["total"] == 0
        assert data["uncategorized"] == 0
        assert data["synced_at"] is None
        assert len(data["questions"]) == 4
        for q in data["questions"]:
            assert q["answered"] == 0
            assert sum(b["count"] for b in q["buckets"]) == 0
        urg = next(q for q in data["questions"] if q["question"] == "urgency")
        assert urg["average"] is None


def test_dashboard_ships_sorter_shell():
    """The served dashboard carries the Sorter shell hooks the card grid renders into."""
    res = client.get("/email-triage")
    assert res.status_code == 200
    html = res.text
    for marker in [
        'id="question-rail"',
        'id="run-bar"',
        'id="card-grid"',
        'id="run-receipt"',
        'id="cost-modal"',
        'id="item-table"',
        "Compare cost",
    ]:
        assert marker in html, f"missing Sorter shell marker: {marker}"
    assert "Email Triage Engine" in html
    assert "TypeSafe Jev System One" in html


@pytest.mark.asyncio
async def test_model_payload_excludes_display_metadata():
    """Decision APIs reject dashboard-only taxonomy fields (title/labels/scale) with 422.

    Reproduces the live Clef failure: 'questions.is_irrelevant.noul.title:
    Extra inputs are not permitted'.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"answers": {}}, "success": True, "errors": []}
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    await email_triage.classify_single_email(
        http_client=mock_client,
        email=MOCK_ENVELOPES[1],
        provider="cloudflare",
        model="@cf/cloudflare/clef-flash",
        cloudflare_token="fake-token",
        cloudflare_account_id="fake-account",
    )

    body = mock_client.post.call_args.kwargs["json"]
    questions = body["questions"]
    assert set(questions["is_irrelevant"]) == {"type", "instructions"}
    assert "labels" not in questions["category"]
    assert "scale" not in questions["urgency"]
    for spec in questions.values():
        assert "title" not in spec

    # every provider path goes through the same stripped payload
    stripped = email_triage.model_questions()
    assert stripped.keys() == email_triage.QUESTIONS_TAXONOMY.keys()
    for spec in stripped.values():
        assert set(spec) <= {"type", "instructions", "criteria"}


def test_distributions_threshold_only_applies_to_irrelevance(tmp_path):
    """The irrelevance slider cutoff must not move action_required's 0.5 cutoff.

    Otherwise dragging the spam slider re-buckets 'Needs a reply' while the
    table badge keeps using 0.50 -> card and badge disagree.
    """
    with patch.object(email_triage, "DB_PATH", tmp_path / "thr.db"):
        email_triage.init_db()
        with email_triage.get_db_connection() as conn:
            conn.execute(
                "INSERT INTO email_triage_cache (message_id, subject, sender_name, "
                "sender_email, date, size, category, is_irrelevant_prob, urgency_score, "
                "action_required_prob, summary, archived, categorized_at) VALUES "
                "('thr-1', 'S', 'F', 'f@e.com', '2026-10-25T00:00:00+00:00', 100, "
                "'work', 0.60, 1.5, 0.60, '', 0, '2026-10-25T09:00:00+00:00')"
            )
            conn.commit()

        res = client.get("/api/email-triage/distributions?threshold=0.7")
        assert res.status_code == 200
        by_q = {q["question"]: q for q in res.json()["questions"]}

        # 0.60 < 0.70 -> still "No" for irrelevance...
        irr_counts = {b["key"]: b["count"] for b in by_q["is_irrelevant"]["buckets"]}
        assert irr_counts == {"yes": 0, "no": 1}
        # ...but action_required keeps its own 0.50 cutoff -> "Yes"
        act_counts = {b["key"]: b["count"] for b in by_q["action_required"]["buckets"]}
        assert act_counts == {"yes": 1, "no": 0}


def test_distributions_score_exposes_band_edges(tmp_path):
    """The drill-through filter needs the same edges the backend bucketed with."""
    with patch.object(email_triage, "DB_PATH", tmp_path / "bands.db"):
        email_triage.init_db()
        res = client.get("/api/email-triage/distributions")
        assert res.status_code == 200
        urg = next(q for q in res.json()["questions"] if q["question"] == "urgency")
        assert urg["bands"] == [1.0, 2.5, 5.0]
        assert all(q["bands"] is None for q in res.json()["questions"] if q["type"] != "score")
