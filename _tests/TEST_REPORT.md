# Astrobot Deterministic Test Suite — Detailed Report

**Generated**: 2026-05-11T12:45:42
**Total tests**: 94
**Passed**: 94
**Failed**: 0

Each test below shows:
- **What it verifies** (docstring)
- **What it calls** (the function under test)
- **What it asserts** (the actual checks)
- **Result** (PASS or FAIL)

---

## File: `test_channel_resolver.py`

### TestChannelResolution
_These are the tests that prevent the bugs we saw in production:
- 'direct' becoming 'DEFAULT'
- 'awareness' getting only 2 of 9 channels
- 'organic' picking the wrong filter_

(21 tests)

#### Test 1: `test_direct_returns_Direct_not_DEFAULT` — ✅ PASS

**What it verifies**: REGRESSION: agent previously used 'DEFAULT' for direct conversions.

**Function under test**:
```python
resolve_channel_reference('NPI', 'direct')
```

**Assertions**:
```python
assert result == ['Direct']
assert 'DEFAULT' not in result
```

---

#### Test 2: `test_direct_case_insensitive` — ✅ PASS

**What it verifies**: direct case insensitive

**Function under test**:
```python
resolve_channel_reference('NPI', term)
```

**Assertions**:
```python
assert resolve_channel_reference('NPI', term) == ['Direct']
```

---

#### Test 3: `test_awareness_includes_all_tv_channels` — ✅ PASS

**What it verifies**: REGRESSION: agent only counted 2 of 9 awareness channels.

**Function under test**:
```python
resolve_channel_reference('NPI', 'awareness')
```

**Assertions**:
```python
assert 'Linear TV' in result
assert 'CTV' in result
assert 'OTT' in result
```

---

#### Test 4: `test_awareness_includes_video_and_audio` — ✅ PASS

**What it verifies**: awareness includes video and audio

**Function under test**:
```python
resolve_channel_reference('NPI', 'awareness')
```

**Assertions**:
```python
assert 'Online Audio' in result
assert 'Online Video' in result
assert 'Paid Video' in result
assert 'Video' in result
```

---

#### Test 5: `test_awareness_includes_offline` — ✅ PASS

**What it verifies**: awareness includes offline

**Function under test**:
```python
resolve_channel_reference('NPI', 'awareness')
```

**Assertions**:
```python
assert 'OOH' in result
assert 'Print' in result
```

---

#### Test 6: `test_awareness_has_at_least_seven_channels` — ✅ PASS

**What it verifies**: awareness has at least seven channels

**Function under test**:
```python
resolve_channel_reference('NPI', 'awareness')
```

**Assertions**:
```python
assert len(result) >= 7
```

---

#### Test 7: `test_organic_includes_organic_search_social_video` — ✅ PASS

**What it verifies**: organic includes organic search social video

**Function under test**:
```python
resolve_channel_reference('NPI', 'organic')
```

**Assertions**:
```python
assert 'Organic Search' in result
assert 'Organic Social' in result
assert 'Organic Video' in result
```

---

#### Test 8: `test_organic_includes_direct_and_referral` — ✅ PASS

**What it verifies**: organic includes direct and referral

**Function under test**:
```python
resolve_channel_reference('NPI', 'organic')
```

**Assertions**:
```python
assert 'Direct' in result
assert 'Referral' in result
assert 'Email' in result
```

---

#### Test 9: `test_organic_excludes_paid_channels` — ✅ PASS

**What it verifies**: organic excludes paid channels

**Function under test**:
```python
resolve_channel_reference('NPI', 'organic')
```

**Assertions**:
```python
assert 'Paid Social' not in result
assert 'Paid Search' not in result
assert 'Demand Gen' not in result
```

---

#### Test 10: `test_direct_response_includes_search_and_email` — ✅ PASS

**What it verifies**: direct response includes search and email

**Function under test**:
```python
resolve_channel_reference('NPI', 'direct response')
```

**Assertions**:
```python
assert 'Paid Search' in result
assert 'Search' in result
assert 'Email' in result
```

---

#### Test 11: `test_direct_response_excludes_tv` — ✅ PASS

**What it verifies**: direct response excludes tv

**Function under test**:
```python
resolve_channel_reference('NPI', 'direct response')
```

**Assertions**:
```python
assert 'Linear TV' not in result
assert 'CTV' not in result
assert 'OTT' not in result
```

---

#### Test 12: `test_upper_funnel_equals_awareness` — ✅ PASS

**What it verifies**: upper funnel equals awareness

**Function under test**:
```python
resolve_channel_reference('NPI', 'upper funnel')
resolve_channel_reference('NPI', 'awareness')
```

**Assertions**:
```python
assert resolve_channel_reference('NPI', 'upper funnel') == resolve_channel_reference('NPI', 'awareness')
```

---

#### Test 13: `test_lower_funnel_equals_direct_response` — ✅ PASS

**What it verifies**: lower funnel equals direct response

**Function under test**:
```python
resolve_channel_reference('NPI', 'lower funnel')
resolve_channel_reference('NPI', 'direct response')
```

**Assertions**:
```python
assert resolve_channel_reference('NPI', 'lower funnel') == resolve_channel_reference('NPI', 'direct response')
```

---

#### Test 14: `test_dr_equals_direct_response` — ✅ PASS

**What it verifies**: dr equals direct response

