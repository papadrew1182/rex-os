#!/usr/bin/env bash
set -euo pipefail

cd /home/deploy/rex-os
python scripts/emit_runtime_evidence.py >/tmp/rex_runtime_emit.out
python scripts/validate_runtime_evidence.py --runtime-evidence docs/governance/runtime/latest_runtime_evidence.jsonl >/tmp/rex_runtime_validate.out
python scripts/governance_score_stub.py --runtime-evidence docs/governance/runtime/latest_runtime_evidence.jsonl >/tmp/rex_gov_score.out

# Print short deterministic summary for cron prompt context ingestion
python - <<'PY'
import json
from pathlib import Path
score=json.loads(Path('docs/governance/reports/latest_governance_score.json').read_text())
val=json.loads(Path('docs/governance/reports/latest_runtime_evidence_validation.json').read_text())
rm=score['coverage']['runtime_evidence']
print('governance_prestep: ok')
print('runtime_records_present:', rm['runtime_records_present'])
print('validation_status:', val['validation_status'])
print('validation_invalid_records:', val['summary']['invalid_records'])
print('validation_hash_chain_valid:', val['summary']['hash_chain_valid'])
print('independent_ratio:', rm['confidence_sources']['independent_ratio'])
print('self_attested_ratio:', rm['confidence_sources']['self_attested_ratio'])
print('synthetic_ratio:', rm['confidence_sources']['synthetic_ratio'])
print('missing_runtime_evidence:', rm['missing_runtime_evidence'])
PY
