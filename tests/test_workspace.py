def synthetic_password(suffix):
    return '-'.join(['synthetic','pass',suffix])

from pathlib import Path
import tempfile,unittest,json,time
from unittest.mock import patch
from test_support import bootstrap
from app.common import database
from app.ocr import ocr_page
from fastapi.testclient import TestClient
from app.main import create_app

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.app=create_app(Path(self.tmp.name));self.a=TestClient(self.app);self.b=TestClient(self.app)
        self.a.post('/api/auth/register',json={'username':'alice','password':synthetic_password('123')})
        self.b.post('/api/auth/register',json={'username':'bobby','password':synthetic_password('456')})
        self.kb=self.a.post('/api/workspace/bases',json={'name':'私有资料'}).json()['id']
    def tearDown(self):self.tmp.cleanup()
    def document(self):return self.a.post('/api/documents',data={'kb_id':self.kb},files={'file':('private.txt','备份文件保留三十天。'.encode())}).json()['id']
    def test_permissions_filter_before_retrieval(self):
        ident=self.document()
        self.assertEqual(self.b.post('/api/ask',json={'question':'备份','kb_id':self.kb}).status_code,403)
        self.assertEqual(self.b.get('/api/documents/'+ident+'/chunks').status_code,403)
        self.a.post('/api/workspace/bases/'+self.kb+'/members',json={'username':'bobby','role':'reader'})
        self.assertEqual(self.b.post('/api/ask',json={'question':'备份','kb_id':self.kb}).status_code,200)
        self.assertEqual(self.b.delete('/api/documents/'+ident).status_code,403)
        self.a.delete('/api/workspace/bases/'+self.kb+'/members/bobby')
        self.assertEqual(self.b.post('/api/ask',json={'question':'备份','kb_id':self.kb}).status_code,403)
    def test_reindex_backup_messages_feedback(self):
        self.document();answer=self.a.post('/api/ask',json={'question':'备份','kb_id':self.kb}).json()
        self.assertTrue(answer['sources']);self.assertEqual(len(self.a.get('/api/workspace/messages?kb='+self.kb).json()),1)
        self.assertEqual(self.a.post('/api/workspace/feedback',json={'message_id':answer['message_id'],'rating':1}).status_code,200)
        self.assertEqual(self.b.post('/api/workspace/feedback',json={'message_id':answer['message_id'],'rating':1}).status_code,404)
        self.assertEqual(self.a.post('/api/workspace/bases/'+self.kb+'/reindex').json()['chunks'],1)
        self.assertEqual(len(self.a.get('/api/workspace/bases/'+self.kb+'/backup').json()['documents']),1)
    def test_revision_preserves_history(self):
        ident=self.document();response=self.a.post('/api/ingest/documents/'+ident+'/revise',files={'file':('new.txt','备份保留六十天。'.encode())})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['version'],2)
        self.assertEqual(self.a.get('/api/ingest/documents/'+ident+'/versions').json()[0]['version'],1)
        self.assertIn('六十天',self.a.post('/api/ask',json={'question':'备份','kb_id':self.kb}).json()['answer'])
    def test_stream_and_cancelled_job(self):
        self.document();response=self.a.post('/api/ask-stream',json={'question':'备份','kb_id':self.kb})
        self.assertIn('event: sources',response.text);self.assertIn('event: done',response.text)
        job=self.a.post('/api/ingest/jobs',data={'kb_id':self.kb},files={'file':('job.txt',b'test')}).json()['id']
        self.assertEqual(self.a.post('/api/ingest/jobs/'+job+'/cancel').status_code,200)
        self.assertEqual(self.a.get('/api/ingest/jobs?kb_id='+self.kb).json()[0]['state'],'cancelled')
    def test_backup_restore_reindexes_and_invalid_backup_is_atomic(self):
        self.document();backup=self.a.get('/api/workspace/bases/'+self.kb+'/backup').json()
        target=self.a.post('/api/workspace/bases',json={'name':'恢复目标'}).json()['id']
        response=self.a.post('/api/workspace/restore-backup',data={'kb_id':target},files={'file':('backup.json',json.dumps(backup).encode())})
        self.assertEqual(response.json()['restored'],1)
        self.assertTrue(self.a.post('/api/ask',json={'question':'备份','kb_id':target}).json()['sources'])
        backup['documents'].append({**backup['documents'][0],'chunks':[{'idx':9,'page':1,'text':'bad'}]})
        target2=self.a.post('/api/workspace/bases',json={'name':'无效恢复'}).json()['id']
        self.assertEqual(self.a.post('/api/workspace/restore-backup',data={'kb_id':target2},files={'file':('backup.json',json.dumps(backup).encode())}).status_code,400)
        self.assertEqual(self.a.get('/api/documents?kb_id='+target2).json(),[])
    def test_semantic_requires_confirmation_and_permissions(self):
        self.document();url='/api/semantic/'+self.kb+'/index'
        with patch('app.semantic.embed',return_value=('test-model',[[1.,0.]])) as provider:
            self.assertEqual(self.b.post(url,json={'confirm':True}).status_code,403)
            self.assertEqual(self.a.post(url,json={'confirm':False}).status_code,400)
            provider.assert_not_called()
            self.assertEqual(self.a.post(url,json={'confirm':True}).json()['indexed'],1)
            answer=self.a.post('/api/ask',json={'question':'归档','kb_id':self.kb,'semantic':True}).json()
            self.assertIn('三十天',answer['sources'][0]['text'])
    def test_semantic_rejects_concurrent_revision(self):
        ident=self.document()
        def revise_during_embed(texts):
            self.a.post('/api/ingest/documents/'+ident+'/revise',files={'file':('new.txt','新版资料'.encode())})
            return 'test-model',[[1.,0.] for _ in texts]
        with patch('app.semantic.embed',side_effect=revise_during_embed):
            self.assertEqual(self.a.post('/api/semantic/'+self.kb+'/index',json={'confirm':True}).status_code,409)
        with database(Path(self.tmp.name)) as db:self.assertEqual(db.execute('SELECT count(*) FROM semantic_vectors').fetchone()[0],0)
    def test_ingest_worker_completes_without_model(self):
        with TestClient(self.app) as active:
            active.cookies.update(self.a.cookies)
            job=active.post('/api/ingest/jobs',data={'kb_id':self.kb},files={'file':('queue.txt','队列文档自动建立索引。'.encode())}).json()['id']
            for _ in range(100):
                row=next(r for r in active.get('/api/ingest/jobs?kb_id='+self.kb).json() if r['id']==job)
                if row['state'] not in {'queued','running'}:break
                time.sleep(.03)
            self.assertEqual(row['state'],'completed')
            self.assertTrue(active.post('/api/ask',json={'question':'队列','kb_id':self.kb}).json()['sources'])
        time.sleep(.6)
    def test_ocr_missing_dependency_is_actionable(self):
        with patch('app.ocr.os.getenv',return_value=None),patch('app.ocr.shutil.which',return_value=None):
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as caught:ocr_page(b'fixture',0)
            self.assertEqual(caught.exception.status_code,503)
    def test_followup_keeps_sources_and_cannot_use_another_users_history(self):
        self.document();first=self.a.post('/api/ask',json={'question':'备份','kb_id':self.kb}).json()
        follow=self.a.post('/api/ask',json={'question':'保留多久？','kb_id':self.kb,'parent_id':first['message_id']}).json()
        self.assertIn('三十天',follow['answer']);self.assertEqual(follow['sources'][0]['version'],1)
        self.a.post('/api/workspace/bases/'+self.kb+'/members',json={'username':'bobby','role':'reader'})
        self.assertEqual(self.b.post('/api/ask',json={'question':'多久','kb_id':self.kb,'parent_id':first['message_id']}).status_code,404)
    def test_real_delta_stream_validates_before_saving(self):
        self.document()
        with patch('app.main.generate_stream',return_value=iter(['保留','三十天[1]'])):
            response=self.a.post('/api/ask-stream',json={'question':'备份','kb_id':self.kb,'use_ai':True})
            self.assertIn('event: done',response.text);self.assertIn('event: text',response.text)
        with patch('app.main.generate_stream',return_value=iter(['无效来源[99]'])):
            response=self.a.post('/api/ask-stream',json={'question':'备份','kb_id':self.kb,'use_ai':True})
            self.assertIn('event: error',response.text);self.assertNotIn('event: done',response.text)
        self.assertEqual(len(self.a.get('/api/workspace/messages?kb='+self.kb).json()),1)
    def test_preview_detects_changed_sources_before_model_request(self):
        ident=self.document();preview=self.a.post('/api/preview',json={'question':'备份','kb_id':self.kb}).json()
        self.a.post('/api/ingest/documents/'+ident+'/revise',files={'file':('revision.txt','备份保留六十天'.encode())})
        with patch('app.main.generate') as provider:
            self.assertEqual(self.a.post('/api/ask',json={'question':'备份','kb_id':self.kb,'use_ai':True,'context_fingerprint':preview['context_fingerprint']}).status_code,409)
            provider.assert_not_called()

if __name__=='__main__':unittest.main()
