# Operators Vault — Ask Page RAG QA Report
**Date:** 2026-03-27
**Backend:** `https://superb-smile-production.up.railway.app`
**Queries run:** 15
**Method:** Parallel (ThreadPoolExecutor, 15 workers)

---

## Results Table

| # | Query Category | Query | Citations | Relevant? | Response Time | Notes |
|---|---------------|-------|-----------|-----------|---------------|-------|
| 1 | BFCM / Seasonal | How do 8-figure brands approach BFCM prep? | 20 | ✅ | 36.2s | Strong answer — specific sub-$30M BFCM winner patterns, Q3 promo witholding strategy. Sources are relevant. |
| 2 | Paid Social | What do operators say about Meta creative fatigue? | 20 | ✅ | 37.0s | Excellent — named insight sources (Operator Definition of Creative Fatigue, Meta Diagnostic), reframed as demographic-level problem. On-target. |
| 3 | Email | Best strategies for email list growth | 20 | ✅ | 25.2s | Good — AI popups leading signal, Postscript SMS mentioned. Actionable. Sources could be more specific but content is solid. |
| 4 | Finance | How should I think about CAC payback period? | 8 | ⚠️ | 20.7s | Reply is good quality but sources are weak/irrelevant ("Founder chat groups know every detail", "Risk-taking is constant in business"). Low citation count (8). Limited finance content in vault. |
| 5 | Post-purchase | What are the best tools for post-purchase upsells? | 5 | ✅ | 16.6s | Specific and correct — AfterSell named twice, one-click upsell mechanics explained. Low citation count but answer is high quality and direct. |
| 6 | Retention | How do top DTC brands reduce churn? | 20 | ⚠️ | 30.5s | Reply starts by admitting limited vault coverage, then pivots to general operator-level advice. Sources are weak (NorthBeam attribution tool cited for churn). Partial hallucination risk — reply outpaces vault coverage. |
| 7 | Influencer | How are DTC brands using creator partnerships? | 2 | ⚠️ | 20.6s | Only 2 citations. Reply invents a "9Operators Framework" hero/micro/nano creator tiering that isn't directly sourced. Answer is plausible but lightly grounded. Gap in vault content on creator/influencer topic. |
| 8 | Ops/Hiring | When should a DTC brand make their first ops hire? | 20 | ✅ | 32.1s | Good — PMO-as-first-hire concept cited, framework is operator-grade. Sources include relevant "PMO as First Hire" insight. |
| 9 | Subscriptions | What subscription models work best for consumables? | 2 | ✅ | 22.4s | Only 2 citations but Nik Sharma's no-discount subscription model is cited directly and correctly. Content quality is high. Needs more vault depth on subscriptions. |
| 10 | LTV | How do you improve customer LTV in DTC? | 20 | ✅ | 39.6s | Strong — correctly calls out LTV-to-CAC as misapplied SaaS metric, NorthBeam sourced, DTC-specific framing. Actionable. |
| 11 | Inventory | How do operators think about inventory planning? | 20 | ✅ | 25.4s | Good — Q4 forcing function, capital allocation framing, cross-functional pacing framework cited. Directly sourced. |
| 12 | Attribution | What do operators say about last-click attribution being broken? | 5 | ✅ | 26.9s | Solid answer but only 5 citations. Sources skew Q4/BFCM-specific rather than attribution-specific. Reply bridges the gap reasonably. MTA/multi-touch framing is correct. |
| 13 | Logistics | Best 3PL strategies for scaling DTC brands? | 20 | ❌ | 35.2s | Reply explicitly admits vault has no direct 3PL coverage, then provides generic DTC 3PL advice from model training data. Sources are irrelevant (fashion merchandising, DTC roll-ups). High hallucination risk — answer is not sourced from vault. |
| 14 | Conversion | How do you improve landing page conversion rate? | 8 | ✅ | 22.2s | Good — Nik Sharma's LP-as-seesaw-lever framing cited. HOOX tool named. Objection-first thinking framework is solid. 8 citations is acceptable. |
| 15 | Newsletter-specific | What does Taylor Holiday say about owning the number? | 3 | ⚠️ | 22.5s | Reply immediately flags vault doesn't directly surface the quote, then synthesizes MER/marketing efficiency framing. Directionally correct but not truly grounded in vault excerpts. 3 citations is low. |

---

## Summary

### Pass Rate

**Criteria:** Citations > 0 AND reply is directly relevant to the question (not admitting absence of vault coverage, not hallucinating from outside the vault)

