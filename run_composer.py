from composer.planner import WorkflowPlanner
from composer.validator import WorkflowValidator


def main():
    task = (
        "When a customer submits a support request, "
        "classify it and send it to the correct team."
    )

    print("\nTASK")
    print(task)

    planner = WorkflowPlanner()

    print("\nGenerating workflow...")
    workflow = planner.generate(task)

    print("\nWORKFLOW")
    print(f"Name: {workflow.name}")
    print(f"Description: {workflow.description}")

    print("\nNODES")
    for node in workflow.nodes:
        print(
            f"- {node.id}: "
            f"type={node.node_type}, "
            f"tool={node.tool}"
        )

    print("\nCONNECTIONS")
    for connection in workflow.connections:
        print(f"- {connection.source} -> {connection.target}")

    result = WorkflowValidator().validate(workflow)

    print("\nVALIDATION")

    if result.is_valid:
        print("VALID ✓")
    else:
        print("INVALID ✗")
        for error in result.errors:
            print(f"- {error}")


if __name__ == "__main__":
    main()