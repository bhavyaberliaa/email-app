import streamlit as st
import google.generativeai as genai

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

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a professional message writer for Bhavya Berlia, a first-year MBA student at UC Berkeley Haas (Class of 2027). You write tailored emails and LinkedIn InMails in Bhavya's authentic voice.

BHAVYA'S BACKGROUND:
{DEFAULT_BACKGROUND}

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

INSTRUCTIONS:
- Write ONLY the message (subject line if InMail, then body). No preamble, no explanation.
- Match the tone and structure from the examples above.
- Be specific to the recipient's company and role — generic messages are unacceptable.
- If bullets are appropriate (e.g., recruiter follow-up with resume), use them.
- Count words carefully and stay within the length rule.
"""

# ── Helpers ───────────────────────────────────────────────────────────────────
def count_words(text: str) -> int:
    return len(text.split())

def generate_message(api_key: str, user_prompt: str) -> str:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(user_prompt)
    return response.text

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("✉️ Bhavya's Message Writer")
st.caption("Write tailored 100–150 word emails & LinkedIn InMails in seconds.")

# API Key
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input("Gemini API Key", type="password",
                            help="Get yours free at aistudio.google.com")
    st.divider()
    st.subheader("Your Background")
    background = st.text_area("Edit your background (used in all prompts)",
                               value=DEFAULT_BACKGROUND, height=220)
    st.caption("This is pre-filled with your profile. Edit anytime.")

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
            "General networking / career advice",
        ])
    else:
        purpose = st.selectbox("Purpose", [
            "Follow up after meeting a recruiter",
            "Cold email to recruiter",
            "Networking (alumni / professional)",
            "Job / internship inquiry",
            "Club or student org",
            "General student / academic",
        ])

st.divider()

# Recipient info
st.subheader("Recipient")
col3, col4, col5 = st.columns(3)
with col3:
    recipient_name = st.text_input("First name", placeholder="e.g. Nikhil")
with col4:
    recipient_role = st.text_input("Role / Title", placeholder="e.g. Head of S&O")
with col5:
    recipient_company = st.text_input("Company", placeholder="e.g. Databricks")

mutual_connection = st.text_input("Mutual connection (optional)",
                                   placeholder="e.g. Shilpa Gopal (MBA '25) suggested I reach out")

st.divider()

# Context
st.subheader("Context")
input_mode = st.radio("How do you want to add context?",
                       ["Quick form", "Paste LinkedIn profile / job description", "Both"],
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

if input_mode in ["Paste LinkedIn profile / job description", "Both"]:
    pasted_context = st.text_area(
        "Paste LinkedIn bio, job description, or any relevant context",
        placeholder="Paste the job description, the person's LinkedIn About section, recent news about the company, etc.",
        height=180,
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
        if key_angle:
            user_prompt += f"\nKey angle / specific ask:\n{key_angle}\n"
        if pasted_context:
            user_prompt += f"\nAdditional context (LinkedIn / job description / notes):\n{pasted_context}\n"

        user_prompt += "\nRemember: strictly 100-150 words for InMail, natural length for email. Be specific to this person and company."

        with st.spinner("Writing your message..."):
            try:
                result = generate_message(api_key, user_prompt)
                st.session_state["result"] = result
            except Exception as e:
                if "API_KEY" in str(e) or "invalid" in str(e).lower():
                    st.error("Invalid API key. Check your key at aistudio.google.com.")
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
            # rerun will re-trigger the generate block — just clear result
            del st.session_state["result"]
            st.rerun()
    with col_b:
        st.download_button("Download as .txt", data=edited,
                           file_name="message.txt", mime="text/plain",
                           use_container_width=True)
