<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# User Message Templates — X Creator Payout Optimizer

Reusable user-message templates for the 6 tabs. The Streamlit app loads this file, selects a template by anchor (e.g. `#earnings-forecast`), substitutes `{{ variable }}` placeholders with live data — including counts pulled from Tool #1 (`transactions`) and Tool #4 (`receipts` + `parsed_items`) via the read-only cross-tool readers — and sends the result as the user message alongside `prompts/system.md`.

System-prompt rules (Articles III, IV, V.1, V.2, VI cost-cap, cross-tool READS only with graceful degradation, no autonomous publishing) are global; templates here only add **task-specific** shape. JSON-only outputs are explicitly noted — the UI injects disclaimers around them.

Placeholder syntax is Jinja2-style (`{{ var }}`) so vendor names, topic strings, and memos with literal special characters don't break substitution.

---

## #earnings-forecast

The user is on the **📈 Earnings Forecast** tab. **JSON-only output.**

```
Forecast the user's creator earnings for the next {{ horizon_days }} days using the last {{ window_days }} days of local data.

Available context:
- Tool #1 transaction summary (from cross-tool reader):
    - earnings rows last {{ window_days }}d: {{ earnings_rows }}
    - mean daily earnings:                    ${{ mean_daily_earnings }}
    - top revenue categories:                 {{ top_revenue_categories }}
- Tool #4 receipt summary (cost side, optional):
    - receipts last {{ window_days }}d:       {{ receipt_count }}
    - total cost outflow:                     ${{ total_cost_outflow }}
- Recent X metrics:
    - reach 7d:                               {{ reach_7d }}
    - engagement rate 30d:                    {{ engagement_rate_30d }}%
    - follower growth 30d:                    {{ follower_growth_30d }}

Cross-tool status (graceful degradation):
- Tool #1 installed: {{ companion_installed }}
- Tool #4 installed: {{ vision_installed }}
If either is False, set top-level confidence to "low" and say what's missing in `confidence_reason`.

Return JSON only — no prose, no banner. Schema:

{
  "horizons": [
    { "label": "30 days", "point": number, "low": number, "high": number },
    { "label": "60 days", "point": number, "low": number, "high": number },
    { "label": "90 days", "point": number, "low": number, "high": number }
  ],
  "drivers": [
    { "name": string, "share_of_forecast": number }   // values 0..1, sum to 1.0
  ],
  "confidence":         "high" | "medium" | "low",
  "confidence_reason":  string,                       // one sentence
  "data_window":        "last {{ window_days }} days, local Tool #1 transactions",
  "model":              "grok-4.3",
  "provenance": {
    "companion_rows_used":  number,
    "vision_rows_used":     number,
    "x_search_calls":       number,
    "retrieved_at":         "ISO8601"
  }
}

Disclaimer enforcement: the surrounding UI prepends V.1 + V.2 around the rendered card — do NOT include the banner inside the JSON.
```

---

## #content-optimization

The user is on the **✍️ Content Optimizer** tab and asked for angles on a topic. **JSON-only output.**

```
Suggest content angles for the topic `{{ topic }}`.

Available context:
- audience profile:                        {{ audience_profile }}
- past 30d top-engagement posts:           {{ top_posts_summary }}
- past payout-by-format breakdown:         {{ payout_by_format }}
- typical follower active hours (cron):    {{ active_hours }}

Return JSON only — no prose, no banner. Schema:

{
  "topic":  "{{ topic }}",
  "angles": [
    {
      "angle":                 string,                  // the suggested angle, ~12-18 words
      "format":                "thread" | "video" | "long-form" | "reply" | "quote",
      "predicted_engagement":  number,                  // 0-10 scale
      "predicted_revenue_usd": number,                  // best estimate over typical post lifetime
      "confidence":            "high" | "medium" | "low",
      "rationale":             string                   // one sentence citing the past pattern that backs it
    }
  ],
  "model":  "grok-4.3",
  "provenance": {
    "post_history_window_days": number,
    "x_search_calls":           number,
    "retrieved_at":              "ISO8601"
  }
}

Rules:
- Return 4–6 angles unless the topic is too narrow.
- Each angle's rationale must cite a real past post pattern (engagement number, format, etc.) — never invent.
- Confidence "low" requires a clarifying question in the angle's rationale field.
```

---

## #tax-burden-estimate