**Function under test**:
```python
resolve_channel_reference('NPI', 'dr')
resolve_channel_reference('NPI', 'direct response')
```

**Assertions**:
```python
assert resolve_channel_reference('NPI', 'dr') == resolve_channel_reference('NPI', 'direct response')
```

---

#### Test 15: `test_television_equals_tv` — ✅ PASS

**What it verifies**: television equals tv

**Function under test**:
```python
resolve_channel_reference('NPI', 'television')
resolve_channel_reference('NPI', 'tv')
```

**Assertions**:
```python
assert resolve_channel_reference('NPI', 'television') == resolve_channel_reference('NPI', 'tv')
```

---

#### Test 16: `test_handles_extra_whitespace` — ✅ PASS

**What it verifies**: handles extra whitespace

**Function under test**:
```python
resolve_channel_reference('NPI', '  awareness  ')
```

**Assertions**:
```python
assert 'Linear TV' in result
```

---

#### Test 17: `test_handles_mixed_case` — ✅ PASS

**What it verifies**: handles mixed case

**Function under test**:
```python
resolve_channel_reference('NPI', 'AWARENESS')
```

**Assertions**:
```python
assert 'Linear TV' in result
```

---

#### Test 18: `test_unknown_term_raises_with_helpful_message` — ✅ PASS

**What it verifies**: unknown term raises with helpful message

**Function under test**:
```python
resolve_channel_reference('NPI', 'gibberish_xyz')
```

**Assertions**:
```python
assert 'Unknown channel reference' in str(exc.value)
```

---

#### Test 19: `test_unknown_client_raises` — ✅ PASS

**What it verifies**: unknown client raises

**Function under test**:
```python
resolve_channel_reference('FakeClient', 'organic')
```

---

#### Test 20: `test_winndixie_tv_channels` — ✅ PASS

**What it verifies**: winndixie tv channels

**Function under test**:
```python
resolve_channel_reference('WinnDixie', 'tv')
```

**Assertions**:
```python
assert 'OTT' in result
assert 'CTV' in result
assert 'Linear TV' in result
```

---

#### Test 21: `test_venetian_awareness_is_ooh` — ✅ PASS

**What it verifies**: venetian awareness is ooh

**Function under test**:
```python
resolve_channel_reference('Venetian', 'awareness')
```

**Assertions**:
```python
assert 'OOH' in result
```

---

### TestClientLookup

(6 tests)

#### Test 22: `test_get_npi_client` — ✅ PASS

**What it verifies**: get npi client

**Function under test**:
```python
get_client('NPI')
```

**Assertions**:
```python
assert client['client_id'] == 'NPI'
assert 'tables' in client
```

---

#### Test 23: `test_npi_has_two_tables` — ✅ PASS

**What it verifies**: npi has two tables

**Function under test**:
```python
list_tables('NPI')
```

**Assertions**:
```python
assert 'performance' in tables
assert 'pacing' in tables
```

---

#### Test 24: `test_venetian_has_performance_table` — ✅ PASS

**What it verifies**: venetian has performance table

**Function under test**:
```python
list_tables('Venetian')
```

**Assertions**:
```python
assert 'performance' in list_tables('Venetian')
```

---

#### Test 25: `test_winndixie_has_performance_table` — ✅ PASS

**What it verifies**: winndixie has performance table

**Function under test**:
```python
list_tables('WinnDixie')
```

**Assertions**:
```python
assert 'performance' in list_tables('WinnDixie')
```

---

#### Test 26: `test_unknown_client_raises` — ✅ PASS

**What it verifies**: unknown client raises

**Function under test**:
```python
get_client('DoesNotExist')
```

---

#### Test 27: `test_unknown_table_raises` — ✅ PASS

**What it verifies**: unknown table raises

**Function under test**:
```python
get_table('NPI', 'does_not_exist')
```

---

### TestConfigLoading

(4 tests)

#### Test 28: `test_config_loads` — ✅ PASS

**What it verifies**: config loads

**Function under test**:
```python
load_config_v3()
```

**Assertions**:
```python
assert 'datasets' in config
assert '_global_rules' in config
```

---

#### Test 29: `test_config_has_expected_clients` — ✅ PASS

**What it verifies**: config has expected clients

**Function under test**:
```python
list_clients()
```

**Assertions**:
```python
assert 'NPI' in clients
assert 'Venetian' in clients
assert 'WinnDixie' in clients
```

---

#### Test 30: `test_config_caches` — ✅ PASS

**What it verifies**: config caches

**Function under test**:
```python
load_config_v3()
load_config_v3()
```

**Assertions**:
```python
assert c1 is c2
```

---

#### Test 31: `test_force_reload_returns_fresh_object` — ✅ PASS

**What it verifies**: force reload returns fresh object

**Function under test**:
```python
load_config_v3()
load_config_v3(force_reload=True)
```

**Assertions**:
```python
assert c1 is not c2
assert c1 == c2
```

---

### TestPacingTable
_The new pacing table has different rules than performance._

(4 tests)

#### Test 32: `test_pacing_table_exists` — ✅ PASS

**What it verifies**: pacing table exists

**Function under test**:
```python
get_table('NPI', 'pacing')
```

**Assertions**:
```python
assert table['table_id'] == 'pacing'
```

---

#### Test 33: `test_pacing_uses_GVMM_channel` — ✅ PASS

**What it verifies**: pacing uses GVMM channel

