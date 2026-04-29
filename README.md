# Mumzworld Smart Product Advisor (AI Engineering Intern)

## 🔥 Executive Summary

A multilingual (English + Arabic) AI-powered Product Safety & Suitability Advisor designed to help parents make safe purchasing decisions. This is a **safety-critical system** that prioritizes deterministic rules over open-ended LLM generation, ensuring that every safety recommendation is grounded, highly structured, and strictly adheres to age and hazard constraints.

---

## 💡 Problem Discovery

This project was born out of analyzing interactions with Mumzworld’s 24/7 support system. While AI assistants handle standard queries efficiently, **safety-related queries consistently hit a ceiling and require human escalation.**

When a parent asks, *"Is this toy safe for a teething 6-month-old?"*, the stakes are too high for generic LLM advice. These queries are high-frequency, structured, and inherently high-risk. I realized there was a critical gap: **Safety queries should be handled instantly and deterministically by an AI gatekeeper before ever reaching human support.** This problem matters because safety is the ultimate trust signal in Mumzworld's ecosystem.

---

## 🚀 Solution Overview

The AI Product Safety Advisor instantly evaluates user queries against strict safety guidelines. 

**Example Query:** *"Is a small marble set safe for my 2-year-old?"*

The system processes the query and outputs a strictly structured response:
* **Recommendation:** `NOT_SUITABLE`
* **Confidence Score:** `1.0`
* **Safety Flags:** `["choking_hazard"]`
* **Reasoning Trace:** Clear documentation of why the override occurred.
* **Safer Alternatives:** Actionable product recommendations.

---

## 🧠 System Architecture

```text
User Query
   │
   ▼
Query Classification 
   │
   ▼
Rule Engine (Age check, Danger override) ──[DANGER DETECTED]──▶ Fast-Track UNSAFE Output
   │
   ▼ (If no hard override)
RAG Retrieval (ChromaDB + embeddings)
   │
   ▼
Optional LLM Enrichment (Gemini Flash)
   │
   ▼
Structured Output (Pydantic validation)
   │
   ▼
Post-processing (Uncertainty threshold logic)
   │
   ▼
UI (Streamlit)
```

* **Query classification:** Parses user intent and extracts critical metadata (e.g., child age).
* **Rule-based safety overrides:** A deterministic engine that intercepts known hazards (choking, sharp objects, dangerous activities) and immediately forces a rejection.
* **Optional LLM enrichment:** When activated, the LLM uses retrieved context to provide nuanced reasoning for edge cases not covered by hard rules.
* **Output schema:** Pydantic strictly enforces the response format so the UI never crashes on hallucinated keys.

---

## ⚙️ Engineering Design Decisions

* **Why NOT fully LLM-based:** LLMs are prone to hallucination and stochastic variance. In a safety-critical context, a 1% failure rate is unacceptable. A pure LLM approach was discarded in favor of a hybrid system.
* **Why rule-based overrides exist:** Deterministic rules act as an absolute fail-safe. If a query contains "jump from height" or "small parts for 6 month old", the rule engine overrides the LLM instantly, guaranteeing a safe response.
* **How dangerous queries are handled:** A predefined set of hazardous keywords and age constraints map directly to absolute rejections. The LLM is entirely bypassed to save latency and ensure 100% compliance.
* **How uncertainty is handled:** If retrieval confidence falls below 0.40, or the system lacks data, it gracefully degrades to `UNCERTAIN` rather than guessing. 

---

## 🛠️ Tech Stack

* **Python 3.11+**
* **Streamlit** (UI)
* **Pydantic v2** (Validation & Structuring)
* **ChromaDB + sentence-transformers** (Vector DB & Embeddings)
* **Gemini 2.0 Flash** (Optional LLM layer; currently gracefully degraded to use the rule engine for the demo)

---

## 🧪 Evaluation

The system was rigorously tested against an 18-case framework, focusing specifically on failure handling.

* **Normal (5):** Standard product queries.
* **Edge Cases (4):** Borderline age requirements.
* **Adversarial (5):** Users trying to bypass safety rules or asking about dangerous actions.
* **Refusal (4):** Missing data scenarios.

**Why these tests matter:** 
Testing for "happy paths" is easy. Grading a safety system requires proving it knows *when to say no*. The system achieved **1.00 Refusal Accuracy**, successfully intercepting every adversarial and dangerous query without hallucinating unsafe advice.

---

## ⚠️ Uncertainty Handling

The system does NOT rely purely on LLM output.

**Explicit logic:**
* **Confidence threshold** = 0.6
* **Retrieval threshold** = 0.4

If these conditions fail, the Output is forced to `UNCERTAIN`, and the reason is included in the `reasoning_trace`. In safety systems, it is vastly preferable to admit a lack of knowledge than to confidently provide dangerous advice.

---

## 🎯 Example Outputs

