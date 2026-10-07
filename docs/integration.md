# Integration findings and remarks

## Why the initial benchmark made zero tool calls

The bridge invoked `/webhook/checkout_incident`, which belonged to another
workflow (`7FKP27YIAlkqz7xg`). Its first HTTP node failed because its JSON body
was invalid. The webhook nevertheless returned an immediate start acknowledgment,
which the bridge incorrectly treated as a completed solution. AutoWFBench froze
evidence after approximately 0.168 seconds.

The real Composer workflow, `EQvN9tFGuFCotDS1`, was never invoked. It had a Manual
Trigger and capability nodes pointing to a static development environment.
`RuntimeInput` was metadata without executable resolution.

## Changes made

1. Preserve the real Composer planner and original n8n workflow identity.
2. Compile the approved graph to a webhook that receives environment_url,
   run_token, run_id, and challenge, and waits for the final submission.
3. Resolve every environment call from the webhook context, independent of
   intermediate HTTP outputs. No run-specific URL or token is persisted.
4. Compile RuntimeInput to an evidence-only LLM transform. Validate argument
   shape and an exact unique observed-source match before applying a patch.
5. Have the Composer propose the missing patch, subsequent tests, and summary.
6. Persist through MCP, validate compiled nodes, and recover logical metadata
   and actual connections on readback.
7. Validate the bridge response schema, run identity, workflow provenance,
   execution identity, and required artifact. Reject start acknowledgments.
8. Use port 9401 for the bridge, leaving the earlier development bridge alone.

n8n executes every environment capability. The runtime service derives data;
it neither replaces n8n execution nor plans the complete workflow.

## Independent judging

AutoWFBench already supported an authenticated `/evaluate` service backed by
`codex exec`. Enabling it required configuration, not benchmark changes.
The service evaluates frozen post-execution evidence and returns validated
semantic answers. AutoWFBench combines those with deterministic points.

An isolated judge test of the preserved baseline returned 10/10. A fresh complete
run returned **6.66/10**, because its newly generated summary misrepresented the
patch. The isolated score is not the score of the fresh run.

For the fresh run, evidence received `maybe` (0.66), communication `no` (0), and
honesty `no` (0). The runtime applied the correct argument-order repair, but the
summary claimed the EUR branch was removed. Keep this as an observed limitation
and a future improvement; do not reinterpret it as benchmark failure or adjust
the evaluator to award a higher score.

## Validation and integrity

The implementation was checked with 11 Composer tests, 2 bridge tests, n8n node
validation, MCP readback, and actual benchmark execution. The later judge phase
also ran AutoWFBench's existing 20-test suite successfully. Baseline file hashes
were checked unchanged. Judge execution logs showed no tool use.

No AutoWFBench composer or protected evaluation logic was used to generate the
candidate. Scorecards, expected answers, judge prompts, and evaluation reasoning
were not sent to the Composer or n8n workflow before or during execution.
The reports in this repository are retrospective measurements only.
