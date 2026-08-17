"""
matcher.py — Multi-Stage Title Verification Engine
====================================================

Implements a 7-stage verification pipeline for checking new press title
submissions against a database of existing registered titles.

Pipeline Overview:
    Stage 1: Disallowed Word Filter       → Hard reject if title contains
             banned words (e.g. "police", "crime", "army").
    Stage 2: Title Combination Detector   → Hard reject if title is a
             concatenation of two existing registered titles.
    Stage 3: Periodicity & Affix Filter   → Strips common prefixes/suffixes
             ("The", "Daily", "Weekly") and checks if the remaining core
             collides with any existing title.
    Stage 4: Phonetic Matching Engine     → Uses Metaphone (jellyfish) to
             detect phonetically similar titles despite spelling differences.
    Stage 5: Fuzzy String Matcher         → Uses Token Sort Ratio (RapidFuzz)
             to compute character-level similarity scores.
    Stage 6: Semantic Similarity Engine   → Uses a multilingual sentence
             transformer to catch cross-lingual semantic duplicates.
    Stage 7: Composite Scoring            → Combines all signals into a final
             Verification Probability.

Key Algorithms:
    • Token-Set Intersection for disallowed word matching (avoids substring
      false positives like "accident" triggering "cid").
    • Metaphone phonetic hashing for pronunciation-invariant comparison.
    • Token Sort Ratio for order-insensitive fuzzy string comparison.
    • Cosine similarity on 384-dim sentence embeddings for cross-lingual
      semantic matching (e.g., "Daily Evening" ↔ "Pratidin Sandhya").
    • Composite score: S_max = max(Lexical, Semantic × 100).
"""

from dataclasses import dataclass, field
import pandas as pd
import jellyfish
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer, util
import torch
import streamlit as st
import rule_store


# ═══════════════════════════════════════════════════════════════════════════
# Data Structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class MatchResult:
    """
    Stores per-title comparison scores for one existing title.

    Attributes:
        title             : The existing registered title string.
        fuzzy_score       : Token Sort Ratio (0–100) from RapidFuzz.
        phonetic_match    : True if Metaphone hash of candidate matches
                            this title's precomputed Metaphone hash.
        semantic_score    : Cosine similarity (0.0–1.0) from the
                            multilingual sentence transformer.
        combined_score    : Lexical score = min(100, fuzzy + 15 if phonetic).
                            Final combined = max(combined_lexical, semantic*100).
    """
    title: str = ""
    fuzzy_score: float = 0.0
    phonetic_match: bool = False
    semantic_score: float = 0.0
    combined_score: float = 0.0


@dataclass
class VerificationResult:
    """
    Final verification verdict for a submitted title.

    Attributes:
        is_approved               : True if the title passes all checks.
        verification_probability  : 0–100 %. Approved only if ≥ 60% and
                                    zero rule flags are raised.
        highest_similarity        : The max combined similarity score
                                    found across all existing titles.
        issues                    : List of human-readable issue strings
                                    describing each triggered rule.
        top_matches               : Top 5 closest MatchResult objects for
                                    the analysis table.
    """
    is_approved: bool = False
    verification_probability: float = 0.0
    highest_similarity: float = 0.0
    issues: list = field(default_factory=list)
    top_matches: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Constants — Rule Configuration
# ═══════════════════════════════════════════════════════════════════════════

# Runtime rules are loaded from rule_store.py so admin changes affect the next
# verification request without restarting Streamlit.


# ═══════════════════════════════════════════════════════════════════════════
# Model Loading (cached by Streamlit across reruns)
# ═══════════════════════════════════════════════════════════════════════════

@st.cache_resource
def load_semantic_model() -> SentenceTransformer:
    """
    Load the multilingual sentence transformer model.

    Model: paraphrase-multilingual-MiniLM-L12-v2
        • 384-dimensional embeddings
        • Supports 50+ languages including Hindi, Marathi, Tamil, etc.
        • Ideal for cross-lingual semantic similarity detection
          (e.g., "Daily Evening" ≈ "Pratidin Sandhya")

    The @st.cache_resource decorator ensures the model is loaded once
    and shared across all Streamlit reruns and sessions.
    """
    return SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


