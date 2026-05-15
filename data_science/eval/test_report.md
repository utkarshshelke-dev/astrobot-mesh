# Astrobot Deterministic Test Suite — Detailed Report

**Generated**: 2026-05-11T15:02:54
**Total tests**: 166
**Passed**: 166
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

## File: `test_knowledge_manager.py`

### TestDiscovery
_Tests for client/table discovery via the facade._

(4 tests)

#### Test 44: `test_list_clients_returns_all_three` — ✅ PASS

**What it verifies**: list clients returns all three

**Function under test**:
```python
km.list_clients()
```

**Assertions**:
```python
assert 'NPI' in clients
assert 'Venetian' in clients
assert 'WinnDixie' in clients
```

---

#### Test 45: `test_list_tables_for_npi` — ✅ PASS

**What it verifies**: list tables for npi

**Function under test**:
```python
km.list_tables('NPI')
```

**Assertions**:
```python
assert 'performance' in tables
assert 'pacing' in tables
```

---

#### Test 46: `test_list_tables_for_venetian_just_performance` — ✅ PASS

**What it verifies**: list tables for venetian just performance

**Function under test**:
```python
km.list_tables('Venetian')
```

**Assertions**:
```python
assert tables == ['performance']
```

---

#### Test 47: `test_data_property_exposes_config` — ✅ PASS

**What it verifies**: data property exposes config

**Assertions**:
```python
assert 'datasets' in km.data
assert '_global_rules' in km.data
```

---

### TestPromptSnippet
_Tests that prompt snippets stay small and include the right info._

(11 tests)

#### Test 48: `test_snippet_under_2000_chars` — ✅ PASS

**What it verifies**: Don't bloat the agent prompt.

**Assertions**:
```python
assert len(snippet) < 2000
```

---

#### Test 49: `test_snippet_includes_client_name` — ✅ PASS

**What it verifies**: snippet includes client name

**Assertions**:
```python
assert 'NPI' in snippet
```

---

#### Test 50: `test_snippet_includes_table_path` — ✅ PASS

**What it verifies**: snippet includes table path

**Assertions**:
```python
assert 'vw_astrobot_npi_nc360_dashboard' in snippet
```

---

#### Test 51: `test_snippet_includes_kpi_column` — ✅ PASS

**What it verifies**: snippet includes kpi column

**Assertions**:
```python
assert 'Conversions' in snippet
```

---

#### Test 52: `test_snippet_mentions_duality_for_performance` — ✅ PASS

**What it verifies**: snippet mentions duality for performance

**Assertions**:
```python
assert 'duality' in snippet.lower() or 'FULL OUTER JOIN' in snippet
```

---

#### Test 53: `test_snippet_includes_active_rules` — ✅ PASS

**What it verifies**: snippet includes active rules

**Assertions**:
```python
assert 'RULES' in snippet.upper()
```

---

#### Test 54: `test_snippet_for_pacing_uses_GVMM` — ✅ PASS

**What it verifies**: snippet for pacing uses GVMM

**Assertions**:
```python
assert 'GVMM_Channel' in snippet
```

---

#### Test 55: `test_snippet_handles_unknown_client` — ✅ PASS

**What it verifies**: snippet handles unknown client

**Assertions**:
```python
assert 'ERROR' in snippet
```

---

#### Test 56: `test_snippet_handles_unknown_table` — ✅ PASS

**What it verifies**: snippet handles unknown table

**Assertions**:
```python
assert 'ERROR' in snippet
```

---

#### Test 57: `test_snippet_respects_max_rules` — ✅ PASS

**What it verifies**: snippet respects max rules

**Assertions**:
```python
assert len(snippet_few) < len(snippet_many)
```

---

#### Test 58: `test_snippet_respects_max_chars_truncation` — ✅ PASS

**What it verifies**: snippet respects max chars truncation

**Assertions**:
```python
assert len(snippet) <= 500
```

---

### TestResolveTerm
_The facade's term-resolution methods, delegating to lib._

(6 tests)

#### Test 59: `test_resolve_direct_returns_Direct_list` — ✅ PASS

**What it verifies**: resolve direct returns Direct list

**Assertions**:
```python
assert km.resolve_term('NPI', 'direct') == ['Direct']
```

---

#### Test 60: `test_resolve_awareness_has_all_channels` — ✅ PASS

**What it verifies**: resolve awareness has all channels

**Assertions**:
```python
assert 'Linear TV' in result
assert 'OOH' in result
assert len(result) >= 7
```

---

#### Test 61: `test_resolve_unknown_term_raises` — ✅ PASS

**What it verifies**: resolve unknown term raises

---

