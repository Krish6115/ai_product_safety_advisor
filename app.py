"""
app.py  –  Mumzworld AI Smart Product Safety Advisor
=====================================================
Images expected in the SAME folder as this file:
  logo.png        → welcome screen centre icon
  mumz_world.png  → header brand image (replaces text)
"""

import streamlit as st
import streamlit.components.v1 as components
import base64, os
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be the very first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Mumzworld Safety Advisor",
    page_icon="🛡️",
    layout="wide",                     # wide → header can span full viewport
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# LOCAL IMAGE → BASE-64 DATA-URI
# ─────────────────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))

def _b64(fname: str) -> str:
    p = os.path.join(_DIR, fname)
    if not os.path.exists(p):
        return ""
    ext  = fname.rsplit(".", 1)[-1].lower()
    mime = {"png":"image/png","jpg":"image/jpeg","jpeg":"image/jpeg",
            "svg":"image/svg+xml","webp":"image/webp"}.get(ext,"image/png")
    return f"data:{mime};base64," + base64.b64encode(open(p,"rb").read()).decode()

BRAND_SRC = _b64("mumz_world.png")   # header logo
ICON_SRC  = _b64("logo.png")         # welcome-screen icon

# ─────────────────────────────────────────────────────────────────────────────
# BACKEND  (tries real agent, falls back to mock)
# ─────────────────────────────────────────────────────────────────────────────
import sys
sys.path.insert(0, _DIR)

def _try_import():
    for mp, fn in [
        ("agent.advisor","run_advisor"), ("agent.advisor","get_recommendation"),
        ("agent.main","run_advisor"),    ("agent.main","get_recommendation"),
        ("agent.agent","run_advisor"),   ("agent.agent","get_recommendation"),
    ]:
        try:
            import importlib
            m = importlib.import_module(mp)
            f = getattr(m, fn, None)
            if callable(f): return f
        except Exception: pass
    return None

_backend = _try_import()

def _mock(query: str) -> dict:
    q = query.lower()
    if any(w in q for w in ["knife","choking","toxic","sharp","unsafe"]):
        return {"query_language":"en","recommendation":"NOT_SUITABLE","confidence":0.91,
                "safety_flags":["choking_hazard","sharp_edges"],
                "reasoning":"This product contains small detachable parts posing a choking hazard for children under 36 months, and sharp edges increase injury risk.",
                "reasoning_trace":["Identified product","Child age: under 3 yrs",
                    "Small detachable parts → choking hazard","Hard plastic with sharp edges",
                    "[OVERRIDE] Critical flags → forced NOT_SUITABLE"],
                "alternatives":[{"product_id":"MW-027","name":"Playgro Sensory Toy",
                    "reason":"No small parts, safe for infants 0–36 months"}]}
    if any(w in q for w in ["unknown","missing","no data","uncertain"]):
        return {"query_language":"en","recommendation":"UNCERTAIN","confidence":0.42,
                "safety_flags":[],"reasoning":"Insufficient product data. Cannot make a definitive recommendation.",
                "reasoning_trace":["Query processed","RAG score 0.31 < threshold 0.40","→ UNCERTAIN"],
                "alternatives":[]}
    return {"query_language":"en","recommendation":"SUITABLE","confidence":0.88,
            "safety_flags":[],"reasoning":"Product meets all safety requirements. No hazardous materials or small parts.",
            "reasoning_trace":["Product identified","Age group validated","No flags","→ SUITABLE"],
            "alternatives":[]}

def call_backend(query: str) -> dict:
    fn = _backend or _mock
    try:
        r = fn(query)
        if hasattr(r,"model_dump"): return r.model_dump()
        if hasattr(r,"dict"):       return r.dict()
        if isinstance(r,dict):      return r
    except Exception as e:
        return {"query_language":"en","recommendation":"UNCERTAIN","confidence":0.0,
                "safety_flags":[],"reasoning":f"Error: {e}","reasoning_trace":[str(e)],"alternatives":[]}
    return _mock(query)

