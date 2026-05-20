#!/usr/bin/env bash
set -euo pipefail

cd /home/deploy/rex-os
python scripts/emit_runtime_evidence.py >/tmp/rex_runtime_emit.out
python scripts/governance_score_stub.py --runtime-evidence docs/governance/runtime/latest_runtime_evidence.jsonl >/tmp/rex_gov_score.out

# Print short, deterministic context summary for cron prompt context ingestion
python - <<'PY'
import json
from pathlib import Path
p=Path('docs/governance/reports/latest_governance_score.json')
d=json.loads(p.read_text())
rm=d['coverage']['runtime_evidence']
print('governance_prestep: ok')
print('runtime_records_present:', rm['runtime_records_present'])
print('independent_ratio:', rm['confidence_sources']['independent_ratio'])
print('self_attested_ratio:', rm['confidence_sources']['self_attested_ratio'])
print('synthetic_ratio:', rm['confidence_sources']['synthetic_ratio'])
print('missing_runtime_evidence:', rm['missing_runtime_evidence'])
PY