#### Test 62: `test_resolve_safe_does_not_raise` — ✅ PASS

**What it verifies**: resolve safe does not raise

**Assertions**:
```python
assert result['error'] is not None
assert result['channels'] == []
assert result['sql_filter'] == ''
```

---

#### Test 63: `test_resolve_safe_returns_sql_filter` — ✅ PASS

**What it verifies**: resolve safe returns sql filter

**Assertions**:
```python
assert result['error'] is None
assert 'Linear TV' in result['sql_filter']
assert 'IN (' in result['sql_filter']
assert 'Channel' in result['sql_filter']
```

---

#### Test 64: `test_resolve_safe_for_pacing_uses_GVMM_channel` — ✅ PASS

**What it verifies**: Pacing table queries should use GVMM_Channel in SQL filter.

**Assertions**:
```python
assert 'GVMM_Channel' in result['sql_filter']
```

---

### TestRouteAndLoadContext
_Tests for the main agent integration point._

(13 tests)

#### Test 65: `test_returns_all_required_fields` — ✅ PASS

**What it verifies**: returns all required fields

**Assertions**:
```python
assert required.issubset(set(ctx.keys()))
```

---

#### Test 66: `test_cpa_question_routes_to_performance` — ✅ PASS

**What it verifies**: cpa question routes to performance

**Assertions**:
```python
assert ctx['routed_table_id'] == 'performance'
```

---

#### Test 67: `test_pacing_question_routes_to_pacing` — ✅ PASS

**What it verifies**: pacing question routes to pacing

**Assertions**:
```python
assert ctx['routed_table_id'] == 'pacing'
```

---

#### Test 68: `test_pacing_context_uses_GVMM_channel` — ✅ PASS

**What it verifies**: Critical: pacing table must report GVMM_Channel as channel_column.

**Assertions**:
```python
assert ctx['channel_column'] == 'GVMM_Channel'
```

---

#### Test 69: `test_performance_context_uses_Channel` — ✅ PASS

**What it verifies**: performance context uses Channel

**Assertions**:
```python
assert ctx['channel_column'] == 'Channel'
```

---

#### Test 70: `test_performance_context_has_duality` — ✅ PASS

**What it verifies**: performance context has duality

**Assertions**:
```python
assert ctx['duality']['has_duality'] is True
```

---

#### Test 71: `test_pacing_context_has_no_duality` — ✅ PASS

**What it verifies**: pacing context has no duality

**Assertions**:
```python
assert ctx['duality']['has_duality'] is False
```

---

#### Test 72: `test_npi_kpi_is_conversions` — ✅ PASS

**What it verifies**: npi kpi is conversions

**Assertions**:
```python
assert ctx['kpi_column'] == 'Conversions'
```

---

#### Test 73: `test_winndixie_kpi_is_KPI` — ✅ PASS

**What it verifies**: winndixie kpi is KPI

**Assertions**:
```python
assert ctx['kpi_column'] == 'KPI'
```

---

#### Test 74: `test_context_includes_taxonomy` — ✅ PASS

**What it verifies**: context includes taxonomy

**Assertions**:
```python
assert 'organic' in ctx['channel_taxonomy']
assert 'awareness' in ctx['channel_taxonomy']
assert 'Linear TV' in ctx['channel_taxonomy']['awareness']
```

---

#### Test 75: `test_context_includes_applicable_rules` — ✅ PASS

**What it verifies**: context includes applicable rules

**Assertions**:
```python
assert isinstance(ctx['applicable_rules'], list)
assert len(ctx['applicable_rules']) > 0
```

---

#### Test 76: `test_pacing_rules_differ_from_performance_rules` — ✅ PASS

**What it verifies**: pacing rules differ from performance rules

**Assertions**:
```python
assert 'pacing_use_days_remaining_for_projections' in pace['applicable_rules']
assert 'pacing_use_days_remaining_for_projections' not in perf['applicable_rules']
```

---

#### Test 77: `test_client_id_preserved_in_context` — ✅ PASS

**What it verifies**: client id preserved in context

**Assertions**:
```python
assert ctx['client_id'] == 'NPI'
```

---

### TestSingleton
_The exported `manager` singleton should behave consistently._

(3 tests)

#### Test 78: `test_singleton_is_KnowledgeManager` — ✅ PASS

**What it verifies**: singleton is KnowledgeManager

**Assertions**:
```python
assert isinstance(manager, KnowledgeManager)
```

---

#### Test 79: `test_singleton_routes_correctly` — ✅ PASS

**What it verifies**: singleton routes correctly

**Assertions**:
```python
assert ctx['routed_table_id'] == 'performance'
```

---