# ─────────────────────────────────────────────────────────────────────────────
# CSS  — force light theme + full styling
# ─────────────────────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900&display=swap');

/* ═══ FORCE LIGHT MODE — override Streamlit dark theme ═══ */
html {
    color-scheme: light !important;
}
html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
section.main,
.main {
    background-color: #ffffff !important;
    background: #ffffff !important;
    color: #111111 !important;
}
/* kill any dark overlays */
[data-testid="stAppViewContainer"] > div { background: transparent !important; }

/* ═══ GLOBAL RESET ═══ */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"] {
    font-family: 'Nunito', sans-serif !important;
}

/* ═══ STRIP STREAMLIT CHROME ═══ */
#MainMenu, footer, header          { visibility: hidden !important; height: 0 !important; }
[data-testid="stToolbar"]          { display: none !important; }
[data-testid="stDecoration"]       { display: none !important; }
[data-testid="stStatusWidget"]     { display: none !important; }
[data-testid="stSidebarContent"]   { display: none !important; }

/* with layout=wide, remove all default padding from block container */
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}
[data-testid="stVerticalBlock"]       { gap: 0 !important; }
[data-testid="stMarkdownContainer"] p { margin: 0 !important; }

/* ═══ HEADER — full viewport width ═══ */
.mw-header {
    width: 100%;
    background: #d12d59;
    padding: 16px 32px 14px;
    box-shadow: 0 3px 20px rgba(209, 45, 89, 0.25);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
}
.mw-brand img {
    height: 75px;
    width: auto;
    display: block;
    object-fit: contain;
    /* NO brightness/invert filter — show logo as-is on pink background */
}
.mw-brand-fallback {
    font-size: 26px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: -1px;
    font-family: 'Nunito', sans-serif;
}
.mw-brand-fallback span { opacity: 0.65; font-weight: 400; }
.mw-header-right { text-align: right; }
.mw-header-q {
    font-size: 14px;
    font-weight: 800;
    color: #ffffff;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 7px;
    margin-bottom: 2px;
}
.mw-header-sub {
    font-size: 11.5px;
    color: rgba(255,255,255,0.70);
    font-weight: 500;
}
.mw-pulse {
    width: 8px; height: 8px; border-radius: 50%;
    background: #5dffc0; display: inline-block; flex-shrink: 0;
    animation: pulse 1.8s infinite;
}
@keyframes pulse {
    0%,100% { box-shadow: 0 0 0 0   rgba(93,255,192,0.7); }
    60%     { box-shadow: 0 0 0 8px rgba(93,255,192,0);   }
}

/* ═══ CONTENT WRAPPER — centres everything below header ═══ */
.mw-wrap {
    max-width: 700px;
    margin: 0 auto;
    padding: 24px 20px 120px;
}

/* ═══ WELCOME SCREEN ═══ */
.mw-welcome { text-align: center; padding: 40px 16px 16px; }
.mw-welcome img.mw-icon {
    height: 80px; width: auto;
    display: block; margin: 0 auto 18px;
    filter: drop-shadow(0 4px 14px rgba(255,0,85,0.15));
}
.mw-welcome .mw-icon-fallback { font-size: 68px; margin-bottom: 14px; }
.mw-welcome h1 {
    font-size: 23px; font-weight: 900;
    color: #0d0d0d; margin-bottom: 10px;
}
.mw-welcome p {
    font-size: 14px; color: #888888; line-height: 1.7;
    max-width: 520px; margin: 0 auto 28px !important;
    text-align: center !important;
}
.mw-chips {
    display: flex; flex-wrap: wrap;
    justify-content: center; gap: 9px;
}
.mw-chip {
    border: 1.5px solid #ff0055; color: #ff0055;
    background: #ffffff; border-radius: 99px;
    font-size: 12.5px; font-weight: 700;
    font-family: 'Nunito', sans-serif;
    padding: 7px 16px; cursor: pointer;
    transition: all 0.14s ease;
    box-shadow: 0 1px 5px rgba(255,0,85,0.07);
}
.mw-chip:hover {
    background: #ff0055; color: #fff;
    box-shadow: 0 3px 12px rgba(255,0,85,0.22);
}