The user is on the **🧮 Tax Estimator** tab and clicked "Confirm and build estimate". **JSON-only output** — the surrounding UI prepends V.1 + V.2 banners.

```
Estimate the user's creator-earnings tax burden for {{ start_date }} → {{ end_date }} in jurisdiction `{{ jurisdiction }}`.

Available context (from Tool #1 read):
- earnings rows in window:        {{ earnings_rows }}
- gross income in window:         ${{ gross_income }}
- countable categories:           {{ countable_categories }}
- expense rows from Tool #4:      {{ expense_count }}
- deductible expenses guess:      ${{ deductible_expenses }}

Return JSON only. Schema:

{
  "jurisdiction":         "{{ jurisdiction }}",
  "period":               { "start": "{{ start_date }}", "end": "{{ end_date }}" },
  "gross_income":         number,
  "deductible_expenses":  number,
  "taxable_income":       number,
  "estimated_rate_pct":   number,
  "estimated_tax_owed":   number,
  "estimated_net":        number,
  "assumptions": [
    string                                          // e.g. "Vietnam 17% baseline rate; no spousal allowance"
  ],
  "confidence":           "high" | "medium" | "low",
  "confidence_reason":    string,
  "model":                "grok-4.3",
  "provenance": {
    "tool1_rows_used":   number,
    "tool4_rows_used":   number,
    "retrieved_at":      "ISO8601"
  }
}

Rules:
- ALWAYS include the V.2-required line in `assumptions[0]`: "NOT TAX ADVICE — coarse jurisdictional baseline; consult a licensed tax professional".
- For jurisdiction `Vietnam`, name the international-platform-earnings consideration explicitly in `assumptions`.
- If the data window is < 30 days OR `expense_count` is 0, drop confidence to `low` and say so.
```

---

## #x-metrics-fetch

The user is on the **📊 X Metrics** tab and the dashboard needs a fresh pull. **JSON-only output** — the UI renders the dashboard around the data.

```
Fetch recent X engagement / reach / payouts metrics for handle `{{ handle }}` over the last {{ period_days }} days via `x_search`.

Return JSON only. Schema:

{
  "handle":               "{{ handle }}",
  "period_days":          {{ period_days }},
  "reach_24h":            number,
  "reach_7d":             number,
  "reach_30d":            number,
  "engagement_rate_30d":  number,                     // %
  "follower_growth_30d":  number,
  "payout_this_month":    number,                     // USD
  "top_posts": [
    { "post_date": "YYYY-MM-DD", "title": string, "reach": number,
      "engagement": number, "payout_usd": number }
  ],
  "confidence":           "high" | "medium" | "low",
  "confidence_reason":    string,
  "provenance": {
    "source":       "x_search via grok-4.3",
    "retrieved_at": "ISO8601",
    "stub":         true                              // set true while the Grok client is stubbed
  }
}

Rules:
- If x_search returns no data (stub mode or rate-limited), set `confidence: "low"` and mark `provenance.stub: true`. Never invent metrics.
```

---

## #content-roi-analysis

The user is on the **💰 Content ROI** tab and asked to break down ROI by topic. **JSON-only output.**

```
Compute content ROI for topic `{{ content_topic }}` between {{ start_date }} and {{ end_date }}.

Available context:
- Tool #1 revenue rows in window (matched to topic): {{ revenue_rows }}
- Tool #4 cost rows in window (matched to topic):    {{ cost_rows }}
- Cross-tool status:
    - companion_installed: {{ companion_installed }}
    - vision_installed:    {{ vision_installed }}

Return JSON only. Schema:

{
  "content_topic":  "{{ content_topic }}",
  "period":         { "start": "{{ start_date }}", "end": "{{ end_date }}" },
  "revenue_usd":    number,
  "cost_usd":       number,
  "net_usd":        number,
  "roi_pct":        number,                           // ((net / cost) * 100), null if cost == 0
  "drivers": [
    { "side": "revenue" | "cost", "source_rows": number, "amount_usd": number, "summary": string }
  ],
  "graceful_degradation": {
    "tool1_missing": boolean,
    "tool4_missing": boolean,
    "implication":   string                           // human-readable explanation
  },
  "confidence":     "high" | "medium" | "low",
  "confidence_reason": string,
  "provenance": {
    "tool1_rows_used":  number,
    "tool4_rows_used":  number,
    "retrieved_at":     "ISO8601"
  }
}

Rules:
- If `cost_rows == 0` AND vision is installed, that's a real "no costs found" — do NOT guess; set confidence "medium" + explain.
- If `vision_installed == false`, set `graceful_degradation.tool4_missing: true`, return `cost_usd: 0`, `roi_pct: null`, confidence "low", and tell the user what installing Tool #4 would unlock.
```