#### Test 80: `test_singleton_resolves_correctly` — ✅ PASS

**What it verifies**: singleton resolves correctly

**Assertions**:
```python
assert manager.resolve_term('NPI', 'direct') == ['Direct']
```

---

## File: `test_question_router.py`

### TestQuestionRouting
_Routes user questions to the right table (performance vs pacing)._

(18 tests)

#### Test 81: `test_cpa_question_routes_to_performance` — ✅ PASS

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

#### Test 82: `test_channel_ranking_routes_to_performance` — ✅ PASS

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

#### Test 83: `test_organic_efficiency_routes_to_performance` — ✅ PASS

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

#### Test 84: `test_tv_halo_routes_to_performance` — ✅ PASS

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

#### Test 85: `test_volatility_routes_to_performance` — ✅ PASS

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

#### Test 86: `test_forecast_routes_to_performance` — ✅ PASS

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

#### Test 87: `test_pacing_question_routes_to_pacing` — ✅ PASS

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

#### Test 88: `test_budget_remaining_routes_to_pacing` — ✅ PASS

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

#### Test 89: `test_underpacing_routes_to_pacing` — ✅ PASS

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

#### Test 90: `test_will_we_hit_budget_routes_to_pacing` — ✅ PASS

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

#### Test 91: `test_days_remaining_routes_to_pacing` — ✅ PASS

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

#### Test 92: `test_burn_rate_routes_to_pacing` — ✅ PASS

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

#### Test 93: `test_geo_budget_routes_to_pacing` — ✅ PASS

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

#### Test 94: `test_unmatched_question_defaults_to_performance` — ✅ PASS

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

