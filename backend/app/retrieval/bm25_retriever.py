"""
Okapi BM25 Lexical Keyword Search Engine.
Provides exact keyword matching for company names, acronyms, and product specifications.
"""
import math
import re
from collections import Counter
from typing import Dict, List, Tuple


class BM25Retriever:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lengths: Dict[str, int] = {}
        self.doc_freqs: Dict[str, int] = {}  # term -> number of documents containing term
        self.term_freqs: Dict[str, Counter] = {}  # doc_id -> Counter(terms)
        self.documents: Dict[str, str] = {}  # doc_id -> content

    def tokenize(self, text: str) -> List[str]:
        """Normalizes and extracts alphanumeric keyword tokens with inflection expansion."""
        raw_tokens = re.findall(r"\b\w+\b", text.lower())
        expanded = []
        for t in raw_tokens:
            expanded.append(t)
            # Suffix stemming & US/UK spelling variants
            if t.endswith("ises") or t.endswith("izes"):
                expanded.extend([t[:-4] + "ise", t[:-4] + "ize", t[:-4] + "ition", t[:-4] + "itions", t[:-4] + "ized", t[:-4] + "ised"])
            elif t.endswith("ised") or t.endswith("ized"):
                expanded.extend([t[:-4] + "ise", t[:-4] + "ize", t[:-4] + "ition", t[:-4] + "itions"])
            elif t.endswith("ition") or t.endswith("itions"):
                stem = t[:-6] if t.endswith("itions") else t[:-5]
                expanded.extend([stem + "ize", stem + "ise", stem + "ized", stem + "ised", stem + "izes", stem + "ises"])
            elif t.endswith("ships") or t.endswith("ship"):
                stem = t.replace("ships", "").replace("ship", "")
                if stem:
                    expanded.extend([stem, stem + "s"])
            elif t.endswith("ies") and len(t) > 4:
                expanded.append(t[:-3] + "y")
            elif t.endswith("s") and len(t) > 3 and not t.endswith("ss"):
                expanded.append(t[:-1])
        return expanded

    def index_documents(self, docs: Dict[str, str]):
        """
        Indexes a dictionary of {doc_id: text_content}.
        """
        self.documents = dict(docs)
        self.corpus_size = len(docs)
        if self.corpus_size == 0:
            return

        total_len = 0
        self.term_freqs.clear()
        self.doc_freqs.clear()
        self.doc_lengths.clear()

        for doc_id, text in docs.items():
            tokens = self.tokenize(text)
            self.doc_lengths[doc_id] = len(tokens)
            total_len += len(tokens)

            counts = Counter(tokens)
            self.term_freqs[doc_id] = counts

            for term in counts.keys():
                self.doc_freqs[term] = self.doc_freqs.get(term, 0) + 1

        self.avg_doc_len = total_len / float(self.corpus_size)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Executes BM25 score calculation for the query.
        Returns sorted list of (doc_id, bm25_score).
        """
        if self.corpus_size == 0:
            return []

        query_tokens = self.tokenize(query)
        scores: Dict[str, float] = {}

        for token in query_tokens:
            if token not in self.doc_freqs:
                continue

            df = self.doc_freqs[token]
            # Standard BM25 IDF with smoothing
            idf = math.log(1.0 + (self.corpus_size - df + 0.5) / (df + 0.5))

            for doc_id, counts in self.term_freqs.items():
                tf = counts.get(token, 0)
                if tf == 0:
                    continue

                doc_len = self.doc_lengths[doc_id]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                score = idf * (numerator / denominator)

                scores[doc_id] = scores.get(doc_id, 0.0) + score

        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]


bm25_retriever = BM25Retriever()
