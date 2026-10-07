from composer.models import CapabilityContract, EnvironmentContext

def benchmark_environment():
    return EnvironmentContext(
    base_url="",
    access_token="",
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
            description="Read checkout.py source code.",
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
                "Apply a minimal checkout source patch. "
                "The old fragment must occur exactly once."
            ),
        ),
        CapabilityContract(
            name="tests.run",
            argument_schema={},
            description="Run actual checkout simulator tests.",
        ),
    ),
)
