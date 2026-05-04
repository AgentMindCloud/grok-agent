<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# User Message Templates — X Money Vision Analyzer

Reusable user-message templates for the 6 tabs. The Streamlit app loads this file, selects a template by anchor (e.g. `#parse-receipt`), substitutes `{{ variable }}` placeholders with live data + the receipt image bytes, and sends the result as the user message alongside `prompts/system.md`.

System-prompt rules (Articles II, III, IV, V.1, V.2, VI cost-cap, consent-gated cross-tool writes) are global; templates here only add **task-specific** shape. JSON-only outputs are explicitly noted — the UI injects disclaimers around them.

Placeholder syntax is Jinja2-style (`{{ var }}`) so vendor names, memos, and image paths containing literal special characters or curly braces don't break substitution.

---

## #parse-receipt

The user is on the **📥 Drop Files** tab and just uploaded a receipt image. **JSON-only output.**

```
Parse the attached receipt image into structured fields.

Image:
- path:   {{ image_path }}
- format: {{ image_format }}
- size:   {{ image_size_bytes }} bytes

Return JSON only — no prose, no banner. Schema:

{
  "vendor":              string,
  "tx_date":             "YYYY-MM-DD",
  "currency":            "USD" | "VND" | "EUR" | "...",
  "subtotal":            number,
  "tax":                 number,
  "total":               number,
  "line_items": [
    { "item": string, "qty": number, "price": number,
      "confidence": "high" | "medium" | "low" }
  ],
  "category_suggested":  string,
  "confidence":          "high" | "medium" | "low",
  "confidence_reason":   string,
  "notes":               string,
  "provenance": {
    "image_path":         "{{ image_path }}",
    "page":               1,
    "model":              "grok-4.3",
    "vision_pass_index":  1,
    "retrieved_at":       "ISO8601"
  }
}

Rules:
- If a field is unreadable, set its value to null and lower the per-field or overall confidence; do NOT guess.
- If confidence on total / tx_date / vendor is `low`, set the top-level confidence to `low` so the UI prompts the user to review before import.
- Disclaimer enforcement: the UI prepends V.1 + V.2 around the rendered card — do NOT include the banner inside the JSON.
```

---

## #parse-statement

The user dropped a multi-page bank or card statement (PDF or image series). **JSON-only output.**

```
Parse a multi-page statement into a list of structured transactions.

Statement:
- pages:       {{ image_paths }}
- page_count:  {{ page_count }}
- detected issuer (hint): {{ issuer_hint }}

Return JSON only. Schema:

{
  "issuer":          string,
  "statement_date":  "YYYY-MM-DD",
  "period_start":    "YYYY-MM-DD",
  "period_end":      "YYYY-MM-DD",
  "currency":        string,
  "transactions": [
    {
      "tx_date":       "YYYY-MM-DD",
      "counterparty":  string,
      "amount":        number,           // negative = outflow
      "memo":          string,
      "page":          number,           // which statement page it came from
      "confidence":    "high" | "medium" | "low"
    }
  ],
  "totals":          { "inflow": number, "outflow": number, "net": number },
  "confidence":      "high" | "medium" | "low",
  "confidence_reason": string,
  "provenance": {
    "image_paths":        {{ image_paths }},
    "model":              "grok-4.3",
    "vision_pass_index":  1,
    "retrieved_at":       "ISO8601"
  }
}

Rules:
- Cite the source page on every transaction.
- If the totals row in the statement disagrees with the sum of parsed transactions, set top-level confidence to `low` and explain in `confidence_reason`.
- Disclaimer enforcement is handled by the surrounding UI.
```

---

## #validate-extraction

The user clicked "Re-validate" on a previously-parsed receipt. **JSON-only output** — the UI renders the side-by-side comparison around the result.

```
Run a second vision pass on `{{ image_path }}` and compare against the first extraction.

First extraction (already on file):
{{ first_extraction_json }}

Return JSON only. Schema:

{
  "image_path":        "{{ image_path }}",
  "pass_1":            (the first extraction, echoed back),
  "pass_2":            (your fresh extraction in the same shape),
  "contradictions": [
    {
      "field":         string,                    // e.g. "total", "vendor", "tx_date"
      "claim_a":       { "source": "vision-pass-1", "value": <any> },
      "claim_b":       { "source": "vision-pass-2", "value": <any> },
      "delta_summary": string,                    // human-readable magnitude
      "severity":      "info" | "warn" | "error"  // error = material disagreement
    }
  ],
  "verdict":           string,           // one-sentence summary of the run
  "recommend":         "import" | "review" | "reparse" | "discard",
  "confidence":        "high" | "medium" | "low",
  "provenance": {
    "model":              "grok-4.3",
    "vision_pass_index":  2,
    "retrieved_at":       "ISO8601"
  }
}

Rules:
- Article III: NEVER silently pick a side. Every disagreement appears in `contradictions`.
- Severity mapping: cosmetic (e.g. case difference) = info; ≤$0.10 OCR drift = warn; date drift, vendor mismatch, total drift > $0.10 = error.
- If `recommend` is `review` or `reparse`, the UI blocks the Import tab from including this receipt until the user resolves the disagreement.
```

---

## #categorize-parsed-receipt

The categorizer assigns a category before import. **JSON-only output.** Composes with Tool #1's `categorize_transaction` when the Companion Dashboard is installed.