/* ═══ MESSAGE ROWS ═══ */
.mw-row { display: flex; margin-bottom: 16px; animation: fi .22s ease; }
.mw-row.user { justify-content: flex-end; }
.mw-row.ai   { justify-content: flex-start; align-items: flex-start; }
@keyframes fi {
    from { opacity:0; transform:translateY(7px); }
    to   { opacity:1; transform:translateY(0);   }
}

/* avatars */
.mw-av {
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 11px; font-weight: 800; flex-shrink: 0;
}
.mw-av.ai  { background:#ff0055; color:#fff; margin-right:9px; margin-top:3px; }
.mw-av.usr { background:#ffe0ea; color:#c8003e; margin-left:9px; margin-top:3px; }

/* bubbles */
.mw-b {
    border-radius: 18px;
    padding: 11px 16px;
    font-size: 14px;
    line-height: 1.65;
}
.mw-b.user-b {
    background: #ff0055; color: #fff;
    border-bottom-right-radius: 4px; max-width: 70%;
}
.mw-b.ai-b {
    background: #ffffff; color: #111111;
    border-bottom-left-radius: 4px; max-width: 85%;
    box-shadow: 0 2px 14px rgba(0,0,0,0.07);
}
.mw-ts { font-size: 10px; margin-top: 4px; }
.mw-ts.l { color: rgba(255,255,255,0.6); text-align: right; }
.mw-ts.d { color: #c0c0c0; }

/* ═══ SAFETY CARD ═══ */
.sc-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 3px 13px; border-radius: 99px;
    font-size: 11px; font-weight: 800;
    letter-spacing: 0.8px; text-transform: uppercase;
    margin-bottom: 10px;
}
.sc-safe     { background:#eafaf1; color:#1a9955; border:1.5px solid #1a9955; }
.sc-unsafe   { background:#fff2f5; color:#cc0035; border:1.5px solid #cc0035; }
.sc-uncertain{ background:#fffbea; color:#a07000; border:1.5px solid #c9a000; }

.sc-product { font-size:14.5px; font-weight:800; color:#0d0d0d; margin-bottom:5px; }
.sc-conf-row {
    display:flex; align-items:center; gap:9px;
    font-size:11.5px; color:#999; margin-bottom:11px;
}
.sc-track { flex:1; height:5px; border-radius:99px; background:#efefef; overflow:hidden; }
.sc-fill  { height:100%; border-radius:99px;
            background: linear-gradient(90deg, #ff0055, #ff6699); }
.sc-reason {
    font-size:13px; color:#444; line-height:1.65;
    background:#f9f9fb; border-radius:10px;
    padding:10px 13px; margin-bottom:10px;
    border-left:3px solid #ff0055;
}
.sc-st {
    font-size:10px; font-weight:800;
    text-transform:uppercase; letter-spacing:0.7px;
    color:#c8c8c8; margin:8px 0 5px;
}
.sc-flags { display:flex; flex-wrap:wrap; gap:5px; margin-bottom:8px; }
.sc-flag {
    background:#fff0f4; color:#c0003a;
    border:1px solid #ffc0d0; border-radius:99px;
    font-size:11px; font-weight:600; padding:2px 10px;
}
.sc-alt {
    background:#f6f6f9; border-radius:10px;
    padding:9px 12px; margin-bottom:6px;
    border:1px solid #ededf2;
}
.sc-alt-head { display:flex; justify-content:space-between; align-items:flex-start; }
.sc-alt-name { font-size:13px; font-weight:700; color:#111; }
.sc-alt-id   { font-size:10px; color:#bbb; font-family:monospace; }
.sc-alt-why  { font-size:12px; color:#666; margin-top:3px; }

details.sc-tr { margin-top:10px; }
details.sc-tr > summary {
    font-size:11.5px; color:#bbb;
    cursor:pointer; user-select:none; font-weight:600; list-style:none;
}
details.sc-tr > summary:hover { color:#ff0055; }
.sc-tr-list { list-style:none; margin-top:7px; padding:0; }
.sc-tr-list li {
    font-size:11px; color:#999;
    padding:3px 0 3px 14px;
    border-left:2px solid #ffd0de;
    margin-bottom:3px; position:relative;
}
.sc-tr-list li::before {
    content:'→'; position:absolute; left:-1px; top:2px;
    font-size:9px; color:#ff99bb;
    background:#fff; padding:0 2px;
}

/* ═══ TYPING DOTS ═══ */
.mw-typing {
    background:#fff; border-radius:18px; border-bottom-left-radius:4px;
    padding:13px 18px; display:flex; gap:5px; align-items:center;
    box-shadow:0 2px 14px rgba(0,0,0,0.07);
}
.mw-d { width:7px;height:7px;border-radius:50%;
        background:#ff0055;opacity:.45;animation:bd 1s infinite; }
.mw-d:nth-child(2){animation-delay:.15s;}
.mw-d:nth-child(3){animation-delay:.30s;}
@keyframes bd {
    0%,80%,100%{transform:translateY(0);opacity:.45;}
    40%{transform:translateY(-6px);opacity:1;}
}
.mw-tl { font-size:11.5px;color:#aaa;font-weight:600;margin-left:6px; }

/* ═══ CHAT INPUT — force white + pink styling ═══ */
[data-testid="stBottom"] {
    background: #ffffff !important;
    border-top: 1px solid #ebebeb !important;
}
[data-testid="stBottom"] > div {
    background: #ffffff !important;
    max-width: 700px !important;
    margin: 0 auto !important;
    padding: 10px 20px 14px !important;
}
[data-testid="stChatInput"] > div {
    background: #0d0f14 !important;   /* ✅ FULL BLACK */
    border-radius: 999px !important;
    border: none !important;
    padding: 6px 10px !important;
    box-shadow: 0 8px 25px rgba(0,0,0,0.15) !important;
}
[data-testid="stChatInputTextArea"] > div,
[data-testid="stChatInputTextArea"] {
    background-color: transparent !important;
}
[data-testid="stChatInput"] > div:focus-within {
    box-shadow: 0 0 0 2px #ff0055 !important;
}
[data-testid="stChatInput"] textarea {
    font-family: 'Nunito', sans-serif !important;
    font-size: 14px !important;
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 11px 18px !important;
    min-height: 44px !important;
    line-height: 1.5 !important;
}
[data-testid="stChatInput"] textarea::placeholder { 
    color: #999 !important; 
    -webkit-text-fill-color: #999 !important;
}
[data-testid="stChatInputSubmitButton"] > button,
[data-testid="stChatInput"] button {
    background: #ff0055 !important;
    border-radius: 50% !important;
    border: none !important;
    width: 42px !important; height: 42px !important;
    box-shadow: 0 4px 14px rgba(255,0,85,0.4) !important;
    transition: transform .13s, box-shadow .13s !important;
    cursor: pointer !important;
}
[data-testid="stChatInputSubmitButton"] > button:hover,
[data-testid="stChatInput"] button:hover {
    transform: scale(1.08) !important;
    box-shadow: 0 5px 18px rgba(255,0,85,0.46) !important;
}
[data-testid="stChatInputSubmitButton"] > button svg,
[data-testid="stChatInput"] button svg { fill: #fff !important; }

/* scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-thumb { background: #ddd; border-radius: 99px; }
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# SAFETY CARD BUILDER
# ─────────────────────────────────────────────────────────────────────────────
def _badge(rec: str):
    r = rec.upper()
    if "UNSUITABLE" in r or "NOT_SUITABLE" in r or "UNSAFE" in r:
        return "sc-unsafe",     "⚠️", "Unsafe"
    if "UNCERTAIN" in r:
        return "sc-uncertain",  "❓", "Uncertain"
    return "sc-safe",           "✅", "Safe"

def safety_card(result: dict, query: str) -> str:
    rec   = result.get("recommendation","UNCERTAIN")
    conf  = float(result.get("confidence",0))
    rsn   = result.get("reasoning","")
    explanation = result.get("user_explanation", "") or ""
    advice = result.get("advice", "") or ""
    flags = result.get("safety_flags",   []) or []
    trace = result.get("reasoning_trace",[]) or []
    alts  = result.get("alternatives",   []) or []

    bcls, bicon, blabel = _badge(rec)
    pct   = int(conf * 100)
    title = " ".join(query.split()[:8]).title() if query else "Product Query"

    h = f"""
<div>
  <div class="sc-badge {bcls}">{bicon}&nbsp;{blabel}</div>
  <div class="sc-product">{title}</div>
  <div class="sc-conf-row">
    <div class="sc-track"><div class="sc-fill" style="width:{pct}%"></div></div>
    <span>{pct}% confidence</span>
  </div>
    <div class="sc-st">Explanation</div>
    <div class="sc-reason">{explanation or rsn}</div>
    <div class="sc-st">What You Should Do</div>
    <div class="sc-reason">{advice or rsn}</div>"""

    if flags:
        h += '<div class="sc-st">Safety Flags</div><div class="sc-flags">'
        for f in flags:
            h += f'<span class="sc-flag">🚩 {f.replace("_"," ").title()}</span>'
        h += '</div>'

    if alts:
        h += '<div class="sc-st">Safer Alternatives</div>'
        for a in alts:
            h += f"""
<div class="sc-alt">
  <div class="sc-alt-head">
    <div class="sc-alt-name">🔄 {a.get("name","—")}</div>
    <div class="sc-alt-id">{a.get("product_id","")}</div>
  </div>
  <div class="sc-alt-why">{a.get("reason","")}</div>
</div>"""

        if rsn or trace:
                items = "".join(f"<li>{t}</li>" for t in trace)
                h += f"""
<details class="sc-tr">
    <summary>⊞ Reasoning details</summary>
    <div class="sc-st">Technical reasoning</div>
    <div class="sc-reason">{rsn}</div>
    <div class="sc-st">Reasoning trace ({len(trace)} steps)</div>
    <ul class="sc-tr-list">{items}</ul>
</details>"""

    h += "</div>"
    return h

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for k, v in [("messages",[]), ("is_loading",False)]:
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# RENDER
# ─────────────────────────────────────────────────────────────────────────────

# 1 — CSS
st.markdown(CSS, unsafe_allow_html=True)

# 2 — Full-width header
brand = (f'<img src="{BRAND_SRC}" alt="Mumzworld">'
         if BRAND_SRC else
         '<div class="mw-brand-fallback">mumz<span>world</span></div>')

st.markdown(f"""
<div class="mw-header">
  <div class="mw-brand">{brand}</div>
  <div class="mw-header-right">
    <div class="mw-header-q">
      <span class="mw-pulse"></span>How can we support you today?
    </div>
    <div class="mw-header-sub">AI Smart Product Safety Advisor</div>
  </div>
</div>
""", unsafe_allow_html=True)

# 3 — Centered content wrapper open
st.markdown('<div class="mw-wrap">', unsafe_allow_html=True)

# 4 — Welcome screen
if not st.session_state.messages and not st.session_state.is_loading:
    icon = (f'<img src="{ICON_SRC}" class="mw-icon" alt="Logo">'
            if ICON_SRC else
            '<div class="mw-icon-fallback">🛡️</div>')
    st.markdown(f"""
<div class="mw-welcome">
  {icon}
  <h1>AI Product Safety Advisor</h1>
  <p>Ask about any product — I'll tell you if it's safe for your child,
  with confidence scores, safety flags and safer alternatives.</p>
  <div class="mw-chips">
    <button class="mw-chip">Is this toy safe for 18 months?</button>
    <button class="mw-chip">Choking hazard risk for newborn?</button>
    <button class="mw-chip">هل هذا المنتج آمن لطفلي؟</button>
    <button class="mw-chip">Car seat for 2 year old — safe?</button>
  </div>
</div>
""", unsafe_allow_html=True)

# 5 — Chat history
for msg in st.session_state.messages:
    ts = msg.get("ts","")
    if msg["role"] == "user":
        st.markdown(f"""
<div class="mw-row user">
  <div>
    <div class="mw-b user-b">{msg["content"]}</div>
    <div class="mw-ts l">{ts}</div>
  </div>
  <div class="mw-av usr">You</div>
</div>""", unsafe_allow_html=True)
    else:
        r = msg.get("result")
        card = safety_card(r, msg.get("query","")) if r else msg.get("content","")
        st.markdown(f"""
<div class="mw-row ai">
  <div class="mw-av ai">MW</div>
  <div>
    <div class="mw-b ai-b">{card}</div>
    <div class="mw-ts d">{ts}</div>
  </div>
</div>""", unsafe_allow_html=True)

# 6 — Typing indicator
if st.session_state.is_loading:
    st.markdown("""
<div class="mw-row ai">
  <div class="mw-av ai">MW</div>
  <div class="mw-typing">
    <div class="mw-d"></div><div class="mw-d"></div><div class="mw-d"></div>
    <span class="mw-tl">Analyzing safety…</span>
  </div>
</div>""", unsafe_allow_html=True)

# 7 — Close content wrapper
st.markdown('</div>', unsafe_allow_html=True)

# 8 — Auto-scroll
components.html("""
<script>
(function(){
  var doc = window.parent.document;
  var c = doc.querySelector('[data-testid="stAppViewBlockContainer"]')
       || doc.querySelector('[data-testid="stAppViewContainer"]');
  if(c) setTimeout(function(){ c.scrollTop = c.scrollHeight; }, 80);

  if (!doc.mwChipListenerAdded) {
      doc.mwChipListenerAdded = true;
      doc.addEventListener("click", function(e) {
          if (e.target && e.target.classList && e.target.classList.contains("mw-chip")) {
              var text = e.target.innerText;
              var textarea = doc.querySelector('[data-testid="stChatInput"] textarea');
              if (textarea) {
                  // Set value using native setter to bypass React's wrapper
                  var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                  nativeInputValueSetter.call(textarea, text);
                  
                  // Dispatch input event so React registers the change
                  textarea.dispatchEvent(new Event('input', { bubbles: true }));
                  textarea.focus();
                  
                  // Optional: Automatically press Enter/Submit (Uncomment to enable)
                  /*
                  setTimeout(function(){
                      var submitBtn = doc.querySelector('[data-testid="stChatInputSubmitButton"] > button') || doc.querySelector('[data-testid="stChatInput"] button');
                      if(submitBtn) submitBtn.click();
                  }, 100);
                  */
              }
          }
      });
  }
})();
</script>""", height=0, width=0)

# 9 — Chat input  (Streamlit's native, properly centred)
user_input = st.chat_input("Ask about product safety… (English or Arabic)")

# ─────────────────────────────────────────────────────────────────────────────
# LOGIC
# ─────────────────────────────────────────────────────────────────────────────
if user_input and user_input.strip():
    ts = datetime.now().strftime("%I:%M %p")
    st.session_state.messages.append(
        {"role":"user","content":user_input.strip(),"ts":ts})
    st.session_state.is_loading = True
    st.rerun()

if st.session_state.is_loading:
    last = next((m for m in reversed(st.session_state.messages)
                 if m["role"]=="user"), None)
    if last:
        result = call_backend(last["content"])
        ts = datetime.now().strftime("%I:%M %p")
        st.session_state.messages.append(
            {"role":"ai","content":"","result":result,"query":last["content"],"ts":ts})
    st.session_state.is_loading = False
    st.rerun()