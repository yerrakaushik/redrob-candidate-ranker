"""
rank.py — Intelligent Candidate Ranking Engine
================================================
Redrob Hackathon: Intelligent Candidate Discovery & Ranking Challenge

Architecture:
  1. Stream 100K candidates from JSONL (memory-efficient)
  2. Multi-signal scoring: Role Fit + Skill Match + Career Quality + Behavioral Signals
  3. Honeypot detection and filtering
  4. Top-100 selection with specific, fact-based reasoning generation
  5. Output valid submission CSV

Constraints:
  - CPU only, no GPU
  - ≤ 5 minutes wall-clock
  - ≤ 16 GB RAM
  - No external API calls
  
Usage:
  python rank.py --candidates ./candidates.jsonl --out ./submission.csv
"""

import argparse
import csv
import json
import math
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, date

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION: JD-derived weights and parameters
# ─────────────────────────────────────────────────────────────────────────────

# The JD is for: Senior AI Engineer — Founding Team at Redrob AI
# Key requirements distilled from the JD:
#   - 5-9 years experience (sweet spot 6-8)
#   - Production embeddings/retrieval systems
#   - Vector DB / hybrid search infra operational experience
#   - Strong Python
#   - Evaluation frameworks for ranking (NDCG, MRR, MAP)
#   - LLM fine-tuning (nice-to-have)
#   - Learning-to-rank (nice-to-have)
#   - Product company background (NOT pure services)
#   - Recent code-writing (not pure architecture/management)
#   - Location: India (Pune/Noida preferred, tier-1 cities OK)
#   - Behavioral: active, responsive, available

# ── Title relevance mapping ──
# The JD explicitly says a "Marketing Manager" with AI keywords is NOT a fit.
# We must reason about what the title MEANS, not just keyword-match.

STRONG_FIT_TITLES = {
    "ai engineer", "ml engineer", "machine learning engineer",
    "senior ai engineer", "senior ml engineer", "senior machine learning engineer",
    "lead ai engineer", "lead ml engineer", "staff ai engineer", "staff ml engineer",
    "applied scientist", "applied ml scientist", "research engineer",
    "nlp engineer", "search engineer", "ranking engineer", "retrieval engineer",
    "recommendation engineer", "data scientist", "senior data scientist",
    "ml platform engineer", "mlops engineer", "ai/ml engineer",
    "deep learning engineer", "ai architect", "ml architect",
    "principal engineer", "staff engineer",
}

MODERATE_FIT_TITLES = {
    "software engineer", "senior software engineer", "backend engineer",
    "senior backend engineer", "full stack engineer", "senior full stack engineer",
    "platform engineer", "data engineer", "senior data engineer",
    "tech lead", "engineering manager", "lead engineer",
    "python developer", "senior python developer",
    "software developer", "senior software developer",
}

NO_FIT_TITLES = {
    "marketing manager", "hr manager", "operations manager",
    "content writer", "graphic designer", "product manager",
    "business analyst", "sales manager", "account manager",
    "project manager", "scrum master", "qa analyst",
    "manual tester", "customer support", "recruiter",
    "finance manager", "admin", "executive assistant",
    "ui designer", "ux designer", "ui/ux designer",
}

# ── Core AI/ML skills the JD explicitly requires ──
MUST_HAVE_SKILLS = {
    # Embeddings & retrieval
    "sentence-transformers", "sentence transformers", "openai embeddings",
    "bge", "e5", "embeddings", "word2vec", "fasttext", "bert",
    "transformers", "huggingface", "hugging face",
    # Vector DBs / hybrid search
    "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
    "elasticsearch", "faiss", "vector database", "vector search",
    "hybrid search", "semantic search",
    # Ranking & retrieval
    "ranking", "information retrieval", "search", "recommendation",
    "bm25", "tf-idf", "learning to rank", "reranking", "re-ranking",
    # Python
    "python",
    # Evaluation
    "ndcg", "mrr", "map", "a/b testing", "evaluation",
    # LLMs
    "llm", "large language model", "gpt", "fine-tuning",
    "lora", "qlora", "peft", "rag",
    # NLP
    "nlp", "natural language processing", "text classification",
    "named entity recognition", "ner", "spacy", "nltk",
    # ML general
    "machine learning", "deep learning", "neural network",
    "pytorch", "tensorflow", "keras", "scikit-learn", "xgboost",
}

