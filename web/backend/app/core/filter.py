from __future__ import annotations
import logging
import re
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .aggregator import Article

logger = logging.getLogger(__name__)

_IMPORTANCE_WORDS = frozenset([
    "breaking","urgent","alert","exclusive","crisis","emergency","disaster",
    "catastrophe","war","attack","killed","dead","deaths","casualties",
    "explosion","shooting","terror","terrorist","collapse","crash","scandal",
    "impeach","historic","landmark","major","critical","significant","record",
    "unprecedented","first","ban","sanctions","election","vote","resign",
    "fired","arrested","outbreak","epidemic","pandemic",
])

_TIER1_SOURCES = frozenset([
    "reuters top news","ap news","bbc news","bbc politics","ny times",
    "the guardian world","guardian politics","financial times",
    "bloomberg markets","wsj world news","al jazeera","npr news",
    "deutsche welle","france 24","who news","nasa news",
])

_W_RELEVANCE   = 0.40
_W_RECENCY     = 0.20
_W_CORROBORATE = 0.20
_W_IMPORTANCE  = 0.12
_W_AUTHORITY   = 0.08


def score_and_select(
    articles: list[Article],
    topics: list[str],
    keywords: list[str],
    relevance_threshold: float = 0.05,
    max_count: int = 20,
) -> list[Article]:
    if not articles:
        return []

    now = datetime.now()
    relevance  = _compute_relevance(articles, topics, keywords)
    recency    = _compute_recency(articles, now)
    corroborate = _compute_corroboration(articles)
    importance = _compute_importance(articles)
    authority  = [1.0 if a.source_name.lower() in _TIER1_SOURCES else 0.0 for a in articles]

    for i, a in enumerate(articles):
        a.relevance_score = round(
            _W_RELEVANCE * relevance[i]
            + _W_RECENCY * recency[i]
            + _W_CORROBORATE * corroborate[i]
            + _W_IMPORTANCE * importance[i]
            + _W_AUTHORITY * authority[i],
            4,
        )

    scored = [a for a in articles if a.relevance_score >= relevance_threshold]
    scored.sort(key=lambda a: a.relevance_score, reverse=True)
    scored = _deduplicate(scored)
    return scored[:max_count]


def _compute_relevance(articles, topics, keywords):
    query = " ".join(topics + keywords).strip()
    if not query:
        return [1.0] * len(articles)
    texts = [f"{a.title} {a.summary}" for a in articles]
    try:
        mat = TfidfVectorizer().fit_transform([query] + texts)
        return [float(s) for s in cosine_similarity(mat[0], mat[1:]).flatten()]
    except ValueError:
        return [0.0] * len(articles)


def _compute_recency(articles, now):
    scores = []
    for a in articles:
        pub = a.published_at.replace(tzinfo=None) if a.published_at.tzinfo else a.published_at
        age_h = max(0.0, (now - pub).total_seconds() / 3600)
        scores.append(max(0.0, 1.0 - age_h / 24.0))
    return scores


def _compute_corroboration(articles):
    if len(articles) <= 1:
        return [0.0] * len(articles)
    titles = [a.title for a in articles]
    try:
        mat = TfidfVectorizer().fit_transform(titles)
        sim = cosine_similarity(mat)
        counts = [sum(1 for j in range(len(articles)) if j != i and sim[i, j] > 0.30)
                  for i in range(len(articles))]
        mx = max(counts) or 1
        return [c / mx for c in counts]
    except ValueError:
        return [0.0] * len(articles)


def _compute_importance(articles):
    scores = []
    for a in articles:
        text = (a.title + " " + a.summary[:200]).lower()
        words = set(re.findall(r"\b\w+\b", text))
        scores.append(min(1.0, len(words & _IMPORTANCE_WORDS) / 3.0))
    return scores


def _deduplicate(articles):
    if len(articles) <= 1:
        return list(articles)
    titles = [a.title for a in articles]
    try:
        mat = TfidfVectorizer().fit_transform(titles)
        sim = cosine_similarity(mat)
        keep = [True] * len(articles)
        for i in range(len(articles)):
            if not keep[i]:
                continue
            for j in range(i + 1, len(articles)):
                if keep[j] and sim[i, j] > 0.85:
                    keep[j] = False
        return [a for a, k in zip(articles, keep) if k]
    except ValueError:
        return list(articles)
