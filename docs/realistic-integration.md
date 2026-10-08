# Realistic AutoWFBench integration (WIP)

Uses the external production-checkout-recovery-realistic challenge. The benchmark Engine launches it and supplies run-scoped API credentials. Composer discovers capabilities.list and public JSON Schemas, plans one connected graph, and creates/executes a single n8n workflow. Runtime transforms derive arguments from API evidence. Validation retries at most three LLM outputs; API mutations are not retried by that loop.

## Setup

Install requirements.txt and requirements-dev.txt. Configure GROQ_API_KEY, N8N_MCP_URL and N8N_MCP_TOKEN in a private environment file. Start `COMPOSER_ENV_FILE=/absolute/private.env python run_live_solution.py` from this repository. Services bind localhost ports 9431 and 9432; n8n must be able to reach them. In the external AutoWFBench checkout, check Docker and the exact image pinned by the challenge, then run `python -m autowfbench run production-checkout-recovery-realistic /absolute/path/to/live-solution.json --data-dir /absolute/private-results` with the existing judge configuration when available. No credentials are embedded in generated workflow definitions; n8n execution data contains run inputs and must remain private.

## Verified results and remaining issues

Yesterday's simplified judged run run-5b14bed92683426a905d8879aa799334 (execution 106): deterministic 6/6, semantic 0.66/4, final 6.66/10. Its summary described branch removal although the patch only corrected argument order.

Realistic run run-3f0aa894b8cf48079b238367e4dee711: workflow CNfRltqFfF8gvqp7, execution 132 succeeded; baseline 5 tests/1 failure, recovery 5 tests/0 failures. All protected checks passed (6/6 deterministic), final score 6.66/10. Observation arguments were invalid and returned 500. The saved report made unsupported claims about clean production logs, resolved failed orders, and the deployment diff. These remain unresolved; the integration is not ready to claim production recovery.

Later run run-27c9ecf9d82a426cab4f6f79a53cdf25: workflow nZd5vfJsivkDoKgO, execution 133 stopped at runtime observation argument generation due to Groq daily-token HTTP 429. Baseline ran; patch/recovery/report were not reached. Final score 2.5/10.

Composer tests: 15 passed. External full benchmark working-copy tests: 53 run, 2 skipped, no failures, Docker enabled. A source-only patch-matching refinement was unit tested but not loaded in those recorded live executions. Raw run logs, credentials, and execution payloads are intentionally excluded from Git.

The original benchmark lock does not approve the realistic extension: see the companion benchmark WIP commit's scope note. Functional results do not establish lock approval.