NICE_TO_HAVE_SKILLS = {
    "lora", "qlora", "peft", "fine-tuning",
    "xgboost", "lightgbm", "catboost",
    "langchain", "llamaindex", "llama index",
    "docker", "kubernetes", "aws", "gcp", "azure",
    "mlflow", "weights & biases", "wandb",
    "airflow", "spark", "kafka",
    "redis", "postgresql", "mongodb",
    "fastapi", "flask", "django",
    "git", "ci/cd", "github actions",
    "distributed systems", "microservices",
}

# ── IT Services / consulting companies (JD explicitly disqualifies) ──
SERVICES_COMPANIES = {
    "tcs", "tata consultancy services", "infosys", "wipro",
    "accenture", "cognizant", "capgemini", "hcl", "hcl technologies",
    "tech mahindra", "mindtree", "mphasis", "l&t infotech",
    "lt infotech", "lti", "ltimindtree", "hexaware",
    "cyient", "zensar", "persistent systems", "sonata software",
    "niit technologies", "coforge", "birlasoft", "mastek",
    "atos", "dxc technology", "deloitte", "kpmg", "ey", "pwc",
    "ibm consulting", "ibm services",
}

# ── Indian tier-1 cities (JD prefers India, especially Pune/Noida) ──
PREFERRED_LOCATIONS = {"pune", "noida", "delhi", "new delhi", "delhi ncr", "gurgaon", "gurugram"}
TIER1_INDIA = {
    "mumbai", "bangalore", "bengaluru", "hyderabad", "chennai",
    "kolkata", "ahmedabad", "jaipur",
}

# ── Scoring weights ──
W_TITLE = 0.20        # Title/role relevance
W_SKILLS = 0.25       # Skill match quality
W_CAREER = 0.20       # Career trajectory & company quality
W_EXPERIENCE = 0.10   # Years of experience sweet spot
W_BEHAVIORAL = 0.15   # Platform engagement & availability
W_LOCATION = 0.05     # Location fit
W_EDUCATION = 0.05    # Education signal (minor)


# ─────────────────────────────────────────────────────────────────────────────
# HONEYPOT DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_honeypot(candidate: dict) -> tuple[bool, str]:
    """
    Detect honeypot candidates with subtly impossible profiles.
    Returns (is_honeypot, reason).
    
    Honeypot signals per the spec (~80 in the dataset):
    - 8+ years at a company founded 3 years ago
    - "expert" proficiency in 10+ skills with 0 duration_months
    - Impossible timeline inconsistencies
    """
    flags = []
    strong_flags = 0  # A single strong flag can mark a honeypot
    
    skills = candidate.get("skills", [])
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    career = candidate.get("career_history", [])
    
    # Check 1: Expert skills with zero duration (strong signal)
    expert_zero_duration = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and s.get("duration_months", 1) == 0
    )
    if expert_zero_duration >= 5:
        strong_flags += 1
        flags.append(f"{expert_zero_duration} 'expert' skills with 0 months usage")
    elif expert_zero_duration >= 2:
        flags.append(f"{expert_zero_duration} 'expert' skills with 0 months usage")
    
    # Check 2: Total skills with zero duration
    zero_duration_skills = sum(
        1 for s in skills if s.get("duration_months", 1) == 0
    )
    if zero_duration_skills >= 6:
        strong_flags += 1
        flags.append(f"{zero_duration_skills} skills with 0 months duration")
    elif zero_duration_skills >= 4:
        flags.append(f"{zero_duration_skills} skills with 0 months duration")
    
    # Check 3: Too many expert skills relative to experience
    expert_count = sum(1 for s in skills if s.get("proficiency") == "expert")
    if expert_count >= 10 and yoe < 5:
        strong_flags += 1
        flags.append(f"{expert_count} expert-level skills with only {yoe} years experience")
    elif expert_count >= 8 and yoe < 4:
        flags.append(f"{expert_count} expert skills with only {yoe}y experience")
    
    # Check 4: Career history impossible timelines
    for job in career:
        duration = job.get("duration_months", 0)
        start = job.get("start_date", "")
        end = job.get("end_date", "")
        if start and end and duration > 0:
            try:
                s = datetime.strptime(start, "%Y-%m-%d")
                e = datetime.strptime(end, "%Y-%m-%d")
                actual_months = (e.year - s.year) * 12 + (e.month - s.month)
                # If claimed duration is more than 2x actual calendar time
                if actual_months > 0 and duration > actual_months * 2:
                    flags.append(
                        f"Claims {duration} months at {job.get('company','')} "
                        f"but dates span only {actual_months} months"
                    )
                    if duration > actual_months * 3:
                        strong_flags += 1
            except (ValueError, TypeError):
                pass
    
    # Check 5: Expert skills with zero endorsements
    zero_endorsement_experts = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and s.get("endorsements", 0) == 0
    )
    if zero_endorsement_experts >= 5:
        flags.append(f"{zero_endorsement_experts} expert skills with 0 endorsements")
    elif zero_endorsement_experts >= 3 and len(skills) >= 12:
        flags.append(f"{zero_endorsement_experts} expert skills with 0 endorsements")
    
    # Check 6: YoE impossibly high for career history dates
    if career:
        earliest_start = None
        for job in career:
            start = job.get("start_date", "")
            if start:
                try:
                    s = datetime.strptime(start, "%Y-%m-%d")
                    if earliest_start is None or s < earliest_start:
                        earliest_start = s
                except (ValueError, TypeError):
                    pass
        if earliest_start:
            actual_career_months = (datetime(2026, 6, 15) - earliest_start).days / 30.44
            claimed_months = yoe * 12
            if claimed_months > actual_career_months * 1.5 and claimed_months > 60:
                flags.append(
                    f"Claims {yoe}y experience but career history starts only "
                    f"{actual_career_months/12:.1f} years ago"
                )
    
    # Decision: strong flag alone, or 2+ regular flags
    is_honeypot = strong_flags >= 1 or len(flags) >= 2
    reason = "; ".join(flags) if flags else ""
    return is_honeypot, reason