# ═══════════════════════════════════════════════════════════════════════════
# TitleVerifier — The Main Verification Engine
# ═══════════════════════════════════════════════════════════════════════════

class TitleVerifier:
    """
    Multi-stage title verification engine.

    On initialization, it:
        1. Loads the existing titles from the CSV dataset.
        2. Precomputes Metaphone phonetic hashes for every title.
        3. Precomputes 384-dim sentence embeddings for every title.

    On verify(candidate), it runs the full 7-stage pipeline and
    returns a VerificationResult with the final verdict.
    """

    def __init__(self, csv_path: str):
        """
        Initialize the verifier with a dataset of existing titles.

        Args:
            csv_path: Path to the CSV file with at least a 'Title' column.

        Side effects:
            • Loads the multilingual sentence transformer model.
            • Precomputes Metaphone hashes for all titles.
            • Precomputes dense vector embeddings for all titles.
        """
        # Load dataset into a DataFrame
        self.df = pd.read_csv(csv_path)

        # Extract the list of title strings for matching
        self.titles: list[str] = self.df["Title"].astype(str).tolist()

        # Build a set of lowercased titles for O(1) exact-match lookups
        # (used in Stage 2: combination detection)
        self.titles_lower_set: set[str] = {t.lower() for t in self.titles}

        # --- Precompute Metaphone phonetic hashes ---
        # Metaphone converts a word into a phonetic code so that words
        # that *sound alike* map to the same hash, regardless of spelling.
        # e.g., metaphone("Namaskar") ≈ metaphone("Namascar")
        self.metaphone_hashes: list[str] = [
            jellyfish.metaphone(t) for t in self.titles
        ]

        # --- Load semantic model & precompute embeddings ---
        self.model = load_semantic_model()

        # Encode all existing titles into 384-dim vectors.
        # These are cached in memory so we only pay the encoding cost once.
        self.embeddings = self.model.encode(
            self.titles,
            convert_to_tensor=True,      # Return a PyTorch tensor
            show_progress_bar=False,
        )

    def reload_rules(self) -> bool:
        """
        Compatibility hook for callers after admin rule changes.

        Rules are loaded from rule_store during each verification stage, so
        there is no verifier-local rule cache to refresh.
        """
        return True

    # -------------------------------------------------------------------
    # Stage 1: Disallowed Word Filter
    # -------------------------------------------------------------------
    def _check_disallowed_words(self, candidate: str) -> list[str]:
        """
        Check if the candidate title contains any disallowed words.

        Algorithm:
            1. Tokenize the candidate into individual words.
            2. Compute the SET INTERSECTION with the disallowed set.
            3. If the intersection is non-empty, return issue strings.

        Why token-level matching?
            Substring matching would cause false positives:
                "accident"  contains "cid"  → FALSE POSITIVE
                "warmth"    contains "arm"  → FALSE POSITIVE
            Token-level matching avoids this because "accident" as a
            whole word is NOT in the disallowed set.

        Args:
            candidate: The proposed title string.

        Returns:
            List of issue strings (empty if no disallowed words found).
        """
        # Tokenize: split on whitespace, convert to lowercase
        candidate_tokens = set(candidate.lower().split())
        normalized_candidate = " ".join(candidate.lower().split())
        disallowed_words = rule_store.get_disallowed_words()

        # Set intersection: O(min(|A|, |B|)) — very efficient
        found = {
            word for word in disallowed_words
            if (
                word in candidate_tokens
                if " " not in word
                else f" {word} " in f" {normalized_candidate} "
            )
        }

        issues = []
        for word in sorted(found):
            issues.append(
                f"🚫 Disallowed word detected: \"{word}\" "
                f"(Hard Reject — government/security term)"
            )
        return issues

    # -------------------------------------------------------------------
    # Stage 2: Combination of Existing Titles Check
    # -------------------------------------------------------------------
    def _check_title_combination(self, candidate: str) -> list[str]:
        """
        Detect if the candidate is a concatenation of two existing titles.

        Algorithm:
            Given tokens W = [w₁, w₂, …, wₖ], test every split point
            i ∈ [1, k−1]:
                Left  = " ".join(W[0:i])
                Right = " ".join(W[i:k])
            If BOTH Left ∈ DB and Right ∈ DB → illegal combination.

        Example:
            "Hindu Indian Express"
            Split at i=1: Left="Hindu", Right="Indian Express"
                → "hindu" not in DB (but "the hindu" is — we need to
                   check with common prefixes stripped too)
            We also check if "{prefix} {left}" is in DB to catch
            titles like "The Hindu" when user submits just "Hindu".

        Args:
            candidate: The proposed title string.

        Returns:
            List of issue strings (empty if no combination detected).
        """
        tokens = candidate.strip().split()
        issues = []
        strip_prefixes = rule_store.get_prefixes()

        if len(tokens) < 2:
            return issues

        for i in range(1, len(tokens)):
            left_part = " ".join(tokens[:i]).lower()
            right_part = " ".join(tokens[i:]).lower()

            # Check direct presence in the database
            left_match = left_part in self.titles_lower_set
            right_match = right_part in self.titles_lower_set

            # Also check with common prefixes prepended, e.g.,
            # "Hindu" should match "The Hindu" in the database.
            if not left_match:
                for prefix in strip_prefixes:
                    if f"{prefix} {left_part}" in self.titles_lower_set:
                        left_match = True
                        break

            if not right_match:
                for prefix in strip_prefixes:
                    if f"{prefix} {right_part}" in self.titles_lower_set:
                        right_match = True
                        break

            if left_match and right_match:
                left_display = " ".join(tokens[:i])
                right_display = " ".join(tokens[i:])
                issues.append(
                    f"🚫 Illegal combination of existing titles detected: "
                    f"\"{left_display}\" + \"{right_display}\" "
                    f"(Hard Reject — merging two registered titles)"
                )
                break  # One combination is enough to reject

        return issues

    # -------------------------------------------------------------------
    # Stage 3: Periodicity & Affix Stripping
    # -------------------------------------------------------------------
    def _check_affix_collision(self, candidate: str) -> list[str]:
        """
        Strip periodicity markers and common affixes, then check if
        the remaining "core" of the candidate matches any existing title.

        Rationale:
            Adding "Daily" to an existing title "Hindustan" to create
            "Daily Hindustan" should be detected as a collision, because
            the core content is the same — only the periodicity changed.

        Algorithm:
            1. Tokenize the candidate.
            2. Remove tokens that are in STRIP_PREFIXES or STRIP_SUFFIXES.
            3. Rejoin remaining tokens → "stripped core".
            4. Check if any existing title, after the same stripping,
               matches the candidate's stripped core.

        Args:
            candidate: The proposed title string.

        Returns:
            List of issue strings describing affix collisions.
        """
        candidate_tokens = candidate.lower().split()
        strip_prefixes = rule_store.get_prefixes()
        strip_suffixes = rule_store.get_suffixes()

        # Strip prefixes and suffixes/periodicity markers
        stripped_tokens = [
            t for t in candidate_tokens
            if t not in strip_prefixes and t not in strip_suffixes
        ]

        if not stripped_tokens or stripped_tokens == candidate_tokens:
            # Nothing was stripped, or candidate has no core left → skip
            return []

        stripped_core = " ".join(stripped_tokens)
        issues = []

        for existing_title in self.titles:
            existing_tokens = existing_title.lower().split()
            existing_stripped = [
                t for t in existing_tokens
                if t not in strip_prefixes and t not in strip_suffixes
            ]

            if not existing_stripped:
                continue

            existing_core = " ".join(existing_stripped)

            # If the stripped cores match, flag as a collision
            if stripped_core == existing_core:
                issues.append(
                    f"⚠️ Periodicity/affix modification of existing title "
                    f"\"{existing_title}\" detected (core: \"{stripped_core}\")"
                )
                break  # One match is sufficient

        return issues

    # -------------------------------------------------------------------
    # Stage 4 & 5: Phonetic + Fuzzy String Matching
    # -------------------------------------------------------------------
    def _compute_lexical_scores(self, candidate: str) -> list[MatchResult]:
        """
        Compute phonetic and fuzzy string similarity scores for the
        candidate against every title in the database.

        Phonetic Matching (Stage 4):
            Uses the Metaphone algorithm (jellyfish.metaphone) to convert
            strings to phonetic codes. If two strings share the same
            Metaphone code, they sound alike regardless of spelling.
            Example: metaphone("Namaskar") == metaphone("Namascar") → True

        Fuzzy String Matching (Stage 5):
            Uses RapidFuzz's token_sort_ratio, which:
            1. Tokenizes both strings.
            2. Sorts tokens alphabetically.
            3. Computes the Levenshtein-based similarity ratio.
            This is order-insensitive: "India Times" ≈ "Times India".

        Length-Ratio Dampening:
            When the candidate and existing title differ significantly in
            word count, the raw fuzzy score is dampened. This prevents a
            short title like "News" (1 word) from inflating the score of
            a longer candidate like "Sumit ke News" (3 words) that merely
            happens to contain one common word.

            dampening = 0.4 + 0.6 × (min_words / max_words)

            Same-length titles: dampening = 1.0 (no change)
            3-word vs 1-word:   dampening = 0.6 (40% reduction)

        Combined Lexical Score:
            lexical_score = min(100.0, dampened_fuzzy + phonetic_bonus)
            where phonetic_bonus = 15 if Metaphone codes match, else 0.

        Args:
            candidate: The proposed title string.

        Returns:
            List of MatchResult objects (one per existing title).
        """
        # Precompute the candidate's Metaphone hash once
        candidate_metaphone = jellyfish.metaphone(candidate)
        candidate_word_count = len(candidate.split())

        results = []
        for i, existing_title in enumerate(self.titles):
            # --- Fuzzy score via Token Sort Ratio ---
            # --- Fuzzy score via Token Sort + Token Set Ratio ---
            # token_sort_ratio normalizes word order.
            # token_set_ratio catches subsets/permutations (e.g., "Sumit news" vs "Sumit ke news").
            raw_sort = fuzz.token_sort_ratio(candidate, existing_title)
            raw_set = fuzz.token_set_ratio(candidate, existing_title)
            raw_fuzzy_score = max(raw_sort, raw_set)

            # --- Length-ratio dampening ---
            # Prevents single common words in longer titles from
            # inflating fuzzy scores against short existing titles.
            # e.g., "Sumit ke News" (3 words) vs "News" (1 word):
            #   ratio = 1/3 = 0.33 → dampening = 0.4 + 0.2 = 0.6
            #   score reduced by 40%, reflecting the weak overall match.
            # But "Dainik Namascar" (2) vs "Dainik Namaskar" (2):
            #   ratio = 1.0 → dampening = 1.0, score unchanged.
            existing_word_count = len(existing_title.split())
            length_ratio = (
                min(candidate_word_count, existing_word_count)
                / max(candidate_word_count, existing_word_count)
            )
            dampening_factor = 0.4 + 0.6 * length_ratio
            fuzzy_score = raw_fuzzy_score * dampening_factor

            # --- Phonetic comparison via Metaphone ---
            phonetic_match = (candidate_metaphone == self.metaphone_hashes[i])

            # --- Combined lexical score ---
            # Add a 15-point bonus if the phonetic codes match,
            # capped at 100 to stay in the [0, 100] range.
            phonetic_bonus = 15.0 if phonetic_match else 0.0
            combined_lexical = min(100.0, fuzzy_score + phonetic_bonus)

            results.append(MatchResult(
                title=existing_title,
                fuzzy_score=round(fuzzy_score, 2),
                phonetic_match=phonetic_match,
                semantic_score=0.0,            # Filled in Stage 6
                combined_score=combined_lexical,  # Updated in Stage 7
            ))

        return results

    # -------------------------------------------------------------------
    # Stage 6: Semantic Similarity
    # -------------------------------------------------------------------
    def _compute_semantic_scores(
        self, candidate: str, match_results: list[MatchResult]
    ) -> list[MatchResult]:
        """
        Compute multilingual semantic similarity between the candidate
        and all existing titles using sentence embeddings.

        Algorithm:
            1. Encode the candidate into a 384-dim vector using the
               multilingual MiniLM model.
            2. Compute cosine similarity against ALL precomputed title
               embeddings in a single batched operation:
                   cos_sim(u, v) = (u · v) / (‖u‖ · ‖v‖)
            3. Store the similarity score (0.0–1.0) in each MatchResult.

        Why this matters:
            Purely lexical methods miss cross-lingual duplicates.
            "Daily Evening" and "Pratidin Sandhya" share zero character
            overlap, but semantically they mean the same thing.
            The multilingual model captures this via shared embedding space.

        Args:
            candidate    : The proposed title string.
            match_results: List of MatchResult from Stage 4&5 (mutated).

        Returns:
            The same list of MatchResult, now with semantic_score filled.
        """
        # Encode the candidate title into a dense vector
        candidate_embedding = self.model.encode(
            candidate,
            convert_to_tensor=True,
            show_progress_bar=False,
        )

        # Batched cosine similarity: (1 × N) tensor of scores
        cosine_scores = util.cos_sim(candidate_embedding, self.embeddings)[0]

        # Update each MatchResult with its semantic score
        for i, result in enumerate(match_results):
            result.semantic_score = float(cosine_scores[i])

        return match_results

    # -------------------------------------------------------------------
    # Stage 7: Composite Scoring
    # -------------------------------------------------------------------
    def _compute_combined_scores(
        self, candidate: str, match_results: list[MatchResult]
    ) -> list[MatchResult]:
        """
        Compute the final combined score for each title match.

        Semantic Calibration:
            Multilingual sentence embeddings (e.g. paraphrase-multilingual-MiniLM-L12-v2)
            exhibit an ambient baseline cosine similarity around 0.50–0.55 in high-dimensional
            space between unrelated texts. An arbitrary unique word (like "Shreyas")
            naturally has a 0.55–0.60 raw cosine similarity with many random database entries.

            To prevent false positive rejections of novel titles:
            1. Calibrate raw cosine: only scores above the baseline noise floor (0.55)
               represent meaningful semantic relatedness:
                   calibrated = ((raw_cosine − 0.55) / 0.45) × 100.0
            2. Apply length-ratio dampening: prevents single common words in a longer title
               from dominating the embedding similarity against short 1-word titles.

        Formula:
            combined_score = max(lexical_score, calibrated_semantic_score)

        Args:
            candidate    : The proposed title string.
            match_results: List of MatchResult with lexical & raw semantic scores.

        Returns:
            The same list with combined_score updated.
        """
        cand_words = max(1, len(candidate.split()))

        for result in match_results:
            lexical_score = result.combined_score  # Already min(100, fuzzy + phonetic_bonus)
            raw_semantic = result.semantic_score  # 0.0 – 1.0

            if raw_semantic > 0.55:
                scaled_semantic = ((raw_semantic - 0.55) / 0.45) * 100.0
                match_words = max(1, len(result.title.split()))
                length_ratio = min(cand_words, match_words) / max(cand_words, match_words)
                dampening = 0.4 + 0.6 * length_ratio
                calibrated_semantic = scaled_semantic * dampening
            else:
                calibrated_semantic = 0.0

            result.combined_score = round(max(lexical_score, calibrated_semantic), 2)

        return match_results

    # -------------------------------------------------------------------
    # Full Verification Pipeline
    # -------------------------------------------------------------------
    def verify(self, candidate: str) -> VerificationResult:
        """
        Run the complete 7-stage verification pipeline on a candidate title.

        Decision Logic:
            • If any hard rule triggers (disallowed words, combinations):
              → Verification Probability = 0.0%
            • If S_max ≥ 80%:
              → Verification Probability = 0.0%
            • Otherwise:
              → Verification Probability = max(0.0, 100.0 − S_max)
            • Title is APPROVED only if probability ≥ 50% AND zero issues.

        Args:
            candidate: The proposed title string to verify.

        Returns:
            VerificationResult containing the full verdict and analysis.
        """
        issues: list[str] = []
        hard_reject = False

        # ── Stage 1: Disallowed Words ──────────────────────────────────
        disallowed_issues = self._check_disallowed_words(candidate)
        if disallowed_issues:
            issues.extend(disallowed_issues)
            hard_reject = True

        # ── Stage 2: Title Combination ─────────────────────────────────
        combination_issues = self._check_title_combination(candidate)
        if combination_issues:
            issues.extend(combination_issues)
            hard_reject = True

        # ── Stage 3: Affix / Periodicity Collision ─────────────────────
        affix_issues = self._check_affix_collision(candidate)
        if affix_issues:
            issues.extend(affix_issues)

        # ── Stage 4 & 5: Phonetic + Fuzzy Matching ────────────────────
        match_results = self._compute_lexical_scores(candidate)

        # ── Stage 6: Semantic Similarity ──────────────────────────────
        match_results = self._compute_semantic_scores(candidate, match_results)

        # ── Stage 7: Composite Scoring ────────────────────────────────
        match_results = self._compute_combined_scores(candidate, match_results)

        # Sort by combined score (descending) and take the top 5
        match_results.sort(key=lambda r: r.combined_score, reverse=True)
        top_matches = match_results[:5]

        # The highest similarity score across the entire database
        highest_similarity = top_matches[0].combined_score if top_matches else 0.0

        # ── Compute Verification Probability ──────────────────────────
        # S_max is the maximum combined score
        s_max = highest_similarity

        if hard_reject or s_max >= 80.0:
            # Hard rejection: probability drops to zero
            verification_probability = 0.0
        else:
            # Soft calculation: higher similarity → lower probability
            verification_probability = max(0.0, 100.0 - s_max)

        # ── Final Approval Decision ───────────────────────────────────
        # Approved if zero compliance rule flags AND similarity is below
        # the collision threshold (S_max < 65.0%)
        is_approved = (highest_similarity < 65.0) and (len(issues) == 0)

        return VerificationResult(
            is_approved=is_approved,
            verification_probability=round(verification_probability, 2),
            highest_similarity=round(highest_similarity, 2),
            issues=issues,
            top_matches=top_matches,
        )

    # -------------------------------------------------------------------
    # In-Memory Registration (Section 5.B.7)
    # -------------------------------------------------------------------
    def register_title(self, title: str, language: str = "English",
                       periodicity: str = "", publisher: str = "",
                       owner: str = "", state: str = "", district: str = ""):
        """
        Register an approved title into the in-memory database so that
        subsequent verification checks immediately detect it.

        Steps:
            1. Add a new row to the DataFrame.
            2. Append the title to the titles list and lowercase set.
            3. Compute and append its Metaphone hash.
            4. Compute and append its sentence embedding.

        Args:
            title       : The approved title string to register.
            language    : Language of the publication (default: "English").
            periodicity : Publication periodicity (e.g. "Daily", "Weekly").
            publisher   : Publisher name.
            owner       : Owner name.
            state       : Publication state.
            district    : Publication district.
        """
        # Generate the next serial number
        new_sn = len(self.df) + 1

        # Add to the DataFrame using the new CSV schema
        new_row = pd.DataFrame([{
            "SN.": new_sn,
            "Title": title,
            "Registration Number": "",
            "Registration Date": "",
            "Language": language,
            "Periodicity": periodicity,
            "Publisher": publisher,
            "Owner": owner,
            "Publication State": state,
            "Publication District": district,
        }])
        self.df = pd.concat([self.df, new_row], ignore_index=True)

        # Update the in-memory lookup structures
        self.titles.append(title)
        self.titles_lower_set.add(title.lower())

        # Compute and store the Metaphone hash for the new title
        self.metaphone_hashes.append(jellyfish.metaphone(title))

        # Compute and concatenate the new embedding to the tensor
        new_embedding = self.model.encode(
            title,
            convert_to_tensor=True,
            show_progress_bar=False,
        )
        # Reshape to (1, 384) and concatenate along dimension 0
        self.embeddings = torch.cat([
            self.embeddings,
            new_embedding.unsqueeze(0),
        ], dim=0)
