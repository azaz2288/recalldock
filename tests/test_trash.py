from pathlib import Path
import copy,json,tempfile,time,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.common import database


class TrashTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.app=create_app(self.root);self.client=TestClient(self.app)
    def tearDown(self):self.tmp.cleanup()
    def upload(self,text='备份文件保留三十天。',name='manual.txt'):
        return self.client.post('/api/documents',files={'file':(name,text.encode())})
    def trash(self,ident):return self.client.delete('/api/documents/'+ident)
    def restore(self,ident):return self.client.post('/api/trash/'+ident+'/restore')
    def ask(self):return self.client.post('/api/ask',json={'question':'备份'}).json()
    def test_retains_all_content_indexes_and_restores_after_restart(self):
        ident=self.upload().json()['id'];before=self.ask()['sources']
        with database(self.root) as db:
            counts={t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['documents','chunks','terms','vectors']}
        self.assertEqual(self.trash(ident).status_code,200)
        with database(self.root) as db:
            self.assertEqual(counts,{t:db.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in counts})
        self.assertEqual(self.client.get('/api/documents').json(),[])
        self.assertEqual(self.ask()['sources'],[])
        self.assertEqual(self.client.get('/api/documents/'+ident+'/chunks').status_code,404)
        self.client=TestClient(create_app(self.root))
        self.assertEqual(self.client.get('/api/trash').json()['total'],1)
        self.assertEqual(self.restore(ident).status_code,200)
        self.assertEqual(before,self.ask()['sources'])
    def test_no_evidence_never_calls_paid_model_and_preview_conflicts(self):
        ident=self.upload().json()['id'];preview=self.client.post('/api/preview',json={'question':'备份'}).json()
        self.trash(ident)
        with patch('app.main.generate') as provider,patch('app.main.generate_stream') as streaming:
            self.assertEqual(self.client.post('/api/ask',json={'question':'备份','use_ai':True}).json()['mode'],'no-evidence')
            self.assertEqual(self.client.post('/api/ask',json={'question':'备份','use_ai':True,'context_fingerprint':preview['context_fingerprint']}).status_code,409)
            provider.assert_not_called();streaming.assert_not_called()
    def test_duplicate_import_cannot_silently_resurrect(self):
        ident=self.upload().json()['id'];self.trash(ident)
        self.assertEqual(self.upload().status_code,409)
        self.assertEqual(self.ask()['sources'],[])
        self.restore(ident);self.assertTrue(self.upload().json()['duplicate'])
    def test_versions_preserved_but_mutations_and_previews_blocked_in_trash(self):
        ident=self.upload().json()['id']
        self.client.post('/api/ingest/documents/'+ident+'/revise',files={'file':('revision.txt','备份保留六十天'.encode())})
        self.trash(ident)
        for endpoint in ['versions','versions/1']:
            self.assertEqual(self.client.get('/api/ingest/documents/'+ident+'/'+endpoint).status_code,404)
        self.assertEqual(self.client.post('/api/ingest/documents/'+ident+'/revise',files={'file':('x.txt',b'replacement')}).status_code,404)
        self.restore(ident)
        self.assertIn('三十天',str(self.client.get('/api/ingest/documents/'+ident+'/versions/1').json()))
        self.assertIn('六十天',self.ask()['answer'])
    def test_revision_checks_trash_again_inside_write_transaction(self):
        ident=self.upload().json()['id']
        from app.main import extract
        def changed(raw,suffix):
            self.trash(ident);return extract(raw,suffix)
        with patch('app.main.extract',side_effect=changed):
            response=self.client.post('/api/ingest/documents/'+ident+'/revise',files={'file':('x.txt',b'new backup')})
        self.assertEqual(response.status_code,409);self.restore(ident)
        self.assertIn('三十天',self.ask()['answer'])
    def test_idempotent_delete_and_explicit_restore_missing_or_active(self):
        ident=self.upload().json()['id']
        self.assertEqual(self.restore(ident).status_code,409)
        self.trash(ident);stamp=self.client.get('/api/trash').json()['items'][0]['deleted_at']
        self.assertEqual(self.trash(ident).status_code,200)
        self.assertEqual(stamp,self.client.get('/api/trash').json()['items'][0]['deleted_at'])
        self.assertEqual(self.restore('missing').status_code,404)
    def test_permissions_and_knowledge_base_scope(self):
        owner=TestClient(self.app);reader=TestClient(self.app)
        for client,user in [(owner,'alice'),(reader,'bobby')]:
            client.post('/api/auth/register',json={'username':user,'password':'-'.join(['synthetic','only',user])})
        kb=owner.post('/api/workspace/bases',json={'name':'合成权限库'}).json()['id']
        ident=owner.post('/api/documents',data={'kb_id':kb},files={'file':('x.txt',b'backup permission fixture')}).json()['id']
        owner.delete('/api/documents/'+ident)
        self.assertEqual(reader.get('/api/trash?kb_id='+kb).status_code,403)
        owner.post('/api/workspace/bases/'+kb+'/members',json={'username':'bobby','role':'reader'})
        self.assertEqual(reader.get('/api/trash?kb_id='+kb).json()['total'],1)
        self.assertEqual(reader.post('/api/trash/'+ident+'/restore').status_code,403)
        owner.post('/api/workspace/bases/'+kb+'/members',json={'username':'bobby','role':'editor'})
        self.assertEqual(reader.post('/api/trash/'+ident+'/restore').status_code,200)
        self.assertEqual(self.client.get('/api/trash').json()['total'],0)
    def test_backup_restores_trash_state_and_legacy_field_defaults_active(self):
        ident=self.upload().json()['id'];self.trash(ident)
        backup=self.client.get('/api/workspace/bases/default/backup').json()
        self.assertGreater(backup['documents'][0]['deleted_at'],0)
        kb=self.client.post('/api/workspace/bases',json={'name':'恢复库'}).json()['id']
        result=self.client.post('/api/workspace/restore-backup',data={'kb_id':kb},files={'file':('b.json',json.dumps(backup))})
        self.assertEqual(result.status_code,200)
        self.assertEqual(self.client.get('/api/trash?kb_id='+kb).json()['total'],1)
        self.assertEqual(self.client.post('/api/ask',json={'question':'备份','kb_id':kb}).json()['sources'],[])
        legacy=copy.deepcopy(backup);legacy['documents'][0].pop('deleted_at')
        kb2=self.client.post('/api/workspace/bases',json={'name':'旧备份恢复库'}).json()['id']
        self.assertEqual(self.client.post('/api/workspace/restore-backup',data={'kb_id':kb2},files={'file':('b.json',json.dumps(legacy))}).status_code,200)
        self.assertTrue(self.client.post('/api/ask',json={'question':'备份','kb_id':kb2}).json()['sources'])
    def test_invalid_backup_trash_metadata_is_atomic(self):
        self.upload();backup=self.client.get('/api/workspace/bases/default/backup').json()
        kb=self.client.post('/api/workspace/bases',json={'name':'无效恢复库'}).json()['id']
        for bad in [-1,True,'now',float('inf'),float('nan'),10**400,None]:
            with self.subTest(bad=bad):
                data=copy.deepcopy(backup);data['documents']*=2;data['documents'][1]['deleted_at']=bad
                self.assertEqual(self.client.post('/api/workspace/restore-backup',data={'kb_id':kb},files={'file':('b.json',json.dumps(data))}).status_code,400)
                self.assertEqual(self.client.get('/api/documents?kb_id='+kb).json(),[])
        for bad in [None,[],1]:
            with self.subTest(document=bad):
                data=copy.deepcopy(backup);data['documents'].append(bad)
                self.assertEqual(self.client.post('/api/workspace/restore-backup',data={'kb_id':kb},files={'file':('b.json',json.dumps(data))}).status_code,400)
    def test_active_statistics_and_reindex_exclude_trash(self):
        ident=self.upload().json()['id'];self.upload('备份策略属于活动资料。','active.txt');self.trash(ident)
        self.assertEqual(self.client.post('/api/workspace/bases/default/reindex').json()['chunks'],1)
        self.assertTrue(all(s['document_id']!=ident for s in self.ask()['sources']))
        self.assertEqual(self.client.get('/api/semantic/default/preview').json()['chunks'],1)
    def test_semantic_index_and_query_exclude_trash_and_detect_midflight_change(self):
        ident=self.upload().json()['id'];self.trash(ident)
        with patch('app.semantic.embed') as provider:
            self.assertEqual(self.client.post('/api/semantic/default/index',json={'confirm':True}).json()['indexed'],0)
            provider.assert_not_called()
        self.restore(ident)
        def change(texts):
            self.trash(ident);return 'mock',[ [1.0,0.0] for t in texts ]
        with patch('app.semantic.embed',side_effect=change):
            self.assertEqual(self.client.post('/api/semantic/default/index',json={'confirm':True}).status_code,409)
        with database(self.root) as db:self.assertEqual(db.execute('SELECT count(*) FROM semantic_vectors').fetchone()[0],0)
        self.restore(ident)
        with patch('app.semantic.embed',return_value=('mock',[[1.0,0.0]])):
            self.client.post('/api/semantic/default/index',json={'confirm':True});self.trash(ident)
            self.assertEqual(self.client.post('/api/ask',json={'question':'备份','semantic':True}).json()['sources'],[])
    def test_paginated_trash_is_stable_bounded_and_validates_query(self):
        for i in range(5):self.trash(self.upload('备份合成文档 '+str(i),str(i)+'.txt').json()['id'])
        first=self.client.get('/api/trash?limit=2').json();last=self.client.get('/api/trash?limit=2&offset=2').json()
        self.assertEqual(first['total'],5);self.assertEqual(len(first['items']),2)
        self.assertFalse(set(x['id'] for x in first['items'])&set(x['id'] for x in last['items']))
        for query in ['offset=-1','limit=0','limit=101']:
            self.assertEqual(self.client.get('/api/trash?'+query).status_code,422)

    def test_lifecycle_audit_is_atomic_and_idempotent(self):
        ident=self.upload().json()['id']
        stamp=time.time()
        with patch('app.trash.time') as clock:
            clock.time.side_effect=[stamp,RuntimeError('synthetic audit fault')]
            response=TestClient(self.app,raise_server_exceptions=False).delete('/api/documents/'+ident)
        self.assertEqual(response.status_code,500);self.assertTrue(self.ask()['sources'])
        self.assertEqual(self.client.get('/api/trash').json()['total'],0)
        self.trash(ident);self.trash(ident);self.restore(ident)
        actions=[r['action'] for r in self.client.get('/api/workspace/bases/default/audit').json()]
        self.assertEqual(actions.count('trash-document'),1);self.assertEqual(actions.count('restore-document'),1)

    def test_legacy_schema_additive_migration_preserves_document(self):
        ident=self.upload().json()['id'];before=self.ask()['sources']
        with database(self.root) as db:
            db.execute('DROP INDEX documents_lifecycle');db.execute('ALTER TABLE documents DROP COLUMN deleted_at')
        self.client=TestClient(create_app(self.root))
        self.assertEqual(self.client.get('/api/documents').json()[0]['id'],ident)
        self.assertEqual(self.ask()['sources'],before)
        self.trash(ident);self.assertEqual(self.restore(ident).status_code,200)

    def test_trash_listing_has_metadata_only_and_history_is_retained(self):
        ident=self.upload().json()['id'];answer=self.ask();self.trash(ident)
        items=self.client.get('/api/trash').json()['items']
        self.assertNotIn('三十天',json.dumps(items,ensure_ascii=False))
        history=self.client.get('/api/workspace/messages?kb=default').json()
        self.assertEqual(history[0]['sources'],answer['sources'])

    def test_second_restored_document_fault_rolls_back_all_states_and_indexes(self):
        self.upload();self.trash(self.upload('备份第二份保留一年','second.txt').json()['id'])
        body=self.client.get('/api/workspace/bases/default/backup').json()
        kb=self.client.post('/api/workspace/bases',json={'name':'原子故障库'}).json()['id']
        from app.backup import index_chunk
        calls=0
        def fault(db,key,text):
            nonlocal calls
            calls+=1
            if calls==2:raise RuntimeError('synthetic second insert failure')
            return index_chunk(db,key,text)
        with patch('app.backup.index_chunk',side_effect=fault):
            response=TestClient(self.app,raise_server_exceptions=False).post('/api/workspace/restore-backup',data={'kb_id':kb},files={'file':('b.json',json.dumps(body))})
        self.assertEqual(response.status_code,500)
        self.assertEqual(self.client.get('/api/documents?kb_id='+kb).json(),[])
        self.assertEqual(self.client.get('/api/trash?kb_id='+kb).json()['total'],0)
        with database(self.root) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE kb_id=?)',(kb,)).fetchone()[0],0)

    def test_background_duplicate_remains_trashed_and_task_failure_actionable(self):
        ident=self.upload().json()['id'];self.trash(ident)
        with TestClient(self.app) as worker:
            job=worker.post('/api/ingest/jobs',files={'file':('manual.txt','备份文件保留三十天。'.encode())}).json()['id']
            for _ in range(100):
                row=next(r for r in worker.get('/api/ingest/jobs').json() if r['id']==job)
                if row['state'] not in {'queued','running'}:break
                time.sleep(.03)
            self.assertEqual(row['state'],'failed');self.assertIn('回收站',row['error'])
            self.assertEqual(worker.get('/api/trash').json()['total'],1)
            self.assertEqual(worker.post('/api/ask',json={'question':'备份'}).json()['sources'],[])
        time.sleep(.6)