# ─────────────────────────────────────────────────────────────────────────────
# SCORING FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def score_title(candidate: dict) -> tuple[float, list[str]]:
    """Score based on current title relevance. 0-1 scale."""
    notes = []
    title = candidate.get("profile", {}).get("current_title", "").lower().strip()
    headline = candidate.get("profile", {}).get("headline", "").lower()
    
    # Check career history titles too
    career_titles = [
        job.get("title", "").lower().strip()
        for job in candidate.get("career_history", [])
    ]
    
    # Direct title match
    if title in STRONG_FIT_TITLES:
        notes.append(f"Strong title match: {candidate['profile']['current_title']}")
        return 1.0, notes
    
    # Check if any strong-fit keywords appear in headline or title
    strong_keywords_in_title = any(
        kw in title or kw in headline
        for kw in ["ai", "ml", "machine learning", "nlp", "search", "ranking",
                    "retrieval", "data scien", "deep learning", "applied scien"]
    )
    
    if strong_keywords_in_title:
        notes.append(f"AI/ML-adjacent title: {candidate['profile']['current_title']}")
        return 0.85, notes
    
    if title in MODERATE_FIT_TITLES:
        notes.append(f"Moderate title fit: {candidate['profile']['current_title']}")
        return 0.55, notes
    
    # Check if any career history had strong titles
    had_strong_title = any(t in STRONG_FIT_TITLES for t in career_titles)
    had_strong_kw = any(
        any(kw in t for kw in ["ai", "ml", "machine learning", "data scien"])
        for t in career_titles
    )
    
    if had_strong_title or had_strong_kw:
        notes.append(f"Previous AI/ML role in career history")
        return 0.5, notes
    
    if title in NO_FIT_TITLES:
        notes.append(f"Non-technical role: {candidate['profile']['current_title']}")
        return 0.0, notes
    
    # Default for unknown titles
    notes.append(f"Unclear role fit: {candidate['profile']['current_title']}")
    return 0.2, notes


