# CleanKars — Ceramic Coating Meta Ads Campaign (Hermes build, July 2026)

Complete design + runbook for the ceramic coating campaign built in the **CleanKars**
Facebook ad account, and the checklist to finish wiring it into GoHighLevel.

## What was built (all created PAUSED — nothing spends until activated)

| Entity | Name | ID |
|---|---|---|
| Ad account | CleanKars | `342135841659556` |
| Campaign | CK \| Ceramic Coating \| Messenger Leads \| Mount Sinai 15mi \| 2026-07 | `120249568167580690` |
| Ad set | Mount Sinai 15mi — Broad Advantage+ — Messenger | `120249568172440690` |
| Ad 1 | Ceramic S-01 — Gyeon Quartz + 56 Reviews (Video, DM) | `120249568185680690` |
| Ad 2 | Ceramic Audi — Mirror Finish (Video, DM) | `120249568187410690` |
| Creative 1 | CK \| Ceramic S-01 \| Messenger DM \| 2026-07 | `1699140784664240` |
| Creative 2 | CK \| Ceramic Audi \| Messenger DM \| 2026-07 | `905414898565251` |

### Campaign settings
- **Objective:** Engagement → Messenger conversations (click-to-Messenger "Get Quote" flow)
- **Budget:** $20/day, campaign-level (CBO), lowest-cost bidding
- **Targeting:** 15-mile radius around Mount Sinai, NY (40.9468, -73.0176),
  Advantage+ audience with age 25+ suggestion, automatic placements
- **CTA:** "Message Page" → opens Messenger DM with the CleanKars page (`m.me/299080249944992`)
- **Copy:** reuses the proven account copy — Gyeon Quartz ceramic, 3–5 yr protection,
  mobile/we-come-to-you, 5.0★ 56 Google reviews, Mount Sinai + 15 miles
- Meta account **Opportunity Score: 100/100** after the build (no outstanding recommendations)

## Why Messenger leads (not a website funnel or instant forms)

Audit findings from the account on 2026-07-10:

1. **cleankars.co is dead** — DNS does not resolve. Every past conversion campaign
   pointed at a page that no longer exists.
2. **All 3 pixels are stale** — "Landing Page" (`416283610938332`) last fired
   2025-09-02; "CleanKars" (`1746794412579190`) last fired 2025-05-30;
   "CleanKars Pixel" (`3079716705513264`) never fired. Website-conversion
   optimization has no signal to learn from.
3. **The Facebook Page has not accepted Meta's Lead Ads terms**
   (`leadgen_tos_accepted = false`), so instant-form lead ads are blocked.
4. Messenger DMs are a **native GoHighLevel channel**, so this is the one lead
   flow that can be fully automated in GHL today.

## To launch (Ads Manager or ask the agent)

Activate top-down: campaign → ad set → both ads. Ads will go through Meta review
on first activation (~minutes to hours).

## GoHighLevel connection checklist (manual — do inside GHL)

GHL account: app.gohighlevel.com (trial started ~2026-07-04, onboarding incomplete).
No GHL connector/API access was available to the agent, so these steps must be done
in the GHL UI (≈15 min):

1. **Finish sub-account setup** for CleanKars if not done (business info, phone number).
2. **Connect Facebook:** Settings → Integrations → Facebook/Instagram → log in as the
   CleanKars page admin → grant ALL permissions → select the CleanKars page.
3. **Enable Messenger channel:** after the integration, DMs to the page appear in
   GHL → Conversations. Send the page a test DM and confirm it shows up.
4. **Auto-reply workflow:** Automation → Workflows → new workflow,
   trigger = "Customer Replied" / channel = Facebook Messenger →
   action = send reply ("Thanks for reaching out about ceramic coating! What year,
   make & model is your car, and what town are you in?") → add tag `ceramic-lead`
   → notify yourself (SMS/push).
5. **Pipeline:** create a "Ceramic Coating" pipeline (New DM → Quoted → Booked → Coated)
   and have the workflow create an opportunity in stage "New DM".
6. **Missed-call text-back + calendar** (optional but recommended for booking).

## Follow-ups that will raise performance later

- **Revive a landing page:** either re-register/repoint cleankars.co or publish a GHL
  funnel page (free subdomain works). Install pixel `416283610938332` (or retire the
  duplicates and standardize on one), then add a second ad set optimizing for
  Lead/SubmitApplication conversions and let it compete with Messenger.
- **Accept Lead Ads ToS** on the Facebook Page to unlock instant forms — GHL can pull
  those leads directly via its Facebook Lead Ads integration.
- **Fix the disabled personal ad account** (`876572584353205`) is unrelated to this
  campaign; CleanKars account is healthy.
- After ~2 weeks of data: kill the losing ad, add 1–2 fresh videos (before/after wash
  beading clips outperform statics for coatings), consider raising budget toward
  $35–50/day if cost-per-conversation is acceptable (target <$8–12 for Suffolk County).
