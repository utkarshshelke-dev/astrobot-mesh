#!/bin/bash
# ============================================================
# Diagnose LLM judge failures
# Usage: ./diagnose_judge.sh <path-to-eval_results-dir>
#   e.g. ./diagnose_judge.sh data_science/eval_results
# ============================================================
set -u
ROOT="${1:-data_science/eval_results}"

if [ ! -d "$ROOT" ]; then
  echo "ERROR: $ROOT not found"; exit 1
fi

echo "============================================================"
echo "  Judge diagnostics — scanning: $ROOT"
echo "============================================================"

# Collect all judge_results.jsonl across runs
mapfile -t FILES < <(find "$ROOT" -name "judge_results.jsonl" -type f | sort)
if [ "${#FILES[@]}" -eq 0 ]; then
  echo "No judge_results.jsonl files found. Did you run the eval yet?"
  exit 1
fi

echo ""
echo "Found ${#FILES[@]} judge result file(s):"
printf '  %s\n' "${FILES[@]}"
echo ""

# Concatenate for analysis
TMP=$(mktemp)
cat "${FILES[@]}" > "$TMP"
TOTAL=$(wc -l < "$TMP")
echo "Total judge records: $TOTAL"
echo ""

# ── 1. Extraction failures (response_preview is empty or starts with '(') ──
echo "─── [1] Extraction failures (judge scored garbage) ───"
EXTRACT_FAIL=$(python3 -c "
import json, sys
fails = 0
samples = []
for line in open('$TMP'):
    try:
        r = json.loads(line)
        prev = (r.get('response_preview') or '').strip()
        if not prev or prev.startswith('(') or len(prev) < 30:
            fails += 1
            if len(samples) < 5:
                samples.append((r.get('eval_json','?'), r.get('verdict','?'), prev[:80]))
    except: pass
print(fails)
for s in samples:
    print('  SAMPLE:', s)
")
echo "$EXTRACT_FAIL"
echo ""

# ── 2. Judge model used (preview vs stable) ──
echo "─── [2] Judge model distribution ───"
python3 -c "
import json
from collections import Counter
c = Counter()
for line in open('$TMP'):
    try:
        r = json.loads(line)
        c[r.get('judge_model') or 'NULL'] += 1
    except: pass
for m, n in c.most_common():
    flag = '  ⚠️ preview/unstable' if 'preview' in m or m == 'NULL' or m == 'unavailable' else ''
    print(f'  {n:4d}  {m}{flag}')
"
echo ""

# ── 3. Verdict distribution by category ──
echo "─── [3] Verdict distribution by category ───"
python3 -c "
import json
from collections import Counter
c = Counter()
for line in open('$TMP'):
    try:
        r = json.loads(line)
        c[(r.get('category','?'), r.get('verdict','?'))] += 1
    except: pass
for (cat, v), n in sorted(c.items()):
    print(f'  {cat:10s} {v:15s} {n}')
"
echo ""

# ── 4. NPI ground-truth bias: non-NPI clients flagged as hallucinating ──
echo "─── [4] Cross-client bias (non-NPI evals with low hallucination scores) ───"
python3 -c "
import json
hits = []
for line in open('$TMP'):
    try:
        r = json.loads(line)
        ej = (r.get('eval_json') or '').lower()
        # non-NPI eval files: chase, duality, venetian, winn
        if any(x in ej for x in ['chase','duality','venetian','winn']):
            h = r.get('scores',{}).get('hallucination_score')
            if isinstance(h,(int,float)) and h < 5:
                hits.append((ej, h, r.get('verdict'), (r.get('reason') or '')[:80]))
    except: pass
if not hits:
    print('  none detected')
else:
    print(f'  ⚠️  {len(hits)} non-NPI evals scored as hallucinating — likely NPI ground-truth bias')
    for h in hits[:8]:
        print(f'    {h}')
"
echo ""

# ── 5. Rule-based vs judge disagreement (need source CSV) ──
echo "─── [5] Rule-verdict vs judge-verdict disagreement ───"
mapfile -t CSVS < <(find "$ROOT" -name "results.csv" -type f | sort)
if [ "${#CSVS[@]}" -gt 0 ]; then
  python3 -c "
import csv
disagree = 0
samples = []
for f in '''$(printf '%s\n' "${CSVS[@]}")'''.strip().split('\n'):
    try:
        for row in csv.DictReader(open(f)):
            rv = row.get('verdict','')
            jv = row.get('judge_verdict','')
            if rv and jv and jv not in ('N/A','UNAVAILABLE',''):
                rule_pass = rv in ('PASS','PASS_REFUSED','PASS_REFUSED_SOFT')
                judge_pass = jv == 'PASS'
                if rule_pass != judge_pass:
                    disagree += 1
                    if len(samples) < 5:
                        samples.append((row.get('test_name',''), rv, jv, (row.get('judge_reason','') or '')[:60]))
    except Exception as e:
        pass
print(f'  Disagreements: {disagree}')
for s in samples:
    print(f'    {s}')
"
else
  echo "  (no results.csv files to compare)"
fi
echo ""

# ── 6. UNAVAILABLE / N/A verdicts (Vertex call failed) ──
echo "─── [6] Judge unavailable / API failures ───"
python3 -c "
import json
n = 0
for line in open('$TMP'):
    try:
        r = json.loads(line)
        if r.get('verdict') in ('UNAVAILABLE','N/A',None):
            n += 1
    except: pass
print(f'  {n} records with no judge verdict')
"
echo ""

rm -f "$TMP"
echo "============================================================"
echo "  Done. Run ./apply_judge_fix.sh to apply patches."
echo "============================================================"