def score_skills(candidate: dict) -> tuple[float, list[str]]:
    """Score based on skill match quality. Considers proficiency AND duration."""
    notes = []
    skills = candidate.get("skills", [])
    
    if not skills:
        return 0.0, ["No skills listed"]
    
    # Build a lookup: skill_name_lower -> skill_obj
    skill_map = {}
    for s in skills:
        name = s.get("name", "").lower().strip()
        skill_map[name] = s
    
    # Also check in summary and career descriptions for implicit skills
    summary = candidate.get("profile", {}).get("summary", "").lower()
    career_text = " ".join(
        job.get("description", "").lower()
        for job in candidate.get("career_history", [])
    ).lower()
    full_text = summary + " " + career_text
    
    # Score must-have skills
    must_have_matches = []
    must_have_implicit = []
    
    for skill_name in MUST_HAVE_SKILLS:
        if skill_name in skill_map:
            s = skill_map[skill_name]
            prof = s.get("proficiency", "beginner")
            dur = s.get("duration_months", 0)
            endorse = s.get("endorsements", 0)
            
            # Weight by proficiency and duration (not just presence)
            prof_weight = {"expert": 1.0, "advanced": 0.8, "intermediate": 0.5, "beginner": 0.2}.get(prof, 0.2)
            dur_weight = min(dur / 36.0, 1.0)  # Normalize to 3 years
            trust = prof_weight * 0.5 + dur_weight * 0.3 + min(endorse / 20.0, 1.0) * 0.2
            
            must_have_matches.append((skill_name, trust))
        elif skill_name in full_text:
            must_have_implicit.append(skill_name)
    
    # Score nice-to-have skills
    nice_matches = []
    for skill_name in NICE_TO_HAVE_SKILLS:
        if skill_name in skill_map or skill_name in full_text:
            nice_matches.append(skill_name)
    
    # Calculate composite skill score
    if must_have_matches:
        avg_trust = sum(t for _, t in must_have_matches) / len(must_have_matches)
        coverage = min(len(must_have_matches) / 8.0, 1.0)  # Expect ~8 core skills
        skill_score = coverage * 0.6 + avg_trust * 0.3
    else:
        skill_score = 0.0
    
    # Implicit skill mentions (from summary/career descriptions)
    implicit_bonus = min(len(must_have_implicit) / 5.0, 1.0) * 0.15
    skill_score += implicit_bonus
    
    # Nice-to-have bonus
    nice_bonus = min(len(nice_matches) / 5.0, 1.0) * 0.1
    skill_score += nice_bonus
    
    skill_score = min(skill_score, 1.0)
    
    # Build notes
    if must_have_matches:
        top_skills = sorted(must_have_matches, key=lambda x: x[1], reverse=True)[:5]
        skill_names = [s[0] for s in top_skills]
        notes.append(f"Core skills: {', '.join(skill_names)}")
    if must_have_implicit:
        notes.append(f"Implicit skills from career: {', '.join(must_have_implicit[:3])}")
    if not must_have_matches and not must_have_implicit:
        notes.append("No relevant AI/ML skills found")
    
    return skill_score, notes