| Status | Count | Queries |
|--------|-------|---------|
| ✅ Pass | 9/15 (60%) | BFCM, Paid Social, Email, Post-purchase, Ops/Hiring, LTV, Inventory, Conversion, Subscriptions |
| ⚠️ Partial | 4/15 (27%) | Finance, Retention, Influencer, Newsletter-specific |
| ❌ Fail | 1/15 (7%) | Logistics |

**Overall pass rate: 60% full pass, 87% with partials included**

---

### Citation Distribution

| Bucket | Count | Queries |
|--------|-------|---------|
| 20 citations (max) | 8 | BFCM, Paid Social, Email, Retention, Ops/Hiring, LTV, Inventory, Logistics |
| 5–8 citations | 4 | Finance (8), Attribution (5), Post-purchase (5), Conversion (8) |
| 1–3 citations | 3 | Influencer (2), Subscriptions (2), Newsletter-specific (3) |

---

### Response Time

- **Fastest:** Post-purchase (16.6s)
- **Slowest:** LTV (39.6s), BFCM (36.2s), Paid Social (37.0s)
- **Average:** ~27s — acceptable for a knowledge-base tool, but on the slower side for a chat interface

---

### Patterns in Failures / Partials

**1. Vault coverage gaps (root cause of 4/5 weak results)**
Specific topics are underrepresented or absent in the vault:
- **Creator/influencer partnerships** — only 2 chunks. The vault is primarily marketing mechanics + paid social, not creator strategy.
- **Logistics / 3PL** — zero relevant vault content. Fully fell back to model knowledge.
- **Finance / CAC payback** — sparse coverage; only 8 relevant chunks and sourced from off-topic excerpts.
- **Taylor Holiday + "owning the number"** — CTC newsletters appear in the vault but the specific phrase isn't well-represented.

**2. Citation count ≠ answer quality**
Several 20-citation responses (Retention, Logistics) returned irrelevant sources despite high count. The retrieval is surfacing chunks that topically overlap but aren't directly answering the query. This suggests the embedding/retrieval is doing broad matching rather than precise semantic matching on some topics.

**3. Hallucination risk on low-coverage topics**
When vault coverage is thin, the model fills gaps with plausible-but-unsourced operator advice (Influencer, Logistics, Finance). The reply quality sounds correct but is not grounded in vault content — a potential credibility issue for users who expect vault-sourced answers.

**4. Source title quality varies significantly**
Some source titles are clean insight labels ("Meta Creative Fatigue Diagnostic"), while others are entire sentences from the transcript chunk ("Sub-$30M BFCM Winners Were Repeat-Purchase Categories:**"). Inconsistent chunking/metadata.

---

### Recommendations

**P0 — Fix immediately**

1. **Add creator/influencer content** — This is a clear vault gap. Pull in Marketing Operators episodes on creator strategy, affiliate/UGC, and creator-led acquisition. Current: ~2 chunks.

2. **Add 3PL/logistics content** — Zero relevant vault coverage. Pull 9Operators or Operations Operators episodes specifically on fulfillment, 3PL selection, and inventory ops. The model is 100% hallucinating on this topic.

**P1 — High value**

3. **Add Finance Operators content on unit economics** — CAC payback, contribution margin, LTV modeling. The Finance Operators YouTube channel is a natural fit. Currently underrepresented.

4. **Add Taylor Holiday / CTC newsletter archives explicitly tagged** — The "owning the number" / MER framework is core CTC IP. Ensure those newsletters are fully ingested and chunked with Taylor's name in metadata.

5. **Improve source metadata** — Source titles should be short, descriptive insight labels (e.g., "Meta creative fatigue — demographic-level definition"), not raw transcript excerpts. This affects both source display quality and retrieval precision.

**P2 — Nice to have**

6. **Add a confidence/coverage disclaimer** — When the model admits lack of vault coverage upfront (Logistics, Retention), it should still cite what IS in the vault and clearly label when it's extending beyond vault knowledge. Current behavior is inconsistent.

7. **Response time optimization** — 27s average is acceptable but noticeable. Consider caching common query embeddings or reducing context_limit for simple queries.

8. **Improve retrieval on "operator name + topic" queries** — "What does Taylor Holiday say about X" style queries only return 3 citations. The chunking should preserve speaker attribution so name-based retrieval is more precise.

---

*Report generated by automated QA script. All queries run in parallel against production endpoint.*
