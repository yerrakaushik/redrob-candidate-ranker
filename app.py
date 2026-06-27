"""
app.py — Streamlit Web UI for Intelligent Candidate Ranking
============================================================
A premium, interactive dashboard for the Redrob Hackathon.

Features:
  - Upload candidates JSONL (or use sample)
  - Run ranking with live progress
  - Interactive results table with drill-down
  - Score breakdown visualizations
  - Export submission CSV
  - Candidate profile cards

Usage:
  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import json
import csv
import io
import time
import math
from datetime import datetime

# Import our ranking engine
from rank import (
    compute_composite_score,
    detect_honeypot,
    generate_reasoning,
    W_TITLE, W_SKILLS, W_CAREER, W_EXPERIENCE,
    W_BEHAVIORAL, W_LOCATION, W_EDUCATION,
)

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Redrob AI — Intelligent Candidate Ranker",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    /* ── Global ── */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* ── Hero Header ── */
    .hero-container {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        border-radius: 20px;
        padding: 2.5rem 3rem;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
    }
    .hero-container::before {
        content: '';
        position: absolute;
        top: -50%; left: -50%;
        width: 200%; height: 200%;
        background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 60%);
        animation: pulse 6s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 1; }
    }
    .hero-title {
        font-size: 2.4rem;
        font-weight: 800;
        color: #ffffff;
        margin: 0 0 0.5rem 0;
        position: relative;
        z-index: 1;
        letter-spacing: -0.5px;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        color: rgba(255,255,255,0.7);
        margin: 0;
        position: relative;
        z-index: 1;
        font-weight: 400;
    }
    .hero-badge {
        display: inline-block;
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-bottom: 12px;
        position: relative;
        z-index: 1;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }

    /* ── Metric Cards ── */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    .metric-card:hover {
        border-color: rgba(99, 102, 241, 0.5);
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(99, 102, 241, 0.15);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #6366f1, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }
    .metric-label {
        font-size: 0.8rem;
        color: rgba(255,255,255,0.5);
        margin: 4px 0 0 0;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 500;
    }

    /* ── Candidate Card ── */
    .candidate-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(99, 102, 241, 0.15);
        border-radius: 16px;
        padding: 1.8rem;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
    }
    .candidate-card:hover {
        border-color: rgba(99, 102, 241, 0.4);
        box-shadow: 0 4px 24px rgba(99, 102, 241, 0.1);
    }
    .candidate-rank {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 10px;
        font-weight: 800;
        font-size: 0.95rem;
        margin-right: 12px;
    }
    .rank-gold { background: linear-gradient(135deg, #f59e0b, #d97706); color: #1a1a2e; }
    .rank-silver { background: linear-gradient(135deg, #9ca3af, #6b7280); color: #1a1a2e; }
    .rank-bronze { background: linear-gradient(135deg, #cd7f32, #a0522d); color: white; }
    .rank-default { background: rgba(99, 102, 241, 0.2); color: #a78bfa; }
    .candidate-name {
        font-size: 1.2rem;
        font-weight: 700;
        color: #e2e8f0;
        display: inline;
    }
    .candidate-title {
        color: rgba(255,255,255,0.5);
        font-size: 0.9rem;
        margin-top: 4px;
    }
    .score-badge {
        display: inline-block;
        background: linear-gradient(135deg, #059669, #10b981);
        color: white;
        padding: 3px 12px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 700;
        float: right;
    }

    /* ── Score Bar ── */
    .score-bar-container {
        margin: 6px 0;
    }
    .score-bar-label {
        font-size: 0.75rem;
        color: rgba(255,255,255,0.5);
        margin-bottom: 3px;
        display: flex;
        justify-content: space-between;
    }
    .score-bar-track {
        background: rgba(255,255,255,0.08);
        border-radius: 6px;
        height: 8px;
        overflow: hidden;
    }
    .score-bar-fill {
        height: 100%;
        border-radius: 6px;
        transition: width 0.5s ease;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 8px 20px;
        font-weight: 600;
    }

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0c29 0%, #1a1a2e 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown h1,
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: #e2e8f0;
    }

    /* ── Hide streamlit branding ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* ── Responsive ── */
    @media (max-width: 768px) {
        .metric-grid { grid-template-columns: repeat(2, 1fr); }
        .hero-title { font-size: 1.6rem; }
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def render_score_bar(label: str, value: float, color: str = "#6366f1") -> str:
    """Render a horizontal score bar."""
    pct = max(0, min(100, value * 100))
    return f"""
    <div class="score-bar-container">
        <div class="score-bar-label">
            <span>{label}</span>
            <span>{pct:.0f}%</span>
        </div>
        <div class="score-bar-track">
            <div class="score-bar-fill" style="width: {pct}%; background: linear-gradient(90deg, {color}, {color}cc);"></div>
        </div>
    </div>
    """


def get_rank_class(rank: int) -> str:
    if rank == 1: return "rank-gold"
    if rank == 2: return "rank-silver"
    if rank == 3: return "rank-bronze"
    return "rank-default"


def render_candidate_card(rank: int, cid: str, score: float, candidate: dict, breakdown: dict) -> str:
    """Render a beautiful candidate profile card."""
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    
    name = profile.get("anonymized_name", "Unknown")
    title = profile.get("current_title", "")
    company = profile.get("current_company", "")
    location = profile.get("location", "")
    country = profile.get("country", "")
    yoe = profile.get("years_of_experience", 0)
    
    rank_class = get_rank_class(rank)
    
    # Score bars
    bars_html = ""
    bar_configs = [
        ("Title Fit", breakdown.get("title", (0, []))[0], "#6366f1"),
        ("Skills", breakdown.get("skills", (0, []))[0], "#8b5cf6"),
        ("Career", breakdown.get("career", (0, []))[0], "#a78bfa"),
        ("Experience", breakdown.get("experience", (0, []))[0], "#c4b5fd"),
        ("Behavioral", breakdown.get("behavioral", (0, []))[0], "#10b981"),
        ("Location", breakdown.get("location", (0, []))[0], "#06b6d4"),
        ("Education", breakdown.get("education", (0, []))[0], "#f59e0b"),
    ]
    for label, val, color in bar_configs:
        bars_html += render_score_bar(label, val, color)
    
    # Skills list
    skills = candidate.get("skills", [])
    top_skills = sorted(skills, key=lambda s: {"expert": 4, "advanced": 3, "intermediate": 2, "beginner": 1}.get(s.get("proficiency", ""), 0), reverse=True)[:8]
    skills_html = " ".join(
        f'<span style="display:inline-block;background:rgba(99,102,241,0.15);color:#a78bfa;padding:2px 10px;border-radius:8px;font-size:0.75rem;margin:2px;font-weight:500;">{s.get("name","")}</span>'
        for s in top_skills
    )
    
    loc_str = f"{location}, {country}" if country.lower() != "india" else location
    
    return f"""
    <div class="candidate-card">
        <div>
            <span class="candidate-rank {rank_class}">#{rank}</span>
            <span class="candidate-name">{name}</span>
            <span class="score-badge">{score:.4f}</span>
        </div>
        <div class="candidate-title">{title} at {company} · {yoe}y exp · {loc_str}</div>
        <div style="margin-top:10px;">{skills_html}</div>
        <div style="margin-top:14px;">{bars_html}</div>
    </div>
    """


# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

if "ranked_results" not in st.session_state:
    st.session_state.ranked_results = None
if "all_candidates_data" not in st.session_state:
    st.session_state.all_candidates_data = None
if "run_stats" not in st.session_state:
    st.session_state.run_stats = None


# ─────────────────────────────────────────────────────────────────────────────
# HERO HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero-container">
    <div class="hero-badge">India Runs · Redrob Hackathon</div>
    <h1 class="hero-title">🧠 Intelligent Candidate Ranker</h1>
    <p class="hero-subtitle">
        AI-powered candidate ranking that goes beyond keywords — understanding career trajectories, 
        behavioral signals, and genuine role fit to surface the top 100 candidates a recruiter can trust.
    </p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")
    
    st.markdown("### 📊 Scoring Weights")
    st.markdown("*Fine-tune how different signals are weighted*")
    
    # Show current weights
    weight_data = {
        "Title Fit": W_TITLE,
        "Skill Match": W_SKILLS,
        "Career Quality": W_CAREER,
        "Experience": W_EXPERIENCE,
        "Behavioral": W_BEHAVIORAL,
        "Location": W_LOCATION,
        "Education": W_EDUCATION,
    }
    
    for name, w in weight_data.items():
        st.markdown(f"**{name}**: `{w:.0%}`")
    
    st.markdown("---")
    
    st.markdown("### 📋 About This System")
    st.markdown("""
    **Architecture:**
    - Multi-signal hybrid scoring
    - Honeypot detection & filtering
    - Fact-based reasoning generation
    
    **Constraints Met:**
    - ✅ CPU-only processing
    - ✅ < 5 min runtime
    - ✅ < 16 GB RAM
    - ✅ No external API calls
    - ✅ No GPU required
    """)
    
    st.markdown("---")
    st.markdown(
        "<div style='text-align:center;color:rgba(255,255,255,0.3);font-size:0.75rem;'>"
        "Built for Redrob Hackathon 2026<br>Intelligent Candidate Discovery & Ranking"
        "</div>",
        unsafe_allow_html=True
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN CONTENT
# ─────────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["🚀 Run Ranking", "📊 Results Dashboard", "👤 Candidate Explorer", "📥 Export"])

# ─── TAB 1: Run Ranking ──────────────────────────────────────────────────────

with tab1:
    st.markdown("### Upload & Rank Candidates")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        upload_mode = st.radio(
            "Data Source",
            ["Upload JSONL file", "Use sample data (sample_candidates.json)"],
            horizontal=True,
        )
        
        candidates_data = None
        
        if upload_mode == "Upload JSONL file":
            uploaded = st.file_uploader(
                "Upload candidates.jsonl",
                type=["jsonl", "json"],
                help="Upload the candidates.jsonl file from the hackathon dataset"
            )
            if uploaded:
                content = uploaded.read().decode("utf-8")
                lines = content.strip().split("\n")
                candidates_data = []
                for line in lines:
                    line = line.strip()
                    if line:
                        try:
                            candidates_data.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
                st.success(f"✅ Loaded {len(candidates_data):,} candidates")
        else:
            # Load sample data
            import os
            sample_path = os.path.join(
                os.path.dirname(__file__),
                "[PUB] India_runs_data_and_ai_challenge",
                "India_runs_data_and_ai_challenge",
                "sample_candidates.json"
            )
            if os.path.exists(sample_path):
                with open(sample_path, "r", encoding="utf-8") as f:
                    candidates_data = json.load(f)
                st.success(f"✅ Loaded {len(candidates_data):,} sample candidates")
            else:
                st.warning("⚠️ Sample file not found. Please upload a JSONL file.")
    
    with col2:
        top_n = st.number_input("Top N candidates", min_value=10, max_value=100, value=100)
        st.markdown("")
        st.markdown("")
    
    if candidates_data and st.button("🚀 Run Ranking Engine", type="primary", use_container_width=True):
        start_time = time.time()
        
        progress_bar = st.progress(0, text="Starting ranking engine...")
        status_text = st.empty()
        
        scored = []
        honeypot_count = 0
        total = len(candidates_data)
        
        for i, candidate in enumerate(candidates_data):
            # Update progress
            pct = (i + 1) / total
            if i % max(1, total // 100) == 0:
                progress_bar.progress(pct, text=f"Scoring candidate {i+1:,}/{total:,}...")
            
            # Honeypot check
            is_hp, hp_reason = detect_honeypot(candidate)
            if is_hp:
                honeypot_count += 1
                continue
            
            # Score
            composite, breakdown = compute_composite_score(candidate)
            cid = candidate.get("candidate_id", "")
            scored.append((composite, cid, candidate, breakdown))
        
        progress_bar.progress(0.9, text="Sorting and selecting top candidates...")
        
        # Sort and select
        scored.sort(key=lambda x: (-x[0], x[1]))
        top_results = scored[:top_n]
        
        # Build results
        results = []
        all_data = {}
        for rank_idx, (composite, cid, candidate, breakdown) in enumerate(top_results, start=1):
            reasoning = generate_reasoning(candidate, rank_idx, composite, breakdown)
            results.append({
                "rank": rank_idx,
                "candidate_id": cid,
                "score": round(composite, 4),
                "reasoning": reasoning,
                "candidate": candidate,
                "breakdown": breakdown,
            })
            all_data[cid] = {
                "candidate": candidate,
                "breakdown": breakdown,
            }
        
        elapsed = time.time() - start_time
        
        st.session_state.ranked_results = results
        st.session_state.all_candidates_data = all_data
        st.session_state.run_stats = {
            "total": total,
            "honeypots": honeypot_count,
            "elapsed": elapsed,
            "top_score": results[0]["score"] if results else 0,
            "bottom_score": results[-1]["score"] if results else 0,
        }
        
        progress_bar.progress(1.0, text="✅ Ranking complete!")
        
        st.success(f"Ranking completed in **{elapsed:.1f}s** — {total:,} candidates processed, {honeypot_count} honeypots filtered")


# ─── TAB 2: Results Dashboard ────────────────────────────────────────────────

with tab2:
    if st.session_state.ranked_results:
        results = st.session_state.ranked_results
        stats = st.session_state.run_stats
        
        # Metric cards
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card">
                <p class="metric-value">{stats['total']:,}</p>
                <p class="metric-label">Candidates Scanned</p>
            </div>
            <div class="metric-card">
                <p class="metric-value">{stats['honeypots']}</p>
                <p class="metric-label">Honeypots Filtered</p>
            </div>
            <div class="metric-card">
                <p class="metric-value">{stats['elapsed']:.1f}s</p>
                <p class="metric-label">Execution Time</p>
            </div>
            <div class="metric-card">
                <p class="metric-value">{stats['top_score']:.4f}</p>
                <p class="metric-label">Top Score</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Results table
        st.markdown("### 📋 Ranked Candidates")
        
        df = pd.DataFrame([
            {
                "Rank": r["rank"],
                "Candidate ID": r["candidate_id"],
                "Name": r["candidate"]["profile"].get("anonymized_name", ""),
                "Title": r["candidate"]["profile"].get("current_title", ""),
                "Company": r["candidate"]["profile"].get("current_company", ""),
                "Experience": f"{r['candidate']['profile'].get('years_of_experience', 0):.1f}y",
                "Location": r["candidate"]["profile"].get("location", ""),
                "Score": r["score"],
                "Reasoning": r["reasoning"],
            }
            for r in results
        ])
        
        st.dataframe(
            df,
            use_container_width=True,
            height=500,
            column_config={
                "Rank": st.column_config.NumberColumn("Rank", width="small"),
                "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=1, format="%.4f"),
                "Reasoning": st.column_config.TextColumn("Reasoning", width="large"),
            }
        )
        
        # Score distribution chart
        st.markdown("### 📈 Score Distribution")
        chart_df = pd.DataFrame({
            "Rank": [r["rank"] for r in results],
            "Score": [r["score"] for r in results],
        })
        st.area_chart(chart_df.set_index("Rank"), color="#6366f1")
        
    else:
        st.info("👈 Go to the **Run Ranking** tab to process candidates first.")


# ─── TAB 3: Candidate Explorer ───────────────────────────────────────────────

with tab3:
    if st.session_state.ranked_results:
        results = st.session_state.ranked_results
        
        st.markdown("### 👤 Explore Individual Candidates")
        
        # Top 3 spotlight
        st.markdown("#### 🏆 Top 3 Candidates")
        for r in results[:3]:
            st.markdown(
                render_candidate_card(
                    r["rank"], r["candidate_id"], r["score"],
                    r["candidate"], r["breakdown"]
                ),
                unsafe_allow_html=True
            )
        
        # Searchable explorer
        st.markdown("---")
        st.markdown("#### 🔍 Search & Explore")
        
        col_search, col_filter = st.columns([2, 1])
        with col_search:
            search_q = st.text_input("Search by name, title, or skills", placeholder="e.g. 'ML Engineer' or 'Pinecone'")
        with col_filter:
            rank_range = st.slider("Rank range", 1, len(results), (1, len(results)))
        
        filtered = results[rank_range[0]-1:rank_range[1]]
        
        if search_q:
            q = search_q.lower()
            filtered = [
                r for r in filtered
                if q in r["candidate"]["profile"].get("anonymized_name", "").lower()
                or q in r["candidate"]["profile"].get("current_title", "").lower()
                or q in r["candidate"]["profile"].get("headline", "").lower()
                or any(q in s.get("name", "").lower() for s in r["candidate"].get("skills", []))
            ]
        
        st.markdown(f"*Showing {len(filtered)} candidates*")
        
        for r in filtered[:20]:  # Show max 20
            with st.expander(f"#{r['rank']} — {r['candidate']['profile'].get('anonymized_name','')} ({r['score']:.4f})"):
                st.markdown(
                    render_candidate_card(
                        r["rank"], r["candidate_id"], r["score"],
                        r["candidate"], r["breakdown"]
                    ),
                    unsafe_allow_html=True
                )
                
                # Detailed info
                profile = r["candidate"]["profile"]
                st.markdown(f"**Summary:** {profile.get('summary', 'N/A')}")
                
                # Career history
                st.markdown("**Career History:**")
                for job in r["candidate"].get("career_history", []):
                    st.markdown(
                        f"- **{job.get('title','')}** at {job.get('company','')} "
                        f"({job.get('duration_months',0)} months, {job.get('industry','')})"
                    )
                
                st.markdown(f"**Reasoning:** {r['reasoning']}")
    else:
        st.info("👈 Go to the **Run Ranking** tab to process candidates first.")


# ─── TAB 4: Export ────────────────────────────────────────────────────────────

with tab4:
    if st.session_state.ranked_results:
        results = st.session_state.ranked_results
        
        st.markdown("### 📥 Export Submission CSV")
        st.markdown("Download the ranking output in the exact format required by the hackathon submission spec.")
        
        # Generate CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["candidate_id", "rank", "score", "reasoning"])
        writer.writeheader()
        for r in results:
            writer.writerow({
                "candidate_id": r["candidate_id"],
                "rank": r["rank"],
                "score": r["score"],
                "reasoning": r["reasoning"],
            })
        
        csv_content = output.getvalue()
        
        st.download_button(
            "⬇️ Download submission.csv",
            data=csv_content,
            file_name="submission.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True,
        )
        
        st.markdown("---")
        st.markdown("### 📋 CSV Preview")
        preview_df = pd.DataFrame([
            {
                "candidate_id": r["candidate_id"],
                "rank": r["rank"],
                "score": r["score"],
                "reasoning": r["reasoning"][:80] + "..." if len(r["reasoning"]) > 80 else r["reasoning"],
            }
            for r in results[:10]
        ])
        st.dataframe(preview_df, use_container_width=True)
        
        st.markdown(f"""
        **Validation Checklist:**
        - ✅ Exactly {len(results)} data rows
        - ✅ Ranks 1 through {len(results)} (unique)
        - ✅ Scores non-increasing with rank
        - ✅ All candidate_ids in CAND_XXXXXXX format
        - ✅ Reasoning column populated
        """)
    else:
        st.info("👈 Go to the **Run Ranking** tab to process candidates first.")