---

## #x-metrics-summary

Markdown narrative render of the X Metrics tab. (Distinct from `#x-metrics-fetch`'s JSON.)

```
Summarize the user's X metrics for the last {{ period_days }} days in 4 lines.

Inputs:
- reach_24h:            {{ reach_24h }}
- reach_7d:             {{ reach_7d }}
- engagement_rate_30d:  {{ engagement_rate_30d }}%
- follower_growth_30d:  {{ follower_growth_30d }}
- payout_this_month:    ${{ payout_this_month }}
- top post:             {{ top_post_summary }}

Produce 4 lines:
1. **Headline takeaway** — one sentence, bold (e.g. "**Reach is 18% above your 30-day average; engagement holding flat.**")
2. The single most surprising number with why it matters
3. One actionable next step (a content angle, a posting time shift, or "no action — pattern is healthy")
4. Confidence line + the Article V.1 disclaimer banner
```

---

## #cross-tool-status-explanation

Used when `cross_tool_status()` shows a sibling missing and the user asks what that means.

```
Explain the cross-tool status to the user.

Inputs:
- companion_installed: {{ companion_installed }}      # bool
- companion_rows:      {{ companion_rows }}
- vision_installed:    {{ vision_installed }}
- vision_rows:         {{ vision_rows }}

Produce:
1. **Status** — one bold sentence summarizing which siblings are present
2. What's available right now (revenue + cost / revenue only / cost only / nothing)
3. What the user gains by installing the missing sibling — be specific (e.g. "installing Tool #4 unlocks per-topic ROI by joining your receipts to your revenue rows")
4. The exact `grok-agent install <slug>` command for any missing sibling
5. End with the confidence line + the Article V.1 disclaimer banner if the answer touches dollars

Reminder: this tool is **read-only** on both siblings. Never propose writing into Tool #1 or Tool #4 — Article III prohibits cross-tool writes from this manifest.
```

---

## #content-angle-detail

The user clicked into one suggested angle on the Content Optimizer tab and wants more depth.

```
Drill down on one content angle.

Inputs:
- angle:                {{ angle_text }}
- format:               {{ format }}
- predicted_engagement: {{ predicted_engagement }}/10
- predicted_revenue:    ${{ predicted_revenue_usd }}
- past similar posts:   {{ similar_posts_summary }}

Produce 5 lines:
1. **Why this angle scores {{ predicted_engagement }}/10** — one bold sentence citing the strongest past pattern
2. The 1–2 risks the user should know (audience fatigue, controversy potential, format match)
3. A specific opening hook (≤ 240 chars, draft only — never auto-post)
4. Best posting window based on follower active hours
5. Confidence line + the Article V.1 disclaimer banner

Reminder: drafts NEVER get auto-posted. The user always reviews and posts manually.
```

---

## #general-chat

Open-ended user question that doesn't fit a specific tab template.

```
Open question from the user about the Payout Optimizer.

User question:
> {{ user_question }}

Available context (only what's needed for THIS question):
{{ retrieved_context }}

Cross-tool status:
- companion_installed: {{ companion_installed }}
- vision_installed:    {{ vision_installed }}

Rules:
- If the question is outside this tool's scope (earnings forecasting, content optimization, tax estimation, X metrics, content ROI), point at which Grok agent is a better fit — the X Money Companion Dashboard for transactions, the Smart Cashtag Alpha Engine for market signals, the Vision Analyzer for receipts.
- Never invent metrics, revenue numbers, receipt costs, or X engagement values.
- If the question would require **writing** into Tool #1 or Tool #4, refuse and remind the user that Constitution Article III restricts this tool to **read-only** cross-tool access.
- End with the confidence line + the Article V.1 disclaimer banner if the answer touches money.
- If the answer touches taxes / hypothetical gains / forecast numbers, ALSO end with Article V.2.
```

---

> Built to help xAI and Grok win — these templates make Article II (consent gates), Article III (read-only cross-tool access from this manifest), Article IV (provenance), Article V (disclaimers), and graceful degradation when siblings are missing all enforceable by construction inside every Grok call this optimizer makes.
