"""New temporary synthetic library; never open the existing user's service/data."""
from pathlib import Path
import os,sys,tempfile,threading,socket
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    with socket.socket() as probe:probe.bind(('127.0.0.1',8899))
    with tempfile.TemporaryDirectory(prefix='recalldock-pages-demo-') as tmp:
        root=Path(tmp);os.environ['APP_DATA_DIR']=str(root/'bootstrap')
        for key in ['LLM_API_KEY','LLM_MODEL','LLM_BASE_URL','EMBEDDING_MODEL','OCR_ENABLED']:os.environ.pop(key,None)
        from app.main import create_app
        from fastapi.testclient import TestClient
        import uvicorn
        app=create_app(root/'demo')
        with TestClient(app) as client:
            text=''.join(f'原创合成段落 {i:03}：仅用于分页验收，不是真实知识。'+(' synthetic text '*20)+'\n' for i in range(120))+'\nTAIL-ORIGINAL-120'
            result=client.post('/api/documents',files={'file':('原创合成长文.txt',text.encode())})
            if result.status_code!=201:raise RuntimeError('synthetic import failed')
            doc=result.json();print('Synthetic chunks:',doc['chunks'],flush=True)
            client.post('/api/workspace/bases',json={'name':'合成空库'})
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8899,log_level='warning'))
        thread=threading.Thread(target=server.run);thread.start()
        print('Synthetic demo: http://127.0.0.1:8899/ ; press Enter to stop.',flush=True)
        try:input()
        finally:server.should_exit=True;thread.join(timeout=15)
        if thread.is_alive():raise RuntimeError('demo did not stop')

if __name__=='__main__':main()
