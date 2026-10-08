"""Compose a complete graph from a live challenge; no environment observations at build time."""
import json
from dataclasses import asdict
from composer.planner import WorkflowPlanner
from composer.validator import WorkflowValidator
from composer.models import EnvironmentContext
from composer.schema import validate_arguments_schema
from adapters.benchmark_compiler import compile_workflow


def environment_for(request):
    import urllib.request
    from composer.models import CapabilityContract
    from jsonschema import Draft7Validator
    env=request['environment']
    req=urllib.request.Request(env['base_url'].rstrip('/')+'/tools',
        data=json.dumps({'operation':'capabilities.list','arguments':{}}).encode(),
        headers={'Content-Type':'application/json','Authorization':'Bearer '+env['access_token']},method='POST')
    with urllib.request.urlopen(req,timeout=10) as response:
        data=json.load(response)
    if data.get('ok') is not True:raise ValueError('Capability discovery failed')
    discovered=data['value']['capabilities']
    names=[c['name'] for c in discovered]
    if len(names)!=len(set(names)) or set(names)!=set(request['challenge']['capabilities']):
        raise ValueError('Discovered capabilities differ from challenge')
    for c in discovered:Draft7Validator.check_schema(c['argument_schema'])
    contracts=tuple(CapabilityContract(c['name'],c['argument_schema'],c.get('description')) for c in discovered)
    return EnvironmentContext(env['base_url'],env['access_token'],contracts)


def compose(challenge, environment, planner=None):
    planner = planner or WorkflowPlanner()
    prompt = '''Generate ONE complete connected linear workflow as JSON.
Return {name,description,nodes,connections}. Nodes use {id,name,node_type,tool,parameters,runtime_input};
connections use {source,target} IDs. runtime_input must be null for trigger and static-argument nodes; never use an empty object. Each node must include node_type. name and description are required at the top level. First node is trigger with tool=null.
node_type MUST be exactly trigger, action, or ai. All environment calls including tests and patches use node_type=action. Final summary uses node_type=ai and tool=summary. Action tools must be supplied capabilities. Use ai/tool=summary as final evidence-summary transform.
Use parameters for known arguments. For unknown arguments use parameters={} and runtime_input={source_nodes:[upstream IDs],instruction:string}.
Do not invent source fragments or repairs. Gather evidence, observe baseline tests, derive a repair at runtime,
verify recovery, and summarize only actual observations. Include relevant prior tests in repair evidence.
Summary must include all observations and repair evidence. Do not return a proposed patch in this planning response.
For EVERY path enum value exposed by a read capability, create one static read node. This is mandatory; do not omit support modules. Read all those paths before baseline tests.
Use baseline tests before patch and recovery tests afterward. Also include checkout.observe after repair with an order derived at runtime from evidence.
The report must be saved through artifact.write using runtime-derived content, with markdown sections Root cause, Customer impact, Fix, Verification.
Only after artifact.write, append the final ai summary. For that summary include artifact.write as an evidence source so it reuses the exact saved content.
An action that derives arguments at runtime must list all relevant upstream observations, including baseline tests for patching and recovery results for reporting.
All nodes must be connected in the listed order. Return JSON only.'''
    payload={'challenge':challenge,'capabilities':[asdict(c) for c in environment.capability_contracts]}
    response=planner.client.chat.completions.create(model=planner.model,temperature=0,response_format={'type':'json_object'},
        messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps(payload)}],timeout=40)
    data=json.loads(response.choices[0].message.content)
    try:
        wf=planner._to_workflow_spec(data)
    except Exception:
        from pathlib import Path
        Path('work').mkdir(exist_ok=True)
        Path('work/rejected-plan.json').write_text(json.dumps(data,indent=2))
        raise
    result=WorkflowValidator().validate(wf,environment.capabilities)
    if not result.is_valid:raise ValueError(result.errors)
    if len({n.name for n in wf.nodes})!=len(wf.nodes):raise ValueError('Duplicate names')
    for n in wf.nodes:
        if n.tool in environment.capabilities:
            schema=environment.get_capability(n.tool).argument_schema
            if n.runtime_input:
                if n.parameters:raise ValueError('Runtime arguments must be resolved together')
            else:validate_arguments_schema(n.parameters,schema)
    return wf


def sdk_code(nodes, name):
    lines=[]
    for i,n in enumerate(nodes):
        factory='trigger' if i==0 else 'node'
        config={k:n[k] for k in ('name','parameters','position','notes') if k in n}
        lines.append(f'const n{i} = {factory}('+json.dumps({'type':n['type'],'version':n['typeVersion'],'config':config})+');')
    lines.append('export default workflow("composer-run",'+json.dumps(name)+').add(n0)'+''.join(f'.to(n{i})' for i in range(1,len(nodes)))+';')
    return '\n'.join(lines)