**Function under test**:
```python
get_channel_column('NPI', 'pacing')
```

**Assertions**:
```python
assert get_channel_column('NPI', 'pacing') == 'GVMM_Channel'
```

---

#### Test 34: `test_pacing_has_flag_definitions` — ✅ PASS

**What it verifies**: pacing has flag definitions

**Function under test**:
```python
get_table('NPI', 'pacing')
```

**Assertions**:
```python
assert 'No spend' in flags
assert 'Pacing' in flags
assert 'Underpacing' in flags
assert 'Overpacing' in flags
```

---

#### Test 35: `test_pacing_has_ignore_default_rule` — ✅ PASS

**What it verifies**: pacing has ignore default rule

**Function under test**:
```python
get_table('NPI', 'pacing')
```

**Assertions**:
```python
assert 'ignore_default_channel_unless_explicit' in table['rules']
```

---

### TestTableMetadata

(8 tests)

#### Test 36: `test_npi_performance_kpi_column` — ✅ PASS

**What it verifies**: npi performance kpi column

**Function under test**:
```python
get_kpi_column('NPI', 'performance')
```

**Assertions**:
```python
assert get_kpi_column('NPI', 'performance') == 'Conversions'
```

---

#### Test 37: `test_winndixie_kpi_column` — ✅ PASS

**What it verifies**: winndixie kpi column

**Function under test**:
```python
get_kpi_column('WinnDixie')
```

**Assertions**:
```python
assert get_kpi_column('WinnDixie') == 'KPI'
```

---

#### Test 38: `test_npi_performance_channel_column` — ✅ PASS

**What it verifies**: npi performance channel column

**Function under test**:
```python
get_channel_column('NPI', 'performance')
```

**Assertions**:
```python
assert get_channel_column('NPI', 'performance') == 'Channel'
```

---

#### Test 39: `test_npi_pacing_channel_column` — ✅ PASS

**What it verifies**: Pacing table uses GVMM_Channel, NOT Channel.

**Function under test**:
```python
get_channel_column('NPI', 'pacing')
```

**Assertions**:
```python
assert get_channel_column('NPI', 'pacing') == 'GVMM_Channel'
```

---

#### Test 40: `test_npi_performance_table_path` — ✅ PASS

**What it verifies**: npi performance table path

**Function under test**:
```python
get_table_path('NPI', 'performance')
```

**Assertions**:
```python
assert 'vw_astrobot_npi_nc360_dashboard' in path
assert 'Astrobot_NPI' in path
```

---

#### Test 41: `test_npi_has_duality_on_performance` — ✅ PASS

**What it verifies**: npi has duality on performance

**Function under test**:
```python
get_duality_info('NPI', 'performance')
```

**Assertions**:
```python
assert d['has_duality'] is True
assert d['spend_rows_filter'] == 'Cost > 0'
assert d['conv_rows_filter'] == 'Conversions > 0'
```

---

#### Test 42: `test_npi_pacing_has_no_duality` — ✅ PASS

**What it verifies**: npi pacing has no duality

**Function under test**:
```python
get_duality_info('NPI', 'pacing')
```

**Assertions**:
```python
assert d['has_duality'] is False
```

---

#### Test 43: `test_npi_unification_map` — ✅ PASS

**What it verifies**: npi unification map

**Function under test**:
```python
get_unification_map('NPI', 'performance')
```

**Assertions**:
```python
assert 'Paid Search' in m
assert set(m['Paid Search']) == {'Search', 'Paid Search'}
assert 'Demand Gen + P-Max' in m
assert 'Demand Gen' in m['Demand Gen + P-Max']
assert 'Performance Max' in m['Demand Gen + P-Max']
```

---

## File: `test_question_router.py`

### TestQuestionRouting
_Routes user questions to the right table (performance vs pacing)._

(18 tests)

#### Test 44: `test_cpa_question_routes_to_performance` — ✅ PASS

**What it verifies**: cpa question routes to performance

**Function under test**:
```python
route_question_to_table('Which channel has the lowest CPA?', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
```

---

#### Test 45: `test_channel_ranking_routes_to_performance` — ✅ PASS

**What it verifies**: channel ranking routes to performance

**Function under test**:
```python
route_question_to_table('Rank channels by efficiency', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
```

---

#### Test 46: `test_organic_efficiency_routes_to_performance` — ✅ PASS

**What it verifies**: organic efficiency routes to performance

**Function under test**:
```python
route_question_to_table("What's the organic efficiency for last 12 months?", 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
```

---

#### Test 47: `test_tv_halo_routes_to_performance` — ✅ PASS

**What it verifies**: tv halo routes to performance

**Function under test**:
```python
route_question_to_table('Does TV halo lift Paid Search conversions?', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
```

---

#### Test 48: `test_volatility_routes_to_performance` — ✅ PASS

**What it verifies**: volatility routes to performance

**Function under test**:
```python
route_question_to_table('Which channel is most volatile?', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
```

---

#### Test 49: `test_forecast_routes_to_performance` — ✅ PASS

**What it verifies**: forecast routes to performance

**Function under test**:
```python
route_question_to_table('Forecast next quarter conversions', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
```

---

#### Test 50: `test_pacing_question_routes_to_pacing` — ✅ PASS

**What it verifies**: pacing question routes to pacing

**Function under test**:
```python
route_question_to_table('Are we pacing well this month?', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'pacing'
```

---

