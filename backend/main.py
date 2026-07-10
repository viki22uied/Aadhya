import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db import get_conn
from rules import (
    fd_snapshot,
    gold_snapshot,
    buy_gold_etf_round_up,
    draw_loan_against_fd,
    compute_allocation,
    get_loan_offer_for_fd,
    trigger_downturn,
    reset_chat_progress,
    approve_fd_ladder,
    build_allocation_share_text,
    build_loan_offer_share_text,
    build_gold_share_text,
    get_gold_milestones,
    create_goal,
    assign_fd_to_goal,
    assign_gold_to_goal,
    get_goal_progress,
    add_to_savings,
)
from seed import seed
from translate_hindi import translate_to_hindi, TranslateUnavailable
from chat import run_chat, build_greeting

app = FastAPI(title="Aadhya API")

# CORS_ORIGINS: comma-separated list of allowed origins (set the deployed
# frontend's URL here on Render). Defaults to localhost for local dev.
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

seed()

DEMO_USER_ID = 1  # ponytail: stub auth per PRD — single demo user until real login exists


@app.get("/health")
def health():
    conn = get_conn()
    conn.execute("SELECT 1")
    conn.close()
    return {"status": "ok"}


@app.get("/me/fd-snapshot")
def get_fd_snapshot():
    return fd_snapshot(DEMO_USER_ID)


class GoldPurchase(BaseModel):
    amount_inr: float = Field(gt=0, le=100)  # PRD A3: ₹10-100 micro-SIP ticket size


@app.get("/me/gold-snapshot")
def get_gold_snapshot():
    return gold_snapshot(DEMO_USER_ID)


@app.post("/me/gold-snapshot/purchase")
def purchase_gold(purchase: GoldPurchase):
    return buy_gold_etf_round_up(DEMO_USER_ID, purchase.amount_inr)


class LoanDraw(BaseModel):
    amount_inr: float = Field(gt=0)


@app.get("/me/fd/{fd_id}/loan-offer")
def loan_offer(fd_id: int):
    """Read-only preview for the interactive draw-amount slider — recomputes
    live as the user drags, no draw recorded."""
    try:
        return get_loan_offer_for_fd(fd_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/me/fd/{fd_id}/loan-draw")
def loan_draw(fd_id: int, draw: LoanDraw):
    try:
        return draw_loan_against_fd(fd_id, draw.amount_inr)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/me/allocation")
def get_allocation():
    return compute_allocation(DEMO_USER_ID)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: list[ChatMessage]


@app.post("/chat")
def chat(request: ChatRequest):
    return run_chat([m.model_dump() for m in request.history])


@app.get("/chat/greeting")
def chat_greeting():
    """Deterministic, no LLM call — decides what Aadhya proactively opens
    with (downturn alert, next step of the FD-first sequence, or a plain
    greeting once that's all done)."""
    return build_greeting()


@app.post("/demo/trigger-downturn")
def demo_trigger_downturn():
    """Demo control only: simulates the user's equity allocation dropping by
    the real 2020 Nifty 50 drawdown. The next chat greeting will lead with it."""
    return trigger_downturn(DEMO_USER_ID)


@app.post("/demo/reset-chat")
def demo_reset_chat():
    """Demo control only: replays the FD-first sequence from scratch."""
    reset_chat_progress(DEMO_USER_ID)
    return {"reset": True}


@app.post("/demo/mature-fd/{fd_id}")
def demo_mature_fd(fd_id: int):
    """Demo control only: forces one FD's maturity date to today so B2's
    ladder-autopilot proposal can be shown without waiting or reseeding."""
    conn = get_conn()
    conn.execute("UPDATE fixed_deposits SET maturity_date = date('now') WHERE id = ?", (fd_id,))
    conn.commit()
    conn.close()
    return {"matured": True, "fixed_deposit_id": fd_id}


@app.post("/me/fd/{fd_id}/approve-ladder")
def approve_ladder(fd_id: int):
    try:
        return approve_fd_ladder(DEMO_USER_ID, fd_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/me/share/allocation")
def share_allocation():
    return {"text": build_allocation_share_text(DEMO_USER_ID)}


@app.get("/me/share/loan-offer/{fd_id}")
def share_loan_offer(fd_id: int):
    try:
        return {"text": build_loan_offer_share_text(fd_id)}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/me/share/gold")
def share_gold():
    return {"text": build_gold_share_text(DEMO_USER_ID)}


@app.get("/me/gold-milestones")
def gold_milestones():
    return get_gold_milestones(DEMO_USER_ID)


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@app.get("/me/goals")
def goals():
    return get_goal_progress(DEMO_USER_ID)


@app.post("/me/goals")
def create_goal_endpoint(goal: GoalCreate):
    return create_goal(DEMO_USER_ID, goal.name)


class GoalAssign(BaseModel):
    goal_id: int


@app.post("/me/fd/{fd_id}/assign-goal")
def assign_fd_goal_endpoint(fd_id: int, assign: GoalAssign):
    try:
        assign_fd_to_goal(fd_id, assign.goal_id)
        return {"assigned": True}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/me/gold/assign-goal")
def assign_gold_goal_endpoint(assign: GoalAssign):
    assign_gold_to_goal(DEMO_USER_ID, assign.goal_id)
    return {"assigned": True}


class TranslateRequest(BaseModel):
    texts: list[str]


@app.post("/translate/hindi")
def translate_hindi_endpoint(request: TranslateRequest):
    """A4: Hindi translation via Google Translate's free public endpoint —
    no key needed, no local model (see translate_hindi.py for the tradeoff).
    Honest failure like the LLM chat path: reports unreachable rather than
    silently returning English."""
    try:
        return {"translated": [translate_to_hindi(t) for t in request.texts], "error": None}
    except TranslateUnavailable as e:
        return {"translated": None, "error": "unreachable", "detail": str(e)}


class SavingsTopUp(BaseModel):
    amount_inr: float = Field(gt=0)


@app.post("/demo/add-savings")
def demo_add_savings(topup: SavingsTopUp):
    """Demo control only: lets judges top up the savings balance on demand."""
    return {"balance": add_to_savings(DEMO_USER_ID, topup.amount_inr)}
