"""
Conservative Query Rewriter.
Resolves pronoun anaphora from recent context without injecting hallucinated facts.
"""
from typing import Dict, List


class QueryRewriter:
    def rewrite_query(self, query: str, conversation_history: List[Dict[str, str]]) -> str:
        """
        Conservatively reformulates follow-up queries.
        If the query is already self-contained, returns it unmodified.
        """
        trimmed = query.strip()
        lower = trimmed.lower()

        # If no history exists, return unchanged
        if not conversation_history:
            return trimmed

        # Pronouns or elliptical phrasing that signal a dependent follow-up
        follow_up_cues = ["where are they", "what about their", "how much does it", "where is it", "who are they", "tell me more"]
        is_follow_up = any(lower.startswith(cue) for cue in follow_up_cues) or (len(trimmed.split()) <= 3 and any(p in lower for p in ["it", "they", "them", "their", "that"]))

        if not is_follow_up:
            return trimmed

        # Find the subject in the most recent user turn
        last_user_turn = ""
        for msg in reversed(conversation_history):
            if msg.get("role") == "user":
                last_user_turn = msg.get("content", "")
                break

        if not last_user_turn:
            return trimmed

        # Extract core subject nouns/keywords conservatively
        subject_keywords = [
            w for w in last_user_turn.split()
            if len(w) > 3 and w.lower() not in {"what", "where", "when", "about", "tell", "does", "have", "please", "with"}
        ]
        subject = " ".join(subject_keywords[:3])

        if subject:
            rewritten = f"{subject} {trimmed}"
            return rewritten

        return trimmed


query_rewriter = QueryRewriter()
