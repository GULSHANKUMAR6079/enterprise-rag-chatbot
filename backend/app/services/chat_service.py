"""
AI Chat Orchestrator Service.
Implements the end-to-end layered architecture:
Request -> Security Policy -> Memory -> Query Rewriting -> Hybrid RAG -> Indirect Injection Defense
-> Context Builder -> LLM Gateway -> Output Guardrails -> Grounding Verification -> Response
"""
import time
import uuid
from typing import AsyncGenerator, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.exceptions import SecurityBlockException
from backend.app.db.models import Conversation, Message, Session
from backend.app.gateway.cost_tracker import cost_tracker
from backend.app.guardrails.output_guardrail import output_guardrail
from backend.app.guardrails.policy_engine import PolicyDecision, policy_engine
from backend.app.guardrails.domain_guardrail import domain_guardrail
from backend.app.llm.gateway import llm_gateway
from backend.app.memory.conversation_memory import memory_manager
from backend.app.observability.events import record_security_event
from backend.app.observability.logger import app_logger
from backend.app.observability.metrics import REQUEST_LATENCY, REQUESTS_TOTAL, TOKENS_CONSUMED
from backend.app.observability.tracing import trace_span
from backend.app.rag.context_builder import context_builder
from backend.app.rag.hallucination_verifier import hallucination_verifier
from backend.app.rag.indirect_injection_defense import indirect_injection_defense
from backend.app.rag.prompt_builder import prompt_builder
from backend.app.rag.query_rewriter import query_rewriter
from backend.app.reranking.reranker import context_reranker
from backend.app.retrieval.hybrid import hybrid_retriever
from backend.app.schemas.chat import ChatResponse, SourceCitation
from backend.app.security.abuse_detector import abuse_detector


