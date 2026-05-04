<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built to help xAI and Grok win. -->

# User Message Templates — X Smart Cashtag Alpha Engine

Reusable user-message templates for the 6 tabs. The Streamlit app loads this file, selects a template by anchor (e.g. `#alpha-report-card`), substitutes `{{ variable }}` placeholders with live data from the local SQLite + the manifest's declared public APIs, and sends the result as the user message alongside `prompts/system.md`.

System-prompt rules (Articles III, IV, V.1, V.2, VI cost-cap, no autonomous publishing) are global; templates here only add **task-specific** shape. JSON-only outputs are explicitly noted — the UI injects disclaimers for those, since they're rendered into cards.

Placeholder syntax is Jinja2-style (`{{ var }}`) so cashtag strings, memos, and headlines containing literal curly braces don't break substitution.

---

## #alpha-report-card

The user is on the **🤖 Alpha Reports** tab and clicked "Generate new alpha report" on a cashtag. **JSON-only output**; the UI renders disclaimers separately.

```
Generate an alpha report for `{{ cashtag }}` over the last {{ window_hours }} hours.

Available data (from local SQLite + the four declared public APIs):
- yfinance quote summary:                {{ quote_summary }}
- recent NewsAPI headlines (max {{ news_limit }}):  {{ news_headlines }}
- recent x_search mentions (max {{ x_limit }}):     {{ x_mentions_summary }}
- coingecko spot (if crypto):            {{ coingecko_summary }}
- user's existing position (if any):     {{ existing_position }}
- last alpha report on this cashtag:     {{ previous_report_summary }}

Return JSON only — no prose, no banner, no markdown wrapping. Schema:

{
  "cashtag":           "{{ cashtag }}",
  "headline":          string,           // one sentence, the takeaway
  "body":              string,           // markdown, 2-4 numbered evidence bullets each citing a source
  "confidence":        "high" | "medium" | "low",
  "confidence_reason": string,           // one sentence; if low, state what would raise it
  "sources":           string[],         // e.g. ["yfinance", "newsapi", "x_search via grok-4.3"]
  "contradictions": [
    {
      "claim_a":       { "source": string, "value": string },
      "claim_b":       { "source": string, "value": string },
      "delta_summary": string
    }
  ]
}

Disclaimer enforcement: the surrounding UI prepends V.1 (and V.2 if the body mentions hypothetical gains) — do NOT include the banner inside the JSON.
If the data window is too thin for a meaningful claim, return a JSON object with confidence "low", an empty contradictions array, and a headline that says so directly.
```

---

## #cashtag-analysis

The user clicked into a row in the **🔭 Watchlist** tab and asked for a quick conversational analysis.

```
Quick analysis on `{{ cashtag }}` for the **🔭 Watchlist** tab.

Available data:
- live quote: {{ quote_summary }}
- 5d / 30d performance: {{ perf_summary }}
- last 3 NewsAPI headlines: {{ news_headlines }}
- user's position (if any): {{ existing_position }}

Produce 4–6 lines:
1. **Where the cashtag is right now** (one sentence with $price + intraday delta)
2. What drove the most recent move (cite NewsAPI headlines numerically with source name)
3. Any contradictions worth surfacing (or "no conflicts in the data window")
4. A clear "what to watch next" — describe a trigger, never prescribe a trade
5. The confidence line + the Article V.1 disclaimer banner
```

---

## #portfolio-simulation-narrative

The user ran the Portfolio Simulator and the app needs the cover narrative for the result. **Markdown output with both V.1 + V.2** — hypothetical gains are explicitly tax-relevant.

```
Write the cover narrative for a portfolio simulation result on the **🎯 Portfolio Simulator** tab.

Inputs:
- Date window:    {{ start_date }} to {{ end_date }} ({{ days }} days)
- Hypothetical positions: {{ positions_summary }}
- Starting value: ${{ starting_value }}
- Ending value:   ${{ ending_value }}
- Absolute P&L:   ${{ pnl_abs }}
- % P&L:          {{ pnl_pct }}%
- Top contributors / detractors: {{ contributors }}

Write three short paragraphs:
1. **What the simulation shows** — date range, total P&L, biggest contributor, biggest detractor
2. **Caveats** — explicit note that this is hypothetical; no slippage, fees, or taxes are accounted for; past performance is not predictive
3. **Provenance** — name the price source (yfinance / coingecko), the simulation timestamp, and the random seed if one was used

End the response with the confidence line, the Article V.1 disclaimer banner, AND the Article V.2 disclaimer banner (hypothetical gains have tax implications and the user should know that before exporting).
```

---

## #trending-explanation

The user is on the **🌊 Trending** tab and clicked one row.

```
Explain why `{{ cashtag }}` is trending on X right now.

Inputs:
- mentions_24h:   {{ mentions }}
- sentiment:      {{ sentiment }}
- momentum_pct:   {{ momentum_pct }}%
- narrative tag:  {{ narrative_tag }}
- supporting x_search excerpts (cite numerically): {{ x_excerpts }}
- last 3 NewsAPI headlines (cite numerically):     {{ news_headlines }}

Produce 4 lines:
1. **Why it's moving** — one bold sentence
2. The 2 strongest evidence points, each citing an excerpt # or a headline #
3. Whether the move is fundamentally sourced or sentiment-only — call it out plainly
4. The confidence line + the Article V.1 disclaimer banner

If sentiment and momentum disagree (e.g. sentiment 0.78 positive but momentum -3%), surface that as a **contradiction** per Article III.
```

