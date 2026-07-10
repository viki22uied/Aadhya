"""Chat orchestration: the LLM only relays what these tools return — it
never computes a financial number inline (PRD hard constraint). Each tool
wraps an existing deterministic function from rules.py so there is exactly
one code path per calculation, whether it's reached via a page or via chat.

Two kinds of Aadhya messages exist here, deliberately handled differently:

- Proactive messages (opening sequence, downturn alert) are fully templated
  in Python, no LLM call at all. These carry the PRD's most trust-critical
  behaviors (principle 1's FD-first ordering, principle 6's "never go
  silent") and must not depend on an LLM being reachable or well-behaved —
  see build_greeting().
- Free-text Q&A goes through the LLM with tool-calling, same as before.

Every reply — templated or LLM-generated — is a LIST of short message
bubbles, not one paragraph. This is a hard structural constraint (not just
prompt wording) because the audience this product is built for (PRD F5: ~27%
national financial literacy, plus elderly/short-attention users) fails on
dense paragraphs regardless of whether the content is accurate. See
enforce_brevity() for the LLM side.
"""
import json
import re

from openai import OpenAIError

import llm
from rules import (
    fd_snapshot,
    gold_snapshot,
    compute_allocation,
    rupee_risk_scenario,
    get_loan_offer_for_fd,
    get_chat_progress,
    mark_chat_step_shown,
    sequence_complete,
    get_pending_downturn,
    mark_downturn_shown,
    get_matured_fds,
    propose_fd_ladder,
    approve_fd_ladder,
    mark_ladder_proposed,
    get_goal_progress,
)

DEMO_USER_ID = 1

