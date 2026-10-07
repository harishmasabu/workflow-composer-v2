from __future__ import annotations

import asyncio

from adapters.n8n_node_adapter import N8nNodeAdapter
from composer.models import (
    ComposerState,
    RejectedProposal,
)
from composer.planner import WorkflowPlanner
from composer.validator import WorkflowValidator
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


def print_workflow(workflow):
    """Display the workflow currently persisted in n8n."""

    print("\nCURRENT N8N WORKFLOW")
    print("-" * 55)

    if not workflow.nodes:
        print("(empty)")
        return

    for index, node in enumerate(
        workflow.nodes,
        start=1,
    ):
        print(
            f"{index}. {node.name} "
            f"[{node.node_type} / {node.tool}]"
        )

    if workflow.connections:
        print("\nConnections:")

        for connection in workflow.connections:
            source = workflow.get_node(
                connection.source
            )

            target = workflow.get_node(
                connection.target
            )

            source_name = (
                source.name
                if source
                else connection.source
            )

            target_name = (
                target.name
                if target
                else connection.target
            )

            print(
                f"  {source_name}"
                f" -> "
                f"{target_name}"
            )


async def read_current_state(
    client: N8nMCPClient,
    adapter: N8nNodeAdapter,
    rejected_proposals,
) -> ComposerState:
    """
    Read the real workflow from n8n and build the
    Composer state from that persisted workflow.
    """

    result = await client.get_workflow_details(
        WORKFLOW_ID
    )

    workflow = adapter.from_n8n_result(
        result
    )

    return ComposerState(
        task=INCIDENT_TASK,
        workflow=workflow,
        rejected_proposals=rejected_proposals,
        is_complete=False,
    )


