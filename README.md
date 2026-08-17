# PSS06 — Automated Press Title Verification System

> **Smart India Hackathon 2026 — Problem Statement PSS06**
> An online system to automatically verify new title submissions by checking for similarities with existing titles.

---

## 🏗️ Architecture Overview

The system employs a **7-stage verification pipeline**:

| Stage | Technique | Library |
|-------|-----------|---------|
| 1 | Disallowed Word Filter (token-level) | Python `set` |
| 2 | Title Combination Detector | Custom split-point algorithm |
| 3 | Periodicity & Affix Stripping | Custom |
| 4 | Phonetic Matching (Metaphone) | `jellyfish` |
| 5 | Fuzzy String Matching (Token Sort Ratio) | `rapidfuzz` |
| 6 | Multilingual Semantic Similarity | `sentence-transformers` |
| 7 | Composite Scoring & Probability Engine | Custom formula |

```
Submitted Title → [1] Disallowed Words → [2] Combination Check → [3] Affix Strip
    → [4] Phonetic Match → [5] Fuzzy Match → [6] Semantic Match → [7] Score → Result
```

---

## 📦 Project Structure

```
title_verification_system/
├── dataset/
│   └── titles_dataset.csv         # Generated synthetic dataset (3,000+ titles)
├── app.py                         # Streamlit UI dashboard
├── matcher.py                     # Multi-stage verification engine
├── generate_dataset.py            # Synthetic dataset generator
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

---

## 🚀 Quick Start

### 1. Create & Activate Virtual Environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Generate the Dataset

```bash
python generate_dataset.py
```

This creates `dataset/titles_dataset.csv` with 3,000+ synthetic press titles.

### 4. Launch the Dashboard

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`.

---

## 🧪 Validation Test Cases

The pipeline is designed to pass these 6 scenarios:

| # | Test Input | Expected Output | Triggered Rule |
|---|-----------|----------------|----------------|
| 1 | `"Delhi Police Times"` | **Rejected (0%)** | Disallowed word (`"police"`) |
| 2 | `"Hindu Indian Express"` | **Rejected (0%)** | Illegal combination of 2 titles |
| 3 | `"Dainik Namascar"` | **Rejected (0–20%)** | Phonetic & fuzzy match |
| 4 | `"Daily Evening"` | **Rejected (0–25%)** | Multilingual semantic equivalence |
| 5 | `"Daily Hindustan"` | **Rejected (0–30%)** | Periodicity modification |
| 6 | `"Zenith Quantum Gazette"` | **Verified (>85%)** | Unique valid submission |

---

## 🔧 Tech Stack

- **Frontend:** Streamlit
- **Fuzzy Matching:** RapidFuzz (Token Sort Ratio)
- **Phonetic Hashing:** Jellyfish (Metaphone)
- **Semantic Similarity:** Sentence-Transformers (paraphrase-multilingual-MiniLM-L12-v2)
- **Data Processing:** Pandas
- **Deep Learning Backend:** PyTorch

---

## 📐 Scoring Formula

```
Lexical Score   = min(100, fuzzy_score + (15 if metaphone_match else 0))
Semantic Score  = cosine_similarity × 100
S_max           = max(Lexical Score, Semantic Score)

If hard_reject OR S_max ≥ 80:
    Verification Probability = 0%
Else:
    Verification Probability = max(0, 100 − S_max)

Title APPROVED if: Probability ≥ 60% AND zero issues raised
```

---

## 👥 Team

Built for SIH 2026 — Problem Statement PSS06
