"""Original synthetic document pagination, revisions and access boundaries."""
from pathlib import Path
from contextlib import contextmanager
import tempfile,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.common import database


class DocumentPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.app=create_app(self.root);self.client=TestClient(self.app)
    def tearDown(self):self.tmp.cleanup()
    def upload(self,text='synthetic backup '+('original text only '*2300),client=None,kb=''):
        response=(client or self.client).post('/api/documents',data={'kb_id':kb},files={'file':('original.txt',text.encode())})
        self.assertEqual(response.status_code,201);return response.json()['id']
    def page(self,ident,**query):
        return self.client.get('/api/documents/'+ident+'/chunks/page',params=query)

    def test_all_pages_match_independent_order_without_missing_tail(self):
        ident=self.upload()
        with database(self.root) as db:
            expected=[dict(r) for r in db.execute('SELECT idx,page,text FROM chunks WHERE document_id=? ORDER BY idx,id',(ident,))]
        self.assertGreater(len(expected),50);seen=[];offset=0;version=None
        while True:
            query={'offset':offset,'limit':20}
            if version is not None:query['expected_version']=version
            response=self.page(ident,**query);self.assertEqual(response.status_code,200)
            self.assertEqual(response.headers['cache-control'],'no-store')
            data=response.json();version=data['document']['version']
            self.assertEqual(data['total'],len(expected));self.assertEqual(data['offset'],offset)
            self.assertEqual(data['document']['id'],ident);self.assertEqual(data['document']['kb_id'],'default')
            self.assertLessEqual(len(data['items']),20);seen.extend(data['items'])
            if data['next_offset'] is None:break
            offset=data['next_offset']
        self.assertEqual(seen,expected)
        legacy=self.client.get('/api/documents/'+ident+'/chunks').json()
        self.assertIsInstance(legacy,list);self.assertEqual(legacy,expected[:50])
        self.assertEqual(self.page(ident,kb_id='other').status_code,404)
        self.assertEqual(self.page(ident,limit=50).json()['items'],expected[:50])

    def test_version_change_conflicts_and_explicit_restart_reads_new_version(self):
        ident=self.upload();first=self.page(ident,limit=1).json()
        result=self.client.post('/api/ingest/documents/'+ident+'/revise',files={'file':('v2.txt',b'new original revision')})
        self.assertEqual(result.status_code,200)
        stale=self.page(ident,offset=1,expected_version=first['document']['version'])
        self.assertEqual(stale.status_code,409);self.assertNotIn('items',stale.json())
        fresh=self.page(ident).json();self.assertEqual(fresh['document']['version'],2)
        self.assertEqual(fresh['items'][0]['text'],'new original revision')

    def test_limits_invalid_input_and_empty_or_out_of_range_page(self):
        ident=self.upload('short fixture')
        for query in ({'offset':-1},{'offset':2147483648},{'limit':0},{'limit':51},{'limit':'x'},{'expected_version':0}):
            with self.subTest(query=query):self.assertEqual(self.page(ident,**query).status_code,422)
        for offset in (1,2147483647):
            data=self.page(ident,offset=offset,limit=50).json()
            self.assertEqual(data['items'],[]);self.assertEqual(data['total'],1);self.assertIsNone(data['next_offset'])
        with database(self.root) as db:db.execute('DELETE FROM chunks WHERE document_id=?',(ident,))
        data=self.page(ident).json();self.assertEqual(data['total'],0);self.assertEqual(data['items'],[])

    def test_trashed_missing_and_restart_do_not_expose_document(self):
        ident=self.upload();self.client.delete('/api/documents/'+ident)
        self.assertEqual(self.page(ident).status_code,404);self.assertEqual(self.page('missing').status_code,404)
        self.client=TestClient(create_app(self.root));self.assertEqual(self.page(ident).status_code,404)
        self.client.post('/api/trash/'+ident+'/restore');self.assertEqual(self.page(ident).status_code,200)

    def test_reader_access_and_revocation_checked_on_every_page(self):
        owner=TestClient(self.app);reader=TestClient(self.app)
        for client,user in ((owner,'alice'),(reader,'bobby')):
            self.assertEqual(client.post('/api/auth/register',json={'username':user,'password':'synthetic-only-'+user}).status_code,201)
        kb=owner.post('/api/workspace/bases',json={'name':'synthetic-private'}).json()['id']
        ident=self.upload('private synthetic text',owner,kb);route='/api/documents/'+ident+'/chunks/page'
        self.assertEqual(reader.get(route).status_code,403);self.assertEqual(self.client.get(route).status_code,403)
        owner.post('/api/workspace/bases/'+kb+'/members',json={'username':'bobby','role':'reader'})
        self.assertEqual(reader.get(route).json()['items'][0]['text'],'private synthetic text')
        owner.delete('/api/workspace/bases/'+kb+'/members/bobby')
        self.assertEqual(reader.get(route).status_code,403)

    def test_read_snapshot_does_not_mix_revision_metadata_count_and_body(self):
        ident=self.upload();before=self.page(ident).json();triggered=[];test=self
        @contextmanager
        def interleaved(root):
            with database(root) as db:
                class Proxy:
                    def execute(self,sql,args=()):
                        result=db.execute(sql,args)
                        if 'SELECT count(*) FROM chunks' in sql and not triggered:
                            triggered.append(True)
                            response=test.client.post('/api/ingest/documents/'+ident+'/revise',files={'file':('new.txt',b'concurrent synthetic revision')})
                            test.assertEqual(response.status_code,200)
                        return result
                yield Proxy()
        with patch('app.document_pages.database',interleaved):
            response=self.page(ident,expected_version=1)
        self.assertEqual(response.status_code,200);self.assertTrue(triggered)
        self.assertEqual(response.json(),before)
        self.assertEqual(self.page(ident,expected_version=1).status_code,409)

if __name__=='__main__':unittest.main()
