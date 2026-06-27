# 🧠 Intelligent Candidate Ranker — Pitch Deck Content
## India Runs × Redrob Data & AI Challenge 2026

Use this content to build your PPT/PDF presentation. Each section below = one slide.

---

## SLIDE 1: Title Slide

**🧠 Intelligent Candidate Ranker**

*Beyond keywords — understanding who genuinely fits the role*

Team: [Your Team Name]  
India Runs × Redrob Data & AI Challenge 2026

---

## SLIDE 2: The Problem

### Recruiters Are Drowning in Profiles

- **100,000+ candidate profiles** to evaluate per role
- Traditional keyword filters surface **false positives** (Marketing Managers with "AI" keywords) and miss **hidden gems** (Backend Engineers who built ranking systems)
- Behavioral signals (response rate, recency, availability) are **completely ignored** by keyword matching
- Result: Recruiters spend hours reviewing irrelevant profiles and still miss the right person

> *"The right answer is NOT 'find candidates whose skills section contains the most AI keywords.' That's a trap."*  
> — Redrob Job Description

---

## SLIDE 3: Our Approach

### Think Like a Great Recruiter, Not a Search Engine

We built a **multi-signal hybrid scoring engine** that evaluates candidates the way an experienced recruiter would:

| Signal | What a Great Recruiter Checks | Our System Does This |
|--------|-------------------------------|---------------------|
| **Title** | "Is this person actually in AI/ML?" | Maps titles to fit tiers, catches keyword stuffers |
| **Skills** | "Do they have REAL depth, not just buzzwords?" | Weighs proficiency × duration × endorsements |
| **Career** | "Product company? Shipped real systems?" | Analyzes company types, production deployment signals |
| **Experience** | "In the 5-9 year sweet spot?" | Gaussian-like scoring around the ideal range |
| **Behavioral** | "Are they actually available and responsive?" | Processes 23 Redrob platform signals |
| **Location** | "Can we actually hire them?" | India-first, Pune/Noida preferred |

---

## SLIDE 4: Architecture

### System Architecture

```
candidates.jsonl (100K profiles)
        │
        ▼
┌──────────────────────┐
│  HONEYPOT DETECTOR   │ ← Filters ~80 impossible profiles
└──────────┬───────────┘
           │
┌──────────▼──────────────────────────┐
│      MULTI-SIGNAL SCORER           │
│                                     │
│  Title Fit ─────────── 20%         │
│  Skill Match ────────── 25%        │
│  Career Quality ─────── 20%        │
│  Experience Range ───── 10%        │
│  Behavioral Signals ─── 15%        │
│  Location Fit ────────── 5%        │
│  Education ──────────── 5%         │
└──────────┬─────────────────────────┘
           │
┌──────────▼───────────┐
│  TOP-100 SELECTOR    │
│  + REASONING GEN     │
└──────────┬───────────┘
           │
     submission.csv
```

**Key:** No external LLMs. No GPUs. No network calls. Pure Python running in < 60 seconds.

---

## SLIDE 5: Honeypot Detection

### Catching Fake Profiles Before They Pollute Rankings

The dataset contains **~80 honeypot candidates** with subtly impossible profiles:

| Red Flag | Example | Detection |
|----------|---------|-----------|
| Expert skills with zero usage | "Expert in PyTorch" — 0 months | Proficiency vs duration cross-check |
| Impossible timelines | 8 years at a 3-year-old company | Date math validation |
| Unearned credibility | 10+ expert skills, 0 endorsements | Endorsement trust analysis |
| Mass keyword stuffing | 20+ skills all at 0 duration | Aggregate zero-duration count |

**Rule:** Multiple red flags (≥2) → honeypot → excluded from ranking.

---

## SLIDE 6: Title-First Gating — The Anti-Keyword-Stuffing Strategy

### Why Title Matters More Than Skills

The JD warns: *"A Marketing Manager with all the AI keywords is NOT a fit."*

**Non-linear penalty:** If title score = 0 → composite capped at 0.15

This means a Marketing Manager with perfect AI skills **still scores below any real AI Engineer**.

| Tier | Examples | Score |
|------|----------|-------|
| 🟢 Strong Fit | AI Engineer, ML Engineer, Data Scientist | 0.85 – 1.0 |
| 🟡 Moderate Fit | Software Engineer, Backend Engineer | 0.55 |
| 🔴 No Fit | Marketing Manager, HR Manager, Content Writer | 0.0 (capped at 0.15 composite) |

---

## SLIDE 7: Skill Scoring — Beyond Keyword Counting

### Trust Score = Proficiency × Duration × Endorsements

```
trust = proficiency_weight × 0.5
      + min(duration / 36 months, 1.0) × 0.3
      + min(endorsements / 20, 1.0) × 0.2
```

**Example:**
- Candidate A: "Python (expert, 60 months, 45 endorsements)" → Trust: **0.97**
- Candidate B: "Python (beginner, 0 months, 0 endorsements)" → Trust: **0.10**

Same keyword. **Completely different signal.** We also detect implicit skills from career descriptions.

---

## SLIDE 8: Career Trajectory & Behavioral Signals

### Career Quality (20%):
- **Product company vs IT services** (JD explicitly filters pure services careers)
- **Production AI deployment** keywords in job descriptions
- **Tenure stability** (penalizes job-hopping every 1.5 years)

### Behavioral Signals (15%):
Per the JD: *"A perfect-on-paper candidate who hasn't logged in for 6 months... is not actually available."*

| Signal | Impact |
|--------|--------|
| Inactive 180+ days | -25% penalty |
| Response rate < 15% | -15% penalty |
| Response rate > 70% | +12% bonus |
| Notice ≤ 30 days | +8% bonus |
| Open to work | +5% bonus |

---

## SLIDE 9: Performance & Constraints

### Built for Production, Not Demos

| Constraint | Required | Ours |
|-----------|----------|------|
| Runtime | ≤ 5 min | **< 60 sec** ✅ |
| Memory | ≤ 16 GB | **< 2 GB** ✅ |
| Compute | CPU only | **Pure Python** ✅ |
| Network | Offline | **No API calls** ✅ |
| Disk | ≤ 5 GB | **< 100 MB** ✅ |

**Why heuristics over ML?**
1. Every score is **explainable** to a recruiter
2. Weights are **tunable** by domain experts
3. System is **auditable** — trace exactly why any candidate ranks where it does

---

## SLIDE 10: Web UI Demo

### Interactive Dashboard (Streamlit)

- **🚀 One-click ranking** — Upload candidates, run scoring, download CSV
- **📊 Results dashboard** — Sortable table with score breakdown visualizations
- **👤 Candidate explorer** — Drill into any profile with score decomposition
- **📥 Export** — Submit-ready CSV in exact hackathon format

```bash
pip install -r requirements.txt
streamlit run app.py
```

*(Include screenshots from the running app)*

---

## SLIDE 11: Key Insights

### What Makes This Different

1. **Title-gating beats keyword-matching** — Catches the JD's trap of keyword-stuffed non-technical roles
2. **Skill depth > skill count** — Trust formula (proficiency × duration × endorsements) is more informative than counting keywords
3. **Career trajectory tells the real story** — IT services + AI keywords ≠ AI engineer
4. **Behavioral signals are the hidden weapon** — Availability and engagement predict actual hireability
5. **Honeypots are solvable** — Simple cross-validation catches fakes naturally

---

## SLIDE 12: Thank You

### 🧠 Intelligent Candidate Ranker

**Making hiring smarter — one ranking at a time.**

Team: [Your Team Name]  
GitHub: [Your Repo URL]

*Built for the India Runs × Redrob Hackathon 2026*
