"""
Domain and Scope Enforcement Guardrail.
Ensures the chatbot operates exclusively within its designated scope as an
official company website assistant.
Detects and safely refuses off-topic requests including general programming/coding,
math/homework problems, creative writing, recipes, and unrelated trivia.
"""
import re
from typing import Optional, Tuple


class DomainScopeGuardrail:
    """
    Evaluates whether an incoming user query is within the company website domain,
    or is an off-topic query that should be politely redirected.
    """

    # Company or platform-specific keywords that whitelist/allow the query
    COMPANY_WHITELIST_TERMS = [
        "incerro", "company", "website", "product", "service", "pricing",
        "plan", "support", "contact", "office", "career", "job", "hiring",
        "headless", "cms", "sanity", "api", "sdk", "documentation", "docs",
        "architecture", "consulting", "modernization", "solution", "team",
        "about you", "who are you", "what can you do", "help",
        # Partners, Clients, Customers, Group companies, and Recognitions
        "partner", "partners", "partnership", "partnerships",
        "client", "clients", "customer", "customers",
        "group", "group company", "group companies", "parent", "parent company", "legal entity",
        "invasion", "invasion software", "codebin",
        "recognize", "recognises", "recognizes", "recognise", "recognition", "recognitions", "award", "awards", "clutch",
        "autodesk", "p&g", "procter & gamble", "g42", "upwork", "altudo", "conformiq", "botco",
        "koble", "lintas", "mullenlowe", "bank of baroda", "riverfront"
    ]

    # Standard conversational greetings/courtesy
    GREETINGS = [
        "hi", "hello", "hey", "hey there", "good morning", "good afternoon",
        "good evening", "how are you", "who are you", "what do you do",
        "what can you do", "help", "help me", "thanks", "thank you", "bye", "goodbye"
    ]

    # 1. General Programming & Code Generation patterns (not company API related)
    CODING_PATTERNS = [
        r"\b(?:palindrome|fibonacci|factorial|binary search|bubble sort|quick sort|merge sort|linked list|leetcode|two sum|reverse string)\b",
        r"\b(?:write|create|generate|provide|give me|show me)\s+(?:a\s+|some\s+)?(?:python|java|c\+\+|javascript|typescript|c#|golang|rust|php|ruby|bash|sql|html|css)?\s*(?:code|script|function|program|algorithm|class|method)\b",
        r"\bhow to (?:code|program|write (?:a\s+)?function|solve) (?:a|an|the)?\s*(?:palindrome|algorithm|loop|recursion|data structure)\b",
        r"\bwrite (?:a|an) (?:palindrome|regex|sql query|python code|react component|sorting algorithm)\b",
        r"\bcan you code\b",
        r"\bwrite code for\b",
        r"\bwrite a (?:program|script|function) to\b",
        r"\bdebug this code\b",
        r"\bfix this code\b"
    ]

    # 2. Math, Homework & Academic solving
    MATH_ACADEMIC_PATTERNS = [
        r"\b(?:solve|calculate|evaluate)\s+(?:the\s+|this\s+|an?\s+)?(?:equation|math|derivative|integral|\d+\s*[\+\-\*\/])\b",
        r"\b(?:derivative|integral|limit)\s+of\b",
        r"\bwrite (?:an?\s+)?(?:essay|paper|thesis|homework)\s+(?:about|on|for)\b",
        r"\bsummarize (?:the book|the play|the movie|hamlet|macbeth|the novel)\b",
        r"\bdo my homework\b"
    ]

    # 3. Recipes, Cooking, Nutrition
    RECIPE_PATTERNS = [
        r"\brecipe\s+(?:for\b|to\b)",
        r"\bhow to (?:cook|bake|make|prepare)\s+.*(?:cake|pasta|pizza|cookies|bread|soup|curry|dinner|lunch|breakfast|pie|cocktail|smoothie|dish|food|meal)\b",
        r"\bingredients for\b"
    ]

    # 4. Creative Writing, Entertainment, Roleplay
    CREATIVE_PATTERNS = [
        r"\b(?:write|compose|generate)\s+(?:a\s+)?(?:poem|poetry|song|lyrics|story|bedtime story|joke|rap)\b",
        r"\btell me a (?:joke|story|riddle)\b"
    ]

    # 5. General World Trivia / Geography / Politics
    TRIVIA_PATTERNS = [
        r"\bwho (?:is|was) the (?:president|king|queen|prime minister|governor|mayor) of\b",
        r"\bwhat is the capital of\b",
        r"\bwho won the (?:world cup|super bowl|oscars|olympics|championship)\b"
    ]

    # 6. Medical / Legal / Personal Advice
    ADVICE_PATTERNS = [
        r"\b(?:what medicine should i take|diagnose my symptoms|how to treat (?:flu|fever|cough|cancer|headache))\b",
        r"\b(?:how to sue|legal advice for|file a lawsuit)\b",
        r"\b(?:which stock to buy|which crypto to invest in|financial investment advice)\b"
    ]

    def is_greeting(self, text: str) -> bool:
        """Checks if the input is simply a polite greeting or identity query."""
        clean = text.strip().lower().rstrip("!?.")
        if clean in self.GREETINGS:
            return True
        tokens = clean.split()
        if len(tokens) <= 3 and any(g == clean or clean.startswith(g + " ") for g in self.GREETINGS):
            return True
        return False

    def check_domain_scope(self, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluates if the text is off-topic.
        Returns:
            (is_off_topic, category, refusal_message)
        """
        lower = text.strip().lower()

        # 1. Allow conversational greetings
        if self.is_greeting(lower):
            return False, None, None

        # 2. Check if the query specifically refers to our company, services, or documentation
        for term in self.COMPANY_WHITELIST_TERMS:
            if re.search(r"\b" + re.escape(term) + r"\b", lower):
                # Even if they say "code", if they ask "Incerro API code", it is on-topic
                # Only block if it's explicitly a generic coding algorithm like palindrome
                if not any(re.search(p, lower, re.IGNORECASE) for p in [r"\b(?:palindrome|fibonacci|factorial|binary search|two sum|bubble sort)\b"]):
                    return False, None, None

        # 3. Check Coding & Software generation patterns
        for pattern in self.CODING_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return (
                    True,
                    "general_programming",
                    "I am the official website assistant for our company. I am designed to assist with questions regarding our company, services, solutions, and website documentation. I cannot generate arbitrary code, solve programming exercises (such as palindromes or algorithms), or assist with general coding tasks. How can I help you with our company's offerings today?"
                )

        # 4. Check Math & Academic homework
        for pattern in self.MATH_ACADEMIC_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return (
                    True,
                    "academic_math",
                    "I am dedicated to helping visitors with questions about our company, products, and services. I am unable to solve academic, math, or homework problems. Please feel free to ask anything about our company or services!"
                )

        # 5. Check Recipes & Cooking
        for pattern in self.RECIPE_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return (
                    True,
                    "recipes_cooking",
                    "I am the company's website assistant, focused on our business solutions and services. I do not provide recipes or culinary advice. Let me know if you'd like to learn more about our company!"
                )

        # 6. Check Creative Writing
        for pattern in self.CREATIVE_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return (
                    True,
                    "creative_writing",
                    "I am configured strictly as an enterprise assistant for our website and do not generate stories, poetry, or creative entertainment. How can I assist you with our products or services?"
                )

        # 7. Check General Trivia
        for pattern in self.TRIVIA_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return (
                    True,
                    "general_trivia",
                    "I am the official website assistant and can only answer questions related to our company, services, and documentation. I do not provide general world trivia or encyclopedia lookup."
                )

        # 8. Check Medical / Legal / Financial Advice
        for pattern in self.ADVICE_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return (
                    True,
                    "personal_advice",
                    "I am an enterprise website assistant and cannot provide medical, legal, or investment advice. For inquiries regarding our company and services, I am here to help!"
                )

        return False, None, None


domain_guardrail = DomainScopeGuardrail()
