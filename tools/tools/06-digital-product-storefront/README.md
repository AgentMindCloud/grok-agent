# 06 · Digital Product Storefront

Category: Monetization

> Sell digital products from your X bio link in 2 minutes.

![Status](https://img.shields.io/badge/Status-Spec'd-52525b?style=for-the-badge&labelColor=000000)
![Family](https://img.shields.io/badge/Family-grok--install-a855f7?style=for-the-badge&labelColor=000000)

## What it does

Digital Product Storefront is a hosted, dark-themed bio-link store for X creators. Upload a PDF, zip, or file link, set a price, pick a payment provider, and paste `xpt.shop/yourname` into your bio. Buyers pay, get an instant download link, and you keep the margin.

## Why it exists

Gumroad and Lemon Squeezy cover the mechanics but look generic and don't feel like part of an X creator's brand. Creators want a storefront that matches the dark, fast, minimal aesthetic they already use across threads and pinned posts. This tool is a standalone X-creator-first storefront with multi-provider payments, instant delivery, and the same visual language as the rest of the toolkit.

## Tech stack

- Next.js frontend, dark-only theme
- Firebase Auth, Firestore, Firebase Storage
- Stripe via NexaPay, NowPayments crypto, PayPal
- Deployed on Render or Vercel
- Custom domain `xpt.shop` with per-user subpath

## Install

This tool is currently in the design phase. See [SPEC.md](./SPEC.md) for full implementation plan.

## License

Apache 2.0 — Part of the [grok-install family](https://github.com/AgentMindCloud/x-platform-toolkit).
