"""Disposable synthetic lifecycle demo; no existing knowledge files are opened."""
from pathlib import Path
import os,sys,tempfile,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    with tempfile.TemporaryDirectory(prefix='recalldock-trash-demo-') as tmp:
        root=Path(tmp);os.environ['APP_DATA_DIR']=str(root/'bootstrap')
        # Do not inherit paid provider/OCR configuration in the disposable demo.
        for key in ['LLM_API_KEY','LLM_MODEL','LLM_BASE_URL','EMBEDDING_MODEL','OCR_ENABLED']:os.environ.pop(key,None)
        from app.main import create_app
        from fastapi.testclient import TestClient
        import uvicorn
        app=create_app(root/'demo');client=TestClient(app)
        client.post('/api/documents',files={'file':('备份手册 · 原创合成.txt','备份文件保留三十天。每晚备份一次，恢复时先核验文件完整性。'.encode())})
        for i in range(22):
            doc=client.post('/api/documents',files={'file':(f'历史合成资料 {i+1:02}.txt',f'历史合成条例编号 {i+1}，仅用于测试分页恢复，不是真实资料。'.encode())}).json()
            client.delete('/api/documents/'+doc['id'])
        server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8895,log_level='warning'))
        thread=threading.Thread(target=server.run);thread.start()
        print('Synthetic demo: http://127.0.0.1:8895/ ; press Enter to stop and clean up.',flush=True)
        try:input()
        finally:server.should_exit=True;thread.join(timeout=15)
        if thread.is_alive():raise RuntimeError('demo server did not stop')

if __name__=='__main__':main()
