"""
generate_dataset.py — Synthetic Press Title Dataset Generator
=============================================================

Generates a realistic CSV dataset of 3,000+ Indian press titles by
combining prefixes, core names, and suffixes drawn from real Indian
newspaper naming conventions.

Combinatorial Strategy:
    title = [Prefix] + CoreName + [Suffix]
    Each combination is assigned a random language, category, and
    registration year, producing a diverse, multilingual dataset that
    mirrors the Press Registrar General of India's (PRGI) registry.

Output:
    dataset/titles_dataset.csv  (columns: title_id, title, language,
                                  category, registration_year)
"""

import os
import random
import itertools
import pandas as pd

# ---------------------------------------------------------------------------
# Vocabulary banks — drawn from real Indian press naming patterns
# ---------------------------------------------------------------------------

PREFIXES = [
    "The", "India", "Daily", "National", "Bharat",
    "New", "Modern", "Rashtriya", "Pradesh", "Nagar",
]

CORE_NAMES = [
    "Samachar", "News", "Times", "Herald", "Express",
    "Tribune", "Post", "Sandesh", "Vichar", "Darpan",
    "Prabhat", "Sandhya", "Jagran", "Bhaskar", "Patrika",
    "Awaaz", "Vartha", "Kesari", "Prakash",
    # Multi-word core names (kept intact as single units)
    "Dainik Namaskar", "Pratidin Sandhya",
    "The Hindu", "Indian Express",
]

SUFFIXES = [
    "Weekly", "Monthly", "Daily", "Today", "Live",
    "Report", "Journal", "Bulletin", "Update",
]

LANGUAGES = [
    "English", "Hindi", "Marathi", "Gujarati", "Bengali",
    "Tamil", "Telugu", "Kannada", "Malayalam", "Punjabi", "Urdu",
]

CATEGORIES = [
    "Newspaper", "Magazine", "Periodical",
    "Journal", "Bulletin", "Digest",
]

# Titles that MUST appear in the dataset for the validation test cases
SEED_TITLES = [
    "The Hindu",
    "Indian Express",
    "Dainik Namaskar",
    "Pratidin Sandhya",
    "Times of India",
    "Hindustan",
    "Navbharat",
]

# ---------------------------------------------------------------------------
# Deterministic seed for reproducibility
# ---------------------------------------------------------------------------
random.seed(42)


def generate_titles() -> list[str]:
    """
    Build a large, unique set of titles via combinatorial expansion.

    Strategy:
        1. Core-only titles            (23 titles)
        2. Prefix + Core               (10 × 23 = 230 combos)
        3. Core + Suffix               (23 × 9  = 207 combos)
        4. Prefix + Core + Suffix      (10 × 23 × 9 = 2,070 combos)
        5. Seed titles (guaranteed)     (7 titles)

    Total unique ≈ 2,530+ (after dedup).  We top up to 3,000+ by creating
    additional variations with double-prefix and regional modifiers.
    """
    titles_set: set[str] = set()

    # --- Layer 1: Core names only ---
    for core in CORE_NAMES:
        titles_set.add(core)

    # --- Layer 2: Prefix + Core ---
    for prefix, core in itertools.product(PREFIXES, CORE_NAMES):
        titles_set.add(f"{prefix} {core}")

    # --- Layer 3: Core + Suffix ---
    for core, suffix in itertools.product(CORE_NAMES, SUFFIXES):
        titles_set.add(f"{core} {suffix}")

    # --- Layer 4: Prefix + Core + Suffix ---
    for prefix, core, suffix in itertools.product(PREFIXES, CORE_NAMES, SUFFIXES):
        titles_set.add(f"{prefix} {core} {suffix}")

    # --- Layer 5: Regional modifiers for more diversity ---
    regional_modifiers = [
        "Mumbai", "Delhi", "Chennai", "Kolkata", "Pune",
        "Lucknow", "Jaipur", "Hyderabad", "Bangalore", "Ahmedabad",
        "Chandigarh", "Bhopal", "Patna", "Ranchi", "Guwahati",
    ]
    for city, core in itertools.product(regional_modifiers, CORE_NAMES):
        titles_set.add(f"{city} {core}")

    # --- Layer 6: City + Core + Suffix for additional diversity ---
    for city, core, suffix in itertools.product(
        regional_modifiers[:5], CORE_NAMES[:10], SUFFIXES[:4]
    ):
        titles_set.add(f"{city} {core} {suffix}")

    # --- Layer 7: Seed titles (guaranteed presence) ---
    for seed in SEED_TITLES:
        titles_set.add(seed)

    return sorted(titles_set)


def build_dataframe(titles: list[str]) -> pd.DataFrame:
    """
    Assign metadata (language, category, year) to each generated title
    and return a structured DataFrame with a sequential title_id.
    """
    records = []
    for idx, title in enumerate(titles, start=1):
        records.append({
            "title_id": f"T{idx:05d}",
            "title": title,
            "language": random.choice(LANGUAGES),
            "category": random.choice(CATEGORIES),
            "registration_year": random.randint(2000, 2024),
        })
    return pd.DataFrame(records)


def main():
    """Entry point: generate titles, build DataFrame, and write CSV."""
    titles = generate_titles()
    df = build_dataframe(titles)

    # Ensure the output directory exists
    os.makedirs("dataset", exist_ok=True)
    output_path = os.path.join("dataset", "titles_dataset.csv")
    df.to_csv(output_path, index=False)

    # --- Summary statistics ---
    print(f"[OK] Dataset generated successfully!")
    print(f"   Total unique titles : {len(df)}")
    print(f"   Languages           : {df['language'].nunique()}")
    print(f"   Categories          : {df['category'].nunique()}")
    print(f"   Year range          : {df['registration_year'].min()} - {df['registration_year'].max()}")
    print(f"   Output file         : {output_path}")

    # Verify seed titles are present
    existing_titles = set(df["title"].values)
    print(f"\n[*] Seed title verification:")
    for seed in SEED_TITLES:
        status = "[OK] Found" if seed in existing_titles else "[!!] MISSING"
        print(f"   {status}: \"{seed}\"")


if __name__ == "__main__":
    main()
