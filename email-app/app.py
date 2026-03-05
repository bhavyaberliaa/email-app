import os
import anthropic
import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="Bhavya's Message Writer", page_icon="✉️", layout="centered")

# ── Style ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { max-width: 780px; }
    .stTextArea textarea { font-size: 14px; }
    .word-count { font-size: 13px; color: #888; margin-top: -12px; }
</style>
""", unsafe_allow_html=True)

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
def build_system_prompt(background_text: str, resume_bullets: dict) -> str:
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
        prompt += """
BHAVYA'S RESUME BULLETS BY ROLE TYPE:
Use these to pick the most relevant 2-3 highlights based on the target role/company. Match bullets to what the recipient cares about.
"""
        for role_type, bullets in resume_bullets.items():
            prompt += f"\n[{role_type}]\n{bullets}\n"

    prompt += """
INSTRUCTIONS:
- Write ONLY the message (subject line if InMail, then body). No preamble, no explanation.
- Match the tone and structure from the examples above.
- Be specific to the recipient's company and role — generic messages are unacceptable.
- If bullets are appropriate (e.g., recruiter follow-up with resume), use them.
- If resume bullets by role type are provided above, select the most relevant ones for this specific message.
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

def parse_resume_file(uploaded_file) -> dict:
    """Parse an uploaded .json or .txt resume bullets file."""
    content = uploaded_file.read().decode("utf-8")
    if uploaded_file.name.endswith(".json"):
        try:
            return json.loads(content)
        except Exception:
            return {}
    # Parse .txt with [Section] headers
    result = {}
    current_section = None
    lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_section and lines:
                result[current_section] = "\n".join(lines)
            current_section = stripped[1:-1]
            lines = []
        elif current_section and stripped:
            lines.append(stripped)
    if current_section and lines:
        result[current_section] = "\n".join(lines)
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
]:
    if _key not in st.session_state:
        st.session_state[_key] = _default

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("✉️ Bhavya's Message Writer")
st.caption("Write tailored 100–150 word emails & LinkedIn InMails in seconds.")

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
            for role, bullets in st.session_state["resume_bullets"].items():
                st.markdown(f"**{role}**")
                st.text(bullets)
        if st.button("Clear resume bullets", use_container_width=True):
            st.session_state["resume_bullets"] = {}
            st.rerun()

# ── Main form ─────────────────────────────────────────────────────────────────
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

st.divider()

# ── Recipient ─────────────────────────────────────────────────────────────────
st.subheader("Recipient")

# LinkedIn auto-fill
li_col1, li_col2 = st.columns([4, 1])
with li_col1:
    linkedin_url = st.text_input(
        "LinkedIn profile URL (optional)",
        placeholder="https://linkedin.com/in/...",
    )
with li_col2:
    st.markdown("<br>", unsafe_allow_html=True)  # vertical align
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

st.divider()

# ── Job Description ───────────────────────────────────────────────────────────
st.subheader("Job Description (optional)")
jd_col1, jd_col2 = st.columns([4, 1])
with jd_col1:
    jd_url = st.text_input(
        "Job posting URL",
        placeholder="https://jobs.lever.co/... or any job board URL",
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
    "Job description text",
    key="jd_text",
    placeholder="Job description will appear here after fetching, or paste it manually.",
    height=130,
    label_visibility="collapsed",
)

st.divider()

# ── Context ───────────────────────────────────────────────────────────────────
st.subheader("Additional Context")
input_mode = st.radio("How do you want to add context?",
                       ["Quick form", "Paste text", "Both"],
                       horizontal=True)

key_angle = ""
pasted_context = ""

if input_mode in ["Quick form", "Both"]:
    key_angle = st.text_area(
        "What's the specific angle or ask?",
        placeholder=(
            "e.g. I applied to the MBA Intern S&O role. I want to ask for a 20-min chat and "
            "mention my background in consulting + Chief of Staff work."
        ),
        height=100,
    )

if input_mode in ["Paste text", "Both"]:
    pasted_context = st.text_area(
        "Paste any additional context",
        placeholder="Recent news about the company, the person's recent posts, extra background, etc.",
        height=130,
    )

tone = st.select_slider("Tone", options=["More formal", "Balanced", "Warm & personal"],
                         value="Balanced")

st.divider()

# ── Generate ──────────────────────────────────────────────────────────────────
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

        system_prompt = build_system_prompt(background, st.session_state["resume_bullets"])

        with st.spinner("Writing your message..."):
            try:
                result = generate_message(api_key, user_prompt, system_prompt)
                st.session_state["result"] = result
            except Exception as e:
                if "API_KEY" in str(e) or "invalid" in str(e).lower():
                    st.error("Invalid API key. Check your key at console.anthropic.com.")
                else:
                    st.error(f"Error: {e}")

# ── Output ────────────────────────────────────────────────────────────────────
if "result" in st.session_state:
    st.divider()
    st.subheader("Your Message")
    result_text = st.session_state["result"]
    wc = count_words(result_text)
    st.markdown(f'<p class="word-count">{wc} words</p>', unsafe_allow_html=True)

    edited = st.text_area("Edit before copying", value=result_text, height=280,
                           label_visibility="collapsed")
    edited_wc = count_words(edited)
    st.markdown(f'<p class="word-count">{edited_wc} words</p>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Regenerate", use_container_width=True):
            del st.session_state["result"]
            st.rerun()
    with col_b:
        st.download_button("Download as .txt", data=edited,
                           file_name="message.txt", mime="text/plain",
                           use_container_width=True)