def score_career(candidate: dict) -> tuple[float, list[str]]:
    """
    Score career trajectory:
    - Product company vs IT services
    - Shipped production systems
    - Career progression
    - Recency of hands-on work
    """
    notes = []
    career = candidate.get("career_history", [])
    profile = candidate.get("profile", {})
    
    if not career:
        return 0.0, ["No career history"]
    
    current_company = profile.get("current_company", "").lower().strip()
    current_industry = profile.get("current_industry", "").lower().strip()
    company_size = profile.get("current_company_size", "")
    
    score = 0.5  # Start neutral
    
    # ── Company type analysis ──
    # Check if ENTIRE career is at services companies (JD disqualifier)
    all_services = all(
        job.get("company", "").lower().strip() in SERVICES_COMPANIES
        or job.get("industry", "").lower().strip() in {"it services", "consulting", "outsourcing"}
        for job in career
    )
    
    has_product_exp = any(
        job.get("industry", "").lower().strip() not in {"it services", "consulting", "outsourcing"}
        and job.get("company", "").lower().strip() not in SERVICES_COMPANIES
        for job in career
    )
    
    if all_services:
        score -= 0.35
        notes.append("Entire career at IT services/consulting companies")
    elif current_company in SERVICES_COMPANIES:
        if has_product_exp:
            score -= 0.05
            notes.append(f"Currently at {profile.get('current_company','')}, but has prior product company experience")
        else:
            score -= 0.25
            notes.append(f"Currently at services company: {profile.get('current_company','')}")
    elif has_product_exp:
        score += 0.15
        notes.append("Product company experience in career history")
    
    # ── Production experience signals ──
    production_keywords = [
        "production", "deployed", "shipped", "scaled", "users",
        "real-time", "pipeline", "infrastructure", "system design",
        "latency", "throughput", "api", "microservice",
    ]
    
    ai_production_keywords = [
        "ranking system", "recommendation system", "search system",
        "embedding", "vector", "retrieval", "model serving",
        "ml pipeline", "model deployment", "feature store",
        "a/b test", "online experiment",
    ]
    
    career_descriptions = " ".join(
        job.get("description", "").lower() for job in career
    )
    
    prod_hits = sum(1 for kw in production_keywords if kw in career_descriptions)
    ai_prod_hits = sum(1 for kw in ai_production_keywords if kw in career_descriptions)
    
    if ai_prod_hits >= 2:
        score += 0.25
        notes.append("Career shows production AI/ML system deployment")
    elif prod_hits >= 3:
        score += 0.1
        notes.append("Career shows production software deployment experience")
    
    # ── Company size diversity (startup experience valued) ──
    small_company_exp = any(
        job.get("company_size", "") in {"1-10", "11-50", "51-200"}
        for job in career
    )
    if small_company_exp:
        score += 0.05
        notes.append("Has startup/small company experience")
    
    # ── Job hopping check (JD dislikes title-chasers changing every 1.5 years) ──
    if len(career) >= 3:
        avg_tenure = sum(job.get("duration_months", 0) for job in career) / len(career)
        if avg_tenure < 18:
            score -= 0.1
            notes.append(f"Short average tenure ({avg_tenure:.0f} months)")
        elif avg_tenure >= 30:
            score += 0.05
            notes.append(f"Stable tenure (avg {avg_tenure:.0f} months)")
    
    score = max(0.0, min(1.0, score))
    return score, notes


def score_experience(candidate: dict) -> tuple[float, list[str]]:
    """Score years of experience. Sweet spot: 5-9 years, ideal 6-8."""
    notes = []
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    
    if 6 <= yoe <= 8:
        score = 1.0
        notes.append(f"{yoe} years experience — ideal range for this role")
    elif 5 <= yoe < 6 or 8 < yoe <= 9:
        score = 0.85
        notes.append(f"{yoe} years experience — within target range")
    elif 4 <= yoe < 5 or 9 < yoe <= 12:
        score = 0.6
        notes.append(f"{yoe} years experience — slightly outside target")
    elif 3 <= yoe < 4 or 12 < yoe <= 15:
        score = 0.35
        notes.append(f"{yoe} years experience — outside ideal range")
    else:
        score = 0.1
        notes.append(f"{yoe} years experience — significantly outside range")
    
    return score, notes


