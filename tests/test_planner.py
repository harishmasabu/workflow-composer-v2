from composer.planner import WorkflowPlanner


def test_convert_llm_json_to_workflow_spec():
    data = {
        "name": "support-routing",
        "description": "Classify and route support requests.",
        "nodes": [
            {
                "id": "receive",
                "name": "Receive request",
                "node_type": "trigger",
                "tool": None,
                "parameters": {},
            },
            {
                "id": "classify",
                "name": "Classify request",
                "node_type": "ai",
                "tool": "llm",
                "parameters": {},
            },
        ],
        "connections": [
            {
                "source": "receive",
                "target": "classify",
            }
        ],
    }

    workflow = WorkflowPlanner._to_workflow_spec(data)

    assert workflow.name == "support-routing"
    assert len(workflow.nodes) == 2
    assert workflow.nodes[1].tool == "llm"
    assert workflow.connections[0].source == "receive"