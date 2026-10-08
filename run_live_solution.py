"""One LLM-generated n8n workflow per AutoWFBench run."""
import asyncio, importlib.util, json, os, threading
from dataclasses import asdict
from pathlib import Path
from http.server import ThreadingHTTPServer
from dotenv import load_dotenv
from compose_run import compose, environment_for, sdk_code
from adapters.benchmark_compiler import compile_workflow, TRIGGER
from adapters.n8n_node_adapter import N8nNodeAdapter
from mcp_client.client import N8nMCPClient
from runtime_service import Handler as RuntimeHandler
spec=importlib.util.spec_from_file_location('bridge',Path(__file__).parent/'integrations/autowfbench/n8n_solution.py')
bridge=importlib.util.module_from_spec(spec);spec.loader.exec_module(bridge)
results={}
run_lock=threading.Lock()

def find_submission(value, run_id):
    if isinstance(value,dict):
        if value.get('protocol_version')=='1.0' and value.get('run_id')==run_id and 'final_answer' in value:return value
        values=value.values()
    elif isinstance(value,list):values=value
    else:return None
    for v in values:
        found=find_submission(v,run_id)
        if found:return found

def execution_status(reply):
    return reply.get('execution', reply).get('status')

async def execute(request):
    client=N8nMCPClient()
    async def call(name,args):
        result=await client._call_tool(name,args)
        data=N8nNodeAdapter._extract_json(result)
        if getattr(result,'is_error',False) or data.get('success') is False or data.get('valid') is False:
            raise ValueError('n8n rejected '+name+': '+json.dumps(data)[:1200])
        return data
    env=environment_for(request)
    wf=compose(request['challenge'],env)
    nodes,connections=compile_workflow(wf,env,request['run_id'],runtime_url='http://127.0.0.1:9432/transform')
    out=Path('work/live')/request['run_id'];out.mkdir(parents=True,exist_ok=True)
    (out/'composer.json').write_text(json.dumps(asdict(wf),indent=2))
    (out/'n8n.json').write_text(json.dumps({'nodes':nodes,'connections':connections},indent=2))
    code=sdk_code(nodes,wf.name);(out/'workflow.js').write_text(code)
    await call('validate_node_config',{'nodes':[{k:n[k] for k in ('name','type','typeVersion','parameters')} for n in nodes]})
    await call('validate_workflow',{'code':code})
    created=await call('create_workflow_from_code',{'code':code,'name':wf.name,'versionName':'Complete Composer graph for benchmark run'})
    (out/'created.json').write_text(json.dumps(created,indent=2))
    workflow_id=created.get('workflowId') or created.get('id') or created.get('workflow',{}).get('id')
    if not workflow_id:raise ValueError('Missing created workflow ID')
    await call('get_workflow_details',{'workflowId':workflow_id})
    payload={'environment_url':env.base_url,'run_token':env.access_token,'run_id':request['run_id'],'challenge':request['challenge']}
    execution=await call('execute_workflow',{'workflowId':workflow_id,'executionMode':'manual','triggerNodeName':TRIGGER,'inputs':{'webhookData':{'method':'POST','body':payload}}})
    execution_id=str(execution.get('executionId') or execution.get('execution',{}).get('id') or '')
    (out/'execution.json').write_text(json.dumps({'workflow_id':workflow_id,'execution_id':execution_id},indent=2))
    if not execution_id:raise ValueError('Missing execution ID: '+json.dumps(execution))
    for _ in range(280):
        reply=await call('get_workflow_execution',{'workflowId':workflow_id,'executionId':execution_id,'includeData':True,'nodeNames':['Benchmark Submission'],'truncateData':1})
        submission=find_submission(reply,request['run_id'])
        if submission:
            if not any(t.get('data',{}).get('workflow_id')==workflow_id for t in submission.get('trace',[])):raise ValueError('Workflow identity mismatch')
            (out/'submission.json').write_text(json.dumps(submission,indent=2))
            return submission
        if execution_status(reply) in ('error','canceled','crashed'):
            raise ValueError('n8n execution failed: '+str(reply.get('data',{}).get('resultData',{}).get('error',{}).get('description','see execution '+execution_id)))
        await asyncio.sleep(.5)
    raise TimeoutError('n8n did not return a final submission')

def trigger(request):
    with run_lock:
        if request['run_id'] in results:return results[request['run_id']]
        try:result=asyncio.run(execute(request))
        except Exception as exc:
            message=str(exc).replace(request['environment']['access_token'],'[REDACTED]')
            result={'protocol_version':'1.0','run_id':request['run_id'],'status':'failed','final_answer':message,'artifacts':[],'trace':[]}
        results[request['run_id']]=result
        return result

if __name__=='__main__':
    load_dotenv(os.environ.get('COMPOSER_ENV_FILE','.env'))
    bridge.trigger_n8n=trigger
    runtime=ThreadingHTTPServer(('127.0.0.1',9432),RuntimeHandler)
    threading.Thread(target=runtime.serve_forever,daemon=True).start()
    print('Live Composer solution on 9431; evidence transforms on 9432',flush=True)
    ThreadingHTTPServer(('127.0.0.1',9431),bridge.Handler).serve_forever()
