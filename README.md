# 🧠 Intelligent Candidate Ranker — Redrob Hackathon

> AI-powered candidate ranking system that goes beyond keyword matching to understand genuine role fit through career trajectory analysis, behavioral signal processing, and multi-dimensional scoring.

## 🎯 Problem Statement

Recruiters go through hundreds of profiles and still miss the right person — not because the talent isn't there, but because keyword filters can't see what actually matters. This system ranks candidates the way a great recruiter would.

## 🏗 Architecture

```
candidates.jsonl (100K profiles)
        │
        ▼
┌──────────────────────┐
│  Honeypot Detection  │  ← Filters ~80 impossible profiles
└──────┬───────────────┘
       │
       ▼
┌──────────────────────────────────────────────────┐
│           Multi-Signal Scoring Engine            │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ Title    │ │ Skill    │ │ Career Quality   │ │
│  │ Fit (20%)│ │Match(25%)│ │ Analysis  (20%)  │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐┌──────┐ │
│  │Experience│ │Behavioral│ │Location ││ Edu  │ │
│  │Fit (10%) │ │Signals   │ │Fit (5%) ││(5%)  │ │
│  │          │ │   (15%)  │ │         ││      │ │
│  └──────────┘ └──────────┘ └─────────┘└──────┘ │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
        ┌──────────────────┐
        │ Top-100 Selection│
        │ + Reasoning Gen  │
        └──────┬───────────┘
               │
               ▼
         submission.csv
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- pip

### Installation
```bash
pip install -r requirements.txt
```

### Run Ranking (CLI)
```bash
python rank.py --candidates ./candidates.jsonl --out ./submission.csv
```

### Run Web UI
```bash
streamlit run app.py
```

## 📊 Scoring Methodology

### 1. Title Fit (20%)
The JD explicitly warns: *"A candidate who has all the AI keywords but whose title is Marketing Manager is not a fit."* Our system maps titles to three tiers:
- **Strong fit**: AI Engineer, ML Engineer, Data Scientist, Search/Ranking Engineer
- **Moderate fit**: Software Engineer, Backend Engineer, Platform Engineer
- **No fit**: Marketing Manager, HR Manager, Content Writer, Graphic Designer

### 2. Skill Match (25%)
Goes beyond keyword counting by evaluating:
- **Proficiency levels** (expert/advanced vs beginner)
- **Duration of usage** (months worked with each skill)
- **Endorsement trust** (social proof)
- **Implicit skills** found in career descriptions (not just the skills list)

### 3. Career Quality (20%)
- Product company vs IT services background (JD explicitly disqualifies 100% services careers)
- Production AI/ML deployment signals in job descriptions
- Startup/small company experience
- Tenure stability (penalizes job-hopping every 1.5 years)

### 4. Experience Range (10%)
Sweet spot of 6-8 years (ideal), with 5-9 years as the acceptable range.

### 5. Behavioral Signals (15%)
- **Recency of activity**: Inactive for 6+ months = likely unavailable
- **Recruiter response rate**: The JD explicitly says to down-weight low responders
- **Notice period**: Prefers sub-30-day notice
- **Interview completion rate, GitHub activity, profile completeness**

### 6. Location (5%) + Education (5%)
India-based candidates preferred; Pune/Noida ideal. Education is a minor signal.

## 🕵️ Honeypot Detection

The dataset contains ~80 honeypot candidates with impossible profiles. Our detector catches:
- "Expert" proficiency in skills with 0 months of usage
- Career durations exceeding calendar time by 3x
- 10+ expert skills with zero endorsements
- Massive skill counts with all-zero durations

## ⚡ Performance

| Metric | Value |
|--------|-------|
| Runtime (100K candidates) | < 60 seconds |
| Memory usage | < 2 GB |
| GPU required | ❌ No |
| External API calls | ❌ None |

## 📁 Project Structure

```
├── rank.py                     # Core ranking engine (CLI)
├── app.py                      # Streamlit web UI
├── requirements.txt            # Dependencies
├── submission_metadata.yaml    # Hackathon metadata
├── README.md                   # This file
└── [PUB] India_runs_data_and_ai_challenge/
    └── India_runs_data_and_ai_challenge/
        ├── candidates.jsonl    # 100K candidate profiles
        ├── job_description.docx
        ├── candidate_schema.json
        ├── sample_candidates.json
        ├── sample_submission.csv
        ├── validate_submission.py
        └── ...
```

## 🔑 Key Design Decisions

1. **No external LLM calls** — Runs entirely offline within constraints
2. **Pure Python + heuristics over ML models** — Faster, more interpretable, more controllable
3. **Fact-based reasoning** — Every reasoning references actual profile data, no hallucination
4. **Title-first gating** — Non-technical roles are immediately capped, preventing keyword-stuffer traps
5. **Behavioral signals as multiplier** — Not just who looks good on paper, but who is actually reachable

## 📝 License

Built for the India Runs × Redrob Hackathon 2026.