#### Test 51: `test_budget_remaining_routes_to_pacing` — ✅ PASS

**What it verifies**: budget remaining routes to pacing

**Function under test**:
```python
route_question_to_table('How much budget is remaining?', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'pacing'
```

---

#### Test 52: `test_underpacing_routes_to_pacing` — ✅ PASS

**What it verifies**: underpacing routes to pacing

**Function under test**:
```python
route_question_to_table('Which flights are underpacing?', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'pacing'
```

---

#### Test 53: `test_will_we_hit_budget_routes_to_pacing` — ✅ PASS

**What it verifies**: will we hit budget routes to pacing

**Function under test**:
```python
route_question_to_table('Will we hit budget for December?', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'pacing'
```

---

#### Test 54: `test_days_remaining_routes_to_pacing` — ✅ PASS

**What it verifies**: days remaining routes to pacing

**Function under test**:
```python
route_question_to_table('How many days remaining on the flight?', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'pacing'
```

---

#### Test 55: `test_burn_rate_routes_to_pacing` — ✅ PASS

**What it verifies**: burn rate routes to pacing

**Function under test**:
```python
route_question_to_table("What's our current burn rate?", 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'pacing'
```

---

#### Test 56: `test_geo_budget_routes_to_pacing` — ✅ PASS

**What it verifies**: geo budget routes to pacing

**Function under test**:
```python
route_question_to_table('Show me geo budget breakdown', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'pacing'
```

---

#### Test 57: `test_unmatched_question_defaults_to_performance` — ✅ PASS

**What it verifies**: unmatched question defaults to performance

**Function under test**:
```python
route_question_to_table('Hello world unrelated question', 'NPI')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
assert r['confidence'] == 'default'
assert r['matched_keywords'] == []
```

---

#### Test 58: `test_result_includes_required_fields` — ✅ PASS

**What it verifies**: result includes required fields

**Function under test**:
```python
route_question_to_table('Lowest CPA channel?', 'NPI')
```

**Assertions**:
```python
assert 'table_id' in r
assert 'table_full_path' in r
assert 'rules' in r
assert 'channel_column' in r
assert 'matched_keywords' in r
assert 'confidence' in r
```

---

#### Test 59: `test_confidence_higher_with_more_matches` — ✅ PASS

**What it verifies**: confidence higher with more matches

**Function under test**:
```python
route_question_to_table('Show CPA, ROAS, and channel ranking for NPI', 'NPI')
route_question_to_table('CPA?', 'NPI')
```

**Assertions**:
```python
assert len(r_high['matched_keywords']) >= len(r_low['matched_keywords'])
```

---

#### Test 60: `test_winndixie_routes_to_its_only_table` — ✅ PASS

**What it verifies**: winndixie routes to its only table

**Function under test**:
```python
route_question_to_table('Show ViVs by month', 'WinnDixie')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
```

---

#### Test 61: `test_venetian_routes_to_its_only_table` — ✅ PASS

**What it verifies**: venetian routes to its only table

**Function under test**:
```python
route_question_to_table('OOH performance?', 'Venetian')
```

**Assertions**:
```python
assert r['table_id'] == 'performance'
```

---

### TestRulesLookup
_Tests that applicable rules are retrieved correctly per table._

(6 tests)

#### Test 62: `test_performance_rules_include_unified_cte` — ✅ PASS

**What it verifies**: performance rules include unified cte

**Function under test**:
```python
get_applicable_rules('NPI', 'performance')
```

**Assertions**:
```python
assert 'blended_cpa_use_unified_cte' in rule_ids
assert 'volatility_use_cv_not_stddev' in rule_ids
```

---

#### Test 63: `test_pacing_rules_include_pacing_specific` — ✅ PASS

**What it verifies**: pacing rules include pacing specific

**Function under test**:
```python
get_applicable_rules('NPI', 'pacing')
```

**Assertions**:
```python
assert 'pacing_use_days_remaining_for_projections' in rule_ids
assert 'ignore_default_channel_unless_explicit' in rule_ids
```

---

#### Test 64: `test_pacing_rules_do_not_include_performance_specific` — ✅ PASS

**What it verifies**: pacing rules do not include performance specific

**Function under test**:
```python
get_applicable_rules('NPI', 'pacing')
```

**Assertions**:
```python
assert 'blended_cpa_use_unified_cte' not in rule_ids
```

---

#### Test 65: `test_rules_include_global_rules` — ✅ PASS

**What it verifies**: rules include global rules

**Function under test**:
```python
get_applicable_rules('NPI', 'performance')
```

**Assertions**:
```python
assert 'always_filter_by_client' in rule_ids
assert 'always_use_date_range_filter' in rule_ids
```

---

#### Test 66: `test_rules_have_descriptions` — ✅ PASS

**What it verifies**: rules have descriptions

**Function under test**:
```python
get_applicable_rules('NPI', 'performance')
```

**Assertions**:
```python
assert r['description']
assert r['description'] != '(no description)'
```

---

#### Test 67: `test_no_duplicate_rules` — ✅ PASS

**What it verifies**: no duplicate rules

**Function under test**:
```python
get_applicable_rules('NPI', 'performance')
```

**Assertions**:
```python
assert len(ids) == len(set(ids))
```

---

## File: `test_sql_builder.py`

### TestBlendedCpaSql
_Blended CPA query with unified CTE and FULL OUTER JOIN._

