What to query — in this order
1. Verify it's connected (no BQ call)
What data do you have access to?
Should describe all 3 clients and their datasets.

2. Basic BQ query — NPI
Show me total spend and clicks by channel for NPI

3. Basic BQ query — Venetian
What are the top 5 campaigns by spend for Venetian?

4. Basic BQ query — WinnDixie
Show me total ViVs by campaign for WinnDixie

5. Pacing (uses the pre-built JOIN SQL)
Show me current month pacing for NPI

6. Channel efficiency audit
Run a channel efficiency CPA audit for NPI

7. Daily trend + chart (uses analytics agent + Code Interpreter)
Plot daily spend trend for NPI as a line chart by channel

8. Device breakdown
Show me cost and clicks split by device for NPI

9. BQML forecast (only if RAG corpus is set up)
I want to forecast NPI spend for the next 14 days using ARIMA

10. Anomaly detection (z-score fallback, no model needed)
Detect any spend anomalies for NPI using z-score method