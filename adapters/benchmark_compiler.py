"""Compile an approved Composer graph into run-scoped n8n nodes."""
import json
from dataclasses import asdict
from composer.validator import WorkflowValidator
from composer.schema import validate_arguments_schema

PREFIX = "composer-v2:"
TRIGGER = "Benchmark Run Context"

def expression(code):
    return "={{ " + code.replace("}}", "} }") + " }}"

def ref(name):
    return "$(" + json.dumps(name) + ").first().json"

def http_node(name, url, body, position, headers=None):
    p = {"method":"POST","url":url,"sendBody":True,"specifyBody":"json",
         "jsonBody":body,"options":{"timeout":90000}}
    if headers:
        p.update(sendHeaders=True,headerParameters={"parameters":headers})
    return {"name":name,"type":"n8n-nodes-base.httpRequest","typeVersion":4.5,
            "parameters":p,"position":position}

def compile_workflow(workflow, environment, workflow_id, runtime_url="http://127.0.0.1:9410/transform"):
    validation=WorkflowValidator().validate(workflow,environment.capabilities)
    if not validation.is_valid:
        raise ValueError(validation.errors)
    # First integration deliberately supports a single unambiguous chain.
    expected={(a.id,b.id) for a,b in zip(workflow.nodes,workflow.nodes[1:])}
    if {(e.source,e.target) for e in workflow.connections} != expected:
        raise ValueError("Benchmark compiler requires a linear connected workflow")
    if workflow.nodes[0].node_type != "trigger":
        raise ValueError("First node must be the trigger")
    names={n.id:(TRIGGER if n.node_type=="trigger" else n.name) for n in workflow.nodes}
    nodes=[]
    context=ref(TRIGGER)+".body"
    for index,n in enumerate(workflow.nodes):
        position=[len(nodes)*280,300]
        if n.node_type=="trigger":
            out={"name":TRIGGER,"type":"n8n-nodes-base.webhook","typeVersion":2,
                 "parameters":{"httpMethod":"POST","path":"composer-v2-"+workflow_id,
                               "responseMode":"lastNode","options":{}},"position":position}
        else:
            evidence="["+",".join(
                "{node_id:"+json.dumps(i)+",capability:"+json.dumps(workflow.get_node(i).tool)+
                ",output:"+ref(names[i])+(",applied_arguments:"+ref("Resolve "+names[i])+".resolved" if workflow.get_node(i).runtime_input and workflow.get_node(i).tool in environment.capabilities else "")+"}" for i in (tuple(prior.id for prior in workflow.nodes[:index] if prior.tool in environment.capabilities) if n.runtime_input else ()))+"]"
            if n.tool=="summary" and n.node_type=="ai":
                if not n.runtime_input:
                    raise ValueError("Summary requires runtime evidence")
                body=expression("JSON.stringify({mode:'summary',instruction:"+
                    json.dumps(n.runtime_input.instruction)+",evidence:"+evidence+"})")
                out=http_node(n.name,runtime_url,body,position)
            else:
                contract=environment.get_capability(n.tool)
                if not contract:
                    raise ValueError("Unknown capability")
                if n.runtime_input:
                    resolver="Resolve "+n.name
                    body=expression("JSON.stringify({mode:'arguments',instruction:"+
                        json.dumps(n.runtime_input.instruction)+",schema:"+json.dumps(contract.argument_schema)+
                        ",evidence:"+evidence+"})")
                    nodes.append(http_node(resolver,runtime_url,body,position))
                    args=ref(resolver)+".resolved"
                    position=[len(nodes)*280,300]
                else:
                    validate_arguments_schema(n.parameters,contract.argument_schema)
                    args=json.dumps(n.parameters)
                out=http_node(n.name,expression(context+".environment_url.replace(/\\/$/, '') + '/tools'"),
                              expression("JSON.stringify({operation:"+json.dumps(n.tool)+",arguments:"+args+"})"),
                              position,[{"name":"Authorization","value":expression("'Bearer ' + "+context+".run_token")}])
        out["id"]=n.id
        out["notes"]=PREFIX+json.dumps(asdict(n))
        nodes.append(out)
        if n.tool in environment.capabilities:
            nodes.append({'name':'Check '+n.name,'type':'n8n-nodes-base.code','typeVersion':2,
                'parameters':{'jsCode':"if ($json.ok !== true) throw new Error('Environment API operation failed'); return $input.all();"},
                'position':[len(nodes)*280,300]})
    if workflow.nodes[-1].tool!="summary":
        raise ValueError("Workflow needs a final summary")
    final_name=workflow.nodes[-1].name
    code=("const ctx = "+context+";\nconst result = "+ref(final_name)+";\n"
          "if (!ctx.run_id || !result.final_answer || !result.artifacts?.length) throw new Error('Missing final submission');\n"
          "return [{json:{protocol_version:'1.0',run_id:ctx.run_id,status:'completed',"
          "final_answer:result.final_answer,artifacts:result.artifacts,trace:[{timestamp:new Date().toISOString(),"
          "kind:'n8n_execution',data:{workflow_id:$workflow.id,execution_id:$execution.id,run_id:ctx.run_id}}]}}];")
    nodes.append({"name":"Benchmark Submission","type":"n8n-nodes-base.code","typeVersion":2,
                  "parameters":{"jsCode":code},"position":[len(nodes)*280,300]})
    connections=[(a["name"],b["name"]) for a,b in zip(nodes,nodes[1:])]
    return nodes,connections
