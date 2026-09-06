"""
Hallucination Verifier and Grounding Confidence Evaluator.
Assesses whether the response is GROUNDED, PARTIALLY_GROUNDED, or INSUFFICIENT_EVIDENCE.
"""
from typing import List, Literal
from backend.app.schemas.chat import SourceCitation

ConfidenceLevel = Literal["grounded", "partially_grounded", "insufficient_evidence"]

SAFE_REFUSAL_TRIGGERS = [
    "i don't have enough verified information",
    "i do not have enough verified information",
    "not enough verified information",
    "cannot find verified information",
    "information is unavailable in the approved knowledge base",
]


class HallucinationVerifier:
    def verify_response(
        self,
        answer: str,
        citations: List[SourceCitation],
        has_retrieved_context: bool
    ) -> ConfidenceLevel:
        """
        Evaluates grounding confidence.
        """
        lower_answer = answer.lower()

        # Check if response explicitly acknowledges lack of evidence
        for trigger in SAFE_REFUSAL_TRIGGERS:
            if trigger in lower_answer:
                return "insufficient_evidence"

        # If answer was generated without any retrieved context or citations
        if not has_retrieved_context or len(citations) == 0:
            # Greetings or general polite exchanges
            if len(answer.split()) < 20 and any(g in lower_answer for g in ["hello", "hi", "how can i help", "welcome"]):
                return "grounded"
            return "insufficient_evidence"

        # Check if citations brackets are present in the answer
        has_citation_bracket = any(f"[{c.id}]" in answer for c in citations)
        if has_citation_bracket:
            return "grounded"

        return "partially_grounded"


hallucination_verifier = HallucinationVerifier()