(7 tests)

#### Test 68: `test_uses_full_outer_join` — ✅ PASS

**What it verifies**: REGRESSION: agent previously joined wrong direction, losing channels.

**Function under test**:
```python
build_blended_cpa_sql('NPI')
```

**Assertions**:
```python
assert 'FULL OUTER JOIN' in sql
```

---

#### Test 69: `test_filters_by_client` — ✅ PASS

**What it verifies**: Critical: must always filter by Client.

**Function under test**:
```python
build_blended_cpa_sql('NPI')
```

**Assertions**:
```python
assert "Client = 'NPI'" in sql
```

---

#### Test 70: `test_uses_date_range_filter` — ✅ PASS

**What it verifies**: uses date range filter

**Function under test**:
```python
build_blended_cpa_sql('NPI', lookback_months=12)
```

**Assertions**:
```python
assert 'INTERVAL 12 MONTH' in sql
```

---

#### Test 71: `test_handles_duality_with_separate_ctes` — ✅ PASS

**What it verifies**: handles duality with separate ctes

**Function under test**:
```python
build_blended_cpa_sql('NPI')
```

**Assertions**:
```python
assert 'WITH unified AS' in sql
assert 'spend AS' in sql
assert 'conv AS' in sql
```

---

#### Test 72: `test_uses_safe_divide` — ✅ PASS

**What it verifies**: uses safe divide

**Function under test**:
```python
build_blended_cpa_sql('NPI')
```

**Assertions**:
```python
assert 'SAFE_DIVIDE' in sql
```

---

#### Test 73: `test_no_duality_path_is_simpler` — ✅ PASS

**What it verifies**: Venetian has no duality - SQL should be simpler.

**Function under test**:
```python
build_blended_cpa_sql('Venetian')
```

**Assertions**:
```python
assert 'FULL OUTER JOIN' not in sql
assert "Client = 'Venetian'" in sql
```

---

#### Test 74: `test_npi_table_path_in_sql` — ✅ PASS

**What it verifies**: npi table path in sql

**Function under test**:
```python
build_blended_cpa_sql('NPI')
```

**Assertions**:
```python
assert 'vw_astrobot_npi_nc360_dashboard' in sql
```

---

### TestFunnelSpendSql
_Spend by funnel category (awareness/DR/mid-funnel)._

(6 tests)

#### Test 75: `test_awareness_includes_all_awareness_channels` — ✅ PASS

**What it verifies**: REGRESSION: agent only counted 2 of 9 awareness channels.

**Function under test**:
```python
build_funnel_spend_sql('NPI')
```

**Assertions**:
```python
assert f"'{ch}'" in sql
```

---

#### Test 76: `test_dr_includes_search_email_shopping` — ✅ PASS

**What it verifies**: dr includes search email shopping

**Function under test**:
```python
build_funnel_spend_sql('NPI')
```

**Assertions**:
```python
assert f"'{ch}'" in sql
```

---

#### Test 77: `test_midfunnel_includes_social_demand_gen_pmax` — ✅ PASS

**What it verifies**: midfunnel includes social demand gen pmax

**Function under test**:
```python
build_funnel_spend_sql('NPI')
```

**Assertions**:
```python
assert f"'{ch}'" in sql
```

---

#### Test 78: `test_computes_awareness_dr_ratio` — ✅ PASS

**What it verifies**: computes awareness dr ratio

**Function under test**:
```python
build_funnel_spend_sql('NPI')
```

**Assertions**:
```python
assert 'awareness_dr_ratio' in sql
```

---

#### Test 79: `test_uses_safe_divide_for_ratio` — ✅ PASS

**What it verifies**: uses safe divide for ratio

**Function under test**:
```python
build_funnel_spend_sql('NPI')
```

**Assertions**:
```python
assert 'SAFE_DIVIDE' in sql
```

---

#### Test 80: `test_returns_all_three_categories` — ✅ PASS

**What it verifies**: returns all three categories

**Function under test**:
```python
build_funnel_spend_sql('NPI')
```

**Assertions**:
```python
assert 'awareness_spend' in sql
assert 'dr_spend' in sql
assert 'midfunnel_spend' in sql
assert 'total_spend' in sql
```

---

### TestOrganicShareSql
_Organic % share query._

(5 tests)

#### Test 81: `test_includes_organic_channels_in_filter` — ✅ PASS

**What it verifies**: includes organic channels in filter

**Function under test**:
```python
build_organic_share_sql('NPI')
```

**Assertions**:
```python
assert 'Organic Search' in sql
assert 'Organic Social' in sql
assert 'Direct' in sql
```

---

#### Test 82: `test_excludes_paid_channels_from_filter` — ✅ PASS

**What it verifies**: REGRESSION: agent previously included Paid channels in 'organic'.

**Function under test**:
```python
build_organic_share_sql('NPI')
```

**Assertions**:
```python
assert "'Paid Social'" not in case_block
assert "'Paid Search'" not in case_block
```

---

#### Test 83: `test_groups_by_month` — ✅ PASS

**What it verifies**: groups by month

**Function under test**:
```python
build_organic_share_sql('NPI')
```

**Assertions**:
```python
assert "FORMAT_DATE('%Y-%m'" in sql
assert 'GROUP BY month' in sql
```

---

#### Test 84: `test_uses_pct_calculation` — ✅ PASS

**What it verifies**: uses pct calculation

