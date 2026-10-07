from composer.models import (
    CapabilityContract,
    ComposerState,
    EnvironmentContext,
    WorkflowNode,
    WorkflowSpec,
)
from composer.planner import WorkflowPlanner
from composer.validator import WorkflowValidator


TASK = """
Investigate a production checkout incident affecting some transactions.
Use available source, deployment and failure evidence to identify the
root cause and impact. Apply the smallest appropriate correction,
verify affected and previously working behavior, and write an incident
summary including root cause, impact, fix, and verification.
Do not disable payment validation.
""".strip()


environment = EnvironmentContext(
    base_url="http://127.0.0.1:49446",
    access_token="test-run-token",
    capability_contracts=(
        CapabilityContract(
            name="incident.read",
            argument_schema={},
            description=(
                "Read failed orders, deployment evidence, "
                "and patch restrictions."
            ),
        ),
        CapabilityContract(
            name="source.read",
            argument_schema={},
            description="Read the checkout source code.",
        ),
        CapabilityContract(
            name="checkout.patch",
            argument_schema={
                "old": {
                    "type": "string",
                    "description": "Exact existing source fragment.",
                },
                "new": {
                    "type": "string",
                    "description": "Replacement source fragment.",
                },
            },
            description=(
                "Apply a minimal source patch. "
                "The old fragment must occur exactly once."
            ),
        ),
        CapabilityContract(
            name="tests.run",
            argument_schema={},
            description="Run the checkout simulator tests.",
        ),
    ),
)


# Pretend the trigger is already approved.
workflow = WorkflowSpec(
    name="Production Checkout Recovery",
    description="Recover the production checkout incident.",
    nodes=(
        WorkflowNode(
            id="start",
            name="Incident Detected",
            node_type="trigger",
            tool=None,
            parameters={},
        ),
    ),
    connections=(),
)


state = ComposerState(
    task=TASK,
    workflow=workflow,
    environment=environment,
)


planner = WorkflowPlanner()

proposal = planner.propose_next(state)

if proposal is None:
    print("Composer says workflow is already complete.")
    raise SystemExit(0)


print("\n=== COMPOSER PROPOSAL ===")
print(f"Name:          {proposal.node.name}")
print(f"Capability:    {proposal.node.tool}")
print(f"Arguments:     {proposal.node.parameters}")
print(f"Runtime input: {proposal.node.runtime_input}")
print(f"Connect from:  {proposal.connect_from}")
print(f"Reason:        {proposal.reason}")


# Validate the proposed workflow as if the node were approved.
candidate = WorkflowSpec(
    name=workflow.name,
    description=workflow.description,
    nodes=workflow.nodes + (proposal.node,),
    connections=workflow.connections,
)

result = WorkflowValidator().validate(
    candidate,
    capabilities=environment.capabilities,
)

print("\n=== VALIDATION ===")
print(f"Valid: {result.is_valid}")

if result.errors:
    for error in result.errors:
        print(f"- {error}")
