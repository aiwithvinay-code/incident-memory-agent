"""Incident Response Agent with persistent memory (Hindsight). Run: streamlit run app.py"""
import os, time, html
import streamlit as st
from dotenv import load_dotenv
from hindsight_client import Hindsight
from openai import OpenAI

load_dotenv()

def get_secret(name, default=None):
    v = os.getenv(name)
    if v:
        return v
    try:
        return st.secrets[name]
    except Exception:
        return default

st.set_page_config(page_title="Incident Memory Agent", page_icon="🧠", layout="wide")

BANK = get_secret("BANK_ID", "incident-bank")
HS_KEY = get_secret("HINDSIGHT_API_KEY")
GROQ_KEY = get_secret("GROQ_API_KEY")
if not HS_KEY or not GROQ_KEY:
    st.error("Missing API keys. Add HINDSIGHT_API_KEY and GROQ_API_KEY in your .env file or the app's Secrets settings.")
    st.stop()

hs = Hindsight(base_url=get_secret("HINDSIGHT_URL", "https://api.hindsight.vectorize.io"), api_key=HS_KEY)
llm = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_KEY)
MODELS = ["openai/gpt-oss-120b", "qwen/qwen3-32b"]

SYSTEM = ("You are an on-call SRE assistant. Given a new incident and (optionally) memories of past "
          "incidents, diagnose the likely root cause and give concrete fix steps. If memory shows a "
          "fix FAILED before, say not to repeat it. If you see a repeating pattern, point it out. "
          "Cite which past incident you are relying on. Format: **Likely cause**, **Do this now** "
          "(numbered steps), **Avoid** (only if memory shows a failed fix). Be concise.")

