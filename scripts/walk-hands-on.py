#!/usr/bin/env python3
"""Exercise the hands-on course against an isolated local workbench and real model.

Uses the same stage, ADK, clock, venue and resume APIs as the visible controls.
It resets this workbench; never aim it at a learner's current experiment.
"""
import argparse,json,time,uuid,urllib.request,urllib.parse
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',required=True);p.add_argument('--output',required=True);args=p.parse_args()
assert urllib.parse.urlsplit(args.url).hostname in ('127.0.0.1','localhost','::1')
report={'chapters':{},'cloud':'UI and source checked separately; no deployed cloud task configured'}
def req(path,body=None):
 r=urllib.request.Request(args.url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(r,timeout=240) as f:return json.load(f)
def wait(fn):
 end=time.time()+150
 while time.time()<end:
  try:
   v=fn()
   if v:return v
  except (OSError,ValueError):pass
  time.sleep(1)
 raise AssertionError('timed out waiting for live state')
def save():
 Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(report,indent=2))
def load(n):
 print(f'Chapter {n}: load',flush=True);assert req('/api/stage',{'step':n,'resetVenue':True})['ok']
 wait(lambda:any(x['name']=='agent' and x['state']=='running' for x in req('/api/services')['services']))
 wait(lambda:req('/svc/agent/list-apps'))
def session(tag):
 sid='verify-'+tag+'-'+uuid.uuid4().hex[:8];req('/svc/agent/apps/concert/users/user/sessions/'+sid,{})
 return sid
def run(sid,text=None,answer=None):
 parts=[{'text':text}] if answer is None else [{'function_response':{'id':req('/api/task?session_id='+sid)['pending']['id'],'name':'adk_request_input','response':{'result':answer}}}]
 events=req('/svc/agent/run',{'app_name':'concert','user_id':'user','session_id':sid,'new_message':{'role':'user','parts':parts}})
 assert isinstance(events,list),events
 assert not any(e.get('errorMessage') or e.get('error_message') for e in events),events
 return events
def raw(sid):return req('/svc/agent/apps/concert/users/user/sessions/'+sid)
def responses(sid,name):
 return [r['response'] for e in raw(sid)['events'] for q in (e.get('content') or {}).get('parts',[]) if (r:=q.get('functionResponse') or q.get('function_response') or {}).get('name')==name]
def task(sid):return req('/api/task?session_id='+sid)
def venue(action,body={}):assert req('/api/venue/'+action,body)['ok']
request='Get me and Sam two tickets to the Amsterdam show.'
try:
 load(1);s=session('meet');run(s,'Which Amsterdam shows still have seats?');assert responses(s,'search_events');assert req('/api/venue/state')['orders']==0
 report['chapters']['meet']={'session':s,'model_reply':True,'no_orders':True};save()
 load(2);s=session('wake');run(s,'Which Amsterdam shows still have seats for me and Sam? Keep checking and tell me if anything changes.')
 before=len(raw(s)['events']);time.sleep(3);assert len(raw(s)['events'])==before
 req('/api/services/monstertix/start',{});wait(lambda:req('/svc/monstertix/health'))
 req('/api/services/clock/restart',{'delay':10,'every':0,'trigger':False})
 wait(lambda:'done. the agent ran' in req('/api/services/clock/log')['log'])
 assert req('/api/venue/state')['orders']==0
 report['chapters']['wake']={'session':s,'idle_without_caller':True,'external_timer':True,'log':req('/api/services/clock/log')['log']};save()
 load(3);a=session('memory-a');run(a,request);assert responses(a,'recall');assert responses(a,'get_seatmap')
 run(a,'Remember this for next time — we always want aisle seats.');assert responses(a,'remember')
 b=session('memory-b');run(b,request);assert 'aisle' in json.dumps(responses(b,'recall')).lower()
 assert not responses(b,'remember');assert a!=b
 report['chapters']['memory']={'sessions':[a,b],'explicit_write':True,'new_session_recalls_aisle':True,'separate_conversations':True};save()
 load(4);s=session('resume');run(s,request);t=task(s);assert t['pending']['kind']=='queue';ticket=t['queue_ticket']
 req('/api/services/agent/kill',{});assert any(x['name']=='agent' and x['state']=='stopped' for x in req('/api/services')['services'])
 assert req('/svc/venue/queue/'+ticket)['ticket']==ticket
 req('/api/services/agent/start',{});wait(lambda:req('/svc/agent/list-apps'))
 venue('advance-queue',{'ticket':ticket});r=req('/api/task/resume',{'session_id':s});assert r['ok'],r
 t=task(s);assert t['queue_ticket']==ticket and t['ready_to_buy'];assert req('/api/venue/state')['orders']==0
 assert req('/api/venue/state')['queue']==1
 report['chapters']['resume']={'session':s,'ticket':ticket,'same_ticket_after_kill':True,'ready_to_buy':True,'zero_orders':True,'invocations':t['invocations']};save()
 load(5);s=session('buy');run(s,request);assert task(s)['pending']['kind']=='person'
 assert not req('/api/task/resume',{'session_id':s})['ok'];assert req('/api/venue/state')['queue']==0
 for answer in ['Two tickets, up to $250 each.',"Yes, that's right."]:run(s,answer=answer)
 t=task(s);assert t['authorization']['confirmed'] and t['pending']['kind']=='queue'
 venue('sellout',{'event_id':t['queue_event_id'],'section':'A'});venue('hang-once');venue('advance-queue',{'ticket':t['queue_ticket']})
 assert req('/api/venue/state')['orders']==0
 r=req('/api/task/resume',{'session_id':s});assert r['ok'],r
 purchases=responses(s,'purchase');assert any(x.get('reason')=='stale_plan' for x in purchases),purchases
 final=next(x for x in purchases if x.get('duplicate'));assert final['attempts']==2 and final['section']=='C',final
 assert req('/api/venue/state')['orders']==1
 report['chapters']['buy']={'session':s,'authorization':t['authorization'],'guard_and_retry':purchases,'exactly_one_order':True};save()
 print('All five local chapters passed on the real model.',flush=True)
except Exception as e:
 report['error']=str(e);raise
finally:save()
