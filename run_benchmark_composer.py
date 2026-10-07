"""Resume the real Composer, compile and persist its graph through n8n MCP."""
import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from adapters.n8n_node_adapter import N8nNodeAdapter
from adapters.benchmark_compiler import compile_workflow
from composer.contracts import benchmark_environment
from composer.models import ComposerState, WorkflowSpec, WorkflowConnection
from composer.planner import WorkflowPlanner
from composer.validator import WorkflowValidator
from mcp_client.client import N8nMCPClient
from run_integrated_demo import TASK, WORKFLOW_ID

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--approve",action="store_true",help="Approve validated proposals for this integration")
    parser.add_argument("--publish",action="store_true")
    args=parser.parse_args()
    client=N8nMCPClient()
    adapter=N8nNodeAdapter()
    raw=adapter._extract_json(await client.get_workflow_details(WORKFLOW_ID))
    wf=adapter.from_n8n_result(await client.get_workflow_details(WORKFLOW_ID))
    Path("work").mkdir(exist_ok=True)
    # Do not export credentials from old node configuration.
    Path("work/composer-before.json").write_text(json.dumps(asdict(wf),indent=2))
    environment=benchmark_environment()
    planner=WorkflowPlanner()
    for _ in range(8):
        if wf.nodes[-1].tool=="summary":
            break
        proposal=planner.propose_next(ComposerState(task=TASK+" Submit incident-summary.md and final answer.",workflow=wf,environment=environment))
        if proposal is None:
            raise ValueError("Planner declared completion before a final summary")
        candidate=WorkflowSpec(wf.name,wf.description,wf.nodes+(proposal.node,),
            wf.connections+(WorkflowConnection(proposal.connect_from,proposal.node.id),))
        validation=WorkflowValidator().validate(candidate,environment.capabilities)
        if not validation.is_valid:
            raise ValueError(validation.errors)
        if proposal.connect_from!=wf.nodes[-1].id:
            raise ValueError("Proposal must append to the linear execution path")
        print(json.dumps(asdict(proposal),indent=2),flush=True)
        if not args.approve and input("Approve proposal? [y/n] ").lower()!="y":
            return
        wf=candidate
    nodes,connections=compile_workflow(wf,environment,WORKFLOW_ID)
    Path("work/composer-approved.json").write_text(json.dumps(asdict(wf),indent=2))
    Path("work/compiled-workflow.json").write_text(json.dumps({"nodes":nodes,"connections":connections},indent=2))
    # Validate the exact compiled node parameters before persisting.
    check=await client._call_tool("validate_node_config",{"nodes":[{k:n[k] for k in ("name","type","typeVersion","parameters")} for n in nodes]})
    data=adapter._extract_json(check)
    print("NODE VALIDATION",json.dumps(data),flush=True)
    if getattr(check,"is_error",False) or data.get("valid") is False:
        raise ValueError("n8n rejected compiled nodes")
    operations=[{"type":"removeNode","nodeName":n["name"]} for n in raw["workflow"]["nodes"]]
    operations += [{"type":"addNode","node":n} for n in nodes]
    operations += [{"type":"addConnection","source":a,"target":b} for a,b in connections]
    operations += [{"type":"setWorkflowSettings","settings":{"executionTimeout":110}}]
    result=await client._call_tool("update_workflow",{"workflowId":WORKFLOW_ID,"operations":operations,
        "versionName":"Composer run-scoped benchmark integration"})
    if getattr(result,"is_error",False):
        raise RuntimeError(str(result))
    persisted=adapter.from_n8n_result(await client.get_workflow_details(WORKFLOW_ID))
    if persisted.nodes != wf.nodes:
        raise RuntimeError("Persisted Composer nodes differ from approved graph")
    print("Verified MCP readback:",WORKFLOW_ID,flush=True)
    if args.publish:
        result=await client._call_tool("publish_workflow",{"workflowId":WORKFLOW_ID})
        client.print_result(result)

if __name__=="__main__":
    asyncio.run(main())
