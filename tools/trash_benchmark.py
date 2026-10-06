"""Synthetic metadata-only trash pagination measurement; not a storage SLA."""
from pathlib import Path
import json,os,sys,tempfile,time,tracemalloc
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    with tempfile.TemporaryDirectory(prefix='recalldock-trash-bench-') as tmp:
        root=Path(tmp);os.environ['APP_DATA_DIR']=str(root/'bootstrap')
        from app.main import create_app
        from app.common import database
        from fastapi.testclient import TestClient
        app=create_app(root/'bench');total=50000
        with database(root/'bench') as db:
            db.executemany('INSERT INTO documents(id,name,digest,kind,pages,characters,created,kb_id,version,deleted_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                [(f'fixture-{i:06}',f'Synthetic {i}',f'digest-{i}','.txt',1,12,1,'default',1,i+1) for i in range(total)])
        client=TestClient(app);samples=[]
        for _ in range(3):
            tracemalloc.start();started=time.perf_counter()
            page=client.get(f'/api/trash?offset={total-100}&limit=100').json()
            elapsed=time.perf_counter()-started;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
            assert page['total']==total and len(page['items'])==100
            assert page['items'][0]['id']=='fixture-000099' and page['items'][-1]['id']=='fixture-000000'
            samples.append({'seconds':round(elapsed,6),'python_peak_bytes':peak})
        print(json.dumps({'synthetic_metadata_rows':total,'offset':total-100,'samples':samples,
            'note':'In-process TestClient; first sample cold, no independent warmup. Python allocations only; excludes SQLite/native RSS. No document body/index load.'},indent=2))

if __name__=='__main__':main()
