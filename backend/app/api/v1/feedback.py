"""
User Feedback API Endpoint.
Captures user ratings (thumbs up/down) and qualitative remarks for RAG and model evaluations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.api.deps import get_session_context
from backend.app.db.models import Feedback, Message, Session
from backend.app.db.session import get_db
from backend.app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    payload: FeedbackRequest,
    session: Session = Depends(get_session_context),
    db: AsyncSession = Depends(get_db)
) -> FeedbackResponse:
    # Verify message exists
    msg_res = await db.execute(select(Message).where(Message.id == payload.message_id))
    msg = msg_res.scalars().first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    # Check if feedback already recorded
    existing_res = await db.execute(select(Feedback).where(Feedback.message_id == payload.message_id))
    fb = existing_res.scalars().first()

    if fb:
        fb.rating = payload.rating
        fb.comment = payload.comment
    else:
        fb = Feedback(
            message_id=payload.message_id,
            rating=payload.rating,
            comment=payload.comment
        )
        db.add(fb)

    await db.commit()
    await db.refresh(fb)

    return FeedbackResponse(
        success=True,
        feedback_id=fb.id,
        message="Thank you for your feedback."
    )