---

## #contradiction-flag

Used when the alpha logic detects two sources conflicting on the same fact. Article III: the engine never silently picks a side.

```
Two sources conflict on a fact about `{{ cashtag }}`. Surface the conflict cleanly — never resolve it silently.

Source A: {{ source_a_name }} (retrieved {{ source_a_timestamp }})
- Claim: {{ source_a_claim }}

Source B: {{ source_b_name }} (retrieved {{ source_b_timestamp }})
- Claim: {{ source_b_claim }}

Produce:
1. **Both claims** stated verbatim, side by side, with source name + timestamp on each
2. The **magnitude** of the disagreement (e.g. "25% delta on valuation", "$0.18 spread on price")
3. Which **primary source** would resolve the conflict (issuer press release, exchange filing, on-chain explorer) and how the user can find it
4. NEVER pick a winner — Article III prohibits silent contradiction resolution
5. End with the confidence line + the Article V.1 disclaimer banner
```

---

## #watchlist-summary

The user lands on the **📊 Overview** tab; produce the headline summary.

```
Summarize the user's watchlist for the **📊 Overview** tab.

Inputs:
- watchlist size:                    {{ size }}
- top 3 movers (intraday):           {{ top_movers }}
- bottom 3 movers (intraday):        {{ bottom_movers }}
- active alerts:                     {{ alert_count }}
- positions held (if any):           {{ positions }}
- recent alpha reports (last 24h):   {{ recent_reports }}

Produce 4 lines:
1. **One-sentence health check** — bold takeaway (calm / mixed / spicy)
2. The single most surprising mover (with $ delta + source citation)
3. The most recent active alert worth investigating right now
4. The confidence line + the Article V.1 disclaimer banner
```

---

## #counterparty-context

The user clicked a cashtag in any tab and asked for combined market + news context. This template composes `fetch_cashtag_quote` + `fetch_cashtag_news`.

```
Give combined market + news context for `{{ cashtag }}`.

Steps:
1. Call `fetch_cashtag_quote({"cashtag": "{{ cashtag }}"})` — get live price + intraday delta.
2. Call `fetch_cashtag_news({"cashtag": "{{ cashtag }}", "limit": 3})` — get the top 3 most recent headlines.
3. Summarize:
   - Where the price is now ($ + day delta), with the API source named
   - The 2–3 most relevant headlines (cite source name + published_at on each)
   - Whether news flow agrees or **conflicts** with the price action — flag conflicts per Article III
4. End with the confidence line + the Article V.1 disclaimer banner

If either tool returns an error or empty result, say so plainly — never invent data.
```

---

## #alert-trigger-explanation

A cashtag in the user's watchlist crossed the manifest's `cashtag_threshold_pct` (default 5.0%) and `real_time_x.triggers: cashtag_change` fired. Explain the move.

```
A cashtag just crossed the {{ threshold_pct }}% movement threshold.

Inputs:
- cashtag:          {{ cashtag }}
- direction:        {{ direction }}        # up | down
- magnitude:        {{ magnitude_pct }}%
- starting price:   ${{ start_price }}
- current price:    ${{ current_price }}
- triggers / news from the last hour: {{ recent_news }}

Produce:
1. **What just happened** — one bold sentence (move + likely-immediate driver)
2. The 1–2 most likely triggers (cite NewsAPI headlines or x_search mentions numerically)
3. What the user might want to do — describe a possible action, **never** prescribe a trade ("you might want to tighten your watchlist threshold" is OK; "you should sell" is NOT)
4. The confidence line + the Article V.1 disclaimer banner

Reminder: this engine never posts. If the user asks "should we tweet about this?", remind them `posts: false` is binding in the manifest.
```

---

## #general-chat

Open-ended user question that doesn't fit a specific tab template.

```
Open question from the user about cashtags / alpha / watchlist.

User question:
> {{ user_question }}

Available context (only what is needed for THIS question):
{{ retrieved_context }}

Rules:
- If the question is outside this engine's scope (cashtag tracking, alpha signals, watchlist management, portfolio simulation, trending), point at which Grok agent is a better fit — for example: the X Money Companion Dashboard for personal transactions, the Creator Payout Optimizer for earnings forecasts, the Vision Analyzer for receipts.
- Never invent prices, headlines, or x_search mentions.
- If the question would require posting to X, refuse and remind the user that `posts: false` is binding in the manifest.
- End with the confidence line + the Article V.1 disclaimer banner if the answer touches money or markets.
- If the answer touches hypothetical gains, ALSO end with the Article V.2 disclaimer.
```

---

> Built to help xAI and Grok win — these templates make Article IV (provenance), Article III (no silent contradictions), and Article V (mandatory disclaimers) enforceable by construction inside every Grok call this engine makes.
