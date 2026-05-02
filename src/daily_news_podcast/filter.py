# Filter: multi-signal importance scoring, deduplication, and selection.
#
# Final score = weighted combination of:
#   - TF-IDF relevance  (how well the article matches your topics/keywords)
#   - Recency           (fresher articles score higher within the 24h window)
#   - Corroboration     (story covered by multiple sources → more important)
#   - Importance cues   (headline words like "breaking", "crisis", "war", etc.)
#   - Source authority  (tier-1 outlets get a weight boost)

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler

from .models import Article, FilterConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Words in a headline that signal high newsworthiness
_IMPORTANCE_WORDS: frozenset[str] = frozenset([
    "breaking", "urgent", "alert", "exclusive",
    "crisis", "emergency", "disaster", "catastrophe",
    "war", "attack", "killed", "dead", "deaths", "casualties",
    "explosion", "shooting", "terror", "terrorist",
    "collapse", "crash", "scandal", "impeach",
    "historic", "landmark", "major", "critical", "significant",
    "record", "unprecedented", "first", "ban", "sanctions",
    "election", "vote", "resign", "fired", "arrested",
    "outbreak", "epidemic", "pandemic",
])

# Tier-1 sources get a 20 % authority boost
_TIER1_SOURCES: frozenset[str] = frozenset([
    "reuters top news", "ap news", "bbc news", "bbc politics",
    "ny times", "the guardian world", "guardian politics",
    "financial times", "bloomberg markets", "wsj world news",
    "al jazeera", "npr news", "deutsche welle", "france 24",
    "who news", "nasa news",
])

# Scoring weights (must sum to 1.0)
_W_RELEVANCE    = 0.40
_W_RECENCY      = 0.20
_W_CORROBORATE  = 0.20
_W_IMPORTANCE   = 0.12
_W_AUTHORITY    = 0.08


class Filter:
    def score_and_select(
        self,
        articles: list[Article],
        config: FilterConfig,
        max_count: int = 20,
    ) -> list[Article]:
        """
        Score articles using multiple importance signals, deduplicate,
        and return the top max_count most important/relevant articles.
        """
        if not articles:
            return []

        now = datetime.now()

        # ------------------------------------------------------------------
        # 1. TF-IDF relevance score  [0, 1]
        # ------------------------------------------------------------------
        relevance_scores = self._compute_relevance(articles, config)

        # ------------------------------------------------------------------
        # 2. Recency score  [0, 1]  — linear decay over 24 h
        # ------------------------------------------------------------------
        recency_scores = []
        for article in articles:
            pub = article.published_at
            # Make both naive for comparison
            if pub.tzinfo is not None:
                pub = pub.replace(tzinfo=None)
            age_hours = max(0.0, (now - pub).total_seconds() / 3600)
            recency_scores.append(max(0.0, 1.0 - age_hours / 24.0))

        # ------------------------------------------------------------------
        # 3. Corroboration score  [0, 1]
        #    Articles whose title is similar to N other articles score higher.
        # ------------------------------------------------------------------
        corroboration_scores = self._compute_corroboration(articles)

        # ------------------------------------------------------------------
        # 4. Importance cue score  [0, 1]
        #    Count how many importance words appear in title + first 20 words.
        # ------------------------------------------------------------------
        importance_scores = []
        for article in articles:
            text = (article.title + " " + article.summary[:200]).lower()
            words = set(re.findall(r"\b\w+\b", text))
            hits = len(words & _IMPORTANCE_WORDS)
            importance_scores.append(min(1.0, hits / 3.0))  # cap at 3 hits = 1.0

        # ------------------------------------------------------------------
        # 5. Source authority score  [0 or 1]
        # ------------------------------------------------------------------
        authority_scores = [
            1.0 if article.source_name.lower() in _TIER1_SOURCES else 0.0
            for article in articles
        ]

        # ------------------------------------------------------------------
        # 6. Combine into final score
        # ------------------------------------------------------------------
        for i, article in enumerate(articles):
            final = (
                _W_RELEVANCE   * relevance_scores[i]
                + _W_RECENCY      * recency_scores[i]
                + _W_CORROBORATE  * corroboration_scores[i]
                + _W_IMPORTANCE   * importance_scores[i]
                + _W_AUTHORITY    * authority_scores[i]
            )
            article.relevance_score = round(final, 4)
            logger.debug(
                "Score %.3f | rel=%.2f rec=%.2f cor=%.2f imp=%.2f auth=%.0f | %s",
                final,
                relevance_scores[i], recency_scores[i], corroboration_scores[i],
                importance_scores[i], authority_scores[i],
                article.title[:60],
            )

        # Drop articles that score below the threshold
        scored = [a for a in articles if a.relevance_score >= config.relevance_threshold]

        # Sort by final score descending
        scored.sort(key=lambda a: a.relevance_score, reverse=True)

        # Deduplicate near-identical titles
        scored = self._deduplicate(scored)

        return scored[:max_count]

    # ------------------------------------------------------------------
    # TF-IDF relevance
    # ------------------------------------------------------------------

    def _compute_relevance(
        self, articles: list[Article], config: FilterConfig
    ) -> list[float]:
        query_terms = config.topics + config.keywords
        query = " ".join(query_terms).strip()

        if not query:
            return [1.0] * len(articles)

        article_texts = [f"{a.title} {a.summary}" for a in articles]
        corpus = [query] + article_texts

        try:
            tfidf = TfidfVectorizer().fit_transform(corpus)
        except ValueError:
            return [0.0] * len(articles)

        sims = cosine_similarity(tfidf[0], tfidf[1:]).flatten()
        return [float(s) for s in sims]

    # ------------------------------------------------------------------
    # Corroboration
    # ------------------------------------------------------------------

    def _compute_corroboration(self, articles: list[Article]) -> list[float]:
        """
        For each article, count how many *other* articles have a title
        cosine similarity > 0.30 (same story, different source).
        Normalise to [0, 1].
        """
        if len(articles) <= 1:
            return [0.0] * len(articles)

        titles = [a.title for a in articles]
        try:
            mat = TfidfVectorizer().fit_transform(titles)
        except ValueError:
            return [0.0] * len(articles)

        sim_matrix = cosine_similarity(mat)

        counts = []
        for i in range(len(articles)):
            # Count other articles (j != i) with similarity > 0.30
            count = sum(
                1 for j in range(len(articles))
                if j != i and sim_matrix[i, j] > 0.30
            )
            counts.append(float(count))

        max_count = max(counts) if max(counts) > 0 else 1.0
        return [c / max_count for c in counts]

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def _deduplicate(self, articles: list[Article]) -> list[Article]:
        """
        Remove near-duplicate articles (title similarity > 0.85).
        Keep the highest-scored one from each cluster.
        Articles must be pre-sorted by descending relevance_score.
        """
        if len(articles) <= 1:
            return list(articles)

        titles = [a.title for a in articles]
        try:
            mat = TfidfVectorizer().fit_transform(titles)
        except ValueError:
            return list(articles)

        sim_matrix = cosine_similarity(mat)
        keep = [True] * len(articles)

        for i in range(len(articles)):
            if not keep[i]:
                continue
            for j in range(i + 1, len(articles)):
                if keep[j] and sim_matrix[i, j] > 0.85:
                    keep[j] = False  # drop lower-scored duplicate

        return [a for a, k in zip(articles, keep) if k]
