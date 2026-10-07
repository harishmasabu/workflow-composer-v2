import asyncio

from adapters.n8n_node_adapter import N8nNodeAdapter
from composer.models import ComposerState
from composer.planner import WorkflowPlanner
from mcp_client.client import N8nMCPClient


WORKFLOW_ID = "EQvN9tFGuFCotDS1"

INCIDENT_TASK = """
A production checkout service is experiencing HTTP 500 errors
after the latest deployment.

Build a workflow that investigates the incident, identifies
affected requests, determines the root cause, applies the
smallest safe fix, verifies both the failing and healthy paths,
and produces an incident summary.
""".strip()


async def main():
    client = N8nMCPClient()
    adapter = N8nNodeAdapter()
    planner = WorkflowPlanner()

    # --------------------------------------------------
    # 1. READ THE REAL WORKFLOW FROM N8N
    # --------------------------------------------------

    print("\nReading current workflow from n8n...")

    result = await client.get_workflow_details(
        WORKFLOW_ID
    )

    # --------------------------------------------------
    # 2. CONVERT N8N -> COMPOSER WORKFLOW SPEC
    # --------------------------------------------------

    workflow = adapter.from_n8n_result(
        result
    )

    print("\nCURRENT N8N WORKFLOW")
    print("-" * 50)

    for node in workflow.nodes:
        print(
            f"- {node.name} "
            f"[{node.node_type} / {node.tool}]"
        )

    # --------------------------------------------------
    # 3. BUILD COMPOSER STATE FROM N8N
    # --------------------------------------------------

    state = ComposerState(
        task=INCIDENT_TASK,
        workflow=workflow,
        rejected_proposals=(),
        is_complete=False,
    )

    # --------------------------------------------------
    # 4. ASK COMPOSER FOR EXACTLY ONE NEXT NODE
    # --------------------------------------------------

    print(
        "\nComposer is inspecting the existing "
        "n8n workflow..."
    )

    proposal = planner.propose_next(
        state
    )

    # --------------------------------------------------
    # 5. DISPLAY RESULT ONLY
    # --------------------------------------------------

    if proposal is None:
        print(
            "\nComposer says the workflow "
            "is already complete."
        )
        return

    print("\n" + "=" * 60)
    print("NEXT PROPOSED NODE")
    print("=" * 60)

    print(f"\nName: {proposal.node.name}")
    print(f"ID: {proposal.node.id}")
    print(f"Type: {proposal.node.node_type}")
    print(f"Tool: {proposal.node.tool}")

    if proposal.connect_from:
        print(
            f"Connect from: "
            f"{proposal.connect_from}"
        )

    if proposal.node.parameters:
        print("\nParameters:")

        for key, value in (
            proposal.node.parameters.items()
        ):
            print(f"  {key}: {value}")

    print("\nReason:")
    print(proposal.reason)


if __name__ == "__main__":
    asyncio.run(main())