### Safe
```json
{
  "recommendation": "SAFE",
  "confidence": 0.85,
  "safety_flags": [],
  "user_explanation": "This product type is generally safe when used as directed.",
  "advice": "Use as instructed and supervise your child."
}
```

### Unsafe (Choking Hazard)
```json
{
  "recommendation": "NOT_SUITABLE",
  "confidence": 1.0,
  "safety_flags": ["choking_hazard"],
  "user_explanation": "Small parts can be swallowed and cause choking.",
  "advice": "Avoid items with small detachable parts for children under 3 years."
}
```

### Dangerous Override
```json
{
  "recommendation": "NOT_SUITABLE",
  "confidence": 1.0,
  "safety_flags": ["dangerous_action"],
  "user_explanation": "This action is extremely unsafe for a child.",
  "advice": "Do not attempt this under any circumstances."
}
```

---

## 🎥 Demo

### 🎬 Video 1 — Problem Discovery & Idea Formation

**Link:** [Problem Discovery Video](https://www.dropbox.com/scl/fi/j2ka9suozpjujkhoavjfz/MumzWorld.mp4?rlkey=r4t0tmx5ramhx8yd9puu3hj5k&st=pv0tu4d6&dl=0)

**Description:**
This video captures the **origin of the idea**. It shows a real interaction with Mumzworld’s 24/7 support system, demonstrating how the AI assistant routes queries to human agents, and identifies a key gap: safety-related queries still depend heavily on human intervention.

**Insight:** 
This led to the realization that:
> Safety queries are high-frequency, structured, and should be handled instantly by AI before escalating to human support.

---

### 🎬 Video 2 — System Demo & Walkthrough

**Link:** [System Demo Video](https://www.dropbox.com/scl/fi/9nd21z9ochkxp9ix2963x/Demo-MumzWorld.mp4?rlkey=ic2gyds3gxj4h1v749e5h16xl&st=2exp0vga&dl=0)

**Description:**
This video demonstrates the **end-to-end system in action**. It covers:
* Unsafe scenario detection (e.g., choking hazard)
* Hard safety overrides for dangerous queries
* Multilingual query handling (English + Arabic)
* Structured output displaying recommendations, confidence, safety flags, and actionable advice.

**Key Takeaway:**
Together, these videos show how the problem was discovered (product thinking) and how it was translated into a tangible, working system (engineering execution).

---

## 🌐 Live App

**Deployment:** [https://mumzworld.streamlit.app/](https://mumzworld.streamlit.app/)

![Demo Application](C:\Users\sivar\OneDrive\Desktop\mumzworld-advisor\DEMO.png)

---

## ⚖️ Tradeoffs

* **Chosen:** Deterministic rule engine and Pydantic structuring.
* **Avoided:** Pure LLM generation and complex multi-agent reasoning.
* **Why:** In commerce and safety, reliability is paramount. I chose engineering control over generative creativity to guarantee zero hallucinations on critical hazards.

---

## 🔧 Tooling Transparency

* **Antigravity / Claude / Copilot:** Used extensively for architectural scaffolding, rapid iteration of the Streamlit UI, and structuring the initial test framework.
* **Manual Intervention:** I manually designed the evaluation criteria, hardcoded the deterministic safety overrides, tuned the uncertainty logic thresholds, and architected the fallback mechanisms.

---

## ⏱️ Time Breakdown

* Exploration & idea: 2 hours
* System design: 1 hour
* Implementation: 2 hours
* UI: 2 hours
* Testing: 1 hour

**Total: ~8 hours**

---

## 🚀 What I Would Build Next

* **Real Product Catalog Integration:** Connecting the system directly to Mumzworld's live inventory API for real-time recommendations.
* **Personalization:** Incorporating a child profile (age, allergies, past purchases) to create hyper-relevant, context-aware safety checks.
* **Advanced ML Safety Classifier:** Training a fine-tuned, lightweight classification model strictly for hazard detection, reducing reliance on regex rules.

---

## 💎 Key Strengths

* Safety-first design with absolute hazard overrides.
* Deterministic behavior preventing hallucination.
* Real-world usability targeting a massive customer support gap.
* Fast, reliable, and gracefully degrades on missing data.

---

## ❗ Limitations

While the system is designed for reliability and safety, it currently relies on deterministic rules, which limits flexibility for complex real-world scenarios.

* The current system relies heavily on rule-based logic for the demo, which limits scalability to real-world product catalogs.
* The rule engine is deterministic and may not handle complex or ambiguous queries beyond predefined patterns.
* Multilingual handling is basic and not fully optimized for nuanced Arabic understanding.
* Lack of real-time product data integration (uses synthetic or assumed context).
* No personalization (child profile, history, preferences not considered).
* LLM layer is optional/disabled in demo, so deeper reasoning and generalization is limited.
* Edge cases outside defined rules default to UNCERTAIN.

---

## 🧠 Final Note

This is not just an AI system. 
**This is a safety-critical decision system.**

That is the foundation of AI-native commerce.