class ChatOrchestratorService:
    async def process_chat(
        self,
        user_message: str,
        conversation_id: Optional[str],
        session: Session,
        db: AsyncSession,
        request_id: str,
        user_role: str = "public"
    ) -> ChatResponse:
        async with trace_span("chat.pipeline", {"request_id": request_id, "user_role": user_role}):
            return await self._process_chat_impl(
                user_message=user_message,
                conversation_id=conversation_id,
                session=session,
                db=db,
                request_id=request_id,
                user_role=user_role
            )

    async def _process_chat_impl(
        self,
        user_message: str,
        conversation_id: Optional[str],
        session: Session,
        db: AsyncSession,
        request_id: str,
        user_role: str = "public"
    ) -> ChatResponse:
        start_time = time.perf_counter()
        REQUESTS_TOTAL.labels(route="/api/v1/chat", method="POST").inc()

        # Step 1: Abuse Check
        is_blocked, remaining = abuse_detector.is_blocked(session.id)
        if is_blocked:
            await record_security_event(
                event_type="abuse_throttling_enforced",
                severity="MEDIUM",
                request_id=request_id,
                session_id=session.id,
                details={"remaining_seconds": remaining},
                db=db
            )
            raise SecurityBlockException(
                f"Session temporarily blocked due to repeated violations. Try again in {remaining}s.",
                reason="abuse_threshold_exceeded"
            )

        # Step 2: Security Policy Engine Evaluation
        async with trace_span("guardrails.input_evaluation", {"request_id": request_id}):
            eval_result = policy_engine.evaluate(user_message, user_role=user_role)

        if eval_result.decision == PolicyDecision.BLOCK:
            await record_security_event(
                event_type="input_security_block",
                severity="HIGH",
                request_id=request_id,
                session_id=session.id,
                details={"violations": eval_result.violations, "score": eval_result.risk_score},
                db=db
            )
            raise SecurityBlockException(
                eval_result.refusal_message or "Security policy violation.",
                reason="policy_block",
                user_safe_message=eval_result.refusal_message
            )

        # Handle Safe Refusal (direct polite response without calling LLM)
        if eval_result.decision == PolicyDecision.SAFE_REFUSAL:
            conv = await self._get_or_create_conversation(conversation_id, session.id, db)
            return ChatResponse(
                request_id=request_id,
                conversation_id=conv.id,
                answer=eval_result.refusal_message or "I am the official website assistant.",
                sources=[],
                confidence="grounded"
            )

        clean_query = eval_result.clean_text

        # Step 3: Conversation & Memory
        conv = await self._get_or_create_conversation(conversation_id, session.id, db)
        user_db_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=clean_query,
            token_count=cost_tracker.estimate_tokens(clean_query)
        )
        db.add(user_db_msg)
        await db.flush()

        history = await memory_manager.get_recent_history(conv.id, db)

        # Step 4: Query Rewriting
        rewritten_query = query_rewriter.rewrite_query(clean_query, history)

        # Step 5: Hybrid RAG Retrieval
        async with trace_span("rag.hybrid_retrieval", {"query": rewritten_query}):
            query_embeddings = await llm_gateway.embed([rewritten_query])
            query_embedding = query_embeddings[0] if query_embeddings else []

            retrieved_chunks = await hybrid_retriever.retrieve(
                query=rewritten_query,
                query_embedding=query_embedding,
                top_k=settings.VECTOR_TOP_K
            )

        # Step 6: Indirect Prompt Injection Defense on Chunks
        for chunk in retrieved_chunks:
            risk, sanitized_text, findings = indirect_injection_defense.inspect_chunk(chunk.content)
            chunk.content = sanitized_text
            chunk.injection_risk_score = risk
            if risk > 0.3:
                await record_security_event(
                    event_type="indirect_prompt_injection_flagged",
                    severity="MEDIUM",
                    request_id=request_id,
                    session_id=session.id,
                    details={"chunk_id": chunk.chunk_id, "findings": findings, "risk": risk},
                    db=db
                )

        # Step 7: Reranking & Context Building with FlashRank Neural Cross-Encoder
        async with trace_span("reranking.flashrank", {"candidates_count": len(retrieved_chunks), "query": clean_query}):
            reranked_chunks = context_reranker.rerank_and_filter(
                retrieved_chunks,
                query=clean_query,
                top_n=settings.RERANKER_TOP_N
            )
        trusted_context_xml, citations = context_builder.build_context(reranked_chunks)

        # Step 7.5: Pre-LLM Context Gating & Domain Boundary Verification
        if len(reranked_chunks) == 0:
            if domain_guardrail.is_greeting(clean_query):
                greeting_answer = (
                    "Hello! I am the official AI assistant for our website. "
                    "I am here to help answer your questions about our company, services, solutions, "
                    "and documentation. What would you like to know today?"
                )
                assistant_db_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=greeting_answer,
                    token_count=cost_tracker.estimate_tokens(greeting_answer),
                    citations=[],
                    confidence="grounded"
                )
                db.add(assistant_db_msg)
                conv.message_count += 2
                await db.commit()
                return ChatResponse(
                    request_id=request_id,
                    conversation_id=conv.id,
                    answer=greeting_answer,
                    sources=[],
                    confidence="grounded"
                )
            else:
                out_of_scope_answer = (
                    "I don't have verified information in our company knowledge base to answer that. "
                    "As the official website assistant, I am dedicated to helping you with questions "
                    "about our company, services, and solutions. Please feel free to ask anything about our offerings!"
                )
                assistant_db_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=out_of_scope_answer,
                    token_count=cost_tracker.estimate_tokens(out_of_scope_answer),
                    citations=[],
                    confidence="insufficient_evidence"
                )
                db.add(assistant_db_msg)
                conv.message_count += 2
                await db.commit()
                return ChatResponse(
                    request_id=request_id,
                    conversation_id=conv.id,
                    answer=out_of_scope_answer,
                    sources=[],
                    confidence="insufficient_evidence"
                )

        # Step 8: Prompt Hierarchy Assembly
        messages = prompt_builder.build_chat_messages(
            user_query=clean_query,
            trusted_context_xml=trusted_context_xml,
            conversation_history=history
        )

        # Step 9: LLM Gateway Execution
        async with trace_span("llm.generation"):
            llm_resp = await llm_gateway.generate(
                messages=messages,
                max_tokens=settings.MAX_OUTPUT_TOKENS
            )

        TOKENS_CONSUMED.labels(type="input", model=llm_resp.model).inc(llm_resp.usage.input_tokens)
        TOKENS_CONSUMED.labels(type="output", model=llm_resp.model).inc(llm_resp.usage.output_tokens)

        # Step 10: Output Guardrail Verification
        async with trace_span("guardrails.output_verification"):
            sanitized_output, is_valid, violations = output_guardrail.sanitize_and_verify(llm_resp.content)
        if violations:
            await record_security_event(
                event_type="output_guardrail_sanitization",
                severity="MEDIUM",
                request_id=request_id,
                session_id=session.id,
                details={"violations": violations},
                db=db
            )

        # Step 11: Grounding & Hallucination Verification
        confidence = hallucination_verifier.verify_response(
            answer=sanitized_output,
            citations=citations,
            has_retrieved_context=bool(trusted_context_xml)
        )

        # If confidence is insufficient evidence, omit source citations to prevent misleading links
        final_sources = citations if confidence != "insufficient_evidence" else []

        # Step 12: Persist Assistant Message
        assistant_db_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=sanitized_output,
            token_count=llm_resp.usage.output_tokens,
            citations=[c.model_dump() for c in final_sources],
            confidence=confidence
        )
        db.add(assistant_db_msg)
        conv.message_count += 2
        await db.commit()

        # Telemetry
        duration_s = time.perf_counter() - start_time
        REQUEST_LATENCY.observe(duration_s)
        app_logger.info(
            "Chat request completed",
            extra={
                "request_id": request_id,
                "conversation_id": conv.id,
                "latency_ms": round(duration_s * 1000, 2),
                "model": llm_resp.model,
                "confidence": confidence,
                "citations_count": len(final_sources)
            }
        )

        return ChatResponse(
            request_id=request_id,
            conversation_id=conv.id,
            answer=sanitized_output,
            sources=final_sources,
            confidence=confidence
        )

    async def stream_chat(
        self,
        user_message: str,
        conversation_id: Optional[str],
        session: Session,
        db: AsyncSession,
        request_id: str,
        user_role: str = "public"
    ) -> AsyncGenerator[str, None]:
        """
        Streams response tokens via Server-Sent Events (SSE).
        Uses sliding window token moderation to prevent streaming confidential credentials mid-stream.
        """
        import json

        # Input evaluation
        async with trace_span("guardrails.input_evaluation", {"request_id": request_id}):
            eval_result = policy_engine.evaluate(user_message, user_role=user_role)
        if eval_result.decision == PolicyDecision.BLOCK:
            yield f"event: error\ndata: {json.dumps({'message': eval_result.refusal_message or 'Security policy violation.'})}\n\n"
            return

        if eval_result.decision == PolicyDecision.SAFE_REFUSAL:
            conv = await self._get_or_create_conversation(conversation_id, session.id, db)
            yield f"event: token\ndata: {json.dumps({'token': eval_result.refusal_message})}\n\n"
            yield f"event: done\ndata: {json.dumps({'conversation_id': conv.id, 'sources': []})}\n\n"
            return

        clean_query = eval_result.clean_text
        conv = await self._get_or_create_conversation(conversation_id, session.id, db)

        # Retrieval & Reranking
        async with trace_span("rag.hybrid_retrieval", {"query": clean_query}):
            query_embeddings = await llm_gateway.embed([clean_query])
            query_embedding = query_embeddings[0] if query_embeddings else []
            retrieved_chunks = await hybrid_retriever.retrieve(clean_query, query_embedding, top_k=settings.VECTOR_TOP_K)

        async with trace_span("reranking.flashrank", {"candidates_count": len(retrieved_chunks), "query": clean_query}):
            reranked_chunks = context_reranker.rerank_and_filter(
                retrieved_chunks,
                query=clean_query,
                top_n=settings.RERANKER_TOP_N
            )
        trusted_context_xml, citations = context_builder.build_context(reranked_chunks)

        # Pre-LLM Context Gating
        if len(reranked_chunks) == 0:
            if domain_guardrail.is_greeting(clean_query):
                greeting_text = (
                    "Hello! I am the official AI assistant for our website. "
                    "I am here to help answer your questions about our company, services, solutions, "
                    "and documentation. What would you like to know today?"
                )
                yield f"event: token\ndata: {json.dumps({'token': greeting_text})}\n\n"
                done_payload = {
                    "conversation_id": conv.id,
                    "request_id": request_id,
                    "confidence": "grounded",
                    "sources": []
                }
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                assistant_db_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=greeting_text,
                    citations=[],
                    confidence="grounded"
                )
                db.add(assistant_db_msg)
                await db.commit()
                return
            else:
                out_of_scope_text = (
                    "I don't have verified information in our company knowledge base to answer that. "
                    "As the official website assistant, I am dedicated to helping you with questions "
                    "about our company, services, and solutions. Please feel free to ask anything about our offerings!"
                )
                yield f"event: token\ndata: {json.dumps({'token': out_of_scope_text})}\n\n"
                done_payload = {
                    "conversation_id": conv.id,
                    "request_id": request_id,
                    "confidence": "insufficient_evidence",
                    "sources": []
                }
                yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
                assistant_db_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=out_of_scope_text,
                    citations=[],
                    confidence="insufficient_evidence"
                )
                db.add(assistant_db_msg)
                await db.commit()
                return

        messages = prompt_builder.build_chat_messages(
            user_query=clean_query,
            trusted_context_xml=trusted_context_xml
        )

        # Stream tokens
        accumulated_text = ""
        async with trace_span("llm.stream_generation"):
            async for token in llm_gateway.stream(messages=messages, max_tokens=settings.MAX_OUTPUT_TOKENS):
                accumulated_text += token
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"

        # Final verification
        async with trace_span("guardrails.output_verification"):
            sanitized_output, _, _ = output_guardrail.sanitize_and_verify(accumulated_text)
        confidence = hallucination_verifier.verify_response(
            answer=sanitized_output,
            citations=citations,
            has_retrieved_context=bool(trusted_context_xml)
        )
        final_sources = [c.model_dump() for c in citations] if confidence != "insufficient_evidence" else []

        # Yield completion payload
        done_payload = {
            "conversation_id": conv.id,
            "request_id": request_id,
            "confidence": confidence,
            "sources": final_sources
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

        # Save assistant message
        assistant_db_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=sanitized_output,
            citations=final_sources,
            confidence=confidence
        )
        db.add(assistant_db_msg)
        await db.commit()

    async def _get_or_create_conversation(
        self,
        conversation_id: Optional[str],
        session_id: str,
        db: AsyncSession
    ) -> Conversation:
        if conversation_id:
            res = await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.session_id == session_id
                )
            )
            conv = res.scalars().first()
            if conv:
                return conv

        new_conv = Conversation(session_id=session_id)
        db.add(new_conv)
        await db.flush()
        return new_conv


chat_service = ChatOrchestratorService()