def score_behavioral(candidate: dict) -> tuple[float, list[str]]:
    """
    Score behavioral/engagement signals from the Redrob platform.
    Per the JD: "a perfect-on-paper candidate who hasn't logged in for
    6 months and has a 5% response rate is not actually available."
    """
    notes = []
    signals = candidate.get("redrob_signals", {})
    
    score = 0.5  # Start neutral
    
    # ── Recency of activity ──
    last_active = signals.get("last_active_date", "")
    if last_active:
        try:
            last_dt = datetime.strptime(last_active, "%Y-%m-%d")
            days_inactive = (datetime(2026, 6, 15) - last_dt).days  # Approximate "now"
            if days_inactive <= 7:
                score += 0.15
                notes.append("Active in last week")
            elif days_inactive <= 30:
                score += 0.1
                notes.append("Active in last month")
            elif days_inactive <= 90:
                score += 0.05
                notes.append(f"Last active {days_inactive} days ago")
            elif days_inactive > 180:
                score -= 0.25
                notes.append(f"Inactive for {days_inactive} days — likely unavailable")
            else:
                score -= 0.1
                notes.append(f"Last active {days_inactive} days ago")
        except (ValueError, TypeError):
            pass
    
    # ── Recruiter response rate (JD explicitly mentions this) ──
    response_rate = signals.get("recruiter_response_rate", 0)
    if response_rate >= 0.7:
        score += 0.12
        notes.append(f"High recruiter response rate ({response_rate:.0%})")
    elif response_rate >= 0.4:
        score += 0.05
    elif response_rate < 0.15:
        score -= 0.15
        notes.append(f"Very low response rate ({response_rate:.0%})")
    
    # ── Open to work ──
    if signals.get("open_to_work_flag", False):
        score += 0.05
        notes.append("Open to work")
    
    # ── Notice period ──
    notice = signals.get("notice_period_days", 90)
    if notice <= 30:
        score += 0.08
        notes.append(f"Short notice period ({notice} days)")
    elif notice <= 60:
        score += 0.03
    elif notice > 90:
        score -= 0.05
        notes.append(f"Long notice period ({notice} days)")
    
    # ── Profile completeness ──
    completeness = signals.get("profile_completeness_score", 0)
    if completeness >= 85:
        score += 0.03
    elif completeness < 50:
        score -= 0.05
        notes.append(f"Low profile completeness ({completeness:.0f}%)")
    
    # ── Interview completion rate ──
    interview_rate = signals.get("interview_completion_rate", 0)
    if interview_rate >= 0.8:
        score += 0.03
    elif interview_rate < 0.4:
        score -= 0.05
        notes.append(f"Low interview completion rate ({interview_rate:.0%})")
    
    # ── GitHub activity ──
    github = signals.get("github_activity_score", -1)
    if github >= 50:
        score += 0.05
        notes.append(f"Active GitHub contributor (score: {github:.0f})")
    elif github >= 20:
        score += 0.02
    
    # ── Saved by recruiters (social proof) ──
    saved = signals.get("saved_by_recruiters_30d", 0)
    if saved >= 5:
        score += 0.03
        notes.append(f"Saved by {saved} recruiters in last 30 days")
    
    # ── Verification signals ──
    verified_count = sum([
        signals.get("verified_email", False),
        signals.get("verified_phone", False),
        signals.get("linkedin_connected", False),
    ])
    if verified_count >= 3:
        score += 0.02
    elif verified_count == 0:
        score -= 0.03
    
    score = max(0.0, min(1.0, score))
    return score, notes


def score_location(candidate: dict) -> tuple[float, list[str]]:
    """Score location fit. JD prefers India, especially Pune/Noida."""
    notes = []
    profile = candidate.get("profile", {})
    location = profile.get("location", "").lower().strip()
    country = profile.get("country", "").lower().strip()
    signals = candidate.get("redrob_signals", {})
    relocate = signals.get("willing_to_relocate", False)
    work_mode = signals.get("preferred_work_mode", "")
    
    # India-based candidates
    if country == "india":
        city_tokens = set(re.split(r'[,\s]+', location))
        
        if any(loc in location for loc in PREFERRED_LOCATIONS):
            score = 1.0
            notes.append(f"Located in preferred city: {profile.get('location','')}")
        elif any(loc in location for loc in TIER1_INDIA):
            score = 0.8
            notes.append(f"Located in tier-1 Indian city: {profile.get('location','')}")
        else:
            score = 0.6
            notes.append(f"India-based: {profile.get('location','')}")
        
        if relocate:
            score = min(score + 0.1, 1.0)
            notes.append("Willing to relocate")
    else:
        # Outside India — JD says case-by-case, no visa sponsorship
        score = 0.15
        notes.append(f"Located outside India: {profile.get('location','')}, {profile.get('country','')}")
        if relocate:
            score = 0.3
            notes.append("Willing to relocate")
    
    return score, notes


def score_education(candidate: dict) -> tuple[float, list[str]]:
    """Score education. Minor signal — the JD doesn't emphasize it heavily."""
    notes = []
    education = candidate.get("education", [])
    
    if not education:
        return 0.3, ["No education listed"]
    
    score = 0.4  # Base
    
    for edu in education:
        tier = edu.get("tier", "unknown")
        field = edu.get("field_of_study", "").lower()
        degree = edu.get("degree", "").lower()
        
        # Tier bonus
        if tier == "tier_1":
            score += 0.25
            notes.append(f"Tier-1 institution: {edu.get('institution','')}")
        elif tier == "tier_2":
            score += 0.15
            notes.append(f"Tier-2 institution: {edu.get('institution','')}")
        
        # Relevant field
        cs_fields = {"computer science", "cs", "information technology", "it",
                      "artificial intelligence", "ai", "machine learning",
                      "data science", "electronics", "ece", "electrical"}
        if any(f in field for f in cs_fields):
            score += 0.1
            notes.append(f"Relevant field: {edu.get('field_of_study','')}")
        
        # Advanced degree
        if any(d in degree for d in ["m.tech", "m.s.", "ms", "mtech", "phd", "ph.d"]):
            score += 0.1
            notes.append(f"Advanced degree: {edu.get('degree','')}")
    
    score = max(0.0, min(1.0, score))
    return score, notes


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE SCORING
# ─────────────────────────────────────────────────────────────────────────────

