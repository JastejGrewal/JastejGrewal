# CleanKars — Hermes Agent System (Deployment Playbook)

The "Hermes agent" = Claude (Max plan) + connected accounts + scheduled Routines +
GoHighLevel handling real-time lead response. This doc is the single source of truth
for what's deployed, what's pending, and the exact go-live order.

## System map

```
Meta Ads (CleanKars acct)                    ALREADY BUILT (paused)
  └─ Ceramic Coating Messenger campaign, $20/day cap, Mount Sinai 15mi
        │  click → Messenger DM to CleanKars page
        ▼
Facebook Page Inbox ──── GHL Facebook integration ────► GoHighLevel
                                                          ├─ instant auto-reply (24/7)
                                                          ├─ tag: ceramic-lead
                                                          ├─ pipeline: New DM → Quoted → Booked → Coated
                                                          └─ notify Jastej (app/SMS)
Claude Routines (deployed, run automatically in this session):
  ├─ Daily 9:00am ET  — spend/conversations/cost-per-convo digest + error watch
  │                      auto-pauses ONLY if a platform error doubles daily spend
  └─ Weekly Mon 9:30am ET — optimization pass, benchmark check, budget rec,
                             appends Performance log to README + push notification
```

## Status board

| Piece | Status | Owner |
|---|---|---|
| Meta campaign + 2 DM ads | ✅ Built, PAUSED | done |
| Daily ops monitor (Routine `trig_01Ppa21ySvmCswUMXduTP629`) | ✅ Live | done |
| Weekly optimizer (Routine `trig_011uojPsaTePys4MT5bgyrFQ`) | ✅ Live | done |
| GHL ↔ Facebook connect | ❌ Requires page-admin OAuth login | **Jastej (~5 min)** |
| GHL auto-reply workflow + pipeline | ❌ Built in GHL UI | **Jastej (~20 min)** |
| Meta Business Suite instant reply (stopgap) | ❌ | Jastej (~3 min) |
| Activate campaign | ⏸ Waiting on GHL connect | say "activate" |
| Lead Ads ToS acceptance (unlocks instant forms) | ❌ Page setting | Jastej (~2 min) |
| Landing page (GHL funnel or renew cleankars.co) | ❌ Optional phase 2 | Jastej decision |
| GHL API access for Claude (Private Integration token) | ❌ Optional | Jastej (~5 min) |

## Go-live order (do it in this sequence)

1. **GHL → Settings → Integrations → Facebook/Instagram** — log in as the CleanKars
   page admin, grant ALL permissions, select the page. This is OAuth; only the page
   admin can click it. 5 minutes.
2. **GHL → Automation → Workflows → Create:**
   - Trigger: "Customer Replied", channel = Facebook Messenger (fires on first inbound DM)
   - Action 1: reply — "Thanks for reaching out about ceramic coating! Quick questions:
     what year/make/model, and what town are you in? We come to you."
   - Action 2: add tag `ceramic-lead`
   - Action 3: create opportunity in pipeline "Ceramic Coating", stage "New DM"
   - Action 4: internal notification (GHL mobile app push or SMS to you)
3. **GHL → Opportunities → create pipeline** "Ceramic Coating":
   New DM → Quoted → Booked → Coated.
4. **Stopgap while doing the above:** Meta Business Suite → Inbox → Automations →
   turn on **Instant Reply** with the same first message, so no DM ever sits cold.
5. **Tell Claude "activate"** → campaign, ad set, and both ads flip ACTIVE
   (top-down), Meta reviews the ads (minutes–hours), then delivery starts and the
   daily/weekly Routines take over monitoring automatically.

## Give Claude direct GHL control (optional, recommended)

GHL ships an official API + MCP. To let Hermes create contacts/opportunities, read
conversations, and manage the pipeline without you clicking:

1. GHL → Settings → **Private Integrations** → create token, scopes:
   contacts, conversations, opportunities, calendars (read+write).
2. Either add GHL as a custom connector on claude.ai (MCP endpoint:
   `https://services.leadconnectorhq.com/mcp/`, auth = that token + your locationId),
   or paste the token into a Claude session and it can drive the REST API directly.
   The token is scoped and revocable in GHL settings at any time.

Note: GHL *workflows* themselves cannot be created via API — step 2 of go-live is
UI-only regardless. That's a GHL platform limitation, not a Claude one.

## Money (as of 2026-07-12)

- Claude Max: $200/mo flat — covers all agent work + Routines, no per-task fees
- Connectors (Meta Ads, Gmail, Drive): $0
- Meta ads: $0 until activated, then hard-capped $20/day (~$600/mo max)
- GHL: free trial started ~Jul 4 → converts to paid (~$97/mo Starter) — confirm or
  cancel before trial end
- Old campaigns: all paused, $0; full deletion only possible in Ads Manager UI

## Guardrails baked into the automation

- Routines never change budget/targeting/status on their own; they recommend.
- Single exception: auto-pause + immediate notification if a platform error pushes
  spend past 2× the daily cap.
- Scale-up rule the weekly optimizer follows: only recommend $35–50/day after cost
  per conversation holds under ~$10.

## Performance log

(Weekly optimizer appends dated entries below once the campaign is live.)
