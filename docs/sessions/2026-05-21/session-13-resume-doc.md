# Session 13 Resume Doc — 2026-05-21

## Production State
- **Cloud Run service:** `astrobot-ds-v4` in `nc-ai-chatbot` (us-central1)
- **Active revision:** `astrobot-ds-v4-00047-mam` (tag `item5`) — 100% traffic
- **Image:** `gcr.io/nc-ai-chatbot/astrobot-ds-v4:item5`
- **Production URL:** https://astrobot-ds-v4-2jfu4lrr2q-uc.a.run.app/dev-ui
- **Git:** branch `v3-dev`, last commit `33457c6`
- **USE_FIRESTORE_CONFIG=true** set on Cloud Run service

## Smoke Suite Status
- 7/8 passing, 1 xfail (Item 10)
- Run: `ASTROBOT_BASE_URL=https://astrobot-ds-v4-2jfu4lrr2q-uc.a.run.app pytest data_science/tests/test_e2e_smoke.py -v`

## Shipped This Session
| Item | Change | Status |
|------|--------|--------|
| Item 2 | USE_DISCOVERED_MODELS + model_name param | ✅ |
| Item 3 | FORECAST CHART INSTRUCTIONS block | ✅ |
| Item 4 | Firestore: saturation_agg fix | ✅ |
| Saturation routing | ROUTING IS HARD-LOCKED | ✅ |
| Venetian Firestore | kpi_column=transactions, duality=True | ✅ |
| WinnDixie Firestore | client_filter_value=TWDC, kpi_column=Conversions | ✅ |
| USE_FIRESTORE_CONFIG | Live on Cloud Run | ✅ |
| kpi_col dynamic | compute_saturation_curve + get_saturation_sql | ✅ |
| Hardcoded refs removed | All prompts + agent.py | ✅ |
| Walled garden | Hard block via types.Content | ✅ |
| train_arima routing | Strengthened prompt | ✅ |
| AdventHealth/Groundworks | Registered in Firestore | ✅ |
| WinnDixie table paths | Astrobot_WinnDixie → Astrobot_TWDC | ✅ |
| client_sync.py | Auto discovery via introspect_table | ✅ |
| Eventarc webhook | Real-time BQ → Firestore sync | ✅ |
| Cloud Scheduler | Nightly 2am UTC sync | ✅ |

## Registered Clients
| Client | kpi_column | has_duality | BQ Dataset |
|--------|------------|-------------|------------|
| NPI | Conversions | True | Astrobot_NPI |
| Venetian | transactions | True | Astrobot_Venetian |
| WinnDixie | Conversions | False | Astrobot_TWDC |
| AdventHealth | Conversions | True | Astrobot_AdventHealth |
| Groundworks | ViVs/Conversions | — | Astrobot_Groundworks |

## Pending Items
| # | Item | Est |
|---|------|-----|
| 1 | Fix orchestrator read-only mode | Unknown |
| 2 | Redeploy webhook with pandas | 10min |
| 3 | Delete test BQ tables | 5min |
| 4 | bq_introspector Fix A/B/C | ~2-3h |
| 5 | Item 1-tail: Steps narration | ~2-4h |
| 6 | Item 5: Phase D train-from-scratch | ~2-3h |
| 7 | Item 10: Audit {state.X} placeholders | ~2-4h |
| 8 | WinnDixie BQML path fix | ~30min |
| 9 | Analytics confidence metric | ~2h |

## Known Issues
1. {state.available_models_summary} never substitutes (Item 10)
2. Venetian saturation R² below 0.5 — data quality issue
3. WinnDixie BQML training fails — path constructs winndixie not wd
4. Orchestrator read-only mode — LLM hallucination, source unknown
5. propose_new_table test gate times out from Cloud Shell
