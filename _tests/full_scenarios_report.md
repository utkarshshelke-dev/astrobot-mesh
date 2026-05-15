# Comprehensive Test Scenarios & Agent Answers

This document lists all scenarios tested across the 94 test cases, showing the exact inputs (Questions) and outputs (Agent Answers).

| Category | Input (Question) | Agent Answer | Details | Result |
| :--- | :--- | :--- | :--- | :--- |
| Routing | [NPI] Which channel has the lowest CPA? | `Table: performance` | Confidence: low, Matches: ['cpa'] | **PASS** |
| Routing | [Venetian] Which channel has the lowest CPA? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Which channel has the lowest CPA? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Rank channels by efficiency | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [Venetian] Rank channels by efficiency | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Rank channels by efficiency | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] What's the organic efficiency for last 12 months? | `Table: performance` | Confidence: low, Matches: ['organic efficiency'] | **PASS** |
| Routing | [Venetian] What's the organic efficiency for last 12 months? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] What's the organic efficiency for last 12 months? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Does TV halo lift Paid Search conversions? | `Table: performance` | Confidence: low, Matches: ['tv halo'] | **PASS** |
| Routing | [Venetian] Does TV halo lift Paid Search conversions? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Does TV halo lift Paid Search conversions? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Which channel is most volatile? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [Venetian] Which channel is most volatile? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Which channel is most volatile? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Forecast next quarter conversions | `Table: performance` | Confidence: low, Matches: ['forecast'] | **PASS** |
| Routing | [Venetian] Forecast next quarter conversions | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Forecast next quarter conversions | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Are we pacing well this month? | `Table: pacing` | Confidence: low, Matches: ['pacing'] | **PASS** |
| Routing | [Venetian] Are we pacing well this month? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Are we pacing well this month? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] How much budget is remaining? | `Table: pacing` | Confidence: low, Matches: ['budget remaining'] | **PASS** |
| Routing | [Venetian] How much budget is remaining? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] How much budget is remaining? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Which flights are underpacing? | `Table: pacing` | Confidence: medium, Matches: ['pacing', 'underpacing'] | **PASS** |
| Routing | [Venetian] Which flights are underpacing? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Which flights are underpacing? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Will we hit budget for December? | `Table: pacing` | Confidence: low, Matches: ['will we hit budget'] | **PASS** |
| Routing | [Venetian] Will we hit budget for December? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Will we hit budget for December? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Show me geo budget breakdown | `Table: pacing` | Confidence: low, Matches: ['geo budget'] | **PASS** |
| Routing | [Venetian] Show me geo budget breakdown | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Show me geo budget breakdown | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [NPI] Show ViVs by month | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [Venetian] Show ViVs by month | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [WinnDixie] Show ViVs by month | `Table: performance` | Confidence: low, Matches: ['vivs'] | **PASS** |
| Routing | [NPI] OOH performance? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Routing | [Venetian] OOH performance? | `Table: performance` | Confidence: low, Matches: ['ooh performance'] | **PASS** |
| Routing | [WinnDixie] OOH performance? | `Table: performance` | Confidence: default, Matches: [] | **PASS** |
| Taxonomy | [NPI] Resolve term: 'direct' | `['Direct']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'direct' | `['Direct']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [WinnDixie] Resolve term: 'direct' | `['Direct']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [NPI] Resolve term: 'awareness' | `['Linear TV', 'CTV', 'OTT', 'Online Audio', 'Online Video', 'Paid Video', 'Video', 'OOH', 'Print']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'awareness' | `['OOH']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [WinnDixie] Resolve term: 'awareness' | `['OTT', 'CTV', 'Linear TV']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [NPI] Resolve term: 'organic' | `['Organic Search', 'Organic Social', 'Organic Video', 'Direct', 'Referral', 'Email']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'organic' | `['Direct', 'Organic Search']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [WinnDixie] Resolve term: 'organic' | `['Direct']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [NPI] Resolve term: 'paid' | `['Paid Social', 'Paid Search', 'Search', 'Cross-network', 'Demand Gen', 'Performance Max', 'Display', 'OTT', 'CTV', 'Linear TV', 'Online Video', 'Paid Video', 'Video', 'OOH', 'Print', 'Online Audio']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'paid' | `['OOH', 'Paid Search', 'Display']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [WinnDixie] Resolve term: 'paid' | `['OTT', 'CTV', 'Linear TV']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [NPI] Resolve term: 'direct response' | `['Search', 'Paid Search', 'Email', 'Shopping']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'direct response' | `['Paid Search']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [WinnDixie] Resolve term: 'direct response' | `SKIPPED/FAIL: Term 'direct response' resolves to taxonomy key 'direct_response', but it is empty for client 'WinnDixie', table 'performance'` | N/A | **INFO** |
| Taxonomy | [NPI] Resolve term: 'upper funnel' | `['Linear TV', 'CTV', 'OTT', 'Online Audio', 'Online Video', 'Paid Video', 'Video', 'OOH', 'Print']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'upper funnel' | `['OOH']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [WinnDixie] Resolve term: 'upper funnel' | `['OTT', 'CTV', 'Linear TV']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [NPI] Resolve term: 'lower funnel' | `['Search', 'Paid Search', 'Email', 'Shopping']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'lower funnel' | `['Paid Search']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [WinnDixie] Resolve term: 'lower funnel' | `SKIPPED/FAIL: Term 'lower funnel' resolves to taxonomy key 'direct_response', but it is empty for client 'WinnDixie', table 'performance'` | N/A | **INFO** |
| Taxonomy | [NPI] Resolve term: 'tv' | `['Linear TV', 'CTV', 'OTT']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'tv' | `SKIPPED/FAIL: Term 'tv' resolves to taxonomy key 'tv', but it is empty for client 'Venetian', table 'performance'` | N/A | **INFO** |
| Taxonomy | [WinnDixie] Resolve term: 'tv' | `['OTT', 'CTV', 'Linear TV']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [NPI] Resolve term: 'social' | `['Paid Social', 'Organic Social']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'social' | `SKIPPED/FAIL: Term 'social' resolves to taxonomy key 'social', but it is empty for client 'Venetian', table 'performance'` | N/A | **INFO** |
| Taxonomy | [WinnDixie] Resolve term: 'social' | `SKIPPED/FAIL: Term 'social' resolves to taxonomy key 'social', but it is empty for client 'WinnDixie', table 'performance'` | N/A | **INFO** |
| Taxonomy | [NPI] Resolve term: 'search' | `['Paid Search', 'Search', 'Organic Search']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'search' | `SKIPPED/FAIL: Term 'search' resolves to taxonomy key 'search', but it is empty for client 'Venetian', table 'performance'` | N/A | **INFO** |
| Taxonomy | [WinnDixie] Resolve term: 'search' | `SKIPPED/FAIL: Term 'search' resolves to taxonomy key 'search', but it is empty for client 'WinnDixie', table 'performance'` | N/A | **INFO** |
| Taxonomy | [NPI] Resolve term: 'television' | `['Linear TV', 'CTV', 'OTT']` | Mapped via channel_taxonomy | **PASS** |
| Taxonomy | [Venetian] Resolve term: 'television' | `SKIPPED/FAIL: Term 'television' resolves to taxonomy key 'tv', but it is empty for client 'Venetian', table 'performance'` | N/A | **INFO** |
| Taxonomy | [WinnDixie] Resolve term: 'television' | `['OTT', 'CTV', 'Linear TV']` | Mapped via channel_taxonomy | **PASS** |
| Metadata | [NPI] What is the KPI and Table Path? | `KPI: Conversions` | Path: nc-ai-chatbot.Astrobot_NPI.vw_astrobot_npi_nc360_dashboard | **PASS** |
| Metadata | [Venetian] What is the KPI and Table Path? | `KPI: KPI` | Path: nc-ai-chatbot.Astrobot_Venetian.sample_astrobot_venetian_nc360_dashboard | **PASS** |
| Metadata | [WinnDixie] What is the KPI and Table Path? | `KPI: KPI` | Path: nc-ai-chatbot.Astrobot_WinnDixie.sample_astrobot_wd_nc360_dashboard | **PASS** |
| SQL Logic | [NPI] Build Unified Channel CTE | `SQL String Generated` | Length: 367 chars | **PASS** |
| SQL Logic | [Venetian] Build Unified Channel CTE | `SQL String Generated` | Length: 7 chars | **PASS** |
| SQL Logic | [WinnDixie] Build Unified Channel CTE | `SQL String Generated` | Length: 99 chars | **PASS** |
