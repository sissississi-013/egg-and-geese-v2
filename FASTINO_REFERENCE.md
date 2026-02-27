# Fastino / GLiNER / Pioneer — Hackathon Reference

> This file exists so we never lose sight of what makes GLiNER special and how
> it should be the **backbone** of Egg & Geese, not an afterthought.

---

## What is GLiNER?

[GLiNER](https://github.com/fastino-ai/GLiNER2) is a generalist Named Entity
Recognition (NER) model that can identify **any entity type** — without
retraining. Unlike traditional NER models locked to fixed categories, GLiNER
accepts **arbitrary entity labels at inference time**.

### Why This Matters for Egg & Geese

GLiNER is NOT just "another NER model." Its zero-shot, schema-driven design
is the reason our platform can work across **any product, any industry, any
audience** without retraining. This is the core differentiator.

### Key Capabilities

| Capability | What it means for us |
|---|---|
| **Zero-shot NER** | Define entity types on the fly per campaign — `["pain point", "benefit", "ingredient"]` for shampoo, `["feature", "pricing tier", "integration"]` for SaaS |
| **Span-based extraction** | Extracts **grounded text spans** from real content, not hallucinated text. Critical for accurate product matching and claim verification |
| **Lightweight & fast** | 100–250ms latency on CPU. Can run in real-time on scouted posts without bottlenecking the pipeline |
| **Structured output** | Perfect for feeding downstream agents, knowledge graphs, and matching algorithms |
| **Multi-domain ready** | Works across skincare, tech, food, finance — any vertical our users bring |

### GLiNER 2 Tasks (Three-in-One)

GLiNER 2 handles three tasks in one forward pass:

1. **Named Entity Recognition (NER)** — extract spans matching any labels
2. **Text Classification** — zero-shot classify text into categories
3. **Structured Data Extraction (JSON)** — parse structured data from text

---

## What is Pioneer?

[Pioneer](https://pioneer.ai/) is the fine-tuning platform for GLiNER. It
handles the full lifecycle:

| Step | What it does |
|---|---|
| Synthetic Data Generation | Auto-generates labeled training data from entity types + domain description |
| Fine-Tuning | Trains a GLiNER model on custom data with optimized hyperparameters |
| Evaluation | Benchmarks precision, recall, F1 |
| Download | Export fine-tuned model for local use |
| Deploy | Hosted inference endpoint ready to call |

### Pioneer Opportunity for Egg & Geese

We could fine-tune a **marketing-domain GLiNER** on Pioneer that's
specifically optimized for:
- Extracting product attributes from product pages
- Identifying pain points and sentiments in social media posts
- Matching scouted content to campaign entities
- Classifying post relevance and engagement potential

---

## API Details

### Endpoint
```
POST https://api.pioneer.ai/gliner-2
```

### Authentication
```
X-API-Key: pio_sk_x3zF8p50lc0txOiCl0bst3r_644c264e-f751-4a3a-8562-56e415fdba79
```

### Request Format
```json
{
  "text": "raw text to analyze",
  "schema": ["entity label 1", "entity label 2", ...],
  "task": "extract_entities | classify_text | extract_json",
  "threshold": 0.3
}
```

### Response Format
```json
{
  "result": {
    "entities": {
      "entity label 1": ["extracted span 1", "extracted span 2"],
      "entity label 2": ["extracted span 3"]
    }
  },
  "token_usage": 25
}
```

### Async Endpoint (for large batches)
```
POST https://api.pioneer.ai/gliner-2/async
GET  https://api.pioneer.ai/gliner-2/jobs/{job_id}
```

### Custom Fine-Tuned Models
```
POST https://api.pioneer.ai/gliner-2/custom
```

---

## How GLiNER Should Power Every Stage of Egg & Geese

### Stage 1: Intent Anchoring (Product Analysis)
**Current**: Claude does most of the work, GLiNER is a secondary enrichment.
**Should be**: GLiNER is the PRIMARY structured extraction engine.

- When a user drops a product link, GLiNER extracts **grounded spans** —
  actual text from the page, not Claude's interpretation
- These spans become the campaign's **entity schema** — the exact terms,
  ingredients, pain points that exist in the real product copy
- Claude's role should be to **synthesize and organize** GLiNER's extractions,
  not replace them

**Why this matters**: GLiNER extractions are grounded in the source text.
Claude can hallucinate product features. GLiNER cannot — it only returns
spans that actually exist in the input.

### Stage 2: Scouting (Finding Relevant Posts)
**Current**: Yutori finds posts, but we don't deeply analyze them.
**Should be**: Every scouted post gets GLiNER extraction.

- Run GLiNER on each scouted post with the campaign's entity schema
- Extract: `["pain point", "product mention", "sentiment", "question", "recommendation request"]`
- **Match score**: How many of the campaign's target entities appear in the post?
- Posts with high entity overlap = high relevance = priority engagement targets

### Stage 3: Engagement (Crafting Responses)
**Current**: Claude generates responses.
**Should be**: GLiNER validates and grounds Claude's responses.

- Before posting a response, run GLiNER on it to verify it mentions the
  right entities (product name, benefits, pain points)
- Use GLiNER classification to score the response's tone alignment
- **Claim verification**: GLiNER extracts claims from the draft response,
  cross-reference with the product's known entities

### Stage 4: Learning & Evolution
**Current**: Metrics are tracked but entity-level analysis is missing.
**Should be**: GLiNER powers entity-level performance tracking.

- Extract entities from successful vs. failed engagements
- Learn which **specific pain points** and **benefits** resonate
- Build a knowledge graph of entity → engagement performance
- Dynamically adjust the entity schema for future scouting based on what works

### Stage 5: Cross-Post Intelligence
**Should be**: GLiNER enables cross-platform entity matching.

- Same pain point discussed differently on Twitter vs. Reddit
- GLiNER extracts the underlying entities regardless of phrasing
- Build entity-level intelligence that transcends platform-specific language

---

## Architecture Principle

```
┌─────────────────────────────────────────────────────┐
│                    GLiNER Layer                       │
│  (zero-shot entity extraction on EVERYTHING)         │
│                                                       │
│  Product pages → entities                             │
│  Social posts  → entities                             │
│  Agent replies → entities (validation)                │
│  Engagement results → entities (learning)             │
│                                                       │
│  Same model, different schemas per campaign           │
│  Grounded spans, not hallucinated text                │
└─────────────┬───────────────────────┬─────────────────┘
              │                       │
    ┌─────────▼─────────┐   ┌────────▼──────────┐
    │   Claude Layer     │   │   Neo4j Layer      │
    │  (synthesis,       │   │  (entity graph,    │
    │   humanization,    │   │   relationships,   │
    │   strategy)        │   │   performance)     │
    └───────────────────┘   └────────────────────┘
```

**GLiNER = structured perception (what entities exist in text)**
**Claude = creative intelligence (what to do with those entities)**
**Neo4j = memory (how entities relate and perform over time)**

---

## Key Differentiators to Emphasize

1. **Not just another ChatGPT wrapper** — GLiNER provides grounded,
   span-based extraction that LLMs cannot match for accuracy
2. **Zero-shot flexibility** — Every campaign gets its own entity schema
   without retraining
3. **Entity-level intelligence** — We don't just track "did the post work?"
   We track "which specific pain points drove engagement?"
4. **Pioneer fine-tuning potential** — As we collect more data, we can
   fine-tune a marketing-specific GLiNER model that outperforms the base
5. **Speed** — GLiNER runs in 100-250ms. We can analyze hundreds of posts
   in real-time without waiting for LLM API calls

---

## Resources

- **GLiNER 2 GitHub**: https://github.com/fastino-ai/GLiNER2
- **Pioneer Platform**: https://pioneer.ai/
- **Pioneer Docs**: https://pioneer.ai/docs
- **Pioneer API**: https://api.pioneer.ai/docs
- **Discord**: https://discord.gg/u3KcfNWp
- **Contact**: marketing@fastino.ai
