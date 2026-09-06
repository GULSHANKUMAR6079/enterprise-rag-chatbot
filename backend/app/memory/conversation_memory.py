"""
Bounded Conversation Memory and Session Pruning.
Maintains recent conversational context within strict token budgets.
"""
from typing import Dict, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.db.models import Message


class ConversationMemoryManager:
    def __init__(self, max_history_turns: int = 5, max_history_tokens: int = 800):
        self.max_history_turns = max_history_turns
        self.max_history_tokens = max_history_tokens

    def estimate_tokens(self, text: str) -> int:
        return max(1, int(len(text) / 3.8))

    async def get_recent_history(
        self,
        conversation_id: str,
        db: AsyncSession
    ) -> List[Dict[str, str]]:
        """
        Retrieves the most recent messages for a conversation, bounded by turns and token budget.
        """
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(self.max_history_turns * 2)
        )
        result = await db.execute(query)
        recent_messages = list(result.scalars().all())

        # Reverse to chronological order
        recent_messages.reverse()

        bounded_history: List[Dict[str, str]] = []
        accumulated_tokens = 0

        # Scan backwards to fit the most recent turns within token budget
        for msg in reversed(recent_messages):
            tokens = self.estimate_tokens(msg.content)
            if accumulated_tokens + tokens > self.max_history_tokens:
                break
            bounded_history.insert(0, {"role": msg.role, "content": msg.content})
            accumulated_tokens += tokens

        return bounded_history


memory_manager = ConversationMemoryManager()
