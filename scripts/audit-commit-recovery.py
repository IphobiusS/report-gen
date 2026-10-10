import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--tool',required=True);p.add_argument('--out',required=True);a=p.parse_args()
sys.path[:0]=[a.tool,str(Path(a.tool)/'webapp')]
import project_history as h
import app
from storage import revision
results=[]
for point in ('before_move','after_move','after_install'):
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp);d=root/'audit';h.save(d,{'meta':{'report_title':'OLD'},'findings':[]});before=revision(d/'engagement.yaml')
  code='''
import os, sys
from pathlib import Path
sys.path[:0]=[sys.argv[1], str(Path(sys.argv[1])/'webapp')]
import project_history as h
root=Path(sys.argv[2]);point=sys.argv[3];rename=Path.rename

def interrupt(self,target):
 if point=='before_move' and self==root: os._exit(91)
 result=rename(self,target)
 if point=='after_move' and self==root: os._exit(91)
 if point=='after_install' and Path(target)==root: os._exit(91)
 return result
Path.rename=interrupt
h.save(root,{'meta':{'report_title':'NEW'},'findings':[]})
'''
  r=subprocess.run([sys.executable,'-c',code,a.tool,str(d),point],env=os.environ.copy())
  app.PROJECTS=root;c=app.app.test_client();listed=c.get('/api/projects');loaded=c.get('/api/projects/audit')
  results.append({'point':point,'exit':r.returncode,'listed':listed.get_json(),'read_status':loaded.status_code,'title':loaded.get_json().get('meta',{}).get('report_title'),'previous_matches':d.exists() and revision(d/'engagement.yaml')==before,'leftovers':[x.name for x in root.iterdir() if x.name.startswith('.')]})
Path(a.out).write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