**Function under test**:
```python
build_organic_share_sql('NPI')
```

**Assertions**:
```python
assert 'pct_organic' in sql
assert '100.0 *' in sql
```

---

#### Test 85: `test_filters_by_client` — ✅ PASS

**What it verifies**: filters by client

**Function under test**:
```python
build_organic_share_sql('NPI')
```

**Assertions**:
```python
assert "Client = 'NPI'" in sql
```

---

### TestUnifiedCte
_The CASE WHEN unification clause._

(3 tests)

#### Test 86: `test_npi_unification_includes_paid_search_grouping` — ✅ PASS

**What it verifies**: npi unification includes paid search grouping

**Function under test**:
```python
build_unified_cte('NPI', 'performance')
```

**Assertions**:
```python
assert 'Paid Search' in sql
assert 'Search' in sql
```

---

#### Test 87: `test_npi_unification_includes_demand_gen_pmax` — ✅ PASS

**What it verifies**: npi unification includes demand gen pmax

**Function under test**:
```python
build_unified_cte('NPI', 'performance')
```

**Assertions**:
```python
assert 'Demand Gen + P-Max' in sql
assert 'Demand Gen' in sql
assert 'Performance Max' in sql
```

---

#### Test 88: `test_unification_is_case_statement` — ✅ PASS

**What it verifies**: unification is case statement

**Function under test**:
```python
build_unified_cte('NPI', 'performance')
```

**Assertions**:
```python
assert 'CASE' in sql
assert 'WHEN' in sql
assert 'THEN' in sql
assert 'ELSE' in sql
assert 'END' in sql
```

---

### TestVolatilitySql
_Coefficient-of-variation volatility query._

(6 tests)

#### Test 89: `test_uses_stddev_div_avg_not_raw_stddev` — ✅ PASS

**What it verifies**: REGRESSION: agent first used raw STDDEV instead of CV.

**Function under test**:
```python
build_volatility_sql('NPI')
```

**Assertions**:
```python
assert 'STDDEV' in sql
assert 'AVG' in sql
assert 'SAFE_DIVIDE(STDDEV' in sql
```

---

#### Test 90: `test_orders_by_cv_desc` — ✅ PASS

**What it verifies**: orders by cv desc

**Function under test**:
```python
build_volatility_sql('NPI')
```

**Assertions**:
```python
assert 'ORDER BY cv DESC' in sql
```

---

#### Test 91: `test_filters_low_sample_channels` — ✅ PASS

**What it verifies**: filters low sample channels

**Function under test**:
```python
build_volatility_sql('NPI', min_months=8)
```

**Assertions**:
```python
assert 'months >= 8' in sql
```

---

#### Test 92: `test_default_metric_is_conversions` — ✅ PASS

**What it verifies**: default metric is conversions

**Function under test**:
```python
build_volatility_sql('NPI')
```

**Assertions**:
```python
assert 'SUM(Conversions)' in sql
```

---

#### Test 93: `test_custom_metric_used` — ✅ PASS

**What it verifies**: custom metric used

**Function under test**:
```python
build_volatility_sql('NPI', metric='Cost')
```

**Assertions**:
```python
assert 'SUM(Cost)' in sql
```

---

#### Test 94: `test_unified_channel_used_in_grouping` — ✅ PASS

**What it verifies**: unified channel used in grouping

**Function under test**:
```python
build_volatility_sql('NPI')
```

**Assertions**:
```python
assert 'CASE' in sql
assert 'GROUP BY month, channel' in sql
```

---

## Summary Table

