import json
import pytest
from composer.models import WorkflowNode,WorkflowSpec,WorkflowConnection,RuntimeInput
from composer.contracts import benchmark_environment
from adapters.benchmark_compiler import compile_workflow
from runtime_service import validate_arguments
from composer.validator import WorkflowValidator

def graph():
    nodes=(WorkflowNode("t","Start","trigger"),
           WorkflowNode("s","Source","action","source.read"),
           WorkflowNode("p","Patch","action","checkout.patch",runtime_input=RuntimeInput(("s",),"Derive patch")),
           WorkflowNode("f","Summary","ai","summary",runtime_input=RuntimeInput(("s","p"),"Summarize")))
    return WorkflowSpec("test","",nodes,tuple(WorkflowConnection(a.id,b.id) for a,b in zip(nodes,nodes[1:])))

def test_context_survives_http_outputs_and_arguments_are_runtime_bound():
    nodes,edges=compile_workflow(graph(),benchmark_environment(),"same-id")
    patch=next(n for n in nodes if n["name"]=="Patch")
    assert 'Benchmark Run Context' in patch["parameters"]["url"]
    assert "environment_url" in patch["parameters"]["url"]
    assert "run_token" in json.dumps(patch["parameters"]["headerParameters"])
    assert 'Resolve Patch' in patch["parameters"]["jsonBody"]
    assert nodes[0]["parameters"]["responseMode"]=="lastNode"
    assert nodes[0]["parameters"]["path"]=="composer-v2-same-id"
    assert ("Resolve Patch","Patch") in edges
    assert "test-run-token" not in json.dumps(nodes)

def test_unobserved_patch_rejected():
    schema={"old":{"type":"string"},"new":{"type":"string"}}
    ev=[{"output":{"ok":True,"value":{"content":"unique old fragment"}}}]
    assert validate_arguments({"old":"old","new":"updated"},schema,ev)["new"]=="updated"
    for args in ({"old":"missing","new":"updated"},{"old":"old","new":"old"},{"old":"old"}):
        with pytest.raises(ValueError):
            validate_arguments(args,schema,ev)

def test_future_runtime_evidence_rejected():
    wf=graph()
    broken=WorkflowNode("p","Patch","action","checkout.patch",runtime_input=RuntimeInput(("f",),"Derive"))
    wf=WorkflowSpec(wf.name,wf.description,(wf.nodes[0],wf.nodes[1],broken,wf.nodes[3]),wf.connections)
    assert not WorkflowValidator().validate(wf,benchmark_environment().capabilities).is_valid

def test_missing_required_arguments_rejected():
    wf=graph()
    wf=WorkflowSpec(wf.name,wf.description,(wf.nodes[0],wf.nodes[1],WorkflowNode("p","Patch","action","checkout.patch"),wf.nodes[3]),wf.connections)
    with pytest.raises(ValueError,match="Required arguments"):
        compile_workflow(wf,benchmark_environment(),"id")

def test_readback_uses_actual_connections():
    from adapters.n8n_node_adapter import N8nNodeAdapter
    nodes,edges=compile_workflow(graph(),benchmark_environment(),"id")
    connections={}
    for a,b in edges:
        connections[a]={"main":[[{"node":b,"type":"main","index":0}]]}
    raw={"name":"test","nodes":nodes,"connections":connections}
    restored=N8nNodeAdapter().from_n8n_workflow(raw)
    assert restored.nodes==graph().nodes
    assert set(restored.connections)==set(graph().connections)
    del connections["Source"]
    restored=N8nNodeAdapter().from_n8n_workflow(raw)
    assert WorkflowConnection("s","p") not in restored.connections