def compute_composite_score(candidate: dict) -> tuple[float, dict]:
    """
    Compute the weighted composite score for a candidate.
    Returns (score, breakdown_dict).
    """
    title_score, title_notes = score_title(candidate)
    skills_score, skills_notes = score_skills(candidate)
    career_score, career_notes = score_career(candidate)
    exp_score, exp_notes = score_experience(candidate)
    behavioral_score, behavioral_notes = score_behavioral(candidate)
    location_score, location_notes = score_location(candidate)
    education_score, education_notes = score_education(candidate)
    
    composite = (
        W_TITLE * title_score +
        W_SKILLS * skills_score +
        W_CAREER * career_score +
        W_EXPERIENCE * exp_score +
        W_BEHAVIORAL * behavioral_score +
        W_LOCATION * location_score +
        W_EDUCATION * education_score
    )
    
    # ── Non-linear penalty: If title is completely wrong, cap the score ──
    # The JD says explicitly: "Marketing Manager" with all AI keywords is NOT a fit.
    if title_score == 0.0:
        composite = min(composite, 0.15)
    
    breakdown = {
        "title": (title_score, title_notes),
        "skills": (skills_score, skills_notes),
        "career": (career_score, career_notes),
        "experience": (exp_score, exp_notes),
        "behavioral": (behavioral_score, behavioral_notes),
        "location": (location_score, location_notes),
        "education": (education_score, education_notes),
    }
    
    return composite, breakdown


