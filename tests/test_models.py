from composer.models import (
    WorkflowConnection,
    WorkflowNode,
    WorkflowSpec,
)


def test_create_workflow_spec():
    trigger = WorkflowNode(
        id="incident",
        name="Incident detected",
        node_type="trigger",
    )

    inspect_logs = WorkflowNode(
        id="inspect_logs",
        name="Inspect production logs",
        node_type="action",
        tool="filesystem",
        parameters={
            "path": "logs/production.log",
        },
    )

    workflow = WorkflowSpec(
        name="production-incident-recovery",
        description="Investigate and recover from a production incident.",
        nodes=(trigger, inspect_logs),
        connections=(
            WorkflowConnection(
                source="incident",
                target="inspect_logs",
            ),
        ),
    )

    assert workflow.name == "production-incident-recovery"

    assert workflow.node_ids() == {
        "incident",
        "inspect_logs",
    }

    assert workflow.get_node("inspect_logs") == inspect_logs
    assert workflow.get_node("does_not_exist") is None