# Astrobot Reliability Test Results

| Test | Question | Truth | Agent Said | Pass/Fail |
|---|---|---|---|---|
| test_01_blended_cpa | Nov/Dec CPA for 3 channels | $15.93/$6.66/$9.31/$3.26/$5.24/$6.38 | (paste agent answer) | ✅/❌ |
| test_02_worst_channels | Bottom 3 channels by conv/$ | Online Audio, Print, OOH | (paste agent answer) | ✅/❌ |
| test_03_organic_pct | Highest % organic month | 2025-06 (61.3%) | (paste agent answer) | ✅/❌ |
| test_04_tv_lift | TV vs Paid Search corr | ~0.68 | (paste agent answer) | ✅/❌ |
| test_05_no_zero_hallucination | All months should have spend | Multiple months $200K-$1.2M | (paste agent answer) | ✅/❌ |

## Test Procedure
1. Restart adk: `pkill -f "adk web"; sleep 2; rm -f ~/astrobot_mesh/data_science/.adk/session.db; cd ~/astrobot_mesh; adk web --allow_origins="*"`
2. For each test, open NEW session and ask the question
3. Capture answer
4. Update this table