| # | File | Class | Test | Result |
|---|------|-------|------|--------|
| 1 | `test_channel_resolver.py` | TestConfigLoading | `test_config_loads` | ✅ PASSED |
| 2 | `test_channel_resolver.py` | TestConfigLoading | `test_config_has_expected_clients` | ✅ PASSED |
| 3 | `test_channel_resolver.py` | TestConfigLoading | `test_config_caches` | ✅ PASSED |
| 4 | `test_channel_resolver.py` | TestConfigLoading | `test_force_reload_returns_fresh_object` | ✅ PASSED |
| 5 | `test_channel_resolver.py` | TestClientLookup | `test_get_npi_client` | ✅ PASSED |
| 6 | `test_channel_resolver.py` | TestClientLookup | `test_npi_has_two_tables` | ✅ PASSED |
| 7 | `test_channel_resolver.py` | TestClientLookup | `test_venetian_has_performance_table` | ✅ PASSED |
| 8 | `test_channel_resolver.py` | TestClientLookup | `test_winndixie_has_performance_table` | ✅ PASSED |
| 9 | `test_channel_resolver.py` | TestClientLookup | `test_unknown_client_raises` | ✅ PASSED |
| 10 | `test_channel_resolver.py` | TestClientLookup | `test_unknown_table_raises` | ✅ PASSED |
| 11 | `test_channel_resolver.py` | TestChannelResolution | `test_direct_returns_Direct_not_DEFAULT` | ✅ PASSED |
| 12 | `test_channel_resolver.py` | TestChannelResolution | `test_direct_case_insensitive` | ✅ PASSED |
| 13 | `test_channel_resolver.py` | TestChannelResolution | `test_awareness_includes_all_tv_channels` | ✅ PASSED |
| 14 | `test_channel_resolver.py` | TestChannelResolution | `test_awareness_includes_video_and_audio` | ✅ PASSED |
| 15 | `test_channel_resolver.py` | TestChannelResolution | `test_awareness_includes_offline` | ✅ PASSED |
| 16 | `test_channel_resolver.py` | TestChannelResolution | `test_awareness_has_at_least_seven_channels` | ✅ PASSED |
| 17 | `test_channel_resolver.py` | TestChannelResolution | `test_organic_includes_organic_search_social_video` | ✅ PASSED |
| 18 | `test_channel_resolver.py` | TestChannelResolution | `test_organic_includes_direct_and_referral` | ✅ PASSED |
| 19 | `test_channel_resolver.py` | TestChannelResolution | `test_organic_excludes_paid_channels` | ✅ PASSED |
| 20 | `test_channel_resolver.py` | TestChannelResolution | `test_direct_response_includes_search_and_email` | ✅ PASSED |
| 21 | `test_channel_resolver.py` | TestChannelResolution | `test_direct_response_excludes_tv` | ✅ PASSED |
| 22 | `test_channel_resolver.py` | TestChannelResolution | `test_upper_funnel_equals_awareness` | ✅ PASSED |
| 23 | `test_channel_resolver.py` | TestChannelResolution | `test_lower_funnel_equals_direct_response` | ✅ PASSED |
| 24 | `test_channel_resolver.py` | TestChannelResolution | `test_dr_equals_direct_response` | ✅ PASSED |
| 25 | `test_channel_resolver.py` | TestChannelResolution | `test_television_equals_tv` | ✅ PASSED |
| 26 | `test_channel_resolver.py` | TestChannelResolution | `test_handles_extra_whitespace` | ✅ PASSED |
| 27 | `test_channel_resolver.py` | TestChannelResolution | `test_handles_mixed_case` | ✅ PASSED |
| 28 | `test_channel_resolver.py` | TestChannelResolution | `test_unknown_term_raises_with_helpful_message` | ✅ PASSED |
| 29 | `test_channel_resolver.py` | TestChannelResolution | `test_unknown_client_raises` | ✅ PASSED |
| 30 | `test_channel_resolver.py` | TestChannelResolution | `test_winndixie_tv_channels` | ✅ PASSED |
| 31 | `test_channel_resolver.py` | TestChannelResolution | `test_venetian_awareness_is_ooh` | ✅ PASSED |
| 32 | `test_channel_resolver.py` | TestTableMetadata | `test_npi_performance_kpi_column` | ✅ PASSED |
| 33 | `test_channel_resolver.py` | TestTableMetadata | `test_winndixie_kpi_column` | ✅ PASSED |
| 34 | `test_channel_resolver.py` | TestTableMetadata | `test_npi_performance_channel_column` | ✅ PASSED |
| 35 | `test_channel_resolver.py` | TestTableMetadata | `test_npi_pacing_channel_column` | ✅ PASSED |
| 36 | `test_channel_resolver.py` | TestTableMetadata | `test_npi_performance_table_path` | ✅ PASSED |
| 37 | `test_channel_resolver.py` | TestTableMetadata | `test_npi_has_duality_on_performance` | ✅ PASSED |
| 38 | `test_channel_resolver.py` | TestTableMetadata | `test_npi_pacing_has_no_duality` | ✅ PASSED |
| 39 | `test_channel_resolver.py` | TestTableMetadata | `test_npi_unification_map` | ✅ PASSED |
| 40 | `test_channel_resolver.py` | TestPacingTable | `test_pacing_table_exists` | ✅ PASSED |
| 41 | `test_channel_resolver.py` | TestPacingTable | `test_pacing_uses_GVMM_channel` | ✅ PASSED |
| 42 | `test_channel_resolver.py` | TestPacingTable | `test_pacing_has_flag_definitions` | ✅ PASSED |
| 43 | `test_channel_resolver.py` | TestPacingTable | `test_pacing_has_ignore_default_rule` | ✅ PASSED |
| 44 | `test_question_router.py` | TestQuestionRouting | `test_cpa_question_routes_to_performance` | ✅ PASSED |
| 45 | `test_question_router.py` | TestQuestionRouting | `test_channel_ranking_routes_to_performance` | ✅ PASSED |
| 46 | `test_question_router.py` | TestQuestionRouting | `test_organic_efficiency_routes_to_performance` | ✅ PASSED |
| 47 | `test_question_router.py` | TestQuestionRouting | `test_tv_halo_routes_to_performance` | ✅ PASSED |
| 48 | `test_question_router.py` | TestQuestionRouting | `test_volatility_routes_to_performance` | ✅ PASSED |
| 49 | `test_question_router.py` | TestQuestionRouting | `test_forecast_routes_to_performance` | ✅ PASSED |
| 50 | `test_question_router.py` | TestQuestionRouting | `test_pacing_question_routes_to_pacing` | ✅ PASSED |
| 51 | `test_question_router.py` | TestQuestionRouting | `test_budget_remaining_routes_to_pacing` | ✅ PASSED |
| 52 | `test_question_router.py` | TestQuestionRouting | `test_underpacing_routes_to_pacing` | ✅ PASSED |
| 53 | `test_question_router.py` | TestQuestionRouting | `test_will_we_hit_budget_routes_to_pacing` | ✅ PASSED |
| 54 | `test_question_router.py` | TestQuestionRouting | `test_days_remaining_routes_to_pacing` | ✅ PASSED |
| 55 | `test_question_router.py` | TestQuestionRouting | `test_burn_rate_routes_to_pacing` | ✅ PASSED |
| 56 | `test_question_router.py` | TestQuestionRouting | `test_geo_budget_routes_to_pacing` | ✅ PASSED |
| 57 | `test_question_router.py` | TestQuestionRouting | `test_unmatched_question_defaults_to_performance` | ✅ PASSED |
| 58 | `test_question_router.py` | TestQuestionRouting | `test_result_includes_required_fields` | ✅ PASSED |
| 59 | `test_question_router.py` | TestQuestionRouting | `test_confidence_higher_with_more_matches` | ✅ PASSED |
| 60 | `test_question_router.py` | TestQuestionRouting | `test_winndixie_routes_to_its_only_table` | ✅ PASSED |
| 61 | `test_question_router.py` | TestQuestionRouting | `test_venetian_routes_to_its_only_table` | ✅ PASSED |
| 62 | `test_question_router.py` | TestRulesLookup | `test_performance_rules_include_unified_cte` | ✅ PASSED |
| 63 | `test_question_router.py` | TestRulesLookup | `test_pacing_rules_include_pacing_specific` | ✅ PASSED |
| 64 | `test_question_router.py` | TestRulesLookup | `test_pacing_rules_do_not_include_performance_specific` | ✅ PASSED |
| 65 | `test_question_router.py` | TestRulesLookup | `test_rules_include_global_rules` | ✅ PASSED |
| 66 | `test_question_router.py` | TestRulesLookup | `test_rules_have_descriptions` | ✅ PASSED |
| 67 | `test_question_router.py` | TestRulesLookup | `test_no_duplicate_rules` | ✅ PASSED |
| 68 | `test_sql_builder.py` | TestUnifiedCte | `test_npi_unification_includes_paid_search_grouping` | ✅ PASSED |
| 69 | `test_sql_builder.py` | TestUnifiedCte | `test_npi_unification_includes_demand_gen_pmax` | ✅ PASSED |
| 70 | `test_sql_builder.py` | TestUnifiedCte | `test_unification_is_case_statement` | ✅ PASSED |
| 71 | `test_sql_builder.py` | TestBlendedCpaSql | `test_uses_full_outer_join` | ✅ PASSED |
| 72 | `test_sql_builder.py` | TestBlendedCpaSql | `test_filters_by_client` | ✅ PASSED |
| 73 | `test_sql_builder.py` | TestBlendedCpaSql | `test_uses_date_range_filter` | ✅ PASSED |
| 74 | `test_sql_builder.py` | TestBlendedCpaSql | `test_handles_duality_with_separate_ctes` | ✅ PASSED |
| 75 | `test_sql_builder.py` | TestBlendedCpaSql | `test_uses_safe_divide` | ✅ PASSED |
| 76 | `test_sql_builder.py` | TestBlendedCpaSql | `test_no_duality_path_is_simpler` | ✅ PASSED |
| 77 | `test_sql_builder.py` | TestBlendedCpaSql | `test_npi_table_path_in_sql` | ✅ PASSED |
| 78 | `test_sql_builder.py` | TestOrganicShareSql | `test_includes_organic_channels_in_filter` | ✅ PASSED |
| 79 | `test_sql_builder.py` | TestOrganicShareSql | `test_excludes_paid_channels_from_filter` | ✅ PASSED |
| 80 | `test_sql_builder.py` | TestOrganicShareSql | `test_groups_by_month` | ✅ PASSED |
| 81 | `test_sql_builder.py` | TestOrganicShareSql | `test_uses_pct_calculation` | ✅ PASSED |
| 82 | `test_sql_builder.py` | TestOrganicShareSql | `test_filters_by_client` | ✅ PASSED |
| 83 | `test_sql_builder.py` | TestFunnelSpendSql | `test_awareness_includes_all_awareness_channels` | ✅ PASSED |
| 84 | `test_sql_builder.py` | TestFunnelSpendSql | `test_dr_includes_search_email_shopping` | ✅ PASSED |
| 85 | `test_sql_builder.py` | TestFunnelSpendSql | `test_midfunnel_includes_social_demand_gen_pmax` | ✅ PASSED |
| 86 | `test_sql_builder.py` | TestFunnelSpendSql | `test_computes_awareness_dr_ratio` | ✅ PASSED |
| 87 | `test_sql_builder.py` | TestFunnelSpendSql | `test_uses_safe_divide_for_ratio` | ✅ PASSED |
| 88 | `test_sql_builder.py` | TestFunnelSpendSql | `test_returns_all_three_categories` | ✅ PASSED |
| 89 | `test_sql_builder.py` | TestVolatilitySql | `test_uses_stddev_div_avg_not_raw_stddev` | ✅ PASSED |
| 90 | `test_sql_builder.py` | TestVolatilitySql | `test_orders_by_cv_desc` | ✅ PASSED |
| 91 | `test_sql_builder.py` | TestVolatilitySql | `test_filters_low_sample_channels` | ✅ PASSED |
| 92 | `test_sql_builder.py` | TestVolatilitySql | `test_default_metric_is_conversions` | ✅ PASSED |
| 93 | `test_sql_builder.py` | TestVolatilitySql | `test_custom_metric_used` | ✅ PASSED |
| 94 | `test_sql_builder.py` | TestVolatilitySql | `test_unified_channel_used_in_grouping` | ✅ PASSED |