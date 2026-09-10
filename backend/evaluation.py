import re
import json
from typing import List, Dict
from dataclasses import dataclass, asdict


@dataclass
class RAGMetrics:
    faithfulness:      float = 0.0
    answer_relevancy:  float = 0.0
    context_precision: float = 0.0
    context_recall:    float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)

    def overall(self) -> float:
        scores = [self.faithfulness, self.answer_relevancy,
                  self.context_precision, self.context_recall]
        return round(sum(scores) / len(scores), 3)


class RAGEvaluator:
    def __init__(self, llm):
        self.llm = llm

    def _parse_score(self, text: str, fallback: float = 0.0) -> float:
        text = text.strip()
        match = re.search(r'(\d+(?:\.\d+)?)', text)
        if match:
            val = float(match.group(1))
            if val > 1.0:
                val = val / 10.0 if val <= 10.0 else val / 100.0
            return round(min(max(val, 0.0), 1.0), 3)
        return fallback

    def _parse_json_list(self, text: str) -> List[str]:
        try:
            clean = text.strip()
            if "```" in clean:
                clean = clean.split("```")[1].split("```")[0].strip()
                if clean.startswith("json"):
                    clean = clean[4:].strip()
            start = clean.find("[")
            end = clean.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(clean[start:end])
        except Exception:
            pass
        return [s.strip().strip("-•").strip()
                for s in text.strip().split("\n")
                if s.strip() and len(s.strip()) > 5]

    def faithfulness(self, question: str, answer: str,
                     contexts: List[str]) -> float:
        if not answer or not contexts:
            return 0.0

        context_block = "\n\n".join([f"[C{i+1}] {c[:500]}"
                                      for i, c in enumerate(contexts[:5])])

        step1_prompt = f"""Given this answer to a question, extract every factual claim
or statement made in the answer. Return them as a JSON list of strings.

Question: {question}

Answer: {answer}

Return ONLY a JSON list of claim strings, e.g. ["claim 1", "claim 2"]:"""

        claims_raw = self.llm.generate(step1_prompt)
        claims = self._parse_json_list(claims_raw)

        if not claims:
            return 0.5

        step2_prompt = f"""For each claim below, determine if it is supported by the
context passages. Return a JSON list of "yes" or "no" for each claim.

Context passages:
{context_block}

Claims:
{json.dumps(claims)}

Return ONLY a JSON list like ["yes", "no", "yes"]:"""

        verdicts_raw = self.llm.generate(step2_prompt)
        verdicts = self._parse_json_list(verdicts_raw)

        if not verdicts:
            return self._parse_score(verdicts_raw, 0.5)

        supported = sum(1 for v in verdicts
                        if isinstance(v, str) and "yes" in v.lower())
        return round(supported / max(len(claims), 1), 3)

    def answer_relevancy(self, question: str, answer: str) -> float:
        if not answer or not question:
            return 0.0

        no_info = "do not contain sufficient information"
        if no_info in answer.lower():
            return 0.3

        prompt = f"""Rate how well this answer addresses the question.
Score from 0.0 to 1.0 where:
  1.0 = perfectly answers the question with specific details
  0.7 = mostly answers but misses some aspects
  0.4 = partially relevant but incomplete
  0.1 = mostly irrelevant

Question: {question}

Answer: {answer[:800]}

Reply with ONLY a decimal number between 0.0 and 1.0:"""

        return self._parse_score(self.llm.generate(prompt), 0.5)

    def context_precision(self, question: str,
                          contexts: List[str]) -> float:
        if not contexts:
            return 0.0

        context_items = "\n".join([
            f"[{i+1}] {c[:300]}"
            for i, c in enumerate(contexts[:6])
        ])

        prompt = f"""For each context passage below, determine if it is relevant to
answering the question. Return a JSON list of "yes" or "no" for each passage.

Question: {question}

Passages:
{context_items}

Return ONLY a JSON list like ["yes", "no", "yes"]:"""

        verdicts_raw = self.llm.generate(prompt)
        verdicts = self._parse_json_list(verdicts_raw)

        if not verdicts:
            return self._parse_score(verdicts_raw, 0.5)

        relevant = [1 if isinstance(v, str) and "yes" in v.lower() else 0
                     for v in verdicts]

        if not any(relevant):
            return 0.0

        precision_at_k = 0.0
        running_relevant = 0
        for i, rel in enumerate(relevant):
            if rel:
                running_relevant += 1
                precision_at_k += running_relevant / (i + 1)

        return round(precision_at_k / max(sum(relevant), 1), 3)

    def context_recall(self, question: str, answer: str,
                       contexts: List[str]) -> float:
        if not answer or not contexts:
            return 0.0

        context_block = "\n\n".join([f"[C{i+1}] {c[:400]}"
                                      for i, c in enumerate(contexts[:5])])

        prompt = f"""Given the answer and context passages, estimate what fraction
of the information needed to answer the question was present in the contexts.

Question: {question}

Answer: {answer[:600]}

Context passages:
{context_block}

Score from 0.0 to 1.0 where:
  1.0 = contexts contain ALL information needed for the answer
  0.7 = most information present, minor gaps
  0.4 = some relevant info but significant gaps
  0.1 = contexts barely relevant

Reply with ONLY a decimal number between 0.0 and 1.0:"""

        return self._parse_score(self.llm.generate(prompt), 0.5)

    def evaluate(self, question: str, answer: str,
                 contexts: List[str]) -> RAGMetrics:
        return RAGMetrics(
            faithfulness=self.faithfulness(question, answer, contexts),
            answer_relevancy=self.answer_relevancy(question, answer),
            context_precision=self.context_precision(question, contexts),
            context_recall=self.context_recall(question, answer, contexts),
        )
