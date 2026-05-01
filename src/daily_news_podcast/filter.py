# Filter: scores articles by TF-IDF relevance, deduplicates, and selects top N.

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .models import Article, FilterConfig

logger = logging.getLogger(__name__)


class Filter:
    def score_and_select(
        self,
        articles: list[Article],
        config: FilterConfig,
        max_count: int = 20,
    ) -> list[Article]:
        """
        Score articles by relevance to configured topics/keywords.
        Deduplicate by title similarity.
        Return top-ranked articles up to max_count.
        """
        if not articles:
            return []

        # --- Relevance Scoring ---
        query_terms = config.topics + config.keywords
        query = " ".join(query_terms).strip()

        if not query:
            # No topics/keywords configured: all articles score 1.0
            for article in articles:
                article.relevance_score = 1.0
            scored = list(articles)
        else:
            # Build corpus: query first, then each article's text
            article_texts = [
                f"{article.title} {article.summary}" for article in articles
            ]
            corpus = [query] + article_texts

            vectorizer = TfidfVectorizer()
            try:
                tfidf_matrix = vectorizer.fit_transform(corpus)
            except ValueError:
                # Corpus is empty or all stop words — assign 0 to all
                for article in articles:
                    article.relevance_score = 0.0
                return []

            query_vec = tfidf_matrix[0]
            article_vecs = tfidf_matrix[1:]

            similarities = cosine_similarity(query_vec, article_vecs).flatten()

            for article, score in zip(articles, similarities):
                article.relevance_score = float(score)

            # Drop articles below the relevance threshold
            scored = [
                a for a in articles
                if a.relevance_score >= config.relevance_threshold
            ]

        # Sort by descending relevance score before deduplication
        scored.sort(key=lambda a: a.relevance_score, reverse=True)

        # --- Deduplication by title similarity ---
        scored = self._deduplicate(scored)

        # --- Selection: top max_count ---
        return scored[:max_count]

    def _deduplicate(self, articles: list[Article]) -> list[Article]:
        """
        Remove near-duplicate articles based on title cosine similarity > 0.85.
        Articles are assumed to be sorted by descending relevance_score.
        The lower-ranked duplicate is dropped.
        """
        if len(articles) <= 1:
            return list(articles)

        titles = [article.title for article in articles]

        vectorizer = TfidfVectorizer()
        try:
            title_matrix = vectorizer.fit_transform(titles)
        except ValueError:
            # All titles are empty or stop words — no deduplication possible
            return list(articles)

        similarity_matrix = cosine_similarity(title_matrix)

        keep = [True] * len(articles)
        for i in range(len(articles)):
            if not keep[i]:
                continue
            for j in range(i + 1, len(articles)):
                if not keep[j]:
                    continue
                if similarity_matrix[i, j] > 0.85:
                    # Drop the lower-ranked one (j has lower score since sorted desc)
                    keep[j] = False

        return [article for article, k in zip(articles, keep) if k]