#### Test 95: `test_result_includes_required_fields` — ✅ PASS

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
# ... (1 more)
```

---

#### Test 96: `test_confidence_higher_with_more_matches` — ✅ PASS

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

#### Test 97: `test_winndixie_routes_to_its_only_table` — ✅ PASS

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

#### Test 98: `test_venetian_routes_to_its_only_table` — ✅ PASS

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

#### Test 99: `test_performance_rules_include_unified_cte` — ✅ PASS

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

#### Test 100: `test_pacing_rules_include_pacing_specific` — ✅ PASS

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

#### Test 101: `test_pacing_rules_do_not_include_performance_specific` — ✅ PASS

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

#### Test 102: `test_rules_include_global_rules` — ✅ PASS

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

#### Test 103: `test_rules_have_descriptions` — ✅ PASS

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

#### Test 104: `test_no_duplicate_rules` — ✅ PASS

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

#### Test 105: `test_uses_full_outer_join` — ✅ PASS

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

#### Test 106: `test_filters_by_client` — ✅ PASS

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

#### Test 107: `test_uses_date_range_filter` — ✅ PASS

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

#### Test 108: `test_handles_duality_with_separate_ctes` — ✅ PASS

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

#### Test 109: `test_uses_safe_divide` — ✅ PASS

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

#### Test 110: `test_no_duality_path_is_simpler` — ✅ PASS

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

#### Test 111: `test_npi_table_path_in_sql` — ✅ PASS

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

#### Test 112: `test_awareness_includes_all_awareness_channels` — ✅ PASS

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

#### Test 113: `test_dr_includes_search_email_shopping` — ✅ PASS

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

#### Test 114: `test_midfunnel_includes_social_demand_gen_pmax` — ✅ PASS

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

#### Test 115: `test_computes_awareness_dr_ratio` — ✅ PASS

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

#### Test 116: `test_uses_safe_divide_for_ratio` — ✅ PASS

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

#### Test 117: `test_returns_all_three_categories` — ✅ PASS

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

#### Test 118: `test_includes_organic_channels_in_filter` — ✅ PASS

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

#### Test 119: `test_excludes_paid_channels_from_filter` — ✅ PASS

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

#### Test 120: `test_groups_by_month` — ✅ PASS

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

#### Test 121: `test_uses_pct_calculation` — ✅ PASS

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

#### Test 122: `test_filters_by_client` — ✅ PASS

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

#### Test 123: `test_npi_unification_includes_paid_search_grouping` — ✅ PASS

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

#### Test 124: `test_npi_unification_includes_demand_gen_pmax` — ✅ PASS

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

#### Test 125: `test_unification_is_case_statement` — ✅ PASS

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

#### Test 126: `test_uses_stddev_div_avg_not_raw_stddev` — ✅ PASS

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

#### Test 127: `test_orders_by_cv_desc` — ✅ PASS

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

#### Test 128: `test_filters_low_sample_channels` — ✅ PASS

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

#### Test 129: `test_default_metric_is_conversions` — ✅ PASS

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

#### Test 130: `test_custom_metric_used` — ✅ PASS

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

#### Test 131: `test_unified_channel_used_in_grouping` — ✅ PASS

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

## File: `test_sql_validator.py`

### TestActiveRules

(5 tests)

#### Test 132: `test_cpa_question_finds_blended_cpa_rule` — ✅ PASS

**What it verifies**: cpa question finds blended cpa rule

**Assertions**:
```python
assert 'blended_cpa_use_unified_cte' in rule_ids
```

---

#### Test 133: `test_volatility_question_finds_cv_rule` — ✅ PASS

**What it verifies**: volatility question finds cv rule

**Assertions**:
```python
assert 'volatility_use_cv_not_stddev' in rule_ids
```

---

#### Test 134: `test_organic_efficiency_finds_rule` — ✅ PASS

**What it verifies**: organic efficiency finds rule

**Assertions**:
```python
assert 'organic_efficiency_use_organic_filter' in rule_ids
```

---

#### Test 135: `test_universal_rules_always_apply` — ✅ PASS

**What it verifies**: Rules with applies_to_question_types = ['*'] should always show up.

**Assertions**:
```python
assert 'never_select_star_without_limit' in rule_ids
assert 'use_safe_divide_for_ratios' in rule_ids
```

---

#### Test 136: `test_pacing_question_finds_GVMM_rule` — ✅ PASS

**What it verifies**: pacing question finds GVMM rule

**Assertions**:
```python
assert 'use_GVMM_Channel_not_Budget_Channel_for_grouping' in rule_ids
```

---

### TestBlendedCpaViolation

(2 tests)

#### Test 137: `test_direct_paid_search_filter_triggers_violation` — ✅ PASS

**What it verifies**: direct paid search filter triggers violation

**Assertions**:
```python
assert 'blended_cpa_use_unified_cte' in rule_ids
```

---

#### Test 138: `test_unified_cte_does_not_violate` — ✅ PASS

**What it verifies**: unified cte does not violate

**Assertions**:
```python
assert 'blended_cpa_use_unified_cte' not in rule_ids
```

---

### TestDecisionLogic

(6 tests)

#### Test 139: `test_no_violations_allows` — ✅ PASS

**What it verifies**: no violations allows

**Assertions**:
```python
assert get_decision(self._make_result()) == 'allow'
```

---

#### Test 140: `test_error_blocks` — ✅ PASS

**What it verifies**: error blocks

**Assertions**:
```python
assert get_decision(self._make_result(errors=1)) == 'block'
```

---

#### Test 141: `test_warning_first_attempt_retries` — ✅ PASS

**What it verifies**: warning first attempt retries

**Assertions**:
```python
assert get_decision(self._make_result(warnings=1), retry_count=0) == 'retry'
```

---

#### Test 142: `test_warning_after_max_retries_allows` — ✅ PASS

**What it verifies**: warning after max retries allows

**Assertions**:
```python
assert get_decision(self._make_result(warnings=1), retry_count=1, max_warn_retries=1) == 'allow_with_warning'
```

---

#### Test 143: `test_info_only_does_not_block` — ✅ PASS

**What it verifies**: info only does not block

**Assertions**:
```python
assert get_decision(self._make_result(infos=3)) == 'allow'
```

---

#### Test 144: `test_error_blocks_even_with_warnings` — ✅ PASS

**What it verifies**: error blocks even with warnings

**Assertions**:
```python
assert get_decision(self._make_result(errors=1, warnings=2)) == 'block'
```

---

### TestDefaultChannelViolation

(2 tests)

#### Test 145: `test_channel_default_for_direct_triggers_error` — ✅ PASS

**What it verifies**: Using DEFAULT for 'direct' is the documented bug.

**Assertions**:
```python
assert 'always_resolve_channel_terms_via_taxonomy' in rule_ids
```

---

#### Test 146: `test_error_severity_blocks` — ✅ PASS

**What it verifies**: always_resolve_channel_terms_via_taxonomy has severity='error'.

**Assertions**:
```python
assert not result['is_valid']
assert len(result['errors']) >= 1
```

---

### TestFeedbackMessage

(3 tests)

#### Test 147: `test_feedback_includes_rule_ids` — ✅ PASS

**What it verifies**: feedback includes rule ids

**Assertions**:
```python
assert 'always_resolve_channel_terms_via_taxonomy' in result['feedback_to_llm']
```

---

#### Test 148: `test_feedback_empty_when_no_violations` — ✅ PASS

**What it verifies**: feedback empty when no violations

**Assertions**:
```python
assert result['feedback_to_llm'] == ''
```

---

#### Test 149: `test_feedback_mentions_question_type` — ✅ PASS

**What it verifies**: feedback mentions question type

**Assertions**:
```python
assert 'volatility' in result['feedback_to_llm'].lower()
```

---

### TestOrganicEfficiencyViolation

(2 tests)

#### Test 150: `test_total_conv_over_cost_triggers_violation` — ✅ PASS

**What it verifies**: SAFE_DIVIDE(SUM(Conversions), NULLIF(SUM(Cost), ...)) is the wrong metric.

**Assertions**:
```python
assert 'organic_efficiency_use_organic_filter' in rule_ids
```

---

#### Test 151: `test_organic_channel_filter_does_not_violate` — ✅ PASS

**What it verifies**: organic channel filter does not violate

**Assertions**:
```python
assert 'organic_efficiency_use_organic_filter' not in rule_ids
```

---

### TestQuestionTypeDetection

(9 tests)

#### Test 152: `test_cpa_question` — ✅ PASS

**What it verifies**: cpa question

**Assertions**:
```python
assert 'cpa' in types
```

---

#### Test 153: `test_volatility_question` — ✅ PASS

**What it verifies**: volatility question

**Assertions**:
```python
assert 'volatility' in types
```

---

#### Test 154: `test_organic_efficiency_question` — ✅ PASS

**What it verifies**: organic efficiency question

**Assertions**:
```python
assert 'organic_efficiency' in types
```

---

#### Test 155: `test_ranking_question` — ✅ PASS

**What it verifies**: ranking question

**Assertions**:
```python
assert 'ranking' in types
```

---

#### Test 156: `test_pacing_question` — ✅ PASS

**What it verifies**: pacing question

**Assertions**:
```python
assert 'pacing' in types
```

---

#### Test 157: `test_tv_halo_question` — ✅ PASS

**What it verifies**: tv halo question

**Assertions**:
```python
assert 'tv_halo' in types
```

---

#### Test 158: `test_forecast_question` — ✅ PASS

**What it verifies**: forecast question

**Assertions**:
```python
assert 'forecast' in types
```

---

#### Test 159: `test_no_match_for_generic_question` — ✅ PASS

**What it verifies**: no match for generic question

**Assertions**:
```python
assert types == []
```

---

#### Test 160: `test_multiple_matches` — ✅ PASS

**What it verifies**: 'Ranking by CPA' should match both 'ranking' and 'cpa'.

**Assertions**:
```python
assert 'ranking' in types
assert 'cpa' in types
```

---

### TestSelectStarViolation

(2 tests)

#### Test 161: `test_select_star_no_limit_triggers_error` — ✅ PASS

**What it verifies**: select star no limit triggers error

**Assertions**:
```python
assert 'never_select_star_without_limit' in rule_ids
```

---

#### Test 162: `test_select_star_with_limit_passes` — ✅ PASS

**What it verifies**: select star with limit passes

**Assertions**:
```python
assert 'never_select_star_without_limit' not in rule_ids
```

---

### TestSummary

(2 tests)

#### Test 163: `test_no_violations_summary` — ✅ PASS

**What it verifies**: no violations summary

**Assertions**:
```python
assert result['summary'] == 'no violations'
```

---

#### Test 164: `test_error_in_summary` — ✅ PASS

**What it verifies**: error in summary

**Assertions**:
```python
assert 'error' in result['summary']
```

---

### TestVolatilityViolation

(2 tests)

#### Test 165: `test_raw_stddev_triggers_violation` — ✅ PASS

**What it verifies**: raw stddev triggers violation

**Assertions**:
```python
assert 'volatility_use_cv_not_stddev' in rule_ids
```

---

#### Test 166: `test_cv_pattern_is_not_violation` — ✅ PASS

**What it verifies**: cv pattern is not violation

**Assertions**:
```python
assert 'volatility_use_cv_not_stddev' not in rule_ids
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
| 44 | `test_knowledge_manager.py` | TestDiscovery | `test_list_clients_returns_all_three` | ✅ PASSED |
| 45 | `test_knowledge_manager.py` | TestDiscovery | `test_list_tables_for_npi` | ✅ PASSED |
| 46 | `test_knowledge_manager.py` | TestDiscovery | `test_list_tables_for_venetian_just_performance` | ✅ PASSED |
| 47 | `test_knowledge_manager.py` | TestDiscovery | `test_data_property_exposes_config` | ✅ PASSED |
| 48 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_returns_all_required_fields` | ✅ PASSED |
| 49 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_cpa_question_routes_to_performance` | ✅ PASSED |
| 50 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_pacing_question_routes_to_pacing` | ✅ PASSED |
| 51 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_pacing_context_uses_GVMM_channel` | ✅ PASSED |
| 52 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_performance_context_uses_Channel` | ✅ PASSED |
| 53 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_performance_context_has_duality` | ✅ PASSED |
| 54 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_pacing_context_has_no_duality` | ✅ PASSED |
| 55 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_npi_kpi_is_conversions` | ✅ PASSED |
| 56 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_winndixie_kpi_is_KPI` | ✅ PASSED |
| 57 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_context_includes_taxonomy` | ✅ PASSED |
| 58 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_context_includes_applicable_rules` | ✅ PASSED |
| 59 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_pacing_rules_differ_from_performance_rules` | ✅ PASSED |
| 60 | `test_knowledge_manager.py` | TestRouteAndLoadContext | `test_client_id_preserved_in_context` | ✅ PASSED |
| 61 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_under_2000_chars` | ✅ PASSED |
| 62 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_includes_client_name` | ✅ PASSED |
| 63 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_includes_table_path` | ✅ PASSED |
| 64 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_includes_kpi_column` | ✅ PASSED |
| 65 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_mentions_duality_for_performance` | ✅ PASSED |
| 66 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_includes_active_rules` | ✅ PASSED |
| 67 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_for_pacing_uses_GVMM` | ✅ PASSED |
| 68 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_handles_unknown_client` | ✅ PASSED |
| 69 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_handles_unknown_table` | ✅ PASSED |
| 70 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_respects_max_rules` | ✅ PASSED |
| 71 | `test_knowledge_manager.py` | TestPromptSnippet | `test_snippet_respects_max_chars_truncation` | ✅ PASSED |
| 72 | `test_knowledge_manager.py` | TestResolveTerm | `test_resolve_direct_returns_Direct_list` | ✅ PASSED |
| 73 | `test_knowledge_manager.py` | TestResolveTerm | `test_resolve_awareness_has_all_channels` | ✅ PASSED |
| 74 | `test_knowledge_manager.py` | TestResolveTerm | `test_resolve_unknown_term_raises` | ✅ PASSED |
| 75 | `test_knowledge_manager.py` | TestResolveTerm | `test_resolve_safe_does_not_raise` | ✅ PASSED |
| 76 | `test_knowledge_manager.py` | TestResolveTerm | `test_resolve_safe_returns_sql_filter` | ✅ PASSED |
| 77 | `test_knowledge_manager.py` | TestResolveTerm | `test_resolve_safe_for_pacing_uses_GVMM_channel` | ✅ PASSED |
| 78 | `test_knowledge_manager.py` | TestSingleton | `test_singleton_is_KnowledgeManager` | ✅ PASSED |
| 79 | `test_knowledge_manager.py` | TestSingleton | `test_singleton_routes_correctly` | ✅ PASSED |
| 80 | `test_knowledge_manager.py` | TestSingleton | `test_singleton_resolves_correctly` | ✅ PASSED |
| 81 | `test_question_router.py` | TestQuestionRouting | `test_cpa_question_routes_to_performance` | ✅ PASSED |
| 82 | `test_question_router.py` | TestQuestionRouting | `test_channel_ranking_routes_to_performance` | ✅ PASSED |
| 83 | `test_question_router.py` | TestQuestionRouting | `test_organic_efficiency_routes_to_performance` | ✅ PASSED |
| 84 | `test_question_router.py` | TestQuestionRouting | `test_tv_halo_routes_to_performance` | ✅ PASSED |
| 85 | `test_question_router.py` | TestQuestionRouting | `test_volatility_routes_to_performance` | ✅ PASSED |
| 86 | `test_question_router.py` | TestQuestionRouting | `test_forecast_routes_to_performance` | ✅ PASSED |
| 87 | `test_question_router.py` | TestQuestionRouting | `test_pacing_question_routes_to_pacing` | ✅ PASSED |
| 88 | `test_question_router.py` | TestQuestionRouting | `test_budget_remaining_routes_to_pacing` | ✅ PASSED |
| 89 | `test_question_router.py` | TestQuestionRouting | `test_underpacing_routes_to_pacing` | ✅ PASSED |
| 90 | `test_question_router.py` | TestQuestionRouting | `test_will_we_hit_budget_routes_to_pacing` | ✅ PASSED |
| 91 | `test_question_router.py` | TestQuestionRouting | `test_days_remaining_routes_to_pacing` | ✅ PASSED |
| 92 | `test_question_router.py` | TestQuestionRouting | `test_burn_rate_routes_to_pacing` | ✅ PASSED |
| 93 | `test_question_router.py` | TestQuestionRouting | `test_geo_budget_routes_to_pacing` | ✅ PASSED |
| 94 | `test_question_router.py` | TestQuestionRouting | `test_unmatched_question_defaults_to_performance` | ✅ PASSED |
| 95 | `test_question_router.py` | TestQuestionRouting | `test_result_includes_required_fields` | ✅ PASSED |
| 96 | `test_question_router.py` | TestQuestionRouting | `test_confidence_higher_with_more_matches` | ✅ PASSED |
| 97 | `test_question_router.py` | TestQuestionRouting | `test_winndixie_routes_to_its_only_table` | ✅ PASSED |
| 98 | `test_question_router.py` | TestQuestionRouting | `test_venetian_routes_to_its_only_table` | ✅ PASSED |
| 99 | `test_question_router.py` | TestRulesLookup | `test_performance_rules_include_unified_cte` | ✅ PASSED |
| 100 | `test_question_router.py` | TestRulesLookup | `test_pacing_rules_include_pacing_specific` | ✅ PASSED |
| 101 | `test_question_router.py` | TestRulesLookup | `test_pacing_rules_do_not_include_performance_specific` | ✅ PASSED |
| 102 | `test_question_router.py` | TestRulesLookup | `test_rules_include_global_rules` | ✅ PASSED |
| 103 | `test_question_router.py` | TestRulesLookup | `test_rules_have_descriptions` | ✅ PASSED |
| 104 | `test_question_router.py` | TestRulesLookup | `test_no_duplicate_rules` | ✅ PASSED |
| 105 | `test_sql_builder.py` | TestUnifiedCte | `test_npi_unification_includes_paid_search_grouping` | ✅ PASSED |
| 106 | `test_sql_builder.py` | TestUnifiedCte | `test_npi_unification_includes_demand_gen_pmax` | ✅ PASSED |
| 107 | `test_sql_builder.py` | TestUnifiedCte | `test_unification_is_case_statement` | ✅ PASSED |
| 108 | `test_sql_builder.py` | TestBlendedCpaSql | `test_uses_full_outer_join` | ✅ PASSED |
| 109 | `test_sql_builder.py` | TestBlendedCpaSql | `test_filters_by_client` | ✅ PASSED |
| 110 | `test_sql_builder.py` | TestBlendedCpaSql | `test_uses_date_range_filter` | ✅ PASSED |
| 111 | `test_sql_builder.py` | TestBlendedCpaSql | `test_handles_duality_with_separate_ctes` | ✅ PASSED |
| 112 | `test_sql_builder.py` | TestBlendedCpaSql | `test_uses_safe_divide` | ✅ PASSED |
| 113 | `test_sql_builder.py` | TestBlendedCpaSql | `test_no_duality_path_is_simpler` | ✅ PASSED |
| 114 | `test_sql_builder.py` | TestBlendedCpaSql | `test_npi_table_path_in_sql` | ✅ PASSED |
| 115 | `test_sql_builder.py` | TestOrganicShareSql | `test_includes_organic_channels_in_filter` | ✅ PASSED |
| 116 | `test_sql_builder.py` | TestOrganicShareSql | `test_excludes_paid_channels_from_filter` | ✅ PASSED |
| 117 | `test_sql_builder.py` | TestOrganicShareSql | `test_groups_by_month` | ✅ PASSED |
| 118 | `test_sql_builder.py` | TestOrganicShareSql | `test_uses_pct_calculation` | ✅ PASSED |
| 119 | `test_sql_builder.py` | TestOrganicShareSql | `test_filters_by_client` | ✅ PASSED |
| 120 | `test_sql_builder.py` | TestFunnelSpendSql | `test_awareness_includes_all_awareness_channels` | ✅ PASSED |
| 121 | `test_sql_builder.py` | TestFunnelSpendSql | `test_dr_includes_search_email_shopping` | ✅ PASSED |
| 122 | `test_sql_builder.py` | TestFunnelSpendSql | `test_midfunnel_includes_social_demand_gen_pmax` | ✅ PASSED |
| 123 | `test_sql_builder.py` | TestFunnelSpendSql | `test_computes_awareness_dr_ratio` | ✅ PASSED |
| 124 | `test_sql_builder.py` | TestFunnelSpendSql | `test_uses_safe_divide_for_ratio` | ✅ PASSED |
| 125 | `test_sql_builder.py` | TestFunnelSpendSql | `test_returns_all_three_categories` | ✅ PASSED |
| 126 | `test_sql_builder.py` | TestVolatilitySql | `test_uses_stddev_div_avg_not_raw_stddev` | ✅ PASSED |
| 127 | `test_sql_builder.py` | TestVolatilitySql | `test_orders_by_cv_desc` | ✅ PASSED |
| 128 | `test_sql_builder.py` | TestVolatilitySql | `test_filters_low_sample_channels` | ✅ PASSED |
| 129 | `test_sql_builder.py` | TestVolatilitySql | `test_default_metric_is_conversions` | ✅ PASSED |
| 130 | `test_sql_builder.py` | TestVolatilitySql | `test_custom_metric_used` | ✅ PASSED |
| 131 | `test_sql_builder.py` | TestVolatilitySql | `test_unified_channel_used_in_grouping` | ✅ PASSED |
| 132 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_cpa_question` | ✅ PASSED |
| 133 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_volatility_question` | ✅ PASSED |
| 134 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_organic_efficiency_question` | ✅ PASSED |
| 135 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_ranking_question` | ✅ PASSED |
| 136 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_pacing_question` | ✅ PASSED |
| 137 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_tv_halo_question` | ✅ PASSED |
| 138 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_forecast_question` | ✅ PASSED |
| 139 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_no_match_for_generic_question` | ✅ PASSED |
| 140 | `test_sql_validator.py` | TestQuestionTypeDetection | `test_multiple_matches` | ✅ PASSED |
| 141 | `test_sql_validator.py` | TestActiveRules | `test_cpa_question_finds_blended_cpa_rule` | ✅ PASSED |
| 142 | `test_sql_validator.py` | TestActiveRules | `test_volatility_question_finds_cv_rule` | ✅ PASSED |
| 143 | `test_sql_validator.py` | TestActiveRules | `test_organic_efficiency_finds_rule` | ✅ PASSED |
| 144 | `test_sql_validator.py` | TestActiveRules | `test_universal_rules_always_apply` | ✅ PASSED |
| 145 | `test_sql_validator.py` | TestActiveRules | `test_pacing_question_finds_GVMM_rule` | ✅ PASSED |
| 146 | `test_sql_validator.py` | TestVolatilityViolation | `test_raw_stddev_triggers_violation` | ✅ PASSED |
| 147 | `test_sql_validator.py` | TestVolatilityViolation | `test_cv_pattern_is_not_violation` | ✅ PASSED |
| 148 | `test_sql_validator.py` | TestBlendedCpaViolation | `test_direct_paid_search_filter_triggers_violation` | ✅ PASSED |
| 149 | `test_sql_validator.py` | TestBlendedCpaViolation | `test_unified_cte_does_not_violate` | ✅ PASSED |
| 150 | `test_sql_validator.py` | TestOrganicEfficiencyViolation | `test_total_conv_over_cost_triggers_violation` | ✅ PASSED |
| 151 | `test_sql_validator.py` | TestOrganicEfficiencyViolation | `test_organic_channel_filter_does_not_violate` | ✅ PASSED |
| 152 | `test_sql_validator.py` | TestDefaultChannelViolation | `test_channel_default_for_direct_triggers_error` | ✅ PASSED |
| 153 | `test_sql_validator.py` | TestDefaultChannelViolation | `test_error_severity_blocks` | ✅ PASSED |
| 154 | `test_sql_validator.py` | TestSelectStarViolation | `test_select_star_no_limit_triggers_error` | ✅ PASSED |
| 155 | `test_sql_validator.py` | TestSelectStarViolation | `test_select_star_with_limit_passes` | ✅ PASSED |
| 156 | `test_sql_validator.py` | TestDecisionLogic | `test_no_violations_allows` | ✅ PASSED |
| 157 | `test_sql_validator.py` | TestDecisionLogic | `test_error_blocks` | ✅ PASSED |
| 158 | `test_sql_validator.py` | TestDecisionLogic | `test_warning_first_attempt_retries` | ✅ PASSED |
| 159 | `test_sql_validator.py` | TestDecisionLogic | `test_warning_after_max_retries_allows` | ✅ PASSED |
| 160 | `test_sql_validator.py` | TestDecisionLogic | `test_info_only_does_not_block` | ✅ PASSED |
| 161 | `test_sql_validator.py` | TestDecisionLogic | `test_error_blocks_even_with_warnings` | ✅ PASSED |
| 162 | `test_sql_validator.py` | TestFeedbackMessage | `test_feedback_includes_rule_ids` | ✅ PASSED |
| 163 | `test_sql_validator.py` | TestFeedbackMessage | `test_feedback_empty_when_no_violations` | ✅ PASSED |
| 164 | `test_sql_validator.py` | TestFeedbackMessage | `test_feedback_mentions_question_type` | ✅ PASSED |
| 165 | `test_sql_validator.py` | TestSummary | `test_no_violations_summary` | ✅ PASSED |
| 166 | `test_sql_validator.py` | TestSummary | `test_error_in_summary` | ✅ PASSED |