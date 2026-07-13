# Founder's Blueprint: AI Shoplifting-Detection Startup (Veesion-Style)

*A comprehensive business + technical plan for building a company that plugs AI-powered, non-facial-recognition theft detection into retailers' existing CCTV systems.*

> **How to read this document.** Every factual claim about the market, competitors, or law is tagged inline as either **[Sourced]** (backed by a specific, named source found during research) or **[Illustrative]** (a reasonable planning estimate with no independent verification — do not repeat these externally as fact). Several **[Sourced]** claims below also carry a **[Needs re-verification]** note where the research could not directly fetch the primary source (e.g., nrf.com, ftc.gov blocked the fetch) and relied on secondary reporting instead. Confirm those against the primary source before using them in an investor deck or public materials.

---

## Table of Contents

1. [Executive Summary & Vision](#1-executive-summary--vision)
2. [Market Landscape & Competitive Analysis](#2-market-landscape--competitive-analysis)
3. [Product Definition](#3-product-definition)
4. [Technical Architecture](#4-technical-architecture)
5. [Legal, Privacy & Compliance Strategy](#5-legal-privacy--compliance-strategy)
6. [Business Model & Pricing](#6-business-model--pricing)
7. [Go-to-Market Strategy](#7-go-to-market-strategy)
8. [Team & Roles Needed](#8-team--roles-needed)
9. [Roadmap & Milestones](#9-roadmap--milestones)
10. [Risks & Mitigations](#10-risks--mitigations)
11. [Financials & Funding Needs](#11-financials--funding-needs)
12. [Success Metrics / KPIs](#12-success-metrics--kpis)
- [Sources Requiring Independent Re-Verification Before External Use](#sources-requiring-independent-re-verification-before-external-use)

---

## 1. Executive Summary & Vision

**Mission.** Reduce retail shrink by giving stores an AI layer that watches their *existing* CCTV cameras for the physical gestures that precede theft — concealment, bag-stuffing, price-tag swapping, cart-stuffing — and alerts staff in real time, without identifying who anyone is. No facial recognition. No biometric watchlists. And no rip-and-replace: any camera meeting our published 1080p-equivalent floor (§4.3b) works as-is; below-spec sites get a partner-fulfilled upgrade path (§3.3) rather than a rejection.

**The wedge.** Every serious competitor in this space (see §2) has picked one of two lanes: identity-based systems that recognize *who* someone is (Corsight, Facewatch), or checkout-focused systems that catch theft *at the register* (Everseen). The gesture-detection lane pioneered by Veesion — catching the *behavior* anywhere in the store, before checkout, without identity — is the most privacy-defensible and the most differentiated. This plan doubles down on that lane, but corrects for two real weaknesses the research surfaced in the incumbent's execution:

- Veesion has already lost a legal battle in France (CNIL/Conseil d'État, June 2024 — see §2.3 and §5) over whether gesture analysis without facial recognition is still GDPR-compliant. We build compliance-by-design from day one instead of defending it after a regulator flags it.
- Veesion has faced credible reporting alleging undisclosed human review of "AI" alerts (the StreetPress/Madagascar story, contested but instructive — see §2.3). We differentiate by being radically transparent that the system is AI-assisted and human-reviewed, and by treating that human review as a *feature* (the fuel for the self-training loop in §4.2), not a liability to hide.

**Why now [Illustrative framing, built on Sourced data points].** Retail shrink and organized retail crime are trending upward according to NRF's most recent survey work (see §2.1), and Veesion — the closest direct competitor — only opened its first US office in 2025 and is still building out that market. That is a real, time-bound window for a US-first or underserved-vertical entrant to establish a beachhead before the incumbent fully scales domestically.

**The core differentiators this plan is built around:**
1. A genuinely **hybrid, ensemble detection pipeline** (skeleton-based + appearance-based + object-context + rule engine + cloud vision API as a bounded tertiary check) rather than a single model family — reduces both false positives and false negatives relative to a single-model approach.
2. A **closed-loop self-training system** where every human confirm/reject decision by loss-prevention (LP) staff becomes labeled training data, prioritized by active learning, and safely promoted through shadow → canary → staged rollout against a frozen evaluation set.
3. An **edge-primary hybrid deployment** that keeps raw video in the store and only ships compact features and flagged clips to the cloud — a real, literal answer to the privacy objection that has already caused Veesion legal trouble.
4. A **published bias-audit program** — a gap the competitive research found *no* competitor currently fills for gesture-based systems (see §2.2) — turned into a market differentiator and a regulatory hedge against an FTC-Rite-Aid-style enforcement action (§5).
5. **Real brownfield-CCTV compatibility, not just a marketing claim.** "Plugs into your existing cameras" only means something if it actually works at the many stores — especially older/independent ones — still running analog DVRs or budget IP NVRs that never advertise ONVIF compliance. §4.3a defines exactly how far that compatibility goes and where the line is drawn.

---

## 2. Market Landscape & Competitive Analysis

### 2.1 Market Size

- **[Sourced, Needs re-verification]** NRF's 2023 National Retail Security Survey — the last edition of NRF's 32-year "classic" format before it was paused over methodology concerns — reported total US retail shrink of **$112.1 billion, or 1.6% of sales, for FY2022**, up from $93.9B/1.4% the prior year.
- **[Sourced, Needs re-verification]** NRF's newer *"Impact of Retail Theft & Violence"* report series (2025 edition) surveyed 70 retail companies representing 168 brands and **$1.3 trillion in annual sales** (25.1% of total US retail). Key findings: an **18% year-over-year increase in average shoplifting incidents** (2024 vs. 2023), a **17% increase in threats/violence** during theft events, **67% of retailers reporting involvement of a transnational organized retail crime (ORC) group** in thefts against their company in the past year, and **64% of retailers reporting they report less than half their incidents to law enforcement**, citing inadequate law-enforcement response as the top reason.
- A commonly cited secondary figure attributes a **"$90 billion"** shrink number to the 2025 report, but this could not be verified against NRF's own primary page during research (nrf.com blocked direct fetch). **Do not use this figure without direct verification at nrf.com.**

**Planning takeaway:** the headline dollar figure to lead with should be re-confirmed directly against nrf.com before it appears in any investor-facing document, but the *directional* story — shrink and organized retail crime both rising, and most incidents going unreported to police — is corroborated across multiple angles of the 2025 report and supports the market timing thesis in §1.

### 2.2 Competitive Landscape

| Company | HQ / Founded | Approach | Funding | How it differs from our play |
|---|---|---|---|---|
| **Veesion** *(the model for this plan)* | Paris; 2018 | Gesture/behavior detection on existing CCTV, no facial recognition | **[Sourced]** €10M Series A (Mar 2022) → May 2025 Series B package reported as **€53M** (€38M equity + €15M non-dilutive) | The direct competitor. See §2.3 for a deep dive. |
| **Everseen** | Cork, Ireland; 2007 | Checkout-focused CV (scan-avoidance, product-switching at self-checkout/staffed lanes) | **[Sourced]** ~$84–113M (sources diverge) | Different problem — catches theft *at the register*, not on the shop floor. Much larger claimed footprint: **10,000+ stores, 150,000+ checkouts [Sourced, vendor claim]**. |
| **Corsight AI** | Israel | **Facial recognition** — identifies repeat offenders and staff/customer "sweethearting" | **[Sourced]** ~$5–8M (small) | Identity-based, the technical opposite of a gesture-only approach. Instructive as a cautionary tale (see Facewatch below). |
| **Facewatch** | UK | **Facial recognition** watchlist shared across subscriber retailers | N/A found | Same identity-based lane as Corsight, at much larger UK retail scale (Sainsbury's expanding to 200 stores by end of 2026 **[Sourced]**). Subject of an ICO complaint from Big Brother Watch (2022) over opaque enrollment onto shared blacklists — a live controversy as it expands **[Sourced]**. This is the clearest "what not to become" reference point in the whole competitive set. |
| **Trigo** | Israel; 2018 | Frictionless/cashierless checkout; added a loss-prevention module | **[Sourced]** $100M raised (2022) | Core business is checkout-free retail, not gesture-based theft alerting — adjacent, not directly competing. Explicitly no facial recognition/biometrics (similar privacy stance to us). Deployed at Tesco (UK), REWE (Germany) **[Sourced]**. |
| **AiFi** | US | Frictionless checkout via anonymized skeletal tracking, no facial recognition | N/A found | Same adjacent category as Trigo. Powers part of 7-Eleven's checkout-free rollout **[Sourced]**. |
| **Vaak** | Japan; ~2017–19 | Behavior/gesture-based theft prediction ("VaakEye") | **[Sourced]** ~¥50M (~$450K) from a SoftBank AI fund, seeking ~$9M Series A as of its early press cycle | The closest conceptual match to our approach, but tiny and early — no evidence of a major recent scale-up found. A real signal that the concept works, and that the market hasn't been won yet outside Veesion. |
| **Auror** | New Zealand / global | Crime-intelligence network aggregating incidents across **85,000+ stores and 3,500+ law enforcement agencies [Sourced, vendor claim]** to flag organized/repeat offenders | N/A found | Fundamentally different: a data-sharing/case-management network, not a real-time per-camera AI detector. Complementary, not substitutable — a plausible acquisition/partnership target once we have scale (see §6). |
| **Malong Technologies** | Shenzhen, China; 2014 | CV-based product recognition for self-checkout loss prevention | N/A found | Checkout/product-recognition focus, not shop-floor gesture detection. |

**Notable market gap found in research:** no competitor in this set has a *published, third-party bias-audit program* for their detection system. The facial-recognition players (Corsight, Facewatch) face the sharpest scrutiny on this (see NIST FRVT bias findings, §5), but the research found no gesture-based competitor — including Veesion — publicly committing to bias testing either. This is a genuine, defensible differentiator (§1, §5).

### 2.3 Veesion Deep-Dive: Lessons for This Plan

**Funding & trajectory [Sourced].** Founded 2018 by Thibault David (CEO), Benoît Koenig (COO), and Damien Menigaux (CTO), who met on a joint AI program at HEC Paris/École Polytechnique. Raised €10M in a March 2022 Series A (Odyssée Venture, Verve Ventures, Swiss Immo Lab, Techmind, plus existing investors), then a May 2025 Series B package headlined by press as **€53M** — €38M in equity plus €15M in non-dilutive financing (White Star Capital, Red River West, Bpifrance, Odyssée Ventures, Founders Future). Note the arithmetic: €53M matches only the 2025 package (38+15) and excludes the 2022 Series A, so no single "total funding" figure reconciles across press reports — treat totals as press-reported, not audited (flagged in the end-of-document verification list). Post-Series-B, co-founder Benoît Koenig relocated to open Veesion's first US office (Florida, targeting ~50 hires), with a stated R&D goal of pushing detection rates above 50% by 2026 and expanding into self-checkout fraud and slip-and-fall detection. Veesion stated it already generated ~10% of revenue from the US *without* a physical presence there pre-expansion — a strong demand signal for the US market this plan targets.

**Customer/country claims [Sourced but unverified].** Marketing materials cite ranges from "6,000+ stores in 25 countries" to "5,000+ stores across 50+ countries" depending on the source and date. No independently audited figure was found. Treat any number Veesion publishes as a marketing claim, and do not rely on our own equivalent claims being taken at face value by press or investors either — build toward auditable numbers (§12) from day one.

**The CNIL/Conseil d'État ruling — the single most important fact in this research pass [Sourced].** In June 2024, France's data protection authority (CNIL) informed Veesion it considered the company's gesture-detection processing non-compliant with GDPR. Veesion sought emergency suspension of that finding before the Conseil d'État (France's highest administrative court); on **21 June 2024 (Case CE-495153)**, the court **rejected Veesion's appeal**, finding no serious doubt about the legality of CNIL's position, and specifically holding that gesture/movement analysis did not qualify for the narrow CCTV exemption (Article R.253-6) Veesion claimed. Advocacy group La Quadrature du Net argues the underlying issue is that gesture/movement analysis constitutes biometric data processing under Article 9 GDPR, which is prohibited absent a specific statutory exception — and that none of Veesion's claimed exceptions applied.

**Why this matters for us, directly:** "we don't use facial recognition" is *not* a GDPR safe harbor. A regulator and a top court have already treated movement/gesture analysis as biometric-adjacent processing requiring the same scrutiny as facial recognition. This plan's entire legal strategy (§5) is built around not repeating this mistake — a DPIA and documented legal basis before any EU pilot, not after a regulator objects.

**The StreetPress/Madagascar allegation [Sourced, contested, single-outlet].** French investigative outlet StreetPress reported in 2023 that Veesion recruited workers in Madagascar whose role, per that reporting, was to manually flag suspicious behavior on live camera feeds in near-real-time — going beyond pure training-data labeling for an ostensibly autonomous model. Researchers at Télécom Paris, cited in the same coverage, frame this as part of a broader "AI-washing" pattern (marketing human-assisted systems as autonomous AI). Veesion has disputed this characterization. This was not independently re-verified against the original StreetPress article during this research pass (only accessible via a secondary summary) — **do not repeat the specific allegation as established fact**, but *do* treat the underlying risk category (undisclosed human review, "AI-washing" reputational and potentially legal exposure) as real and worth designing against, which §3 and §5 do explicitly.

---

## 3. Product Definition

### 3.1 Target Segments (ranked by shrink exposure)

1. **Grocery / convenience** — highest shrink rates in the industry **[Illustrative — commonly asserted industry pattern; verify against NRF sector-level shrink data before external use]**, high camera counts, thin margins that make even modest shrink reduction ROI-positive.
2. **Pharmacy** — high-value, easily concealed merchandise (the same segment where the Rite Aid facial-recognition scandal occurred, §5 — a segment already primed to want a *privacy-defensible* alternative).
3. **Apparel** — fitting-room-adjacent concealment patterns, a distinct gesture vocabulary from grocery that the detection pipeline needs to be trained for separately.
4. **Big-box / general merchandise** — largest camera counts per site, best fit for the enterprise pricing tier (§6).

### 3.2 Core Feature Set

- **Real-time alerting**: push notification + dashboard alert, routed to on-duty LP staff, with confidence-tiered urgency (§4.1).
- **Clip-based review workflow**: every alert carries a short pre/post-roll clip and a one-tap **Confirm theft / False alarm / Unsure** control — this is simultaneously the core UX and the label-generation mechanism for §4.2.
- **Case management**: confirmed incidents roll into a case record (time, location, item category if known, resolution) for LP and loss-prevention managers.
- **Store analytics & ROI dashboard**: shrink-relevant trends by store/zone/time, alert-confirmation rates, and an ROI view management can use to justify the subscription cost (§7).
- **LP-staff mobile app**: the primary interface for floor staff — alerts, clip review, confirm/reject, in a phone-first UI.

### 3.3 Onboarding: Site Compatibility Survey

Onboarding begins with a formal **site compatibility survey**, run from the site-survey checklist that install partners are certified on (§7): camera count, per-camera resolution and field-of-view assessment against the hard minimum spec (§4.3b), recorder/NVR make and model (to classify the site into an integration tier, §4.3a), and network readiness (uplink quality, whether the cellular-failover option is needed, §4.3).

Stores below the minimum camera spec are not simply turned away — the default motion is a **bundled camera-replacement upsell quote**, fulfilled through the install-partner network (§7), with outright decline as the fallback only if the prospect won't upgrade. This keeps the worst-shrink, oldest-hardware stores addressable without compromising detection accuracy.

### 3.4 Explicit Non-Features (Stated Boundaries)

These boundaries are deliberate product and legal decisions, not omissions:

- **No facial recognition.** Ever. This is the core positioning against Corsight/Facewatch, and — per §2.3 and §5 — we still don't treat this alone as a compliance strategy.
- **No cross-retailer identity sharing or blacklisting.** Directly differentiates from Facewatch's shared-watchlist model, which is the subject of an active UK privacy controversy.
- **No employee biometric tracking.** Uniform/badge visual cues are used only to suppress false positives during restocking (a rule-engine input, §4.1), never to identify or track individual employees.

---

## 4. Technical Architecture

### 4.1 Detection Pipeline Design

The pipeline is a **staged, multi-model cascade**: cheap/fast models run on every frame to narrow attention; progressively more expensive models run only on candidate windows. This is what makes real-time multi-camera inference affordable on edge hardware.

**Stage A — Person detection & tracking** *(every frame, edge)*
YOLOv8/v11-n or -s (Ultralytics), fine-tuned for the person class, INT8-quantized, paired with **ByteTrack** or **BoT-SORT** for multi-object tracking so downstream stages reason over a temporal window per shopper rather than per frame.

**Stage B — Pose estimation** *(per tracked person, every frame)*
**RTMPose** (OpenMMLab/MMPose) as primary — strong real-time accuracy/speed tradeoff, exports cleanly to ONNX → TensorRT. **MediaPipe Pose (BlazePose)** as a lightweight fallback for lower-tier edge hardware. Output is a sequence of keypoints per person per frame — the *privacy-preserving* representation the rest of the system prefers, since skeleton data carries essentially no biometric-identity value, unlike a face embedding.

**Stage C — Temporal action/gesture recognition** *(sliding window, ~2–3s at 15–30fps)*
The core "is this concealment?" classifier is itself a **two-branch ensemble**, because the branches fail differently:
- *Skeleton-based branch*: ST-GCN, or stronger variants CTR-GCN/MS-G3D, or PoseC3D (MMAction2, treats stacked pose heatmaps as pseudo-video). Fast, edge-native, privacy-friendly, robust to lighting/clothing changes.
- *Appearance-based branch*: a lightweight video model on the cropped person patch, with the **face region blurred/excluded before this model ever sees pixels**. MoViNet for edge efficiency, or a distilled VideoMAE/SlowFast backbone as a cloud-side secondary opinion on flagged clips only. Catches what skeleton alone misses — object texture in the hand, whether something visibly entered a bag opening.

**Stage D — Object/context detection** *(auxiliary, every frame or every Nth frame)*
YOLO fine-tuned on custom classes: bag/backpack, pocket, product/merchandise, cart, shelf-edge, POS/checkout zone, hand. Feeds structured context into the fusion layer ("hand entered bag-opening region," "item left shelf zone with no subsequent scan event").

**Stage E — Rule-based/heuristic layer** *(deterministic, on top of all model outputs)*
Zone logic, dwell-time thresholds, gesture-sequence rules (pickup → concealment → no payment correlation within N minutes), repetition heuristics, and employee-uniform/badge exclusion rules. **This layer does most of the actual false-positive suppression in production** — the ML models alone will over-trigger on innocuous bag-adjustment and clothes-shopping motions.

**Stage F — Ensemble/fusion & confidence scoring**
A small learned meta-model (LightGBM or shallow MLP) combines the skeleton-branch score, appearance-branch score, object-context features, and rule-engine flags into a calibrated fused confidence, with **temporal hysteresis** (require N consecutive positive windows, not a single flicker) and **confidence-tiered routing**: low → log only (a training-data candidate, no alert), medium → soft notification, high → real-time push alert with clip.

This design keeps the expensive appearance model and any cloud vision API call invoked only on the narrow set of candidates that clear the cheap skeleton+rule filters — critical for both edge compute budget and cloud API cost, and the concrete realization of the "hybrid ensemble" requirement from §1.

### 4.2 Self-Training / Continuous Learning Loop

**Feedback capture.** Every alert delivered to LP staff carries the Confirm/False-alarm/Unsure control from §3.2, plus an optional reason tag (employee restocking, trying on clothing, bag adjustment, other). This turns embedded domain experts into a labeling workforce on real production distribution — the single highest-leverage design decision in the loop. Secondary weak signal: cross-reference with EAS gate alarms and, where available, POS/inventory shrink data, as noisy auxiliary labels (never used alone to trigger retraining).

**Active learning.** Every event (not just alerts) logs its full feature trace. The human-review queue is prioritized by: (1) ensemble disagreement between the skeleton and appearance branches, (2) boundary confidence (fused score near 0.4–0.6), (3) novelty/outlier detection via embedding similarity search (pgvector or Qdrant), and (4) stratified low-rate sampling of confident negatives, to catch silent model failures rather than only reviewing what the model already flagged.

**Retraining pipeline.** Scheduled (e.g., weekly) or threshold-triggered on N new confirmed labels: pull labeled data → merge with the existing training set with class-rebalancing → retrain/fine-tune per stage (the pose model rarely changes; the action-recognition branches and fusion meta-model retrain most often) → evaluate against a **frozen golden evaluation set** — curated, double-annotated, and *never* influenced by the feedback loop — plus per-store validation slices.

**Model versioning.** MLflow (or W&B Artifacts) tracks model version, metrics, and lineage back to a specific DVC/lakeFS-versioned data snapshot. Each pipeline stage versions independently (`pose-vX`, `action-vY`, `fusion-vZ`) since they update on different cadences.

**Safe promotion — the loop's most important guardrail.**
1. *Shadow mode*: a new model version runs in parallel on live edge streams, logs predictions, never triggers alerts, and is compared against the production model and confirmed ground truth over a fixed window.
2. *Canary*: enabled for alerting on a small slice of stores/cameras (~5%), monitored for precision/recall/false-positive-rate deltas with automatic rollback triggers.
3. *Staged rollout*: 25% → 100%, gated at each step by the golden-set metric plus live canary metrics. **A retrained model must beat baseline on the frozen golden set, not merely fit the live feedback distribution** — the primary defense against the loop reward-hacking itself.

**Guardrails against feedback poisoning / bias drift.** Only explicitly human-confirmed labels enter the retraining set (weak signals are down-weighted separately, never auto-promoted). Per-tenant fine-tuning happens via isolated adapters, not full base-model updates, so one store's biased or low-quality feedback (e.g., staff rubber-stamping "false alarm" to avoid confrontation) can't corrupt the shared global model. Rate/diversity caps apply per store/camera on any single retraining batch. Periodic bias audits segment FP/TP rates by store, region, and (carefully, given no facial data exists) proxy attributes like clothing style — this is the technical backbone of the bias-audit program that §1 and §5 position as a market differentiator. Random double-review of a sample of "confirmed" labels by a second/senior reviewer catches labeling drift over time, with full data lineage (DVC/lakeFS) so a bad label batch can be identified and rolled back.

### 4.3 Edge vs. Cloud Deployment — Recommendation: Edge-Primary Hybrid

**Recommendation.** Run the real-time detection pipeline (Stages A–F) on-prem at the edge, per store; reserve the cloud for the heavier appearance-model second opinion, all storage/dashboard/alerting backend, and the entire MLOps/retraining loop.

**Justification:**
- **Bandwidth**: a single 1080p RTSP stream runs ~2–4 Mbps; a mid-size store with 16–32 cameras streaming continuously to the cloud is 32–128+ Mbps sustained — often exceeding typical retail-site business internet uplinks, and expensive at fleet scale. Edge inference means only compact telemetry (a few KB/s/camera) and short flagged clips leave the store.
- **Latency**: actionable real-time alerting needs staff to intervene within seconds. WAN round-trips plus shared cloud GPU queueing across a fleet make that hard to guarantee; on-prem inference gives sub-200ms local latency independent of internet conditions.
- **Privacy/legal**: minimizing raw video leaving the premises is a real GDPR data-minimization advantage, and directly answers the exact concern that produced Veesion's CNIL setback (§2.3, §5) — sending pose-derived features instead of pixels for the vast majority of traffic is a literal instantiation of privacy-by-design, with only flagged/reviewed events ever leaving as short, face-blurred clips.
- **Reliability**: retail-site internet is often flaky; edge autonomy keeps detection running through an outage and queues events for sync when connectivity returns.

**Offline tolerance is a Phase 1 requirement, not a later-phase hardening task.** The stores most likely to run legacy camera systems are also the stores most likely to have weak or unreliable networking, so the two problems arrive together. From the MVP onward the edge box must: keep detecting with zero connectivity, persist the ring buffer and event/telemetry queue locally across an outage, batch-sync on reconnect, and optionally take a cellular-failover module (4G/LTE USB or M.2 modem) for sites whose primary uplink can't be trusted. This was originally scoped as a Phase 3–4 concern and has been deliberately pulled forward (§4.7).

**Edge hardware.**
- *Primary/standard tier*: **NVIDIA Jetson Orin family** (Orin Nano/NX for small-to-mid camera counts, AGX Orin for larger stores) — mature TensorRT toolchain, strong multi-stream RTSP decode (NVDEC), and the same class of hardware most production CV/retail-analytics vendors already build on.
- *Budget tier*: **Hailo-8/Hailo-8L** M.2 accelerator paired with a cheap x86 mini-PC or Raspberry Pi 5 host — excellent $/TOPS and power efficiency, a good fit for small stores and a lever for a lower-cost SMB pricing tier (§6).
- *Google Coral*: mentioned as an option but not the roadmap's foundation — INT8-only, narrower op support, and inconsistent long-term support commitment from Google.

**What runs where:**

| Stage | Location |
|---|---|
| RTSP ingest/decode, person detect+track | Edge |
| Pose estimation | Edge |
| Skeleton action recognition | Edge |
| Object/context detection | Edge |
| Rule engine + primary fusion score | Edge |
| Rolling video ring buffer (60–90s/camera) | Edge |
| Alert publish + telemetry | Edge → Cloud (MQTT, offline-resilient queue) |
| Appearance-model "second opinion" | Cloud (only on flagged/borderline clips) |
| Optional cloud vision API (Rekognition/Video Intelligence) | Cloud (tertiary signal, flagged clips only — cost-bounded) |
| Alert routing, dashboard backend, storage | Cloud |
| Labeling tool, retraining pipeline, model registry | Cloud |
| Fleet OTA model push | Cloud → Edge |

### 4.3a Legacy Camera Ingestion — the Brownfield Reality

The original draft of this plan silently assumed every store exposes clean RTSP/ONVIF streams. Real retail doesn't. **[Sourced]** Analog CCTV still holds an estimated **30–37% of the installed base** industry-wide as of 2025 (market-report estimates, directional not survey-grade), concentrated in exactly the older/independent stores this plan targets. Field reality breaks into four integration tiers:

| Tier | What's actually installed | How we connect | v1 support |
|---|---|---|---|
| **(a) Modern IP** | IP cameras/NVR with ONVIF/RTSP | ONVIF WS-Discovery, plug-and-play | ✅ Yes |
| **(b) Budget/OEM IP** | White-label NVRs built on Hikvision/Dahua/Uniview chipsets (resold under dozens of brand names), often no advertised ONVIF compliance | **Vendor-URL-pattern fallback library** — documented per-channel RTSP templates (Hikvision `rtsp://…/Streaming/Channels/101`, Dahua `rtsp://…/cam/realmonitor?channel=1&subtype=0`, Uniview `rtsp://…/unicast/c1/s0/live`) tried against detected devices when ONVIF discovery fails | ✅ Yes — software only, no new hardware |
| **(c) Pure analog** | CVBS/BNC cameras + analog DVR, **no digital output at all** | Requires a physical analog-to-IP encoder ($70–400+/channel **[Sourced, directional]**) and — because most analog DVRs expose only a single cycling/quad "spot monitor" output, not simultaneous per-channel access **[Sourced]** — a coax tap near each camera via a powered distribution amplifier. Materially invasive install. | ❌ **Not in v1.** Referred to the install-partner's own encoder/bridge offering as a prerequisite upgrade; revisit as a bundled resell only with real pilot demand data. |
| **(d) HD-analog (TVI/CVI/AHD)** | Coax transport but 1080p–4K resolution, usually recorded on a hybrid DVR/XVR | If the hybrid recorder has a network port exposing RTSP (most do), treat as tier (b). Transport medium doesn't matter once resolution and a network path both clear the bar. | ✅ Yes, via the recorder's RTSP |

**Connection flow at install time**: (1) ONVIF WS-Discovery scan of the store LAN → (2) on failure, port-554 probe + vendor-URL-pattern library against detected devices → (3) on failure, site is classified tier (c) and routed to the partner-upgrade path. This is a well-trodden approach — open-source camera-URL databases (iSpyConnect/Agent DVR's crowd-sourced list) and ONVIF discovery libraries already prove it out **[Sourced]** — so the adapter is an engineering task, not a research risk.

**Why exclude tier (c) from v1**: Veesion's own public positioning states RTSP support as its core requirement and recommends IP over analog **[Sourced, needs re-verification — marketing page snippet only]**, implying the incumbent also pushes bridging cost outward. Owning coax-splicing work in v1 would add per-channel hardware COGS, field labor, and liability for physically modifying a store's existing security wiring — for the segment with the lowest willingness to pay. The partner-referral path keeps those stores in the funnel (as camera-upgrade prospects, §3.3) without loading the v1 product with hardware complexity.

### 4.3b Minimum Camera Spec — a Hard Floor, Not a Suggestion

**Policy: HD-analog/1080p-equivalent or better is a hard sales prerequisite.** Sites below it default into the camera-replacement upsell path (§3.3), never a silently-degraded accuracy SLA.

**Why hard, not soft [Sourced]:** legacy standard-def analog formats — CIF (352×288, ~0.1MP), D1 (720×576, ~0.4MP), 960H (976×582, ~0.6MP) — sit in a resolution regime where published action-recognition research reports models "degrade drastically," and low-resolution action recognition remains an open research problem, not something a better model release fixes. Concealment detection is a *small-motion* gesture task: at 0.1–0.6MP, the hands-into-bag signal can be a handful of pixels. Running detection there means shipping low-confidence alerts, which is exactly the wrongful-accusation liability surface §5 and §10 exist to shrink. The practical insight from the research: **resolution tier matters more to model accuracy than IP-vs-analog transport does** — which is why tier (d) HD-analog passes and tier (c)-resolution feeds don't.

### 4.4 Full Technical Stack

- **Model training**: Python + PyTorch. OpenMMLab (MMPose for RTMPose, MMAction2 for PoseC3D/action models, MMDetection) as the base for pose/action models; Ultralytics YOLOv8/v11 for detection; HuggingFace `transformers`/`timm` for VideoMAE-style backbones.
- **Edge inference**: ONNX as the universal export format → TensorRT engine builds for Jetson; Hailo Dataflow Compiler → HEF for the Hailo-8 tier; ONNX Runtime/OpenVINO for x86 host-side processing. NVIDIA DeepStream SDK (GStreamer-based) for multi-stream RTSP ingest/decode/orchestration on Jetson.
- **Backend services**: Go for high-throughput ingestion/alert-routing (MQTT consumers, telemetry ingestion); Python (FastAPI) for ML-adjacent services (retraining orchestration, labeling backend). Docker + Kubernetes (EKS/GKE) for cloud orchestration.
- **Real-time messaging**: MQTT (EMQX or AWS IoT Core) for edge↔cloud telemetry/alerts (fits distributed, intermittently-connected edge devices well). Kafka (or Kinesis) as the durable cloud event backbone, with stream processing (Flink/ksqlDB) fanning out to notification/storage/analytics. FCM/APNs for LP-staff mobile push; WebSocket (Redis pub/sub-backed) for live dashboard updates.
- **Databases**: PostgreSQL + TimescaleDB as primary store (alerts, stores, cameras, users, feedback labels, model registry metadata, time-series telemetry). Redis for caching/sessions/pub-sub. pgvector (or Qdrant) for active-learning novelty search.
- **Video/object storage**: S3/GCS for flagged clips and training data, with lifecycle policies auto-purging raw clips after a defined retention window (§5) and retaining only labeled/derived features long-term. CloudFront for dashboard clip playback (HLS via video.js/hls.js).
- **Frontend**: React + TypeScript dashboard (shadcn/ui or Mantine, TanStack Query, WebSocket live feed, video.js/hls.js). LP-staff mobile app in React Native, sharing the web team's TS/React skillset.
- **Infra**: AWS as primary recommendation (broadest IoT + ML tooling in one place — IoT Core, S3, EKS, Kinesis, optional SageMaker); GCP as a viable alternative. Terraform for IaC. **balenaCloud** recommended over AWS IoT Greengrass for edge fleet management — purpose-built for fleets of Linux boxes in remote physical locations needing OTA container/model updates, materially simpler to operate for a small team.
- **MLOps**: MLflow for experiment tracking + model registry; DVC or lakeFS for dataset versioning; Label Studio (self-hosted, open-source, supports video + keypoint annotation) for labeling; Airflow or Prefect for retraining pipeline orchestration; Weights & Biases as an optional richer experiment-viz layer.

### 4.5 Data Strategy

**Bootstrapping from zero.** Public datasets: **UCF-Crime** (real surveillance footage including a shoplifting category), **DCSASS** (shoplifting-focused subset), Kinetics/UCF101 (general action-recognition pretraining), **NTU RGB+D** (skeleton-action pretraining — pretrain ST-GCN/PoseC3D here before domain fine-tuning), COCO keypoints (already baked into pretrained RTMPose/MediaPipe checkpoints).

**Synthetic data generation.** Game-engine-driven synthetic humans (motion-capture-driven avatars performing scripted concealment/bag-stuffing/swap motions) with domain randomization (camera angle, height, lighting, clothing, store layout) to cheaply cover rare gestures. Especially valuable for the skeleton branch, since skeleton data transfers from synthetic to real far better than raw pixels do.

**Staged/simulated theft filming.** Hire actors (or use willing employees) to film staged theft *and* normal-shopping behavior across many angles/lighting/store setups. Deliberately over-invest in **hard negatives** — innocent bag reach, trying on clothes, employee restocking, phone-checking gestures that superficially resemble concealment — since these are usually under-collected and are exactly what drives false-positive rate down.

**Pilot retailer partnerships.** Once a pilot store is landed, anonymized production footage (under contractual data-use rights) becomes the highest-value data source — real layout, real camera quality, real customer behavior distribution — and is where the active-learning loop starts compounding. The face-blur/anonymization pipeline must be built *before* any raw clip is contractually allowed to leave the store, and skeleton-derived features are preferred over raw video wherever the model doesn't need pixels.

**Labeling workflow.** Label Studio for video clip labeling with a structured taxonomy (concealment-shelf, concealment-fitting-room-adjacent, bag-stuffing, item-swap/price-tag-switch, cart-stuffing, normal-shopping, employee-restocking, ambiguous) plus temporal segment boundaries and periodic pose-QA spot checks. Double-annotation + adjudication for the golden evaluation set; single-pass, active-learning-prioritized review for the larger production feedback pool. Track inter-annotator agreement (Cohen's kappa) over time as a label-quality health metric.

### 4.6 System Architecture

```
┌─────────────────────────────── STORE PREMISES ───────────────────────────────┐
│                                                                                 │
│   [Existing CCTV Cameras / NVR] ──RTSP──▶ [Edge Box: Jetson Orin / Hailo-8]    │
│    (ONVIF discovery → vendor-URL-      │                                       │
│     pattern fallback, §4.3a)           ▼                                       │
│                              DeepStream ingest/decode                          │
│                                        │                                       │
│                    ┌───────────────────┼────────────────────┐                 │
│                    ▼                   ▼                    ▼                 │
│         Person Detect+Track    Pose Estimation      Object/Context Detect     │
│           (YOLO+ByteTrack)      (RTMPose/MediaPipe)     (YOLO fine-tune)      │
│                    │                   │                    │                 │
│                    └────────► Skeleton Action Model ◀────────┘                │
│                                (ST-GCN/PoseC3D)                                │
│                                        │                                       │
│                              Rule Engine + Fusion                              │
│                            (zones, thresholds, meta-model)                     │
│                                        │                                       │
│                         ┌──────────────┴───────────────┐                      │
│                         ▼                               ▼                     │
│                 Low/med confidence                High confidence             │
│                 → log features only          → publish alert (MQTT)           │
│                                               → extract clip from ring buffer  │
│                                                          │                     │
└──────────────────────────────────────────────────────────┼───────────────────┘
                                                              │ MQTT (alert + telemetry)
                                                              │ clips (only flagged) → S3
                                                              ▼
┌────────────────────────────────── CLOUD ──────────────────────────────────────┐
│                                                                                 │
│   MQTT Broker (IoT Core/EMQX) ──▶ Kafka event backbone ──▶ Stream Processing   │
│                                                                    │           │
│         ┌──────────────────────────────────────────────┬─────────┘           │
│         ▼                                               ▼                     │
│  Appearance-model 2nd opinion                   Alert Routing Service         │
│  (MoViNet/VideoMAE) on flagged clip                       │                   │
│  + optional cloud vision API                              ▼                   │
│         │                                        Push (FCM/APNs) + WebSocket  │
│         └──────────────────────────────────────────────┐  to Dashboard/App    │
│                                                           ▼                     │
│                                              [LP Staff Dashboard / Mobile App] │
│                                                           │                     │
│                                                 Confirm / False Alarm / Unsure │
│                                                           │                     │
│                                                           ▼                     │
│                                          Feedback Store (Postgres/Timescale)   │
│                                                           │                     │
│                                            Active Learning Selector            │
│                                     (disagreement, boundary-conf, novelty)     │
│                                                           │                     │
│                                                           ▼                     │
│                                          Human Review Queue (Label Studio)     │
│                                                           │                     │
│                                                           ▼                     │
│                              Retraining Pipeline (Airflow/Prefect + MLflow)    │
│                              Golden-set eval gate → Shadow → Canary → Rollout  │
│                                                           │                     │
│                                                           ▼                     │
│                              Model Registry (MLflow) → OTA push (balenaCloud)  │
└───────────────────────────────────────────────────────────┼──────────────────┘
                                                               │
                                                               ▼
                                          back to [Edge Box] (new model version)
```

### 4.7 Phased Technical Build Roadmap

- **Phase 0 — Data collection & baseline model.** Bootstrap from public datasets (UCF-Crime, DCSASS, NTU RGB+D, Kinetics/COCO) plus staged filming. Build a baseline skeleton-only classifier (pose estimator + ST-GCN), offline evaluation only. Establish the **frozen golden evaluation set now**, before any production feedback exists, so it is never contaminated by the loop.
- **Phase 1 — Single-camera MVP, human review only, no self-training.** Stand up the edge pipeline on one Jetson dev kit for one camera: person detect+track, pose, single skeleton-based action model, rule engine, basic fusion. Alerting can start as simple as a webhook/Slack notification or a minimal dashboard. Add the confirm/reject UI. Labels accumulate but nothing retrains automatically yet. **Two items pulled forward into this phase from later** (per the legacy-hardware audit): the ONVIF-discovery + vendor-URL-pattern ingestion adapter (§4.3a) — validated against at least one real budget/OEM NVR, not just a lab IP camera — and offline-tolerant edge operation (§4.3) — validated by physically pulling the store uplink and confirming detection continues and events batch-sync on reconnect. Goal: validate real-time latency, real-world false-positive tolerance, *and* brownfield connectivity in an actual store.
- **Phase 2 — Active learning + retraining pipeline.** Build the data lake (S3 + DVC/lakeFS) and Label Studio integration, implement uncertainty-sampling logic, stand up the scheduled retraining pipeline (MLflow + Airflow/Prefect), and build shadow deployment + golden-set-gated promotion. Still single-model, but the full continuous-learning loop closes end-to-end.
- **Phase 3 — Multi-model ensemble + edge optimization.** Add the appearance-based branch and object/context detector, build the real fusion meta-model, optionally wire in a cloud vision API as a tertiary signal on flagged clips. Push TensorRT/DeepStream optimization for higher per-box camera throughput. Build canary-rollout infrastructure that works across a multi-store fleet.
- **Phase 4 — Scale / multi-tenant infra.** Multi-store fleet management via balenaCloud OTA, per-tenant model isolation, multi-region cloud infra, dashboard multi-tenant RBAC, fleet health observability (Prometheus/Grafana), a formalized bias/fairness audit pipeline, and broad INT8 quantization/distillation for cost optimization at scale.

**First files/directories to create** when this moves from planning to implementation: `docs/architecture/detection-pipeline.md` (canonical spec of §4.1), `docs/architecture/continuous-learning.md` (the §4.2 golden-set-gating policy — this document is the single most likely thing to prevent a costly production mistake, so it deserves to be a first-class, reviewed spec), `infra/terraform/` (AWS stack IaC), `edge/deepstream-pipeline/` (Jetson pipeline config), `mlops/mlflow-registry/` and `mlops/pipelines/` (registry + retraining DAGs).

---

## 5. Legal, Privacy & Compliance Strategy

This is a first-class workstream, not an appendix — because Veesion's own CNIL/Conseil d'État precedent (§2.3) proves the naive version of this business ("we don't use facial recognition, so we're fine") does not survive regulatory contact.

- **GDPR (EU) [Sourced].** French regulators and the Conseil d'État have treated gesture/movement analysis as biometric-adjacent processing under Article 9 even without facial recognition. A **mandatory DPIA (Data Protection Impact Assessment) and documented legal basis are required before any EU pilot**, not after. Budget for privacy counsel early — this is now a proven, not hypothetical, regulatory risk.
- **Illinois BIPA [Sourced].** A gesture-only, non-identifying system has a stronger argument for falling outside BIPA's "biometric identifier" definition than facial-recognition competitors — Target (motion to dismiss denied, Nov 2024) and Home Depot (sued Aug 2025) are both currently defending BIPA suits over in-store facial recognition. This is an argument to get formally legally reviewed, not an assumption to build the company on. Note also that a 2024 BIPA amendment capped per-person damages at one violation (max $5,000/person) rather than per-scan, meaningfully reducing class-action exposure industry-wide — BIPA filings dropped from 427 cases in 2024 to 150 in 2025 as a result.
- **EU AI Act [Sourced].** Article 5's real-time biometric identification ban is scoped to law-enforcement use, so commercial retail use is likely not directly prohibited. However, "biometric-based" categorization is defined broadly enough (including behavioral signals) that **Annex III high-risk classification** — triggering conformity assessment, technical documentation, and post-market monitoring duties — is a live, unsettled risk for gesture-based systems. Monitor EU Commission guidance actively; this is explicitly an open interpretive question, not a settled safe harbor. Penalties for Article 5 violations run up to €35M or 7% of global annual turnover.
- **CCPA/CPRA (California) [Sourced, behavioral summary — verify exact statutory text with counsel].** California's definition of biometric information explicitly includes behavioral characteristics such as gait patterns, and CPRA classes biometric information processed for unique identification as "sensitive personal information," triggering added consumer rights (limit-use, access, deletion, portability). Video-derived behavioral data captured without consumer consent is not "publicly available" and remains covered personal information.
- **FTC precedent — Rite Aid [Sourced, Needs re-verification — primary FTC order not fetched; substance corroborated by multiple reputable secondary sources].** The FTC's December 2023 settlement with Rite Aid — its first algorithmic-discrimination enforcement action — banned Rite Aid from facial-recognition surveillance for 5 years and ordered destruction of all collected photos/videos plus instructions to third parties to delete derived models. The FTC's underlying allegation: Rite Aid deployed for nearly a decade without testing for accuracy or bias, and Black and Asian customers were more likely to be misidentified, leading to wrongful shoplifting accusations. **Even for a non-facial-recognition product, the lesson is direct**: pre-deployment bias testing and documented accuracy validation are a regulatory necessity, not a nice-to-have — the FTC's theory of harm was about undisclosed, untested algorithmic decision-making causing consumer harm, a theory that is not inherently limited to facial recognition.
- **Bias research gap [Sourced].** No NIST-equivalent, peer-reviewed bias study specifically testing gesture/movement-based shoplifting-prediction algorithms (as distinct from facial recognition) was found. This is both a risk (untested territory that could surface in future journalism the way facial-recognition bias did, per the NIST FRVT Part 3 findings on facial recognition) and, per §1/§2.2, a genuine differentiation opportunity: commit publicly to bias testing/audits that no competitor currently performs.

**Company compliance commitments built into this plan:**
- Mandatory DPIA before every new jurisdiction's pilot, not retroactively.
- Scheduled third-party bias audits, published — directly filling the market gap identified above, and directly hedging the FTC/Rite-Aid theory of enforcement risk.
- Strict clip retention limits with automated purge (technical mechanism in §4.4's S3 lifecycle policies).
- Visible in-store signage disclosing AI-assisted monitoring.
- A customer-facing redress process for anyone wrongly flagged.
- Explicit "AI-assisted, human-reviewed" marketing language — directly avoiding the "AI-washing" criticism leveled at Veesion (§2.3).
- No cross-retailer identity sharing or blacklisting — differentiates from Facewatch's model and its associated controversy.
- E&O and general liability insurance sized specifically for wrongful-accusation exposure, informed by the Rite Aid and facial-recognition wrongful-arrest cases in §10.
- **Installation liability split**: physical installation is partner-led (§7, §8), so primary liability for physical work — mounting edge boxes, and any modification of a store's existing camera wiring — is contractually assigned to the certified partner installer in the install agreement. Our E&O/liability coverage is scoped to the software/detection/data side. This split only holds if partners are actually vetted, so a **partner certification and insurance-verification program** (license check, COI on file, install-quality audit) is a precondition for any partner performing installs — otherwise an uninsured sub-installer's mistake lands on us anyway.

---

## 6. Business Model & Pricing

**[Illustrative — Veesion's actual pricing is not publicly disclosed, and no figures below should be treated as sourced from a competitor's real pricing.]**

- **Core model**: per-camera, per-month SaaS subscription — the standard model in this category based on the general shape of competitor go-to-market (though exact competitor numbers are undisclosed).
- **Tiering**:
  - *SMB tier*: Hailo-8-based edge hardware, lower per-camera price, targeted at single/few-location convenience and pharmacy operators.
  - *Enterprise tier*: Jetson Orin-based edge hardware, volume pricing, targeted at regional/national grocery and big-box chains.
- **One-time install/hardware fee** covering edge box provisioning and camera integration.
- **Add-on modules** (later phases, per §9): self-checkout fraud detection, and a longer-term Auror-style organized-retail-crime case-sharing network as a potential partnership or acquisition rather than a build-from-scratch effort (§2.2 notes Auror as complementary, not competing).
- **Motion**: land-and-expand — single-store pilot → regional chain → franchise/national rollout, mirroring the go-to-market sequencing in §7 and the funding-stage mapping in §9 and §11.
- **Hardware COGS scope** (a deliberate boundary, per §4.3a): our own hardware COGS are limited to the edge box (Jetson/Hailo). Camera replacements and any analog-to-IP encoder hardware a site needs are quoted and fulfilled by the install partner as a **pass-through line item** (referral/revenue-share terms TBD), keeping the margin structure close to SaaS rather than hardware reseller — even though every deployment involves physical installation.

---

## 7. Go-to-Market Strategy

- **Vertical-first focus**: grocery/convenience and pharmacy first, per the shrink-exposure ranking in §3.1.
- **Channel partnerships**: CCTV/NVR installers (natural distribution — they already have the customer relationship and the hardware access), POS vendors (integration point for shrink/ROI reporting), and franchise associations (single decision-maker unlocking many locations at once).
- **The installer relationship is a delivery network, not just a lead channel.** Certified partners run the site compatibility survey (§3.3), perform every physical install, fulfill camera-replacement upsells and tier-(c) analog-bridging upgrades (§4.3a), and carry primary installation liability (§5). Partners are trained and certified on the survey checklist and hardware requirements before their first install. This makes partner recruitment/certification a launch-critical GTM workstream — the product literally cannot deploy without it.
- **Pilot-driven sales motion**: every new logo starts as a single-store or small-cluster pilot with a published shrink-reduction ROI calculator, feeding directly into the case-study library needed for the next sale.
- **Timing argument [built on Sourced facts from §2.3]**: Veesion only opened its first US office in 2025 and is still building out that market (targeting ~50 US hires, per its own Series B announcement). That is a real, dated window for a US-first or underserved-vertical entrant to establish reference customers before the incumbent's US presence matures.

---

## 8. Team & Roles Needed

**Founding technical team:**
- CV/ML lead (owns the detection pipeline, §4.1–4.2)
- Embedded/edge engineer (owns the Jetson/DeepStream deployment, §4.3)
- Backend/infra engineer (owns the cloud stack, §4.4)
- Founding full-stack engineer (owns the dashboard/LP-staff app, §3.2)

**Deliberately absent: in-house field-installation headcount.** Installation is partner-led (§5, §7), so the company never builds a truck-roll team. The corresponding hire is instead a **channel/partner-operations role** — owning installer recruitment, certification, insurance verification, and install-quality assurance — needed in Phase 1–2, earlier than a typical channel hire, because the partner network is the delivery arm from the first pilot onward.

**Hiring roadmap**, tied to the phases in §4.7/§9:
- *Phase 1–2*: add a data-labeling/annotation lead (owns the Label Studio workflow, §4.5), privacy/compliance counsel (owns the DPIA process, §5), and the channel/partner-operations role above — all three need to be in place *before* the first real pilot, not after.
- *Phase 3*: add an MLOps engineer (owns the retraining pipeline's shadow/canary/rollout infrastructure, §4.2) and the first sales hire (owns the channel-partnership motion, §7).
- *Phase 4*: build out customer success (owns pilot-to-scale account expansion) and a dedicated bias-audit/fairness function, formalizing the differentiator from §5 into a standing team responsibility rather than a project.

---

## 9. Roadmap & Milestones

Mapped directly to the technical phases in §4.7:

- **Pre-seed / build** *(Phase 0–1)*: baseline skeleton model built and evaluated against the frozen golden set; single-store pilot live with human-review-only alerting.
- **Seed** *(Phase 2)*: active-learning loop live end-to-end; 3–5 paying pilot stores; first DPIA and legal review complete for the pilot jurisdiction(s).
- **Series A** *(Phase 3)*: multi-model ensemble in production; regional chain rollout underway; bias-audit program launched publicly as a market differentiator (§1, §5).
- **Growth** *(Phase 4)*: multi-tenant fleet scale; multi-region compliance program covering the jurisdictions in §5; franchise/national accounts.

---

## 10. Risks & Mitigations

| Risk | Mitigation (cross-referenced) |
|---|---|
| False positive/negative rates erode customer trust | Ensemble detection + rule-engine layer (§4.1); temporal hysteresis and confidence tiering |
| GDPR/biometric-classification risk — proven, not hypothetical, per Veesion's own CNIL ruling (§2.3) | Mandatory DPIA before every jurisdiction's pilot; edge-primary architecture minimizing raw data transmission (§4.3, §5) |
| Bias/discrimination and wrongful-accusation liability (Rite Aid precedent, §5) | Published third-party bias audits; golden-set-gated model promotion (§4.2); redress process for wrongly flagged customers |
| Data breach exposure on stored clips | Strict retention limits with automated purge; face-blur pipeline before any clip leaves a store (§4.5, §5) |
| Competing against a well-funded incumbent (a €53M 2025 financing package, §2.3) and much-larger-scale Everseen | Vertical-first focus and US-timing window (§7); differentiation on published bias audits and transparency (§1) that neither currently offers |
| Edge hardware supply chain/cost | Two-tier hardware strategy (Jetson enterprise / Hailo-8 budget, §4.3) to hedge cost and availability |
| Reputational risk from undisclosed human review ("AI-washing", per the contested StreetPress allegation against Veesion, §2.3) | Explicit "AI-assisted, human-reviewed" marketing from day one (§5) — treat human review as a disclosed feature, not a hidden dependency |
| Employee misuse of alerts (profiling risk) | Rule-engine exclusion logic scoped to uniform/badge only, never identity (§3.4); audit logging on alert dispositions |
| Legacy-CCTV compatibility gap shrinks the addressable market or breaks the "existing cameras" promise | ONVIF + vendor-URL-pattern adapter covers tiers (a)/(b)/(d) in software (§4.3a); tier (c) analog and sub-HD sites stay in the funnel via the partner upgrade/upsell path (§3.3) rather than being declined outright |
| Dependence on install partners for every deployment (quality, speed, coverage) | Partner certification + insurance-verification program before first install (§5); channel/partner-ops hire in Phase 1–2 (§8); install-quality audits as a standing QA function |
| Unreliable store internet interrupts alerting and delays event sync — most likely at exactly the legacy-hardware sites this plan targets | Offline-tolerant edge operation as a Phase 1 requirement (§4.3, §4.7): detection continues with zero connectivity, ring buffer and event queue persist locally, batch sync on reconnect, optional cellular failover for untrusted uplinks |

---

## 11. Financials & Funding Needs

**[Illustrative — no sourced figures exist for a hypothetical company; treat all ranges as planning placeholders to be replaced with real modeling before fundraising.]**

- **Seed round**: sized to reach Phase 2 — a working self-training loop, a handful of paying pilot stores, and the first completed legal/compliance pass (DPIA + jurisdictional review) from §5.
- **Series A**: sized to reach Phase 3–4 — the multi-model ensemble in production, regional-chain scale, and the public bias-audit program operating as a standing differentiator rather than a launch-day announcement.

---

## 12. Success Metrics / KPIs

- **Detection precision/recall and false-positive rate**, measured against the **frozen golden set** (§4.2) — deliberately not measured against live feedback alone, to avoid the loop grading its own homework.
- **Time-to-alert latency**, validated against the sub-200ms edge-local target from §4.3.
- **Per-store shrink-reduction %**, the core ROI number for the dashboard in §3.2 and the sales motion in §7.
- **Alert-confirmation rate by LP staff**, both a product-quality signal and a direct active-learning input (§4.2).
- **Model-drift/bias-audit pass rate**, the operational metric behind the compliance commitments in §5.
- **Customer retention/expansion and ARR**, tracked against the land-and-expand motion in §6.

---

## Sources Requiring Independent Re-Verification Before External Use

Flagged throughout this document, consolidated here for convenience:
- NRF's exact shrink dollar/percentage figures — both the 2023 National Retail Security Survey ($112.1B / 1.6% of sales, FY2022) and the 2025 "Impact of Theft & Violence" report (nrf.com blocked direct fetch during research; all figures via secondary reporting).
- Veesion's funding totals (the press-reported "€53M" covers only the May 2025 package of €38M equity + €15M non-dilutive and excludes the 2022 €10M Series A; no reconciled total-funding figure was found — see §2.3).
- The CCPA/CPRA statutory definitions of biometric information in §5 (behavioral summary from secondary guides; verify exact statutory text with privacy counsel).
- The FTC's exact order language in the Rite Aid settlement (ftc.gov blocked; substance corroborated by multiple reputable secondary sources — Forbes, NBC News, Cooley, WilmerHale).
- Veesion's precise current customer/country counts (conflicting marketing figures; no independent audit found).
- The StreetPress Madagascar story (only accessible via a secondary summary from La Quadrature du Net, not the original article; treat the underlying risk category as real, the specific allegation as unverified).
- The analog-CCTV installed-base share (30–37%) and per-channel encoder pricing in §4.3a (market-report and vendor-blog estimates, directional not survey-grade; the deepest industry data sits behind IPVM's paywall).
- Veesion's own analog-vs-IP support posture and RTSP requirement (§4.3a; taken from a marketing-page search snippet — the full page blocked direct fetch).
