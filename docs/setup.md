# Local setup and reproduction

## Requirements

- Python 3.11+ and the dependencies in requirements-dev.txt.
- A running n8n instance exposing the MCP tools used by mcp_client/client.py.
- The existing workflow identified by WORKFLOW_ID in run_integrated_demo.py.
  To target your own instance, provision a Composer workflow and deliberately
  align that ID with WORKFLOW_ID in integrations/autowfbench/n8n_solution.py.
- A local AutoWFBench checkout with its own prepared Python environment.
- Groq credentials in the Composer's ignored .env file.
- For semantic evaluation: an authenticated Codex CLI and supported explicit model.

The dependency versions are those installed during verification. They are not
claims about minimum supported versions. The bridge imports AutoWFBench's
submission validator as an external dependency; the benchmark is not vendored.

## Composer and candidate services

Run commands from this repository root. Copy .env.example to .env, fill in the
secrets, and confirm the MCP URL against your n8n instance.

Start the evidence transform service:

```sh
.venv/bin/python runtime_service.py
```

In another terminal, point at your external benchmark checkout and start the
candidate bridge. This uses the benchmark's existing environment, without editing
its files:

```sh
export AUTOWFBENCH_ROOT=/absolute/path/to/AutoWFBench
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$AUTOWFBENCH_ROOT" \
  "$AUTOWFBENCH_ROOT/.venv/bin/python" integrations/autowfbench/n8n_solution.py
```

The service ports are 9410 (runtime transforms) and 9401 (solution bridge).
Keep both services running for benchmark execution.

To propose, approve, compile, persist, and publish the workflow:

```sh
.venv/bin/python run_integrated_demo.py --publish
```

This asks for approval of new proposals. Use `--approve --publish` only when
explicitly approving validated proposals noninteractively. The compiler updates
the selected existing workflow atomically through MCP. It does not create a
separate handcrafted solution. Generated snapshots go into ignored work/.

## Existing AutoWFBench judge

No new judge implementation is required. Use AutoWFBench's built-in `codex` mode.
The integration was verified with `gpt-6-sol`. Authenticate the Codex CLI first.

Create an ignored configuration file for engine/judge use only:

```sh
mkdir -p work
python3 - <<'PY'
import secrets
from pathlib import Path
p = Path('work/judge.env')
if p.exists():
    raise SystemExit('Judge configuration already exists; reuse it.')
p.write_text('export AWB_JUDGE_TOKEN=' + secrets.token_urlsafe(32) + '\n'
             'export AWB_JUDGE_MODEL=gpt-6-sol\n'
             'export AWB_JUDGE_URL=http://127.0.0.1:9100\n')
p.chmod(0o600)
PY
```

Do not source this file in the Composer, runtime transform, or n8n process.
In a separate judge terminal, from this repository:

```sh
export AUTOWFBENCH_ROOT=/absolute/path/to/AutoWFBench
source work/judge.env
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$AUTOWFBENCH_ROOT" \
  "$AUTOWFBENCH_ROOT/.venv/bin/python" -m autowfbench judge \
  --port 9100 --data-dir "$PWD/work/judge"
```

In a separate engine terminal, also from this repository:

```sh
export AUTOWFBENCH_ROOT=/absolute/path/to/AutoWFBench
source work/judge.env
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$AUTOWFBENCH_ROOT" \
  "$AUTOWFBENCH_ROOT/.venv/bin/python" -m autowfbench run \
  production-checkout-recovery integrations/autowfbench/n8n-generated-solution.json \
  --judge-url http://127.0.0.1:9100 --data-dir "$PWD/work/runs"
```

New judge evidence and run results stay outside the benchmark checkout. Inspect
result.json, run-log.json, and scorecard-result.json; an exit code alone is not
proof of successful execution or judging. Without a judge URL, the benchmark
leaves the total null until independent judging is completed.

Keep full benchmark evidence separate from composition input. Do not put judge
criteria or evaluator output into the planner context to improve a measured run.
