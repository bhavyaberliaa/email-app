import os
import csv
import io
import datetime
import anthropic
import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
try:
    from audio_recorder_streamlit import audio_recorder
    AUDIO_RECORDER_AVAILABLE = True
except ImportError:
    AUDIO_RECORDER_AVAILABLE = False
try:
    import groq as groq_sdk
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Bhavya's Message Writer", page_icon="✉️", layout="centered")

# ── Style ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Layout ── */
    .block-container { max-width: 800px; padding-top: 1.5rem; }

    /* ── Typography ── */
    .stTextArea textarea { font-size: 14px; line-height: 1.6; }
    .word-count { font-size: 12px; color: #9ca3af; margin-top: -8px; margin-bottom: 8px; }

    /* ── Section cards ── */
    .section-card {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1.2rem 1.4rem 0.8rem;
        margin-bottom: 1rem;
    }
    .section-card-dark {
        background: #f0f9ff;
        border: 1px solid #bae6fd;
        border-radius: 10px;
        padding: 1.2rem 1.4rem 0.8rem;
        margin-bottom: 1rem;
    }

    /* ── Section headings ── */
    h3 { font-size: 1rem !important; font-weight: 600 !important; color: #1e293b !important; margin-bottom: 0.5rem !important; }

    /* ── Primary button ── */
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        border: none;
        color: white;
        font-weight: 600;
        font-size: 1rem;
        padding: 0.65rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 2px 8px rgba(99,102,241,0.3);
        transition: box-shadow 0.15s ease;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        box-shadow: 0 4px 16px rgba(99,102,241,0.45);
    }

    /* ── Secondary buttons ── */
    div[data-testid="stButton"] > button[kind="secondary"] {
        border-radius: 7px;
        font-size: 0.87rem;
    }

    /* ── Output message box ── */
    .message-output {
        background: #ffffff;
        border: 2px solid #6366f1;
        border-radius: 10px;
        padding: 1.2rem 1.4rem;
        font-size: 14.5px;
        line-height: 1.7;
        white-space: pre-wrap;
        margin-top: 0.5rem;
    }

    /* ── Tab styling ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 6px;
        border-bottom: 2px solid #e2e8f0;
        margin-bottom: 1rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.5rem 1.1rem;
        font-weight: 500;
        font-size: 0.9rem;
        color: #64748b;
    }
    .stTabs [aria-selected="true"] {
        background: #6366f1 !important;
        color: white !important;
    }

    /* ── Expander tweak ── */
    .streamlit-expanderHeader { font-size: 0.9rem; font-weight: 500; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] { background: #f8fafc; }
    [data-testid="stSidebar"] h2 { font-size: 1rem; }

    /* ── History entry label ── */
    .hist-label { font-size: 0.88rem; color: #475569; }
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "message_history.json")

# ── History helpers ───────────────────────────────────────────────────────────
def load_history() -> list:
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_to_history(entry: dict):
    history = load_history()
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def history_to_csv(history: list) -> str:
    if not history:
        return ""
    fieldnames = ["timestamp", "msg_type", "purpose", "recipient_name",
                  "recipient_role", "recipient_company", "message"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(history)
    return buf.getvalue()

# ── Few-shot training examples from Bhavya's real messages ───────────────────
EXAMPLES = """
--- EXAMPLE 1: LinkedIn InMail to Adobe employee (warm, mutual connection) ---
SUBJECT: Haas MBA '27 | Interested in Adobe's Education Team
Hi Cailin, I hope you're doing well! My name is Bhavya — I'm a current first-year student at Haas. Shilpa Gopal (MBA '25) suggested I reach out, and I noticed we have pretty similar backgrounds! A little about me: I worked as a consultant helping governments and philanthropies in India build education-focused products (a reading game with Google for Education, an AI assessment app for teachers, and more). After that, I served as Chief of Staff at an ed-tech startup, where I built and took early education products to market. I'd love to learn more about the work your team does at Adobe, especially as I recruit for summer internships. I'd be really grateful to hear whether your team is hiring interns and any advice you might have on how to stand out. Best, Bhavya Berlia

--- EXAMPLE 2: LinkedIn InMail to Adobe/Unity (career pivot, no mutual connection) ---
SUBJECT: Haas MBA '27 | Exploring education and creative tech
Hi Elana, I hope you're doing well. My name is Bhavya, and I am a current first-year MBA student at Haas. Shilpa Gopal (MBA '25) suggested I reach out, and I noticed we have fairly similar backgrounds. A little about me: I previously worked as a consultant helping governments and philanthropies in India build education-focused products, including a reading game with Google for Education and an AI assessment app for teachers. After that, I served as Chief of Staff at an ed-tech startup, where I helped build and take early education products to market. I saw that you worked on the Creative Cloud Education Team at Adobe and am also very intrigued by the learning-focused work you are leading at Unity. I would love to learn how you have shaped your career at the intersection of creativity, technology, and education. If you would be open to a brief conversation, I would be incredibly grateful for any insights or advice you might have as I think through my summer internship search. Thank you so much, Bhavya Berlia

--- EXAMPLE 3: LinkedIn InMail to Databricks (strategy/ops, applied to roles) ---
SUBJECT: Haas '27 would love to learn from your path
Hi Nikhil, I'm Bhavya, a current first-year MBA at Haas ('27). I'm really excited about what Databricks is building. The way the company sits at the intersection of data infrastructure and AI, and is still scaling so fast, is exactly the kind of environment I want to be in. Your path from consulting to a decade in S&O to the Office of the CEO is something I find really compelling. I'd love to hear how you've built a career at that intersection of strategy and execution, and what the work actually looks like from the inside. My background is in strategy consulting and as Chief of Staff at a high-growth ed-tech startup, so I feel a real pull toward this kind of role. I've applied to both the MBA Intern - Corporate Operations and Strategy & Execution roles at Databricks, so any perspective on the team would mean a lot. Would you be open to a 20-minute chat? Best, Bhavya

--- EXAMPLE 4: LinkedIn InMail to ClassDojo PM (direct PM opportunity pitch) ---
SUBJECT: Haas MBA | AI ed-tech PM with 2M+ user product experience
Hi Patrick, I'm Bhavya, a first-year MBA student at UC Berkeley Haas with 5+ years across ed-tech and impact consulting. Before Haas, I was Chief of Staff at Rocket Learning, where I led AI product development that reached 2M+ users, working directly with public schools and districts to embed our tools into classrooms. Prior to that, I consulted on foundational math and literacy programs in India and built a reading game with Google to drive learning outcomes at scale. I bring a mix of 0-to-1 product experience, deep familiarity with how schools and districts actually operate, and a genuine obsession with how AI can reshape learning. I'd love to explore how this background translates to what you're building with Dojo Islands. If there are summer PM opportunities where I could contribute, I'd love to connect. Best, Bhavya Berlia

--- EXAMPLE 5: Follow-up email after meeting recruiter at TikTok Open Day ---
Hi Natalie, I hope you are well. We met at the Open Day at the TikTok office on 25th Feb. It was great to meet you and learn about your journey from Reddit to Pixar and finally to TikTok.
I'm a first-year MBA at Berkeley Haas recruiting for PM summer internships. I wanted to share my background since we discussed potential fit:
Before Haas, I was Chief of Staff at a 5M-user ed-tech startup where I led 0→1 product launches including Appu—an AI voice learning companion built with Google.org that scaled to 100K+ users, and drove GTM strategy and product roadmap for apps reaching 15M+ users.
Before that, I worked in ads at Publicis (Leo Burnett), running performance campaigns for global brands and optimizing $20M+ in ad spend.
I'm a builder at heart—currently developing an AI voice journaling app at Haas—and the execution-first, innovation-driven culture at TikTok really resonates with me. I've attached my resume as suggested; I'd really appreciate any guidance on relevant PM internships or next steps.
Best, Bhavya Berlia

--- EXAMPLE 6: Follow-up email after meeting recruiter (S&O focused) ---
Hi Jenny, Thanks for taking the time to chat at the Open Day! As discussed, I'm sharing my resume for GMP summer internships, primarily interested in Strategy & Operations roles in monetization, with strong interest in PM positions as well.
Specifically, I want to share why I'm a strong fit for Strategy & Ops:
- Strategy consulting: 2.5 years at Samagra leading strategic diagnostics, building roadmaps, and designing KPI frameworks for 10M+ user programs
- Operations & revenue planning: Chief of Staff at 5M-user ed-tech startup driving revenue planning, building operational dashboards, and designing GTM strategy across 6 markets
- Monetization strategy: Ads experience at Publicis optimizing $20M+ ad spend and improving campaign performance
I'm a builder at heart (currently developing an AI voice journaling app at Haas) with a strong execution focus, which aligns well with TikTok's culture. I've attached my resumes as suggested; I'd really appreciate any guidance on relevant internships or next steps.
Best, Bhavya Berlia
"""

# ── Background about Bhavya (pre-filled) ─────────────────────────────────────
DEFAULT_BACKGROUND = """- Haas MBA '27 (Class of 2027), UC Berkeley, first-year student
- Chief of Staff at Rocket Learning (5M-user ed-tech startup): led 0→1 product launches, built Appu (AI voice learning companion with Google.org, 100K+ users), drove GTM across 6 markets, revenue planning & operational dashboards
- Strategy consultant at Samagra (2.5 years): education policy consulting for governments/philanthropies in India, built reading game with Google for Education, AI assessment app for teachers, KPI frameworks for 10M+ user programs
- Ads at Publicis/Leo Burnett: performance campaigns for global brands, optimized $20M+ ad spend
- Currently building an AI voice journaling app at Haas
- Interests: PM, Strategy & Ops, education tech, AI/ML products, creative tech, monetization"""

# ── System prompt builder ─────────────────────────────────────────────────────
def build_system_prompt(background_text: str, resume_bullets: dict, recipient_company: str = "") -> str:
    prompt = f"""You are a professional message writer for Bhavya Berlia, a first-year MBA student at UC Berkeley Haas (Class of 2027). You write tailored emails and LinkedIn InMails in Bhavya's authentic voice.

BHAVYA'S BACKGROUND:
{background_text}

BHAVYA'S WRITING STYLE (learned from real messages):
- Warm, confident, and genuine — never salesy or overly formal
- Opens with a brief personal intro and mentions any mutual connection naturally
- Connects personal background to the recipient's specific work/company (shows research)
- 2-3 crisp sentences of relevant background — picks the most relevant highlights
- Clear, specific ask (coffee chat, 20-min call, internship guidance)
- Grateful but not sycophantic closing
- Signs off: "Best, Bhavya" or "Best, Bhavya Berlia"
- LinkedIn InMail subject lines follow format: "[School/Year] | [Specific Hook]"

LENGTH RULES:
- LinkedIn InMails: STRICTLY 100-150 words (body only, not subject line)
- Emails: 100-200 words (can use bullets if listing qualifications, like after meeting a recruiter)
- ALWAYS state the word count at the end in parentheses, e.g. (143 words)

REAL EXAMPLES OF BHAVYA'S MESSAGES:
{EXAMPLES}
"""
    if resume_bullets:
        nested = is_nested_bullets(resume_bullets)
        if nested:
            prompt += "\nBHAVYA'S RESUME BULLETS (organized by company and role type):\n"
            prompt += "Company-specific bullets are listed first — prefer those over generic ones.\n"
            # Company-specific bullets first
            company_key = next(
                (k for k in resume_bullets if k.lower() == recipient_company.lower()),
                None
            ) if recipient_company else None
            if company_key:
                prompt += f"\n[{company_key} — PREFERRED for this message]\n"
                for role, bullets in resume_bullets[company_key].items():
                    prompt += f"  [{role}]\n{bullets}\n"
            # Generic/other companies as fallback
            for company, roles in resume_bullets.items():
                if company_key and company.lower() == company_key.lower():
                    continue
                prompt += f"\n[{company}]\n"
                for role, bullets in roles.items():
                    prompt += f"  [{role}]\n{bullets}\n"
        else:
            prompt += "\nBHAVYA'S RESUME BULLETS BY ROLE TYPE:\n"
            prompt += "Use these to pick the most relevant 2-3 highlights based on the target role/company.\n"
            for role_type, bullets in resume_bullets.items():
                prompt += f"\n[{role_type}]\n{bullets}\n"

    prompt += """
INSTRUCTIONS:
- Write ONLY the message (subject line if InMail, then body). No preamble, no explanation.
- Match the tone and structure from the examples above.
- Be specific to the recipient's company and role — generic messages are unacceptable.
- If bullets are appropriate (e.g., recruiter follow-up with resume), use them.
- If resume bullets are provided above, select the most relevant ones for this specific message.
- Count words carefully and stay within the length rule.
"""
    return prompt

# ── Helpers ───────────────────────────────────────────────────────────────────
def count_words(text: str) -> int:
    return len(text.split())

def fetch_url_text(url: str, max_chars: int = 5000) -> tuple[str, bool]:
    """Fetch a URL and return cleaned text content. Returns (text, success)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            # Collapse excessive blank lines
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text[:max_chars], True
        return "", False
    except Exception:
        return "", False

def extract_profile_info(api_key: str, profile_text: str) -> dict:
    """Use Claude Haiku to extract name, role, company from profile text."""
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=150,
        messages=[{
            "role": "user",
            "content": (
                "Extract from this LinkedIn profile text:\n"
                "1. First name only\n"
                "2. Current job title/role\n"
                "3. Current company name\n\n"
                "Return ONLY a JSON object like: {\"name\": \"...\", \"role\": \"...\", \"company\": \"...\"}\n"
                "If you can't find a field, use an empty string.\n\n"
                f"Profile text:\n{profile_text[:2500]}"
            ),
        }]
    )
    try:
        raw = resp.content[0].text.strip()
        # Extract JSON even if there's surrounding text
        match = re.search(r"\{[^}]+\}", raw)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {}

def is_nested_bullets(d: dict) -> bool:
    """Return True if dict is {str: {str: str}} (company+role nested format)."""
    return d and all(isinstance(v, dict) for v in d.values())

def parse_resume_file(uploaded_file) -> dict:
    """Parse an uploaded .json or .txt resume bullets file.

    Supports two formats:
    - Flat: {"PM": "...", "S&O": "..."} — role type only
    - Nested: {"generic": {"PM": "..."}, "Databricks": {"S&O": "..."}} — company + role type

    TXT supports:
    - [Section] headers → flat
    - [Company/RoleType] headers → nested (stored as nested dict)
    """
    content = uploaded_file.read().decode("utf-8")
    if uploaded_file.name.endswith(".json"):
        try:
            return json.loads(content)
        except Exception:
            return {}
    # Parse .txt with [Section] or [Company/Role] headers
    result = {}
    current_key = None  # tuple (company, role) or (role,)
    lines = []

    def flush():
        if current_key and lines:
            if len(current_key) == 2:
                company, role = current_key
                result.setdefault(company, {})[role] = "\n".join(lines)
            else:
                result[current_key[0]] = "\n".join(lines)

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            flush()
            lines = []
            header = stripped[1:-1]
            if "/" in header:
                parts = header.split("/", 1)
                current_key = (parts[0].strip(), parts[1].strip())
            else:
                current_key = (header,)
        elif current_key and stripped:
            lines.append(stripped)
    flush()
    return result

def generate_message(api_key: str, user_prompt: str, system_prompt: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return message.content[0].text

# ── Company news search ───────────────────────────────────────────────────────
def search_company_news(api_key: str, company: str, role: str = "") -> list[dict]:
    """Search DuckDuckGo for recent company news and summarize with Claude Haiku.

    Returns a list of dicts: [{title, snippet, url, hook}]
    """
    # Build search query targeting last 6 months of news
    query = f"{company} news updates 2025 2026"
    if role:
        team_guess = role.split()[0] if role else ""
        query = f"{company} {team_guess} news 2025 2026"

    search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}&df=6m"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        resp = requests.get(search_url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for result in soup.select(".result")[:8]:
            title_el = result.select_one(".result__title")
            snippet_el = result.select_one(".result__snippet")
            url_el = result.select_one(".result__url")
            if title_el and snippet_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "snippet": snippet_el.get_text(strip=True),
                    "url": url_el.get_text(strip=True) if url_el else "",
                })
        if not results:
            return []
        # Summarize and generate hooks with Claude Haiku
        results_text = "\n".join(
            f"{i+1}. {r['title']}\n   {r['snippet']}" for i, r in enumerate(results)
        )
        client = anthropic.Anthropic(api_key=api_key)
        resp2 = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": (
                f"Bhavya Berlia (Haas MBA student) is reaching out to someone at {company}. "
                f"Here are recent news results about {company}:\n\n{results_text}\n\n"
                "For each genuinely useful and recent update (skip generic/irrelevant ones), "
                "provide a one-line message hook Bhavya could reference to show she's done her homework. "
                "Format as JSON array: "
                '[{"title": "...", "hook": "I saw that [company] recently [did X] — ..."}, ...]'
                "\nReturn ONLY the JSON array, no other text."
            )}]
        )
        raw = resp2.content[0].text.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            # Merge hook back with original results
            for item in parsed:
                for r in results:
                    if item.get("title", "")[:30] in r["title"]:
                        item["url"] = r.get("url", "")
                        break
            return parsed[:5]
    except Exception:
        pass
    return []

# ── LinkedIn analyzer ─────────────────────────────────────────────────────────
def analyze_linkedin_profile(api_key: str, profile_text: str, background_text: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=700,
        messages=[{"role": "user", "content": (
            "Analyze this LinkedIn profile for Bhavya Berlia (MBA student at Haas) who wants to reach out.\n\n"
            f"BHAVYA'S BACKGROUND:\n{background_text}\n\n"
            f"LINKEDIN PROFILE:\n{profile_text[:4000]}\n\n"
            "Return a structured analysis with these four sections using markdown:\n"
            "## Name / Role / Company\n(one line: Name | Role | Company)\n\n"
            "## Key Career Highlights\n(3-4 bullets of their most notable achievements)\n\n"
            "## Personalization Hooks\n(2-3 specific things to reference — overlaps with Bhavya, interesting projects, shared background)\n\n"
            "## Suggested Message Angle\n(one sentence: what angle would resonate most for Bhavya's outreach)"
        )}]
    )
    return resp.content[0].text

# ── Groq Whisper transcription ────────────────────────────────────────────────
def transcribe_audio(groq_api_key: str, audio_bytes: bytes) -> str:
    client = groq_sdk.Groq(api_key=groq_api_key)
    transcription = client.audio.transcriptions.create(
        model="whisper-large-v3-turbo",
        file=("audio.wav", audio_bytes),
    )
    return transcription.text

# ── API key resolution ────────────────────────────────────────────────────────
def resolve_api_key() -> tuple[str, str]:
    """Returns (api_key, source) where source is 'secrets', 'env', or ''."""
    try:
        key = st.secrets.get("ANTHROPIC_API_KEY", "")
        if key:
            return key, "secrets"
    except Exception:
        pass
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key, "env"
    return "", ""

# ── Session state initialization ──────────────────────────────────────────────
for _key, _default in [
    ("recipient_name", ""),
    ("recipient_role", ""),
    ("recipient_company", ""),
    ("linkedin_fetch_failed", False),
    ("jd_text", ""),
    ("resume_bullets", {}),
    ("li_analysis", ""),
    ("key_angle_text", ""),
    ("pasted_context_text", ""),
    ("history_confirm_clear", False),
    ("company_news", None),
    ("company_news_for", ""),
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ── UI ────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.2rem;">
  <span style="font-size:1.7rem;">✉️</span>
  <span style="font-size:1.5rem; font-weight:700; color:#1e293b;">Bhavya's Message Writer</span>
</div>
<p style="color:#64748b; margin-top:0; margin-bottom:1.2rem; font-size:0.93rem;">
  Tailored 100–150 word emails &amp; LinkedIn InMails — in seconds.
</p>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Settings")
    _auto_key, _source = resolve_api_key()
    if _auto_key:
        st.success("API key loaded automatically")
        with st.expander("Override API key"):
            _override = st.text_input("Paste a different key", type="password",
                                      label_visibility="collapsed",
                                      placeholder="sk-ant-...")
        api_key = _override if _override else _auto_key
    else:
        api_key = st.text_input("Anthropic API Key", type="password",
                                help="Get yours at console.anthropic.com")
        with st.expander("Save key permanently"):
            st.markdown(
                "Add to `~/.streamlit/secrets.toml`:\n"
                "```toml\nANTHROPIC_API_KEY = \"sk-ant-...\"\n```\n"
                "Then restart the app — no more typing!"
            )
    st.divider()
    # Groq API key for speech-to-text
    st.subheader("Groq API Key (Speech-to-Text)")
    _groq_auto = ""
    try:
        _groq_auto = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        pass
    if not _groq_auto:
        _groq_auto = os.environ.get("GROQ_API_KEY", "")
    if _groq_auto:
        st.success("Groq key loaded automatically")
        with st.expander("Override Groq key"):
            _groq_override = st.text_input("Paste a different Groq key", type="password",
                                           label_visibility="collapsed", key="groq_key_override",
                                           placeholder="gsk_...")
        groq_api_key = _groq_override if _groq_override else _groq_auto
    else:
        groq_api_key = st.text_input("Groq API Key", type="password",
                                     key="groq_key_input",
                                     help="Free at console.groq.com — used for speech-to-text",
                                     placeholder="gsk_...")
        if not groq_api_key:
            st.caption("Get a free key at [console.groq.com](https://console.groq.com)")
    st.divider()
    st.subheader("Your Background")
    background = st.text_area("Edit your background (used in all prompts)",
                               value=DEFAULT_BACKGROUND, height=200)
    st.caption("Pre-filled with your profile. Edit anytime.")
    st.divider()
    st.subheader("Resume Bullets by Role")
    st.caption(
        "Upload a `.json` or `.txt` file with resume highlights organized by role type "
        "(PM, S&O, etc.). Claude will pick the most relevant bullets per message."
    )
    resume_file = st.file_uploader("Upload resume bullets file", type=["json", "txt"],
                                   label_visibility="collapsed")
    if resume_file:
        parsed = parse_resume_file(resume_file)
        if parsed:
            st.session_state["resume_bullets"] = parsed
            st.success(f"Loaded {len(parsed)} role type(s): {', '.join(parsed.keys())}")
        else:
            st.error("Could not parse file. Check the format.")
    if st.session_state["resume_bullets"]:
        with st.expander("View loaded bullets"):
            rb = st.session_state["resume_bullets"]
            if is_nested_bullets(rb):
                for company, roles in rb.items():
                    st.markdown(f"**{company}**")
                    for role, bullets in roles.items():
                        st.markdown(f"*{role}*")
                        st.text(bullets)
            else:
                for role, bullets in rb.items():
                    st.markdown(f"**{role}**")
                    st.text(bullets)
        if st.button("Clear resume bullets", use_container_width=True):
            st.session_state["resume_bullets"] = {}
            st.rerun()

# ── STT recorder helper (defined before tabs so it's available everywhere) ────
def _render_stt_recorder(field_key: str, groq_key: str):
    """Render a speech-to-text recorder for a given session state field."""
    if not AUDIO_RECORDER_AVAILABLE or not GROQ_AVAILABLE:
        return
    with st.expander("🎤 Record instead of typing"):
        if not groq_key:
            st.caption("Add a Groq API key in the sidebar to enable speech-to-text.")
            return
        audio_bytes = audio_recorder(text="Click to record", pause_threshold=3.0,
                                     key=f"recorder_{field_key}")
        if audio_bytes:
            with st.spinner("Transcribing..."):
                try:
                    transcribed = transcribe_audio(groq_key, audio_bytes)
                    st.session_state[field_key] = transcribed
                    st.success(f"Transcribed: {transcribed[:80]}{'...' if len(transcribed) > 80 else ''}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Transcription error: {e}")

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_write, tab_research, tab_history = st.tabs(["✍️  Write", "🔍  Research", "📋  History"])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — WRITE
# ════════════════════════════════════════════════════════════════════════════════
with tab_write:

    # ── Message type & purpose ────────────────────────────────────────────────
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        msg_type = st.selectbox("Message Type", ["LinkedIn InMail", "Email"])
    with col2:
        if msg_type == "LinkedIn InMail":
            purpose = st.selectbox("Purpose", [
                "Learn about a company / role",
                "Build relationship for internship search",
                "Reach out after applying to a role",
                "Request a referral",
                "Post-event follow-up (panel / info session)",
                "Alumni coffee chat",
                "Thank you after informational chat",
                "General networking / career advice",
            ])
        else:
            purpose = st.selectbox("Purpose", [
                "Follow up after meeting a recruiter",
                "Cold email to recruiter",
                "Networking (alumni / professional)",
                "Job / internship inquiry",
                "Request a referral",
                "Thank you after interview",
                "Post-event follow-up",
                "Thank you after informational chat",
                "Club or student org",
                "General student / academic",
            ])
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Recipient ─────────────────────────────────────────────────────────────
    st.markdown("### Recipient")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)

    li_col1, li_col2 = st.columns([4, 1])
    with li_col1:
        linkedin_url = st.text_input(
            "LinkedIn profile URL",
            placeholder="https://linkedin.com/in/... (optional — auto-fills fields below)",
        )
    with li_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch_li_btn = st.button("Auto-fill", use_container_width=True)

    if fetch_li_btn:
        if not linkedin_url:
            st.warning("Paste a LinkedIn URL first.")
        elif not api_key:
            st.warning("Enter your API key in the sidebar first.")
        else:
            with st.spinner("Fetching LinkedIn profile..."):
                profile_text, success = fetch_url_text(linkedin_url, max_chars=3000)
            if success and profile_text:
                with st.spinner("Extracting info..."):
                    info = extract_profile_info(api_key, profile_text)
                if info.get("name") or info.get("company"):
                    st.session_state["recipient_name"] = info.get("name", "")
                    st.session_state["recipient_role"] = info.get("role", "")
                    st.session_state["recipient_company"] = info.get("company", "")
                    st.session_state["linkedin_fetch_failed"] = False
                    st.success("Fields auto-filled! Check and edit below if needed.")
                else:
                    st.session_state["linkedin_fetch_failed"] = True
            else:
                st.session_state["linkedin_fetch_failed"] = True

    if st.session_state["linkedin_fetch_failed"]:
        st.info(
            "LinkedIn blocked the request (common). "
            "Paste the profile text below and click **Extract**."
        )
        pasted_li = st.text_area(
            "Paste LinkedIn profile text",
            placeholder="Copy the person's name, title, About section, or Experience from their LinkedIn page and paste here.",
            height=120,
        )
        if st.button("Extract from pasted text"):
            if not pasted_li:
                st.warning("Paste some profile text first.")
            elif not api_key:
                st.warning("Enter your API key in the sidebar first.")
            else:
                with st.spinner("Extracting..."):
                    info = extract_profile_info(api_key, pasted_li)
                if info.get("name") or info.get("company"):
                    st.session_state["recipient_name"] = info.get("name", "")
                    st.session_state["recipient_role"] = info.get("role", "")
                    st.session_state["recipient_company"] = info.get("company", "")
                    st.session_state["linkedin_fetch_failed"] = False
                    st.success("Fields auto-filled!")
                    st.rerun()
                else:
                    st.warning("Couldn't extract info — fill the fields below manually.")

    col3, col4, col5 = st.columns(3)
    with col3:
        recipient_name = st.text_input("First name", key="recipient_name",
                                       placeholder="e.g. Nikhil")
    with col4:
        recipient_role = st.text_input("Role / Title", key="recipient_role",
                                       placeholder="e.g. Head of S&O")
    with col5:
        recipient_company = st.text_input("Company", key="recipient_company",
                                          placeholder="e.g. Databricks")

    mutual_connection = st.text_input(
        "Mutual connection (optional)",
        placeholder="e.g. Shilpa Gopal (MBA '25) suggested I reach out",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Job Description ───────────────────────────────────────────────────────
    st.markdown("### Job Description")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    jd_col1, jd_col2 = st.columns([4, 1])
    with jd_col1:
        jd_url = st.text_input(
            "Job posting URL",
            placeholder="https://jobs.lever.co/... — paste URL to auto-fetch (optional)",
            label_visibility="collapsed",
        )
    with jd_col2:
        fetch_jd_btn = st.button("Fetch JD", use_container_width=True)

    if fetch_jd_btn:
        if not jd_url:
            st.warning("Paste a job URL first.")
        else:
            with st.spinner("Fetching job description..."):
                jd_content, success = fetch_url_text(jd_url, max_chars=4000)
            if success and jd_content:
                st.session_state["jd_text"] = jd_content
                st.success("Job description fetched! Review/edit below.")
            else:
                st.warning("Couldn't fetch the page. Paste the JD text below manually.")

    jd_text = st.text_area(
        "Job description",
        key="jd_text",
        placeholder="Job description will appear here after fetching, or paste it directly.",
        height=120,
        label_visibility="collapsed",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Additional Context ────────────────────────────────────────────────────
    st.markdown("### Additional Context")
    st.markdown('<div class="section-card">', unsafe_allow_html=True)

    input_mode = st.radio("Input mode",
                           ["Quick form", "Paste text", "Both"],
                           horizontal=True,
                           label_visibility="collapsed")

    key_angle = ""
    pasted_context = ""

    if input_mode in ["Quick form", "Both"]:
        _render_stt_recorder("key_angle_text", groq_api_key)
        key_angle = st.text_area(
            "What's the specific angle or ask?",
            value=st.session_state["key_angle_text"],
            placeholder=(
                "e.g. I applied to the MBA Intern S&O role. I want to ask for a 20-min chat and "
                "mention my background in consulting + Chief of Staff work."
            ),
            height=90,
            key="key_angle_input",
        )
        st.session_state["key_angle_text"] = key_angle

    if input_mode in ["Paste text", "Both"]:
        _render_stt_recorder("pasted_context_text", groq_api_key)
        pasted_context = st.text_area(
            "Paste any additional context",
            value=st.session_state["pasted_context_text"],
            placeholder="Recent news about the company, the person's recent posts, extra background, etc.",
            height=120,
            key="pasted_context_input",
        )
        st.session_state["pasted_context_text"] = pasted_context

    if st.session_state.get("company_news"):
        st.caption(
            f"News hooks loaded for **{st.session_state.get('company_news_for', '')}** — "
            "go to the Research tab to browse & add them."
        )

    tone = st.select_slider("Tone", options=["More formal", "Balanced", "Warm & personal"],
                             value="Balanced")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Generate ──────────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Generate Message", type="primary", use_container_width=True):
        if not api_key:
            st.error("Please enter your Anthropic API key in the sidebar.")
        elif not recipient_name or not recipient_company:
            st.error("Please fill in at least the recipient's name and company.")
        else:
            user_prompt = f"""Write a {msg_type} for the following situation:

Recipient: {recipient_name}, {recipient_role} at {recipient_company}
Message purpose: {purpose}
Tone: {tone}
Mutual connection: {mutual_connection if mutual_connection else "None"}

My background to draw from:
{background}
"""
            if jd_text:
                user_prompt += f"\nJob description (use this to tailor the message to the role):\n{jd_text}\n"
            if key_angle:
                user_prompt += f"\nKey angle / specific ask:\n{key_angle}\n"
            if pasted_context:
                user_prompt += f"\nAdditional context:\n{pasted_context}\n"

            user_prompt += "\nRemember: strictly 100-150 words for InMail, natural length for email. Be specific to this person and company."

            system_prompt = build_system_prompt(background, st.session_state["resume_bullets"],
                                                 recipient_company=recipient_company)

            with st.spinner("Writing your message..."):
                try:
                    result = generate_message(api_key, user_prompt, system_prompt)
                    st.session_state["result"] = result
                    save_to_history({
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "msg_type": msg_type,
                        "purpose": purpose,
                        "recipient_name": recipient_name,
                        "recipient_role": recipient_role,
                        "recipient_company": recipient_company,
                        "message": result,
                    })
                except Exception as e:
                    if "API_KEY" in str(e) or "invalid" in str(e).lower():
                        st.error("Invalid API key. Check your key at console.anthropic.com.")
                    else:
                        st.error(f"Error: {e}")

    # ── Output ────────────────────────────────────────────────────────────────
    if "result" in st.session_state:
        st.markdown("<br>", unsafe_allow_html=True)
        result_text = st.session_state["result"]
        wc = count_words(result_text)

        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:0.4rem;">'
            f'<span style="font-size:1rem;font-weight:600;color:#1e293b;">Your Message</span>'
            f'<span style="font-size:0.82rem;color:#6366f1;font-weight:500;">{wc} words</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        edited = st.text_area("Edit before copying", value=result_text, height=270,
                               label_visibility="collapsed", key="output_editor")
        edited_wc = count_words(edited)
        st.markdown(f'<p class="word-count">{edited_wc} words</p>', unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns([2, 2, 1])
        with col_a:
            if st.button("Regenerate", use_container_width=True):
                del st.session_state["result"]
                st.rerun()
        with col_b:
            st.download_button("Download .txt", data=edited,
                               file_name="message.txt", mime="text/plain",
                               use_container_width=True)
        with col_c:
            st.markdown(
                f'<p style="font-size:0.78rem;color:#9ca3af;padding-top:8px;text-align:center;">'
                f'Saved to history</p>',
                unsafe_allow_html=True,
            )

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — RESEARCH
# ════════════════════════════════════════════════════════════════════════════════
with tab_research:
    st.caption("Use these tools to research your recipient before writing. Results feed into the Write tab.")

    # ── LinkedIn Profile Analyzer ─────────────────────────────────────────────
    st.markdown("### LinkedIn Profile Analyzer")
    st.markdown('<div class="section-card-dark">', unsafe_allow_html=True)
    st.caption("Paste the full LinkedIn profile text — AI extracts highlights, personalization hooks, and suggests a message angle.")

    li_full_text = st.text_area(
        "LinkedIn profile text",
        placeholder="Copy everything from their LinkedIn page: name, title, About, Experience, Education...",
        height=180,
        label_visibility="collapsed",
    )
    if st.button("Analyze Profile", use_container_width=True, key="analyze_profile_btn"):
        if not li_full_text.strip():
            st.warning("Paste some profile text first.")
        elif not api_key:
            st.warning("Enter your Anthropic API key in the sidebar first.")
        else:
            with st.spinner("Analyzing profile..."):
                try:
                    analysis = analyze_linkedin_profile(api_key, li_full_text, background)
                    st.session_state["li_analysis"] = analysis
                    info = extract_profile_info(api_key, li_full_text)
                    if info.get("name") or info.get("company"):
                        st.session_state["recipient_name"] = info.get("name", st.session_state["recipient_name"])
                        st.session_state["recipient_role"] = info.get("role", st.session_state["recipient_role"])
                        st.session_state["recipient_company"] = info.get("company", st.session_state["recipient_company"])
                        st.success("Recipient fields auto-filled in the Write tab!")
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.session_state["li_analysis"]:
        st.markdown(st.session_state["li_analysis"])
        if st.button("Send suggested angle → Write tab", key="use_angle_btn"):
            analysis_text = st.session_state["li_analysis"]
            angle_match = re.search(r"## Suggested Message Angle\n(.+?)(?:\n##|$)", analysis_text, re.DOTALL)
            if angle_match:
                st.session_state["key_angle_text"] = angle_match.group(1).strip()
                st.success("Angle sent! Switch to the Write tab and it'll be pre-filled.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Company News ──────────────────────────────────────────────────────────
    st.markdown("### Company News Search")
    st.markdown('<div class="section-card-dark">', unsafe_allow_html=True)
    st.caption("Searches the last 6 months of news about the company and generates message hooks you can reference.")

    news_company = st.text_input(
        "Company",
        value=st.session_state.get("recipient_company", ""),
        placeholder="e.g. Databricks",
        key="news_company_input",
    )
    news_role = st.text_input(
        "Role / team (optional, narrows results)",
        value=st.session_state.get("recipient_role", ""),
        placeholder="e.g. Strategy & Operations",
        key="news_role_input",
    )
    if st.button("Search recent news", use_container_width=True, key="search_news_btn"):
        if not news_company.strip():
            st.warning("Enter a company name first.")
        elif not api_key:
            st.warning("Enter your Anthropic API key in the sidebar first.")
        else:
            with st.spinner(f"Searching recent news for {news_company}..."):
                try:
                    news_items = search_company_news(api_key, news_company, news_role)
                    st.session_state["company_news"] = news_items
                    st.session_state["company_news_for"] = news_company
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.session_state["company_news"] = []

    if st.session_state.get("company_news"):
        st.markdown(f"**Recent updates for {st.session_state.get('company_news_for', '')}:**")
        for i, item in enumerate(st.session_state["company_news"]):
            col_news, col_btn = st.columns([5, 1])
            with col_news:
                st.markdown(f"**{item.get('title', '')}**")
                st.caption(item.get("hook", ""))
                if item.get("url"):
                    st.caption(f"[{item['url'][:60]}]")
            with col_btn:
                if st.button("Use", key=f"use_news_{i}", use_container_width=True):
                    hook_text = item.get("hook", item.get("title", ""))
                    existing = st.session_state.get("pasted_context_text", "")
                    st.session_state["pasted_context_text"] = (
                        f"{existing}\n\nRecent news hook: {hook_text}".strip()
                    )
                    st.success("Hook added to context in the Write tab!")
    elif "company_news" in st.session_state and st.session_state["company_news"] == []:
        st.info("No recent news found — try a different company name or add context manually.")
    st.markdown('</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — HISTORY
# ════════════════════════════════════════════════════════════════════════════════
with tab_history:
    history = load_history()
    if not history:
        st.markdown(
            '<div style="text-align:center;padding:3rem 1rem;color:#94a3b8;">'
            '<div style="font-size:2.5rem;margin-bottom:0.5rem;">📭</div>'
            '<div style="font-size:1rem;font-weight:500;">No messages yet</div>'
            '<div style="font-size:0.87rem;margin-top:0.3rem;">Generate a message in the Write tab and it\'ll appear here.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        h_col1, h_col2, h_col3 = st.columns([3, 1, 1])
        with h_col1:
            st.markdown(
                f'<p style="color:#64748b;font-size:0.9rem;padding-top:6px;">'
                f'{len(history)} message{"s" if len(history) != 1 else ""} saved</p>',
                unsafe_allow_html=True,
            )
        with h_col2:
            csv_data = history_to_csv(history)
            st.download_button("Download CSV", data=csv_data,
                               file_name="message_history.csv", mime="text/csv",
                               use_container_width=True)
        with h_col3:
            if st.session_state["history_confirm_clear"]:
                pass  # handled below
            else:
                if st.button("Clear all", use_container_width=True):
                    st.session_state["history_confirm_clear"] = True
                    st.rerun()

        if st.session_state["history_confirm_clear"]:
            st.warning("This will permanently delete all saved messages. Are you sure?")
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("Yes, delete all", use_container_width=True, type="primary"):
                    if os.path.exists(HISTORY_FILE):
                        os.remove(HISTORY_FILE)
                    st.session_state["history_confirm_clear"] = False
                    st.rerun()
            with cc2:
                if st.button("Cancel", use_container_width=True):
                    st.session_state["history_confirm_clear"] = False
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        for i, entry in enumerate(reversed(history)):
            ts = entry.get("timestamp", "")
            name = entry.get("recipient_name", "?")
            company = entry.get("recipient_company", "?")
            mtype = entry.get("msg_type", "")
            label = f"{ts}  ·  **{name}** @ {company}  ·  {mtype}"
            with st.expander(label):
                purpose_label = entry.get("purpose", "")
                if purpose_label:
                    st.caption(purpose_label)
                msg_val = entry.get("message", "")
                wc_h = count_words(msg_val)
                st.markdown(
                    f'<p style="font-size:0.78rem;color:#6366f1;margin-bottom:4px;">{wc_h} words</p>',
                    unsafe_allow_html=True,
                )
                st.text_area("Message", value=msg_val, height=200,
                             label_visibility="collapsed",
                             key=f"hist_msg_{i}")
                st.download_button(
                    "Download .txt",
                    data=msg_val,
                    file_name=f"message_{ts.replace(' ', '_').replace(':', '-')}.txt",
                    mime="text/plain",
                    key=f"hist_dl_{i}",
                    use_container_width=True,
                )
