# Mumzworld Smart Product Advisor (AI Engineering Intern Assignment)

## 🔥 Summary

A multilingual (English + Arabic) AI-powered Product Safety & Suitability Advisor that helps parents make safe purchasing decisions.

Given a natural language query like:

> "Is this toy safe for my 18-month-old?"

The system:

* Retrieves relevant product + safety data (RAG)
* Applies safety rules and constraints
* Returns a structured recommendation with:
  * Safety status (SAFE / UNSAFE / UNCERTAIN)
  * Confidence score
  * Reasoning trace
  * Safer alternatives (if applicable)

---

## 🚀 Why This Problem

Safety is the highest-leverage trust signal in Mumzworld’s ecosystem.

Unlike generic recommendation systems, this problem:

* Has **objective correctness** (age + safety rules)
* Requires **grounded reasoning (no hallucinations)**
* Directly impacts **customer trust and liability**

---

## 🧠 System Architecture

User Query
→ RAG Retrieval (ChromaDB + embeddings)
→ Tooling (age_check, safety rules)
→ LLM (Gemini Flash)
→ Structured Output (Pydantic validation)
→ Post-processing (uncertainty threshold logic)
→ Final Response

---

## 🛠️ Tech Stack (Free Only)

* **LLM**: Gemini 2.0 Flash (free tier)
* **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
* **Vector DB**: ChromaDB (local)
* **Backend**: Python 3.11+
* **Validation**: Pydantic v2
* **UI**: Streamlit
* **Testing**: pytest
* **Eval Metrics**: custom accuracy + refusal accuracy

---

## ⚙️ Setup & Run (Under 5 Minutes)

```bash
git clone <repo>
cd mumzworld-advisor

python -m venv venv
# Windows:
venv\Scripts\activate
# Mac/Linux:
# source venv/bin/activate

pip install -r requirements.txt

# Add your Gemini API key
copy .env.example .env

# Run app
streamlit run app.py
```

---

## 🧪 Evaluation

### Test Coverage

* **Total cases**: 18
  * Normal: 5
  * Edge cases: 4
  * Adversarial: 5
  * Refusal: 4

### Metrics

* Overall Accuracy
* Refusal Accuracy
* Category-wise Accuracy

## 📊 Eval Results

| Metric              | Score |
|-------------------|------|
| Overall Accuracy   | 0.89 |
| Refusal Accuracy   | 1.00 |
| Normal Cases       | 1.00 |
| Edge Cases         | 0.75 |
| Adversarial Cases  | 0.80 |
| Refusal Cases      | 1.00 |

### Key Insight

The system is explicitly tested against:

* Unsafe recommendations
* Missing data scenarios
* Adversarial queries
* Multilingual consistency

---

## ⚠️ Uncertainty Handling

The system does NOT rely purely on LLM output.

Explicit logic:

* **Confidence threshold** = 0.6
* **Retrieval threshold** = 0.4

If conditions fail:
→ Output = `UNCERTAIN`
→ Reason included in `reasoning_trace`

This prevents hallucinated recommendations.

---

## 🔍 Example Output

```json
{
  "query_language": "en",
  "recommendation": "NOT_SUITABLE",
  "confidence": 0.87,
  "safety_flags": ["choking_hazard"],
  "reasoning": "This product contains small parts and is a choking hazard for a 6-month-old.",
  "reasoning_trace": [
    "Identified product: Small toy knife set",
    "Child age: 6 months",
    "Product contains small detachable parts",
    "Choking hazard for children under 3 years",
    "[OVERRIDE] Critical safety flags ['choking_hazard'] detected — forced NOT_SUITABLE"
  ],
  "alternatives": [
    {
      "product_id": "MW-027",
      "name": "Playgro Sensory Toy",
      "reason": "No small parts, absolutely safe for infants 0+ months"
    }
  ]
}
```

---

## 🎥 Demo (3-Min Loom)

Covers:

1. Normal safe recommendation
2. Unsafe product detection
3. Arabic query
4. Missing data → UNCERTAIN
5. Adversarial input

---

## ⚖️ Tradeoffs

### Why this approach

* **RAG ensures grounding** → avoids hallucination
* **Structured output** ensures reliability
* **Explicit thresholds** → engineering control over LLM

## ❗ Known Limitations

* The system may struggle when product descriptions lack detailed safety attributes (e.g., missing material or part size info).
* Multilingual parity depends on model consistency; some Arabic outputs may be less fluent than English.
* Retrieval quality is limited by the synthetic dataset used.

### What was cut (time constraint)

* Real product dataset (used 30-product synthetic data instead)
* Advanced reranking models
* UI polish beyond functional demo

### What I would build next

* Real-time catalog integration
* Fine-tuned safety classifier
* Personalization layer (child profile)

---

## 🧰 Tooling Transparency

* Used Gemini Flash via API for generation
* Used AI coding tools (Antigravity + Claude) for scaffolding and iteration
* Manual intervention for:
  * Eval design
  * Schema enforcement
  * Uncertainty logic

---

## ⏱️ Time Log

* Problem selection: 45 min
* Core system: 2.5 hrs
* Eval framework: 1 hr
* UI + polish: 45 min
* README + demo prep: 30 min

**Total: ~5 hours**

---

## ✅ Key Strengths

* Grounded, non-hallucinating outputs
* Explicit uncertainty handling
* Strong eval framework (not vibes)
* Multilingual support (EN + AR)
* Production-style structured responses

---

## 📌 Final Note

This project focuses on **trust-critical AI** — not just generating answers, but knowing when NOT to answer.

That is the foundation of AI-native commerce.
