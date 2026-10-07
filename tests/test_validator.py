from composer.models import (
    WorkflowConnection,
    WorkflowNode,
    WorkflowSpec,
)
from composer.validator import WorkflowValidator


def test_valid_workflow():
    workflow = WorkflowSpec(
        name="support-routing",
        description="Route incoming support requests.",
        nodes=(
            WorkflowNode(
                id="receive",
                name="Receive request",
                node_type="trigger",
            ),
            WorkflowNode(
                id="classify",
                name="Classify request",
                node_type="ai",
                tool="llm",
            ),
            WorkflowNode(
                id="forward",
                name="Forward request",
                node_type="action",
                tool="email",
            ),
        ),
        connections=(
            WorkflowConnection("receive", "classify"),
            WorkflowConnection("classify", "forward"),
        ),
    )

    result = WorkflowValidator().validate(workflow)

    assert result.is_valid
    assert result.errors == ()


def test_duplicate_node_id_is_rejected():
    workflow = WorkflowSpec(
        name="bad-workflow",
        description="Contains duplicate IDs.",
        nodes=(
            WorkflowNode(
                id="same",
                name="Trigger",
                node_type="trigger",
            ),
            WorkflowNode(
                id="same",
                name="Action",
                node_type="action",
                tool="filesystem",
            ),
        ),
        connections=(),
    )

    result = WorkflowValidator().validate(workflow)

    assert not result.is_valid
    assert "Duplicate node ID: same" in result.errors


def test_unknown_tool_is_rejected():
    workflow = WorkflowSpec(
        name="bad-tool",
        description="Contains an unsupported tool.",
        nodes=(
            WorkflowNode(
                id="start",
                name="Start",
                node_type="trigger",
            ),
            WorkflowNode(
                id="danger",
                name="Dangerous action",
                node_type="action",
                tool="unknown_tool",
            ),
        ),
        connections=(
            WorkflowConnection("start", "danger"),
        ),
    )

    result = WorkflowValidator().validate(
    workflow,
    capabilities=(
        "incident.read",
        "source.read",
        "checkout.patch",
        "tests.run",
    ),
)

    assert not result.is_valid


def test_connection_to_missing_node_is_rejected():
    workflow = WorkflowSpec(
        name="broken-edge",
        description="Contains an invalid connection.",
        nodes=(
            WorkflowNode(
                id="start",
                name="Start",
                node_type="trigger",
            ),
        ),
        connections=(
            WorkflowConnection("start", "missing"),
        ),
    )

    result = WorkflowValidator().validate(workflow)

    assert not result.is_valid
    assert (
        "Connection target 'missing' does not exist"
        in result.errors
    )