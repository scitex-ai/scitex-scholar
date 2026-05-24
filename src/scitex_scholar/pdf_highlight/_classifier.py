"""LLM and offline classifiers for the semantic highlighter."""

from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Optional

# Namespaced so Scholar never silently consumes an ambient ANTHROPIC_API_KEY
# ("surprise use"); the key must be set explicitly under the SciTeX Scholar
# namespace. Mirrors the SCITEX_*/SAC_* convention used across the ecosystem.
API_KEY_ENV = "SCITEX_SCHOLAR_ANTHROPIC_API_KEY"

from ._blocks import Block
from ._colors import CATEGORIES

CLASSIFIER_SYSTEM = """You tag sentences from an academic paper into at most one of these rhetorical categories. Be highly selective: the goal is a reader's highlighter, not a coverage map. The strong default is "none". Most sentences — usually the large majority — are "none". Only mark a sentence if a busy expert skimming the paper would deliberately underline it. When in doubt, "none".

Categories (use these exact strings):
  focal_claim            — a HEADLINE finding, result, or interpretation of THIS paper: something
                           novel, surprising, or central to its conclusions. First-person stance
                           markers ("we show/find/demonstrate/establish", "our results",
                           "these data indicate") plus a substantive result are strong signals.
                           Mark the sentence that STATES the finding, not every sentence that
                           restates or elaborates it. One claim per distinct finding — do not
                           highlight a result and its three follow-up sentences.
                           NOT routine or secondary numbers; NOT setup or transitions.
  focal_method           — ONLY the one or few sentences that name THIS paper's core methodological
                           CONTRIBUTION (the novel model/algorithm/design that makes the paper new).
                           This is rare — typically a handful per paper. Routine procedure,
                           parameter settings, software used, cohort logistics, and standard
                           analysis steps are "none", even when phrased in the first person.
                           If you are tempted to mark many method sentences, mark none of them.
  focal_limitation       — a self-admitted limitation, caveat, confound, or threat to validity of
                           THIS paper's own work.
  related_supportive     — a specific prior/other paper whose finding SUPPORTS this paper's position
                           ("consistent with X (2019)", "as shown by Y", "corroborates").
  related_contradictive  — a specific prior/other paper whose finding CONTRADICTS this paper
                           ("in contrast to X", "unlike Y", "disagrees with").
  none                   — everything else: background, setup, transitions, routine procedure,
                           reference entries, headers, figure/table prose, boilerplate. THE DEFAULT.

Priority order when a sentence could fit two labels: focal_claim > focal_limitation >
related_* > focal_method. If a sentence both describes a method and reports what it yielded,
prefer focal_claim. If it mentions prior work without taking a supportive or contradictive
stance, return "none".

Confidence in [0,1], honestly calibrated: reserve >0.85 for unambiguous, textbook-clear cases;
0.5-0.7 means "plausible but arguable" — and for anything you would rate below ~0.6, prefer
"none" outright. Do not inflate confidence to justify a label.

Respond with ONLY a JSON array of objects: {"id": int, "category": str, "confidence": float}. Include every input id exactly once."""


def _extract_text_from_message(msg: Any) -> str:
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""


def _strip_code_fence(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return raw


def _available_models(client: Any) -> list[str]:
    """Best-effort list of model IDs the account can call. Empty on failure."""
    try:
        return [m.id for m in client.models.list()]
    except Exception:
        return []


def _model_not_found_error(model: str, client: Any) -> RuntimeError:
    """Build a helpful error that hints the available model IDs."""
    models = _available_models(client)
    if models:
        hint = "available models:\n  " + "\n  ".join(models)
    else:
        hint = "could not retrieve the list of available models"
    return RuntimeError(f"unknown model: {model!r}\n{hint}")


def _retry_wait_seconds(exc: Any, attempt: int, base: float, cap: float) -> float:
    """Seconds to wait before the next retry.

    Prefers the server's ``Retry-After`` header; otherwise uses exponential
    backoff (``base * 2**attempt``, capped) with full jitter so concurrent
    callers don't retry in lockstep.
    """
    try:
        retry_after = exc.response.headers.get("retry-after")
        if retry_after is not None:
            return max(0.0, float(retry_after))
    except (AttributeError, TypeError, ValueError):
        pass
    ceiling = min(cap, base * (2**attempt))
    return ceiling * (0.5 + random.random() * 0.5)


def _classify_one_batch(
    client: Any,
    anthropic: Any,
    model: str,
    batch: list[Block],
    retryable: tuple,
    max_retries: int,
    backoff_base: float,
    backoff_cap: float,
    info: Any,
) -> Optional[Any]:
    """Call the API for one batch, retrying transient errors with backoff.

    Returns the message on success, or ``None`` if it stays unrecoverable
    after ``max_retries``. Raises for non-retryable errors (bad model, other
    4xx) so the whole run aborts on those.
    """
    payload = [{"id": b.id, "text": b.text} for b in batch]
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(
                model=model,
                max_tokens=2048,  # stx-allow: STX-NL001
                system=CLASSIFIER_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Classify these {len(batch)} units:\n\n"
                            f"{json.dumps(payload, ensure_ascii=False)}"
                        ),
                    }
                ],
            )
        except anthropic.NotFoundError as exc:
            raise _model_not_found_error(model, client) from exc
        except retryable as exc:
            if attempt >= max_retries:
                return None
            wait = _retry_wait_seconds(exc, attempt, backoff_base, backoff_cap)
            kind = (
                "rate limited"
                if isinstance(exc, anthropic.RateLimitError)
                else "transient API error"
            )
            info(
                f"      {kind}; waiting {wait:.0f}s then retrying "
                f"(attempt {attempt + 1}/{max_retries})"
            )
            time.sleep(wait)
        except anthropic.APIStatusError as exc:
            raise RuntimeError(
                f"Anthropic API error (HTTP {exc.status_code}): {exc.message}"
            ) from exc
    return None