SYSTEM_PROMPT = (
    "You are Aadhya, a warm wealth advisor inside an Indian bank's app, texting a real "
    "person about their own money.\n\n"
    "Write like you're texting a busy friend, not writing a paragraph. Maximum 2 short "
    "sentences per message. Each sentence: simple subject-verb-object, minimal commas, no "
    "stacked subordinate clauses. If you need to say more than 2 sentences, stop after 2 and "
    "ask if they want more instead of continuing.\n\n"
    "Zero financial jargon (no 'LTV', 'drawdown', 'tenure', 'CAGR' etc). Never explain what a "
    "product generically is (e.g. never say what a fixed deposit is) — the user already has "
    "one, so talk only about their specific numbers.\n\n"
    "Never calculate or estimate any rupee amount, percentage, or rate yourself — always call "
    "a tool to get the real number first. Never guess or make up an id for a fixed deposit — "
    "if you need a specific FD (e.g. 'their second FD'), call get_fd_snapshot first and pick "
    "from the real list, in the order it's returned. If a tool errors, say so honestly in one "
    "short sentence rather than guessing.\n\n"
    "If the user has named goals (check get_goals), talk about holdings by goal name — e.g. "
    "'your emergency cushion' — instead of 'FD #2' or 'your gold', whenever a holding is tagged "
    "to a goal."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_fd_snapshot",
            "description": "Get the user's savings balance and all fixed deposits, including current/maturity value and post-tax real yield.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_loan_offer",
            "description": "Get the max loan-against-FD amount and interest rate range for one specific fixed deposit, by its id.",
            "parameters": {
                "type": "object",
                "properties": {"fixed_deposit_id": {"type": "integer", "description": "The FD's id, from get_fd_snapshot."}},
                "required": ["fixed_deposit_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_allocation",
            "description": "Get the user's recommended portfolio split across FDs/savings, gold ETF, and equity, with reasoning for each.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_risk_scenario",
            "description": "Get the historical 2020-crash worst-case and rebound best-case rupee outcome for a given amount invested in equity.",
            "parameters": {
                "type": "object",
                "properties": {"equity_amount_inr": {"type": "number"}},
                "required": ["equity_amount_inr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ladder_proposal",
            "description": "Get the proposed re-ladder/sweep split for one matured fixed deposit, by its id.",
            "parameters": {
                "type": "object",
                "properties": {"fixed_deposit_id": {"type": "integer"}},
                "required": ["fixed_deposit_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_ladder",
            "description": "Approve the ladder proposal for a matured fixed deposit — actually creates the new FD and debt sweep. Only call this if the user has clearly said yes/approve/go ahead.",
            "parameters": {
                "type": "object",
                "properties": {"fixed_deposit_id": {"type": "integer"}},
                "required": ["fixed_deposit_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_goals",
            "description": "Get the user's named goals (e.g. 'emergency cushion', 'child's education') with the real current value of holdings tagged to each.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

# Tools that surface market-linked (equity) content — gated behind the
# FD-first sequence per PRD principle 1 ("never open with a market-linked
# product"). Enforced here in code, not left to the LLM's judgment.
GATED_TOOLS = {"get_allocation", "get_risk_scenario"}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_MAX_COMMAS_PER_SENTENCE = 2


def _shorten_comma_heavy(sentence: str) -> tuple[str, bool]:
    """A single grammatical sentence can still be a wall of stacked clauses
    (no period, just commas all the way down) — this is the exact "what is a
    fixed deposit" explainer-paragraph failure mode. Cut it down to its first
    couple of clauses rather than passing the whole run-on through."""
    if sentence.count(",") <= _MAX_COMMAS_PER_SENTENCE:
        return sentence, False
    clauses = sentence.split(",")
    shortened = ",".join(clauses[: _MAX_COMMAS_PER_SENTENCE + 1]).strip()
    if not shortened.endswith((".", "!", "?")):
        shortened += "."
    return shortened, True


def enforce_brevity(text: str, max_sentences: int = 2) -> list[str]:
    """Hard post-processing cap, not just prompt compliance — the model
    won't always follow the length instruction, so this guarantees the
    structural constraint regardless. Splits on sentence boundaries, keeps
    at most `max_sentences`, shortens any single comma-stacked run-on
    sentence, and appends a short opt-in offer if anything was cut rather
    than silently truncating content."""
    if not text:
        return []
    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]

    truncated = len(sentences) > max_sentences
    kept = []
    for sentence in sentences[:max_sentences]:
        shortened, was_cut = _shorten_comma_heavy(sentence)
        kept.append(shortened)
        truncated = truncated or was_cut

    if truncated:
        kept.append("Want me to say more?")
    return kept


def _call_tool(name: str, args: dict, user_id: int) -> dict:
    if name in GATED_TOOLS and not sequence_complete(user_id):
        return {
            "blocked": True,
            "reason": (
                "The FD and gold walkthrough isn't finished yet for this user — "
                "acknowledge their question in one short sentence, then redirect them to "
                "finish that first. Do not answer with equity/allocation numbers."
            ),
        }
    if name == "get_fd_snapshot":
        return fd_snapshot(user_id)
    if name == "get_loan_offer":
        return get_loan_offer_for_fd(args["fixed_deposit_id"])
    if name == "get_allocation":
        return compute_allocation(user_id)
    if name == "get_risk_scenario":
        return rupee_risk_scenario(args["equity_amount_inr"])
    if name == "get_ladder_proposal":
        return propose_fd_ladder(args["fixed_deposit_id"])
    if name == "approve_ladder":
        return approve_fd_ladder(user_id, args["fixed_deposit_id"])
    if name == "get_goals":
        return {"goals": get_goal_progress(user_id)}
    raise ValueError(f"unknown tool {name}")


def run_chat(history: list[dict], user_id: int = DEMO_USER_ID) -> dict:
    """Runs one user turn through the tool-calling loop. `history` is a list
    of {role, content} dicts (no system prompt — added here). Returns
    {reply, tool_calls} where `reply` is a list of short message bubbles
    (see enforce_brevity) and tool_calls is the raw list of (name, args,
    result) actually executed, so the frontend can render structured cards
    inline instead of just text."""
    progress = get_chat_progress(user_id)
    progress_note = (
        f"Sequencing state for this user — FD/savings shown: {progress['fd_shown']}, "
        f"post-tax reality shown: {progress['post_tax_shown']}, gold ETF intro shown: "
        f"{progress['gold_shown']}. If any are False and the user asks about equity, "
        "allocation, or risk, redirect them in 1 short sentence to finish those first — "
        "don't call get_allocation or get_risk_scenario yet."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": progress_note},
        *history,
    ]
    executed_tool_calls = []

    try:
        response = llm.chat(messages, tools=TOOLS)
    except OpenAIError as e:
        return {"reply": None, "tool_calls": [], "error": "llm_unavailable", "detail": str(e)}

    message = response.choices[0].message

    while message.tool_calls:
        messages.append(message.model_dump(exclude_unset=True))
        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments or "{}")
            try:
                result = _call_tool(tool_call.function.name, args, user_id)
            except ValueError as e:
                result = {"error": str(e)}
            executed_tool_calls.append({"name": tool_call.function.name, "args": args, "result": result})
            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)}
            )
        try:
            response = llm.chat(messages, tools=TOOLS)
        except OpenAIError as e:
            return {
                "reply": None,
                "tool_calls": executed_tool_calls,
                "error": "llm_unavailable",
                "detail": str(e),
            }
        message = response.choices[0].message

    return {"reply": enforce_brevity(message.content), "tool_calls": executed_tool_calls, "error": None}


def build_greeting(user_id: int = DEMO_USER_ID) -> dict:
    """Deterministic, no LLM call. Decides what Aadhya proactively leads
    with when a chat session opens: a pending downturn alert (highest
    priority — PRD principle 6, never go silent), then the FD-first
    sequence (A1 -> A2 -> A3, principle 1), then a plain ready-to-chat
    greeting once all of that has been shown. Every reply is a list of
    short bubbles — numbers live in the inline data card, not the prose."""
    downturn = get_pending_downturn(user_id)
    if downturn is not None:
        mark_downturn_shown(downturn["id"])
        before = f"₹{downturn['equity_amount_before']:,.0f}"
        after = f"₹{downturn['equity_amount_after']:,.0f}"
        reply = [
            "I need to tell you something first.",
            f"Your equity dropped from {before} to {after}.",
            "This looks like the 2020 crash.",
            "Markets recovered in about 10 months back then.",
            "That's history, not a promise for this time.",
            "People who stayed invested usually did better than people who panic-sold.",
            "Want to talk it through?",
        ]
        return {
            "reply": reply,
            "tool_calls": [
                {
                    "name": "get_risk_scenario",
                    "result": {
                        "equity_amount_before": downturn["equity_amount_before"],
                        "equity_amount_after": downturn["equity_amount_after"],
                        "drawdown_percent": downturn["drawdown_percent"],
                    },
                }
            ],
            "stage": "downturn",
        }

    matured = get_matured_fds(user_id)
    unproposed = [fd for fd in matured if not fd["ladder_proposed"]]
    if unproposed:
        fd = unproposed[0]
        mark_ladder_proposed(fd["id"])
        proposal = propose_fd_ladder(fd["id"])
        reply = [
            "One of your FDs just matured.",
            f"I'd put ₹{proposal['ladder_amount']:,.0f} into a new FD and move ₹{proposal['sweep_amount']:,.0f} "
            "to something steadier.",
            "One tap and it's done — want me to go ahead?",
        ]
        return {
            "reply": reply,
            "tool_calls": [{"name": "get_ladder_proposal", "result": proposal}],
            "stage": "ladder_proposal",
        }

    progress = get_chat_progress(user_id)

    if not progress["fd_shown"]:
        snapshot = fd_snapshot(user_id)
        mark_chat_step_shown(user_id, "fd_shown")
        reply = ["Hi, I'm Aadhya.", "Let me show you what you already have."]
        return {"reply": reply, "tool_calls": [{"name": "get_fd_snapshot", "result": snapshot}], "stage": "fd_intro"}

    if not progress["post_tax_shown"]:
        snapshot = fd_snapshot(user_id)
        mark_chat_step_shown(user_id, "post_tax_shown")
        reply = ["Tax and inflation quietly eat into your FDs.", "I checked the real numbers below."]
        return {"reply": reply, "tool_calls": [{"name": "get_fd_snapshot", "result": snapshot}], "stage": "post_tax_intro"}

    if not progress["gold_shown"]:
        snapshot = gold_snapshot(user_id)
        mark_chat_step_shown(user_id, "gold_shown")
        reply = ["Want a small next step?", "Try gold, ₹10 to ₹100 at a time."]
        return {"reply": reply, "tool_calls": [{"name": "get_gold_snapshot", "result": snapshot}], "stage": "gold_intro"}

    return {
        "reply": ["Good to see you again.", "Ask me about your FDs, gold, or allocation."],
        "tool_calls": [],
        "stage": "ready",
    }
