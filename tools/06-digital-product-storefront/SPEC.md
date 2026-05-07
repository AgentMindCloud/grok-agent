# SPEC · 06 Digital Product Storefront

## Tagline

Sell digital products from your X bio link in 2 minutes.

## Why it exists

X creators have exactly one link in their bio and a narrow window to convert a curious profile visitor into a paying customer. Existing storefronts like Gumroad and Lemon Squeezy solve the payment plumbing but come with generic templates, third-party branding, and limited support for crypto or regional payment methods. The bio-link click lands on a page that feels like it belongs to someone else.

This tool is a storefront designed specifically for the X bio-link use case. Dark-only theme that matches thread screenshots, instant checkout, multi-provider payments including crypto, and a short-URL format (`xpt.shop/yourname`) that looks native to the platform.

## User journey

1. Creator signs up with Firebase Auth (email or Google).
2. Creator uploads a product: PDF, zip, or external hosted link, plus cover image and short description.
3. Creator sets price, currency, and toggles which payment providers accept it (Stripe via NexaPay, NowPayments for crypto, PayPal).
4. Tool assigns a storefront URL in the format `xpt.shop/{username}` and shows a preview.
5. Creator pastes URL into X bio.
6. Buyer visits page, picks a payment method, completes checkout, and receives a signed download link by email within seconds.

## Data sources

- Internal: product metadata in Firestore, files in Firebase Storage
- Stripe webhooks for Stripe/NexaPay checkout completion
- NowPayments IPN for crypto confirmations
- PayPal IPN for PayPal orders
- SendGrid or Resend for delivery emails

## Tech stack

- Next.js 14 app router, dark-only design system, deployed on Vercel (primary) or Render
- Firebase Auth for creator accounts
- Firestore for product, order, and payout records
- Firebase Storage with signed URLs for file delivery
- Stripe (via NexaPay wrapper), NowPayments, PayPal SDKs
- Custom domain `xpt.shop` with wildcard subpath routing

## Estimated build

16–24 hours.

## Open questions / risks

- Multi-provider checkout means three webhook surfaces to secure and reconcile. Order state machine must be idempotent.
- Signed download URLs need expiry and re-issue flow for buyers who lose the email.
- Payout structure: platform fee vs. direct-to-creator Stripe Connect. Direct-to-creator is cleaner but adds onboarding friction.
- Chargebacks and refunds across three providers need consistent UI.
- File size limits on Firebase Storage free tier may force a paid plan from day one.
- `xpt.shop` domain must be registered and SSL-provisioned before launch.