# ─────────────────────────────────────────────────────────────────────────────
# REASONING GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_reasoning(candidate: dict, rank: int, score: float, breakdown: dict) -> str:
    """
    Generate specific, fact-based reasoning for a ranked candidate.
    Must reference specific facts from the profile.
    Must NOT hallucinate skills or details not in the profile.
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    
    parts = []
    
    # Lead with title and experience
    title = profile.get("current_title", "Unknown")
    company = profile.get("current_company", "Unknown")
    yoe = profile.get("years_of_experience", 0)
    parts.append(f"{title} at {company} with {yoe} years experience")
    
    # Key skill highlights (only what exists)
    skills_score, skills_notes = breakdown.get("skills", (0, []))
    if skills_notes:
        parts.append(skills_notes[0])  # First note is most important
    
    # Career quality
    career_score, career_notes = breakdown.get("career", (0, []))
    if career_notes:
        # Pick the most informative note
        for note in career_notes:
            if "production" in note.lower() or "product company" in note.lower() or "services" in note.lower():
                parts.append(note.lower())
                break
    
    # Location
    location = profile.get("location", "")
    country = profile.get("country", "")
    if country.lower() == "india":
        parts.append(f"based in {location}")
    else:
        parts.append(f"based in {location}, {country}")
    
    # Behavioral concerns or strengths
    response_rate = signals.get("recruiter_response_rate", 0)
    notice = signals.get("notice_period_days", 0)
    
    behavioral_parts = []
    if response_rate >= 0.6:
        behavioral_parts.append(f"response rate {response_rate:.0%}")
    elif response_rate < 0.2:
        behavioral_parts.append(f"low response rate ({response_rate:.0%})")
    
    if notice <= 30:
        behavioral_parts.append(f"{notice}-day notice")
    elif notice > 90:
        behavioral_parts.append(f"long notice period ({notice} days)")
    
    if behavioral_parts:
        parts.append("; ".join(behavioral_parts))
    
    # Concerns for lower-ranked candidates
    if rank > 50:
        concerns = []
        title_score = breakdown.get("title", (0, []))[0]
        if title_score < 0.5:
            concerns.append("title not directly in AI/ML")
        
        exp_score = breakdown.get("experience", (0, []))[0]
        if exp_score < 0.5:
            concerns.append(f"experience ({yoe}y) outside ideal range")
        
        loc_score = breakdown.get("location", (0, []))[0]
        if loc_score < 0.5:
            concerns.append("location mismatch")
        
        if concerns:
            parts.append("Concerns: " + ", ".join(concerns))
    
    reasoning = "; ".join(parts) + "."
    
    # Ensure it's not too long (CSV-friendly)
    if len(reasoning) > 300:
        reasoning = reasoning[:297] + "..."
    
    return reasoning


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────────────────────────

def rank_candidates(candidates_path: str, output_path: str, top_n: int = 100):
    """
    Main ranking pipeline.
    Streams candidates, scores them, and outputs top-N ranked CSV.
    """
    start_time = time.time()
    
    print(f"[1/5] Loading candidates from {candidates_path}...")
    
    # ── Phase 1: Stream and score all candidates ──
    # We use a min-heap approach to keep only top_n * 5 candidates in memory
    # to handle tie-breaking and honeypot filtering.
    BUFFER_SIZE = top_n * 10  # Keep top 1000 for safety
    
    scored_candidates = []  # List of (score, candidate_id, candidate, breakdown, is_honeypot)
    total_count = 0
    honeypot_count = 0
    
    with open(candidates_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            
            total_count += 1
            
            if total_count % 10000 == 0:
                elapsed = time.time() - start_time
                print(f"    Processed {total_count:,} candidates ({elapsed:.1f}s)")
            
            cid = candidate.get("candidate_id", "")
            
            # Honeypot detection
            is_honeypot, honeypot_reason = detect_honeypot(candidate)
            if is_honeypot:
                honeypot_count += 1
                continue  # Skip honeypots entirely
            
            # Score the candidate
            composite, breakdown = compute_composite_score(candidate)
            
            scored_candidates.append((composite, cid, candidate, breakdown))
            
            # Periodically trim to keep memory bounded
            if len(scored_candidates) > BUFFER_SIZE * 2:
                scored_candidates.sort(key=lambda x: x[0], reverse=True)
                scored_candidates = scored_candidates[:BUFFER_SIZE]
    
    elapsed = time.time() - start_time
    print(f"[2/5] Scored {total_count:,} candidates in {elapsed:.1f}s")
    print(f"       Detected {honeypot_count} honeypots (excluded)")
    
    # ── Phase 2: Round scores first, then sort to ensure consistent tie-breaking ──
    print(f"[3/5] Selecting top {top_n} candidates...")
    # Round scores BEFORE sorting so the validator sees consistent CID-ascending ties
    scored_candidates = [
        (round(score, 4), cid, candidate, breakdown)
        for score, cid, candidate, breakdown in scored_candidates
    ]
    scored_candidates.sort(key=lambda x: (-x[0], x[1]))  # Score desc, then CID asc for ties
    top_candidates = scored_candidates[:top_n]
    
    # ── Phase 3: Generate reasoning and write CSV ──
    print(f"[4/5] Generating reasoning and writing {output_path}...")
    
    rows = []
    for rank_idx, (composite, cid, candidate, breakdown) in enumerate(top_candidates, start=1):
        reasoning = generate_reasoning(candidate, rank_idx, composite, breakdown)
        rows.append({
            "candidate_id": cid,
            "rank": rank_idx,
            "score": composite,
            "reasoning": reasoning,
        })
    
    # Write CSV
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        writer.writerows(rows)
    
    elapsed = time.time() - start_time
    print(f"[5/5] Done! Wrote {len(rows)} candidates to {output_path}")
    print(f"       Total time: {elapsed:.1f}s")
    print(f"       Peak rank-1 score: {rows[0]['score']}")
    print(f"       Rank-100 score: {rows[-1]['score']}")
    
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Rank candidates for the Senior AI Engineer role at Redrob AI"
    )
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to candidates.jsonl file"
    )
    parser.add_argument(
        "--out",
        required=True,
        help="Output CSV file path"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Number of top candidates to output (default: 100)"
    )
    
    args = parser.parse_args()
    rank_candidates(args.candidates, args.out, args.top_n)


if __name__ == "__main__":
    main()
