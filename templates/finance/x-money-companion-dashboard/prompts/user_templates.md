<!-- Copyright 2026 AgentMindCloud -->
<!-- Licensed under the Apache License, Version 2.0 -->
<!-- http://www.apache.org/licenses/LICENSE-2.0 -->
<!-- Built for xAI, X, Grok and the ecosystem community. ❤️ -->

# User Message Templates — X Money Companion Dashboard

Reusable user-message templates for the 6 tabs of the X Money Companion Dashboard. The Streamlit app loads this file, selects a template by anchor (e.g. `#overview-insight`), substitutes `{{ variable }}` placeholders with live data from the local SQLite, and sends the result as the user message alongside `prompts/system.md`.

All templates assume the system prompt at `prompts/system.md` is already loaded. The system prompt enforces Article V.1 + V.2 disclaimers, provenance, and confidence scoring globally — templates here only add the **task-specific** shape.

Placeholder syntax is intentionally Jinja2-style (`{{ var }}`) so user memo / counterparty strings containing literal curly braces don't break substitution.

---

## #overview-insight

The user is on the **📊 Overview** tab and wants a one-screen takeaway.

```
You are looking at the **📊 Overview** tab.

Recent activity (last {{ days }} days):
- Net cashflow: ${{ net }}
- Inflow:  ${{ inflow }}  across {{ inflow_count }} transactions
- Outflow: ${{ outflow }} across {{ outflow_count }} transactions
- Top 3 counterparties by absolute spend: {{ top_counterparties }}
- Active alerts: {{ alert_count }}

Generate an Overview insight that:
1. Opens with the single most important pattern (one sentence, **bold**)
2. Lists 2–4 supporting bullets, each with a $ figure
3. Names the next-best action the user could take inside this dashboard (one bullet)
4. Ends with the confidence line + the Article V.1 disclaimer banner
```

---

## #transaction-categorize

Used by the `categorize_transaction` tool when the user adds, edits, or imports a transaction.

```
You are categorizing a single X Money transaction. Return JSON only — no prose.

Transaction:
- Date: {{ tx_date }}
- Amount: {{ amount }} {{ currency }}
- Counterparty: {{ counterparty }}
- Memo: {{ memo }}
- Source: {{ source }}   # one of: manual | vision | api

Return a JSON object with exactly these fields:
- `category` — one of: subscriptions, food_drink, transport, groceries, housing, infrastructure, x_payouts, ad_revenue, taxes, other
- `confidence` — high | medium | low
- `reasoning` — one sentence (≤ 25 words)
- `clarifying_question` — non-empty string ONLY when confidence is `low`; otherwise empty string

Disclaimer enforcement is handled by the surrounding categorization UI for this template; do NOT add the disclaimer banner inside the JSON.
```

---

## #grok-insights-card

The user is on the **🤖 Grok Insights** tab and clicked "Generate new insight".

```
You are generating a fresh insight card for the **🤖 Grok Insights** tab.

Local data summary (from SQLite — no external calls unless explicitly requested):
- Window: last {{ days }} days
- Total transactions: {{ tx_count }}
  ({{ vision_count }} from receipt scans, {{ api_count }} from APIs, {{ manual_count }} manual)
- Net cashflow: ${{ net }}
- Subscription footprint MoM: ${{ subs_this_month }} (vs ${{ subs_last_month }} last month)
- Top categories by spend: {{ top_categories }}
- Notable transactions: {{ notable_transactions }}

Produce a 5–8 line insight card that:
1. Opens with one **bold** headline takeaway
2. Numbers 2–4 driver bullets, each grounded in a $ figure from the data above
3. Calls out one cross-tool integration win or gap (for example, the Vision Analyzer hit rate or a missing-receipt pattern)
4. Ends with the confidence line + the Article V.1 disclaimer banner

If a market quote or news headline would materially strengthen the insight, propose the `fetch_market_quote` or `fetch_relevant_news` tool call instead of guessing — and stop until the user approves.
```

---

## #tax-export-narrative

The user is on the **📤 Tax Export** tab, has selected a date range, and just confirmed the consent gate. Generate the cover-page narrative for the export PDF / CSV.

