"""Unified Decision Model Client for System One Architecture.

Supports:
- TypeSafe Official API (Jev models)
- OpenRouter API (typesafe/jev-1.13, ~typesafe/jev-latest)
- Cloudflare Workers AI REST API (Clef & Clef-Flash models)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Union

ProviderName = Literal["typesafe", "openrouter", "cloudflare", "vercel"]


@dataclass
class NoulAnswer:
    noul: float  # Probability of yes (0.0 to 1.0)


@dataclass
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: Dict[str, float]


@dataclass
class ScoreAnswer:
    score: float  # Expected continuous value on rubric scale
    confidence: float
    probabilities: Dict[str, float]
    legend: Optional[Dict[str, str]] = None


@dataclass
class DecisionResponse:
    provider: str
    model: str
    answers: Dict[str, Any]
    raw: Dict[str, Any]
    usage: Optional[Dict[str, Any]] = None

    def get_noul(self, question_id: str) -> float:
        ans = self.answers.get(question_id, {})
        if isinstance(ans, dict):
            for k in ("noul", "probability", "prob", "score"):
                if k in ans:
                    return float(ans[k])
        if isinstance(ans, (int, float)):
            return float(ans)
        raise KeyError(f"Question '{question_id}' not found or not a valid Noul/Boolean answer")

    def get_choice(self, question_id: str) -> ChoiceAnswer:
        ans = self.answers.get(question_id, {})
        if isinstance(ans, dict) and "choice" in ans:
            return ChoiceAnswer(
                choice=ans.get("choice", ""),
                confidence=float(ans.get("confidence", 0.0)),
                probabilities=ans.get("probabilities", {}),
            )
        raise KeyError(f"Question '{question_id}' not found or not a valid Choice answer")

    def get_score(self, question_id: str) -> ScoreAnswer:
        ans = self.answers.get(question_id, {})
        if isinstance(ans, dict) and "score" in ans:
            return ScoreAnswer(
                score=float(ans.get("score", 0.0)),
                confidence=float(ans.get("confidence", 0.0)),
                probabilities=ans.get("probabilities", {}),
                legend=ans.get("legend"),
            )
        raise KeyError(f"Question '{question_id}' not found or not a valid Score answer")


class DecisionClient:
    """Unified client for TypeSafe Jev (official / OpenRouter) and Cloudflare Clef."""

    def __init__(
        self,
        default_provider: ProviderName = "openrouter",
        typesafe_api_key: Optional[str] = None,
        typesafe_base_url: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_base_url: Optional[str] = None,
        cloudflare_api_token: Optional[str] = None,
        cloudflare_account_id: Optional[str] = None,
        cloudflare_gateway_id: Optional[str] = None,
        vercel_api_key: Optional[str] = None,
        vercel_base_url: Optional[str] = None,
        timeout: int = 30,
    ):
        self.default_provider = default_provider
        self.typesafe_api_key = typesafe_api_key or os.getenv("TYPESAFE_API_KEY")
        self.typesafe_base_url = (
            typesafe_base_url or os.getenv("TYPESAFE_BASE_URL") or "https://api.typesafe.ai"
        ).rstrip("/")
        self.openrouter_api_key = openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
        self.openrouter_base_url = (
            openrouter_base_url
            or os.getenv("OPENROUTER_BASE_URL")
            or "https://openrouter.ai/api"
        ).rstrip("/")
        self.cloudflare_api_token = (
            cloudflare_api_token
            or os.getenv("CLOUDFLARE_API_TOKEN")
            or os.getenv("CF_API_TOKEN")
        )
        self.cloudflare_account_id = (
            cloudflare_account_id
            or os.getenv("CLOUDFLARE_ACCOUNT_ID")
            or os.getenv("CF_ACCOUNT_ID")
        )
        self.cloudflare_gateway_id = (
            cloudflare_gateway_id
            or os.getenv("CLOUDFLARE_GATEWAY_ID")
            or os.getenv("CF_GATEWAY_ID")
        )
        self.vercel_api_key = (
            vercel_api_key
            or os.getenv("VERCEL_AI_GATEWAY_API_KEY")
            or os.getenv("AI_GATEWAY_API_KEY")
            or os.getenv("VERCEL_API_KEY")
            or os.getenv("VERCEL_OIDC_TOKEN")
        )
        self.vercel_base_url = (
            vercel_base_url
            or os.getenv("VERCEL_AI_GATEWAY_BASE_URL")
            or "https://ai-gateway.vercel.sh"
        ).rstrip("/")
        self.timeout = timeout

    def decide(
        self,
        state: Union[str, Dict[str, Any], List[Any]],
        questions: Dict[str, Dict[str, Any]],
        provider: Optional[ProviderName] = None,
        model: Optional[str] = None,
        images: Optional[List[str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> DecisionResponse:
        """Execute typed decision evaluation across selected backend.

        Args:
            state: Text, JSON-compatible dict or list representing current application state.
            questions: Dictionary mapping question_id to question spec (noul, choice, or score).
            provider: 'typesafe', 'openrouter', 'cloudflare', or 'vercel'. Defaults to instance setting.
            model: Model identifier override.
            images: Optional images (supported natively by Cloudflare Clef).
            extra_headers: Custom HTTP headers.
        """
        selected_provider = provider or self.default_provider

        if selected_provider == "typesafe":
            return self._call_typesafe(
                state=state,
                questions=questions,
                model=model or "jev-1.13",
                extra_headers=extra_headers,
            )
        elif selected_provider == "openrouter":
            return self._call_openrouter(
                state=state,
                questions=questions,
                model=model or "typesafe/jev-1.13",
                extra_headers=extra_headers,
            )
        elif selected_provider == "cloudflare":
            return self._call_cloudflare(
                state=state,
                questions=questions,
                model=model or "@cf/cloudflare/clef",
                images=images,
                extra_headers=extra_headers,
            )
        elif selected_provider == "vercel":
            return self._call_vercel(
                state=state,
                questions=questions,
                model=model or "convaiinnovations/laya-free",
                extra_headers=extra_headers,
            )
        else:
            raise ValueError(f"Unknown provider '{selected_provider}'. Choose typesafe, openrouter, cloudflare, or vercel.")

    def decide_with_fallback(
        self,
        state: Union[str, Dict[str, Any], List[Any]],
        questions: Dict[str, Dict[str, Any]],
        providers: Optional[List[ProviderName]] = None,
        images: Optional[List[str]] = None,
    ) -> DecisionResponse:
        """Attempt primary provider and automatically fall back on errors."""
        order = providers or ["cloudflare", "vercel", "openrouter", "typesafe"]
        errors = []

        for p in order:
            try:
                return self.decide(state=state, questions=questions, provider=p, images=images)
            except Exception as e:
                errors.append(f"[{p}]: {e}")
                continue

        raise RuntimeError(f"All decision providers failed. Errors: {'; '.join(errors)}")

    # --- Provider Implementations ---

    def _call_typesafe(
        self,
        state: Any,
        questions: Dict[str, Any],
        model: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> DecisionResponse:
        if not self.typesafe_api_key:
            raise ValueError("TYPESAFE_API_KEY is not configured.")

        url = f"{self.typesafe_base_url}/v1/systemone"
        headers = {
            "Authorization": f"Bearer {self.typesafe_api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        payload = {
            "model": model,
            "state": state,
            "questions": questions,
        }

        data = self._http_post(url, headers, payload)
        answers = data.get("answers", {})
        return DecisionResponse(
            provider="typesafe",
            model=data.get("model", model),
            answers=answers,
            raw=data,
            usage=data.get("usage"),
        )

    def _call_openrouter(
        self,
        state: Any,
        questions: Dict[str, Any],
        model: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> DecisionResponse:
        if not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured.")

        url = f"{self.openrouter_base_url}/v1/systemone"
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://typesafe.ai",
            "X-Title": "TypeSafe-Decision-Client",
        }
        if extra_headers:
            headers.update(extra_headers)

        # Normalize model identifier for OpenRouter
        clean_model = model
        if not clean_model.startswith("typesafe/") and not clean_model.startswith("~typesafe/"):
            clean_model = f"typesafe/{clean_model}"

        payload = {
            "model": clean_model,
            "state": state,
            "questions": questions,
        }

        data = self._http_post(url, headers, payload)
        answers = data.get("answers", {})
        return DecisionResponse(
            provider="openrouter",
            model=data.get("model", clean_model),
            answers=answers,
            raw=data,
            usage=data.get("usage"),
        )

    def _call_cloudflare(
        self,
        state: Any,
        questions: Dict[str, Any],
        model: str,
        images: Optional[List[str]] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> DecisionResponse:
        if not self.cloudflare_api_token:
            raise ValueError("CLOUDFLARE_API_TOKEN is not configured.")
        if not self.cloudflare_account_id:
            raise ValueError("CLOUDFLARE_ACCOUNT_ID is not configured.")

        # Normalize Cloudflare model tag and selector
        if "clef-flash" in model.lower():
            model_tag = "@cf/cloudflare/clef-flash"
            model_selector = "clef-flash"
        else:
            model_tag = "@cf/cloudflare/clef"
            model_selector = "clef"

        if self.cloudflare_gateway_id:
            url = f"https://gateway.ai.cloudflare.com/v1/{self.cloudflare_account_id}/{self.cloudflare_gateway_id}/workers-ai/run/{model_tag}"
        else:
            url = f"https://api.cloudflare.com/client/v4/accounts/{self.cloudflare_account_id}/ai/run/{model_tag}"

        headers = {
            "Authorization": f"Bearer {self.cloudflare_api_token}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        payload: Dict[str, Any] = {
            "model": model_selector,
            "state": state,
            "questions": questions,
        }
        if images:
            payload["images"] = images

        data = self._http_post(url, headers, payload)

        # Cloudflare Workers AI returns {"result": {"answers": ...}, "success": true}
        res_payload = data.get("result", data) if isinstance(data, dict) else {}
        answers = res_payload.get("answers", res_payload)

        return DecisionResponse(
            provider="cloudflare",
            model=model_tag,
            answers=answers,
            raw=data,
            usage=data.get("usage"),
        )

    def _call_vercel(
        self,
        state: Any,
        questions: Dict[str, Any],
        model: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> DecisionResponse:
        if not self.vercel_api_key:
            raise ValueError("VERCEL_AI_GATEWAY_API_KEY (or AI_GATEWAY_API_KEY) is not configured.")

        headers = {
            "Authorization": f"Bearer {self.vercel_api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            headers.update(extra_headers)

        # Normalize endpoint selection based on model
        clean_model = model
        if clean_model in ("laya", "laya-free"):
            clean_model = "convaiinnovations/laya-free"

        if clean_model.startswith("typesafe-ai/") or clean_model.startswith("typesafe/"):
            url = f"{self.vercel_base_url}/typesafe/v1/systemone"
            payload = {
                "model": clean_model,
                "state": state,
                "questions": questions,
            }
        else:
            # Map noul to boolean for /v1/evaluate
            mapped_q = {}
            for qid, qspec in questions.items():
                q_copy = dict(qspec)
                if q_copy.get("type") == "noul":
                    q_copy["type"] = "boolean"
                mapped_q[qid] = q_copy
            url = f"{self.vercel_base_url}/v1/evaluate"
            payload = {
                "model": clean_model,
                "state": state,
                "questions": mapped_q,
            }

        data = self._http_post(url, headers, payload)
        answers = data.get("answers", data)
        return DecisionResponse(
            provider="vercel",
            model=data.get("model", clean_model),
            answers=answers,
            raw=data,
            usage=data.get("usage"),
        )

    def _http_post(self, url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8")
            raise RuntimeError(f"HTTP error {e.code} ({e.reason}) calling {url}: {error_body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error calling {url}: {e.reason}") from e