EXAMPLES = {
    "Payments timeouts": "payments-service: 504 timeouts, error 'connection pool exhausted'",
    "Cart data loss": "cart-service: users losing cart items, Redis READONLY errors after maintenance",
    "Friday deploy errors": "checkout-service: spike of 500 errors right after a Friday 5pm deploy",
}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stApp { font-family: 'Figtree', sans-serif; }
.stApp { background: #EEF1F6; color: #1B2433; }
.block-container { padding-top: 2rem; max-width: 1200px; }
h1 { font-weight: 700; letter-spacing: -0.02em; margin-bottom: 0; }
.sub { color: #5B6675; margin: 0 0 1.2rem 0; font-size: 1.05rem; }
.stat { background:#fff; border-radius:12px; padding:14px 18px; border:1px solid #DDE3EC; color:#1B2433; }
.stat b { font-size: 1.6rem; display:block; line-height:1.1; }
.stat span { color:#5B6675; font-size:.9rem; }
.trail { background:#fff; border-radius:10px; padding:12px 14px; margin-bottom:10px; color:#1B2433;
         border:1px solid #DDE3EC; border-left:5px solid #9AA5B4; font-size:.92rem; line-height:1.45; }
.trail.worked { border-left-color:#1E9E63; } .trail.failed { border-left-color:#D6402F; }
.badge { display:inline-block; padding:2px 10px; border-radius:99px; font-size:.78rem;
         font-weight:600; margin-bottom:6px; background:#E6EAF0; color:#44505F; }
.badge.worked { background:#DDF3E8; color:#137548; } .badge.failed { background:#FBE1DD; color:#A32A1C; }
.pill { display:inline-block; padding:3px 12px; border-radius:99px; font-size:.82rem; font-weight:600; }
.pill.on { background:#DCE6FD; color:#2143B0; } .pill.off { background:#E6EAF0; color:#44505F; }
.empty { color:#5B6675; padding:14px; border:1px dashed #B9C2CF; border-radius:10px; background:#fff; }
</style>
""", unsafe_allow_html=True)

for k, v in {"n_diag": 0, "n_recalled": 0, "n_retained": 0}.items():
    st.session_state.setdefault(k, v)

def ask_llm(prompt):
    err = None
    for attempt in range(3):
        try:
            r = llm.chat.completions.create(model=MODELS[attempt % 2], temperature=0.3,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
            return r.choices[0].message.content
        except Exception as e:
            err = e; time.sleep(1)
    return f"⚠️ The AI model didn't respond ({err}). Click Diagnose to try again."

def trail(memories):
    if not memories:
        st.markdown('<div class="empty">No past incidents recalled yet. Diagnose an incident to see what the team already knows.</div>', unsafe_allow_html=True)
        return
    for m in memories:
        t = m.upper()
        cls = "failed" if "FAILED" in t else "worked" if "WORKED" in t else ""
        label = {"failed": "Fix failed", "worked": "Fix worked"}.get(cls, "Related memory")
        st.markdown(f'<div class="trail {cls}"><span class="badge {cls}">{label}</span><br>{html.escape(m)}</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Settings")
    use_memory = st.toggle("Use team memory", value=True,
                           help="Turn off to see how the agent answers without memory.")
    st.caption("Switch this off and rerun the same incident to compare a generic answer with a remembered one.")
    st.divider()
    st.caption("Memory: Hindsight · Model: Groq")

st.title("🧠 On-Call Memory Agent")
st.markdown('<p class="sub">Paste an incident. The agent recalls how your team fixed it before, and learns from every outcome.</p>', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
c1.markdown(f'<div class="stat"><b>{st.session_state.n_diag}</b><span>Incidents diagnosed this session</span></div>', unsafe_allow_html=True)
c2.markdown(f'<div class="stat"><b>{st.session_state.n_recalled}</b><span>Past incidents recalled</span></div>', unsafe_allow_html=True)
c3.markdown(f'<div class="stat"><b>{st.session_state.n_retained}</b><span>New lessons saved</span></div>', unsafe_allow_html=True)
st.write("")

tab1, tab2, tab3 = st.tabs(["Diagnose", "Memory explorer", "Recurring patterns"])

with tab1:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.caption("Try an example:")
        ex_cols = st.columns(len(EXAMPLES))
        for col, (name, text) in zip(ex_cols, EXAMPLES.items()):
            col.button(name, use_container_width=True, on_click=lambda t=text: st.session_state.update(incident_text=t))
        incident = st.text_area("What's happening?", key="incident_text", height=130,
                                placeholder="service name, symptoms, error messages, when it started")
        sev = st.radio("Severity", ["SEV1 – outage", "SEV2 – degraded", "SEV3 – minor"], index=1, horizontal=True)
        if st.button("Diagnose incident", type="primary", use_container_width=True):
            if not incident.strip():
                st.warning("Describe the incident first, or pick an example above.")
            else:
                with st.spinner("Checking team memory and thinking..."):
                    memories = []
                    if use_memory:
                        try:
                            memories = [m.text for m in hs.recall(bank_id=BANK, query=incident).results][:6]
                        except Exception as e:
                            st.error(f"Couldn't reach memory: {e}")
                    ctx = "\n".join(f"- {m}" for m in memories) or "(no memory used)"
                    ans = ask_llm(f"Severity: {sev}\nNew incident:\n{incident}\n\nPast memories:\n{ctx}")
                st.session_state.update(incident=incident, memories=memories, answer=ans,
                                        used_memory=use_memory, saved=False)
                st.session_state.n_diag += 1
                st.session_state.n_recalled += len(memories)

        if "answer" in st.session_state:
            with st.container(border=True):
                pill = ('<span class="pill on">Memory on</span>' if st.session_state.used_memory
                        else '<span class="pill off">Memory off</span>')
                st.markdown(f"#### Diagnosis {pill}", unsafe_allow_html=True)
                st.markdown(st.session_state.answer)
            with st.container(border=True):
                st.markdown("#### Teach the agent")
                outcome = st.radio("Did the suggested fix work?", ["worked", "failed", "partially"], horizontal=True)
                notes = st.text_area("What actually fixed it? (optional)", height=80)
                if st.button("Save lesson to memory", disabled=st.session_state.saved):
                    text = (f"Incident: {st.session_state.incident}. Agent suggested: {st.session_state.answer[:600]}. "
                            f"Outcome: {outcome.upper()}. Engineer feedback: {notes or 'none'}.")
                    try:
                        hs.retain(bank_id=BANK, content=text, context="resolved incident with feedback")
                        st.session_state.saved = True
                        st.session_state.n_retained += 1
                        st.toast("Lesson saved. The agent will use it next time.", icon="✅")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Couldn't save to memory: {e}")
                if st.session_state.saved:
                    st.success("Saved. Try a similar incident to see it recalled.")
    with right:
        st.markdown("#### Memory trail")
        st.caption("Past incidents the agent used for this diagnosis.")
        trail(st.session_state.get("memories", []))

with tab2:
    st.markdown("Search everything the agent knows.")
    q = st.text_input("Search", value="past incidents and their fixes", label_visibility="collapsed")
    if st.button("Search memory"):
        with st.spinner("Searching..."):
            try:
                res = [m.text for m in hs.recall(bank_id=BANK, query=q).results]
                st.caption(f"{len(res)} memories found")
                trail(res)
            except Exception as e:
                st.error(f"Search failed: {e}")

with tab3:
    st.markdown("Ask the agent to look across every incident and find what keeps going wrong.")
    if st.button("Find recurring patterns", type="primary"):
        with st.spinner("Reflecting across all incidents..."):
            try:
                r = hs.reflect(bank_id=BANK, query=(
                    "What recurring failure patterns exist across incidents, which fixes failed before, "
                    "and what preventive actions do you recommend?"))
                with st.container(border=True):
                    st.markdown(getattr(r, "text", str(r)))
            except Exception as e:
                st.error(f"Couldn't analyze patterns: {e}")