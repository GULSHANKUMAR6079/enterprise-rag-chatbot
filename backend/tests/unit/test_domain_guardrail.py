"""
Unit Tests for Domain and Scope Enforcement Guardrail.
Verifies that off-topic programming tasks (like palindrome, sorting, leetcode),
math, homework, recipes, and trivia are safely intercepted and refused.
"""
import pytest
from backend.app.guardrails.domain_guardrail import domain_guardrail
from backend.app.guardrails.policy_engine import PolicyDecision, policy_engine


def test_palindrome_queries_intercepted():
    queries = [
        "write a python function to check palindrome",
        "how to check if a string is palindrome in python",
        "write code for palindrome",
        "can you write a palindrome program in java",
        "palindrome code please",
        "give me a palindrome function"
    ]
    for q in queries:
        is_off, cat, msg = domain_guardrail.check_domain_scope(q)
        assert is_off is True, f"Failed to detect off-topic on: {q}"
        assert cat == "general_programming"
        assert "official website assistant" in msg

        # Ensure Policy Engine safely refuses
        eval_result = policy_engine.evaluate(q)
        assert eval_result.decision == PolicyDecision.SAFE_REFUSAL
        assert "official website assistant" in eval_result.refusal_message


def test_general_coding_queries_intercepted():
    queries = [
        "write python code for binary search",
        "solve two sum in c++",
        "how to reverse a linked list in python",
        "give me a javascript function to sort an array",
        "write a script to scrape google search",
        "can you code a snake game in html"
    ]
    for q in queries:
        is_off, cat, _ = domain_guardrail.check_domain_scope(q)
        assert is_off is True, f"Failed to detect off-topic on: {q}"
        assert cat == "general_programming"


def test_academic_math_and_recipes_intercepted():
    queries = [
        "solve this equation: 3x + 12 = 45",
        "calculate the derivative of sin(x)",
        "write an essay on the French Revolution",
        "recipe for chocolate cake",
        "how to bake pasta with cheese",
        "who is the president of France",
        "what is the capital of Australia"
    ]
    for q in queries:
        is_off, cat, _ = domain_guardrail.check_domain_scope(q)
        assert is_off is True, f"Failed to detect off-topic on: {q}"


def test_company_queries_allowed():
    queries = [
        "tell me about Incerro",
        "what services does Incerro provide",
        "what is headless CMS and how does Incerro support it",
        "what pricing plans do you offer",
        "where is your headquarters located",
        "how can I contact your support team",
        "what career opportunities are open at your company",
        # Partners, clients, group companies, recognitions
        "who are partners or companies having partnership with Incerro",
        "who are Incerro customers or clients",
        "what are Incerro's group companies",
        "what is Incerro's parent legal entity",
        "who recognises Incerro and what awards do they have",
        "tell me about Incerro's work with Autodesk and P&G",
        "is Incerro an official Sanity agency partner"
    ]
    for q in queries:
        is_off, _, _ = domain_guardrail.check_domain_scope(q)
        assert is_off is False, f"Should NOT be off-topic: {q}"

        eval_result = policy_engine.evaluate(q)
        assert eval_result.decision in (PolicyDecision.ALLOW, PolicyDecision.ALLOW_WITH_REDACTION)


def test_conversational_greetings_allowed():
    greetings = [
        "hi",
        "hello",
        "hey there",
        "good morning",
        "who are you",
        "what can you do",
        "help"
    ]
    for g in greetings:
        assert domain_guardrail.is_greeting(g) is True
        is_off, _, _ = domain_guardrail.check_domain_scope(g)
        assert is_off is False
