from __future__ import annotations

import json

from rightsize.client import OpenRouterClient
from rightsize.models import JudgeScore

JUDGE_PROMPT_WITH_EXPECTED = """\
You are evaluating an LLM response. Score from 0.0 to 1.0.

Scoring guide:
- 1.0: Output matches expected (exact match, or semantically equivalent)
- 0.8: Very close but minor differences (extra whitespace, slightly different wording)
- 0.5: Partially correct or addresses the task but differs from expected
- 0.0: Wrong, irrelevant, or fails to follow the requested format

--- PROMPT SENT TO MODEL ---
{prompt}

--- EXPECTED OUTPUT ---
{expected_output}

--- ACTUAL OUTPUT ---
{actual_output}

Return JSON only: {{"score": float, "reasoning": "brief explanation"}}
"""

JUDGE_PROMPT_GENERIC = """\
You are evaluating an LLM response. Score from 0.0 to 1.0.

Scoring guide:
- 1.0: Excellent - accurate, complete, follows requested format
- 0.8: Good - mostly correct with minor issues
- 0.5: Acceptable - partially addresses the task
- 0.0: Poor - wrong, irrelevant, or fails to follow instructions

--- PROMPT SENT TO MODEL ---
{prompt}

--- ACTUAL OUTPUT ---
{actual_output}

Return JSON only: {{"score": float, "reasoning": "brief explanation"}}
"""


async def judge_output(
    client: OpenRouterClient,
    judge_model: str,
    prompt: str,
    expected: str | None,
    actual: str,
) -> JudgeScore:
    if expected is None:
        judge_prompt = JUDGE_PROMPT_GENERIC.format(prompt=prompt, actual_output=actual)
    else:
        judge_prompt = JUDGE_PROMPT_WITH_EXPECTED.format(
            prompt=prompt, expected_output=expected, actual_output=actual
        )
    messages = [{"role": "user", "content": judge_prompt}]
    content, _, _, _ = await client.complete(judge_model, messages, temperature=0.0)
    try:
        payload = json.loads(content)
        score = float(payload.get("score", 0.0))
        reasoning = str(payload.get("reasoning", "")).strip()
    except (ValueError, TypeError, json.JSONDecodeError):
        return JudgeScore(score=0.0, reasoning="Judge response was not valid JSON.")

    score = max(0.0, min(1.0, score))
    return JudgeScore(score=score, reasoning=reasoning)