def _apply_predictions(batch: list[Block], raw: str) -> None:
    """Parse the model's JSON reply and write categories onto ``batch``."""
    preds = json.loads(_strip_code_fence(raw))
    by_id = {b.id: b for b in batch}
    for p in preds:
        b = by_id.get(p.get("id"))
        if b is None:
            continue
        cat = p.get("category", "none")
        if cat in CATEGORIES:
            b.category = cat
            b.confidence = float(p.get("confidence", 0.0))


def classify_llm(
    blocks: list[Block],
    model: str,
    batch_size: int = 25,
    on_warning: Optional[Any] = None,
    on_info: Optional[Any] = None,
    max_retries: int = 8,
    backoff_base: float = 2.0,
    backoff_cap: float = 60.0,
    concurrency: int = 4,
) -> None:
    """Classify blocks in-place by calling the Anthropic Messages API.

    Batches are sent concurrently (up to ``concurrency`` in flight) to cut
    wall-clock time, while each batch independently retries rate-limit (429)
    and transient server/connection errors with exponential backoff that
    honors any ``Retry-After`` header. A batch that stays unrecoverable is
    skipped (its units stay unclassified) so the run still produces a partial
    result. Per-batch progress is reported via ``on_info``.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor, as_completed

    import anthropic

    info = on_info or (lambda _msg: None)
    warn = on_warning or (lambda _msg: None)
    api_key = os.environ.get(API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"{API_KEY_ENV} is not set. Scholar uses a namespaced key and "
            "does not read the ambient ANTHROPIC_API_KEY. Export "
            f"{API_KEY_ENV}, or run with --stub for an offline pass."
        )
    # Pass the key explicitly (never let the SDK pick up ANTHROPIC_API_KEY).
    # We drive retries ourselves for visibility, so disable the SDK's own
    # silent retry loop. The client is thread-safe for concurrent requests.
    client = anthropic.Anthropic(api_key=api_key, max_retries=0)
    retryable = (
        anthropic.RateLimitError,
        anthropic.APIConnectionError,
        anthropic.InternalServerError,
    )

    batches = [
        blocks[start : start + batch_size]
        for start in range(0, len(blocks), batch_size)
    ]
    total = len(batches)
    if total == 0:
        return
    workers = max(1, min(concurrency, total))
    info(
        f"      {len(blocks)} units in {total} batches "
        f"({workers} concurrent request{'s' if workers > 1 else ''})"
    )

    lock = threading.Lock()
    counters = {"done": 0, "failed_units": 0}

    def _run(batch: list[Block]) -> None:
        msg = _classify_one_batch(
            client,
            anthropic,
            model,
            batch,
            retryable,
            max_retries,
            backoff_base,
            backoff_cap,
            info,
        )
        failed = False
        if msg is None:
            failed = True
            warn(
                f"a batch was skipped after {max_retries} retries "
                f"(rate limit / transient error); {len(batch)} units stay "
                "unclassified"
            )
        else:
            try:
                _apply_predictions(batch, _extract_text_from_message(msg))
            except json.JSONDecodeError as exc:
                failed = True
                warn(f"parse failure in a batch: {exc}")
        with lock:
            counters["done"] += 1
            if failed:
                counters["failed_units"] += len(batch)
            info(f"      classified {counters['done']}/{total} batches")

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_run, batch) for batch in batches]
        for fut in as_completed(futures):
            # Re-raise non-retryable errors (e.g. unknown model) on the main
            # thread so the run aborts with a clear message.
            fut.result()

    if counters["failed_units"]:
        warn(
            f"{counters['failed_units']}/{len(blocks)} units could not be "
            "classified (left unhighlighted). Re-run later or use --stub."
        )


def classify_stub(blocks: list[Block]) -> None:
    """Offline keyword heuristic. No API calls. Useful for smoke tests."""
    rules = [
        (
            "focal_limitation",
            ("limitation", "caveat", "however, our", "we did not", "a threat to"),
        ),
        (
            "focal_method",
            ("we propose", "we introduce", "our method", "our approach", "we develop"),
        ),
        (
            "focal_claim",
            (
                "we show",
                "we find",
                "we demonstrate",
                "we suggest",
                "we clarify",
                "we establish",
                "our results",
                "we report",
                "this finding",
            ),
        ),
        (
            "related_contradictive",
            ("in contrast", "unlike", "disagree", "contrary to", "fails to"),
        ),
        (
            "related_supportive",
            (
                "consistent with",
                "in line with",
                "as shown by",
                "supports",
                "corroborat",
            ),
        ),
    ]
    for b in blocks:
        low = b.text.lower()
        for cat, needles in rules:
            if any(n in low for n in needles):
                b.category = cat
                b.confidence = 0.5
                break