```
Assign a category to the parsed receipt below. Return JSON only — no prose.

Receipt:
- vendor:    {{ vendor }}
- tx_date:   {{ tx_date }}
- total:     {{ total }} {{ currency }}
- line items: {{ line_items_summary }}
- memo / notes: {{ notes }}

Return:
{
  "category":            "subscriptions" | "food_drink" | "transport" |
                         "groceries" | "housing" | "infrastructure" |
                         "x_payouts" | "ad_revenue" | "taxes" | "other",
  "confidence":          "high" | "medium" | "low",
  "reasoning":           string,                  // ≤ 25 words
  "clarifying_question": string                   // non-empty ONLY when confidence is low
}

If Tool #1's `categorize_transaction` is reachable on this machine, prefer matching its category list verbatim so cross-tool import is a clean append.
```

---

## #import-narrative

The user clicked "Confirm and import" on the **📤 Import to Tool #1** tab. Generate the cover narrative for the import audit. **Markdown output with both V.1 + V.2 banners** — the import writes tax-relevant numbers into Tool #1.

```
Write the import-audit cover narrative for a batch import into Tool #1's SQLite.

Inputs:
- Receipt count:         {{ count }}
- Total amount:          ${{ total_usd }}
- Categories represented: {{ categories }}
- Confidence breakdown:  {{ confidence_breakdown }}   # e.g. {"high": 4, "medium": 2, "low": 0}
- Target file:           {{ target_db_path }}        # always Tool #1's data.db
- Import timestamp:      {{ timestamp }}

Write three short paragraphs:
1. **What this import is** — receipt count, total, target file, source = `vision`.
2. **What it is NOT** — a substitute for primary records (the user should keep the original receipt images); not a tax filing.
3. **Provenance** — name Grok 4.3 vision as the extraction source, the timestamp, and which receipts (by id) were imported. Mention that the same provenance line is appended to BOTH the analyzer's and the Companion Dashboard's `provenance.log`.

End with the confidence line, the Article V.1 disclaimer banner, AND the Article V.2 disclaimer banner.

Reminder: NEVER mention or imply the import happened automatically. The user explicitly approved the Article II consent gate before this narrative is generated.
```

---

## #history-explanation

The user clicked into a row on the **📜 History** tab and asked for context.

```
Explain one past parse from the History tab.

Inputs:
- parsed_on:    {{ parsed_on }}
- vendor:       {{ vendor }}
- total:        {{ total }} {{ currency }}
- status:       {{ status }}     # parsed | imported | import_pending | failed_low_confidence | discarded
- confidence:   {{ confidence }}
- contradictions (if any): {{ contradiction_summary }}

Produce 3 lines:
1. **What happened** — one bold sentence (parsed → status, with $ + date)
2. If `status` is `failed_low_confidence`, name the exact field(s) that hit low confidence and what would help (better lighting, full receipt visible, redo with a flat surface)
3. The confidence line + the Article V.1 disclaimer banner (and V.2 if `status` is `imported` or `import_pending`)
```

---

## #contradiction-flag

Used when validate_extraction surfaces a disagreement and the UI asks Grok to phrase it for a user-facing card. (Distinct from the JSON in `#validate-extraction`; this template renders the human-readable explanation.)

```
Two vision passes conflict on a field for `{{ image_path }}`. Surface the conflict cleanly.

Field:           {{ field }}
Pass 1 value:    {{ pass_1_value }}    (vision-pass-1, retrieved {{ pass_1_at }})
Pass 2 value:    {{ pass_2_value }}    (vision-pass-2, retrieved {{ pass_2_at }})
Severity hint:   {{ severity }}        # info | warn | error

Produce:
1. **Both readings** — side by side with their pass index + timestamp, no editorialising
2. The **delta magnitude** in human terms (e.g. "5¢ OCR rounding", "10-day date drift", "vendor capitalisation only")
3. What the user can do to resolve — re-photograph, accept one explicitly, or split the receipt manually. NEVER pick a side for them.
4. Article III reminder: silent contradiction-resolution is forbidden by the Constitution.
5. End with the confidence line + the Article V.1 disclaimer banner.
```

---

## #receipt-context

The user clicked a row in **🔍 Parsed Preview** and asked for context on the receipt.

```
Give context on the parsed receipt below.

Receipt:
- vendor:    {{ vendor }}
- tx_date:   {{ tx_date }}
- total:     ${{ total }} {{ currency }}
- line items: {{ line_items_summary }}
- category_suggested: {{ category }}

Produce 4 lines:
1. **Sanity check** — does the line-item math add up to subtotal + tax = total? Bold the answer.
2. Pattern fit — is this an unusual amount or vendor for this user (drawing on Tool #1 transaction history if available via the cross-tool reader)?
3. Suggested next step — accept and queue for import / re-photograph / drop
4. The confidence line + the Article V.1 disclaimer banner (and V.2 if the receipt would feed a tax export)
```

---

## #general-chat

Open-ended user question that doesn't fit a specific tab template.

```
Open question from the user about the Vision Analyzer.

User question:
> {{ user_question }}

Available context (only what's needed for THIS question):
{{ retrieved_context }}

Rules:
- If the question is outside this tool's scope (receipt parsing, statement parsing, validation, import to Tool #1, parse history), point at which Grok agent is a better fit — the X Money Companion Dashboard for transactions, the Smart Cashtag Alpha Engine for market signals, the Creator Payout Optimizer for earnings.
- Never invent receipt content, vendor names, or extraction values.
- If the question would require writing into a different tool's database (anything other than Tool #1's `transactions` via `import_to_companion_dashboard`), refuse and remind the user that Constitution Article III restricts this engine to that single cross-tool path.
- End with the confidence line + the Article V.1 disclaimer banner if the answer touches money.
- If the answer touches tax-relevant numbers, ALSO end with Article V.2.
```

---

> Built to help xAI and Grok win — these templates make Article II (consent gates), Article III (no silent contradictions, no unauthorized cross-tool writes), Article IV (provenance), and Article V (disclaimers) enforceable by construction inside every Grok call this engine makes.