```
You are writing the **cover-page narrative** for a tax export.

Range: {{ start_date }} to {{ end_date }} ({{ days }} days)
Format: {{ fmt }}     # csv | pdf
Transaction count: {{ tx_count }}
Total inflow:  ${{ inflow }}
Total outflow: ${{ outflow }}
Top expense categories: {{ top_expense_categories }}
Top income categories:  {{ top_income_categories }}

Write three short paragraphs:
1. **What this export is** — one paragraph stating the date range, transaction count, and totals.
2. **What this export is NOT** — one paragraph stating that this is a personal record only, **not** a filed tax return; final tax obligations depend on the user's jurisdiction.
3. **Provenance** — one paragraph naming the data source (`local SQLite`), the import sources used (`manual` / `vision` / `api`), and the timestamp the export was generated.

The export pipeline injects the V.1 + V.2 disclaimer banners onto the first page automatically — do NOT repeat them inside the narrative paragraphs.
```

---

## #alert-explanation

The user clicked "Investigate" on an alert in the **🔔 Alerts** tab.

```
You are explaining one alert in plain English.

Alert:
- Title: {{ title }}
- Level: {{ level }}    # warn | info
- Body:  {{ body }}
- Category: {{ category }}
- Supporting transactions: {{ supporting_transactions }}

Produce:
1. A one-sentence **why this fired** (the underlying anomaly or pattern)
2. The 2–3 supporting transactions that drove the alert (with $ amounts and dates)
3. One next-best action — either a dashboard action ("filter the Transactions tab to category={{ category }}") or "no action — just a heads-up"
4. The confidence line + the Article V.1 disclaimer banner

If the alert level is `info` AND the supporting evidence is weak (≤ 2 transactions), say so explicitly — do not over-state.
```

---

## #counterparty-context

The user clicked into a row in the **💳 Transactions** tab and asked for context on the counterparty.

```
You are giving market and news context for a single counterparty.

Counterparty: {{ counterparty }}
Total transacted with this counterparty in last {{ days }} days: ${{ total }} across {{ tx_count }} transactions.

Steps:
1. If `{{ counterparty }}` looks like a known public ticker or a recognizable brand, call `fetch_market_quote({"ticker": "..."})` for a current price.
2. If the counterparty is a recognizable company / product / platform, call `fetch_relevant_news({"query": "...", "from_date": "{{ from_date }}"})` for 1–3 recent headlines.
3. Summarize:
   - The user's pattern with this counterparty (frequency, $ size, category)
   - The market / news context (with cited source + timestamp per Article IV)
   - Whether anything looks off (price spike, unusual frequency, contradicting headline)
4. End with the confidence line + the Article V.1 disclaimer banner.

If neither tool returns useful results, say so plainly — do not pad.
```

---

## #anomaly-investigation

The user is investigating a single flagged transaction (from the **🔔 Alerts** tab or a Transactions row).

```
You are investigating one flagged transaction.

Transaction:
- Date:        {{ tx_date }}
- Amount:      {{ amount }} {{ currency }}
- Counterparty:{{ counterparty }}
- Memo:        {{ memo }}
- Category:    {{ category }}
- Source:      {{ source }}
- Why flagged: {{ flag_reason }}

User's recent context with this counterparty:
{{ counterparty_history }}

Output:
1. **Likely a true anomaly** OR **likely a false positive** — one sentence, bold verdict
2. The 2–3 strongest pieces of evidence either way (each grounded in a transaction or a stated fact)
3. One clear next-best action — re-categorize, request a receipt via the Vision Analyzer, dismiss, or escalate to the user's accountant
4. The confidence line + the Article V.1 disclaimer banner
```

---

## #general-chat

Open-ended question from the user that doesn't fit a specific tab template.

```
You are answering an open question from the user about their dashboard.

User question:
> {{ user_question }}

Available context (only what is needed for THIS question):
{{ retrieved_context }}

Rules:
- If the question is outside the scope of this dashboard (X Money cashflow, transactions, categorization, tax export, alerts), say so and point at which Grok agent or template would be a better fit (e.g. "the Smart Cashtag Alpha Engine for portfolio analysis, the Creator Payout Optimizer for earnings forecasts, the Vision Analyzer for receipts").
- If the question requires data the dashboard doesn't have, say what's missing and how the user could add it.
- Never invent transactions, prices, or headlines.
- End with the confidence line + the Article V.1 disclaimer banner if the answer touches money or markets in any way.
```

---

> Built for xAI, X, Grok and the ecosystem community — these templates are how we keep the Companion Dashboard's Grok layer finance-safe by construction, not by hope.