async def main():
    client = N8nMCPClient()
    adapter = N8nNodeAdapter()
    planner = WorkflowPlanner()
    validator = WorkflowValidator()

    rejected_proposals = ()

    print("\n" + "=" * 60)
    print("AI WORKFLOW COMPOSER")
    print("=" * 60)

    print("\nTASK")
    print(INCIDENT_TASK)

    print(
        f"\nConnected n8n workflow: {WORKFLOW_ID}"
    )

    while True:

        # =====================================================
        # 1. READ N8N
        # =====================================================

        print(
            "\nReading current workflow from n8n..."
        )

        try:
            state = await read_current_state(
                client=client,
                adapter=adapter,
                rejected_proposals=rejected_proposals,
            )

        except Exception as exc:
            print("\nFAILED TO READ N8N WORKFLOW")
            print(str(exc))
            break

        print_workflow(
            state.workflow
        )

        # =====================================================
        # 2. COMPOSER PROPOSES ONE NEXT NODE
        # =====================================================

        print(
            "\nComposer is deciding the next step..."
        )

        try:
            proposal = planner.propose_next(
                state
            )

        except Exception as exc:
            print("\nCOMPOSER FAILED")
            print(str(exc))
            break

        if proposal is None:
            print("\n" + "=" * 60)
            print("WORKFLOW COMPOSITION COMPLETE")
            print("=" * 60)

            print_workflow(
                state.workflow
            )

            print(
                "\nThe Composer believes the workflow "
                "now satisfies the task."
            )

            break

        # =====================================================
        # 3. SHOW PROPOSAL
        # =====================================================

        print("\n" + "=" * 60)
        print("PROPOSED NEXT NODE")
        print("=" * 60)

        print(
            f"\nName: {proposal.node.name}"
        )

        print(
            f"ID: {proposal.node.id}"
        )

        print(
            f"Type: {proposal.node.node_type}"
        )

        print(
            f"Tool: {proposal.node.tool}"
        )

        if proposal.connect_from:
            source = state.workflow.get_node(
                proposal.connect_from
            )

            if source:
                print(
                    f"Connect from: "
                    f"{source.name}"
                )
            else:
                print(
                    f"Connect from: "
                    f"{proposal.connect_from}"
                )

        if proposal.node.parameters:
            print("\nParameters:")

            for key, value in (
                proposal.node.parameters.items()
            ):
                print(
                    f"  {key}: {value}"
                )

        print("\nReason:")
        print(
            proposal.reason
        )

        # =====================================================
        # 4. HUMAN APPROVAL
        # =====================================================

        while True:
            decision = input(
                "\nAdd this node? [y/n/q]: "
            ).strip().lower()

            if decision in {
                "y",
                "n",
                "q",
            }:
                break

            print(
                "Please enter y, n, or q."
            )

        if decision == "q":
            print(
                "\nComposition cancelled."
            )
            break

        # =====================================================
        # 5. REJECTION
        # =====================================================

        if decision == "n":
            feedback = input(
                "\nWhy are you rejecting this node? "
                "(optional): "
            ).strip()

            rejection = RejectedProposal(
                proposal=proposal,
                feedback=feedback or None,
            )

            rejected_proposals = (
                rejected_proposals
                + (rejection,)
            )

            print(
                f"\n✗ Rejected: "
                f"{proposal.node.name}"
            )

            if feedback:
                print(
                    f"Feedback recorded: "
                    f"{feedback}"
                )

            # Loop again.
            #
            # n8n has NOT changed.
            # Composer gets rejection feedback.
            continue

        # =====================================================
        # 6. VALIDATE PROPOSED RESULT
        # =====================================================

        candidate_nodes = (
            state.workflow.nodes
            + (proposal.node,)
        )

        candidate_connections = (
            state.workflow.connections
        )

        if proposal.connect_from:
            from composer.models import (
                WorkflowConnection,
                WorkflowSpec,
            )

            candidate_connections += (
                WorkflowConnection(
                    source=proposal.connect_from,
                    target=proposal.node.id,
                ),
            )

            candidate_workflow = WorkflowSpec(
                name=state.workflow.name,
                description=state.workflow.description,
                nodes=candidate_nodes,
                connections=candidate_connections,
            )

        else:
            from composer.models import WorkflowSpec

            candidate_workflow = WorkflowSpec(
                name=state.workflow.name,
                description=state.workflow.description,
                nodes=candidate_nodes,
                connections=candidate_connections,
            )

        validation = validator.validate(
            candidate_workflow
        )

        if not validation.is_valid:
            print("\nVALIDATION FAILED")

            for error in validation.errors:
                print(
                    f"- {error}"
                )

            print(
                "\nNothing was written to n8n."
            )

            continue

        # =====================================================
        # 7. TRANSLATE COMPOSER NODE -> N8N NODE
        # =====================================================

        position = [
            240
            + (
                len(state.workflow.nodes)
                * 300
            ),
            300,
        ]

        try:
            n8n_node = adapter.convert(
                proposal.node,
                position=position,
            )

        except Exception as exc:
            print(
                "\nNODE TRANSLATION FAILED"
            )
            print(
                str(exc)
            )
            continue

        # =====================================================
        # 8. FIND REAL N8N SOURCE NODE
        # =====================================================

        source_name = None

        if proposal.connect_from:
            source_node = (
                state.workflow.get_node(
                    proposal.connect_from
                )
            )

            if source_node is None:
                print(
                    "\nCONNECTION FAILED"
                )

                print(
                    "Composer referenced a node "
                    "that does not exist in the "
                    "current n8n workflow."
                )

                continue

            source_name = (
                source_node.name
            )

        # =====================================================
        # 9. WRITE APPROVED NODE TO N8N
        # =====================================================

        print(
            "\nWriting approved node to n8n..."
        )

        try:
            await client.add_approved_node(
                workflow_id=WORKFLOW_ID,
                node=n8n_node,
                connect_from=source_name,
            )

        except Exception as exc:
            print(
                "\nN8N UPDATE FAILED"
            )

            print(
                str(exc)
            )

            print(
                "\nThe Composer will NOT assume "
                "the node was added."
            )

            continue

        print(
            f"\n✓ Approved and persisted: "
            f"{proposal.node.name}"
        )

        # IMPORTANT:
        #
        # We deliberately do NOT update local workflow
        # state here.
        #
        # The loop starts again and reads n8n.
        # Therefore n8n remains the source of truth.

        print(
            "\nRefreshing workflow from n8n..."
        )


if __name__ == "__main__":
    asyncio.run(main())