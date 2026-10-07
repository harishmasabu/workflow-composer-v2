import asyncio


WORKFLOW_ID = "EQvN9tFGuFCotDS1"

TASK = """
Investigate a production checkout incident affecting some transactions.
Use available source, deployment and failure evidence to identify the
root cause and impact. Apply the smallest appropriate correction,
verify affected and previously working behavior, and write an incident
summary including root cause, impact, fix, and verification.
Do not disable payment validation.
""".strip()


async def main():
    # Keep the original entry point on the same validated benchmark compiler.
    from run_benchmark_composer import main as compose_benchmark
    await compose_benchmark()


if __name__ == "__main__":
    asyncio.run(main())
