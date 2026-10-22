"""Historical pages use synthetic revision snapshots, never the user's library."""
from contextlib import contextmanager
from pathlib import Path
import json,tempfile,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from test_support import bootstrap
from app.main import create_app
from app.common import database


class VersionPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.app=create_app(self.root);self.client=TestClient(self.app)
    def tearDown(self):self.tmp.cleanup()
    def fixture(self,client=None,kb=''):
        client=client or self.client
        original='original synthetic history '+('original text only '*2300)+' TAIL-HISTORY'
        result=client.post('/api/documents',data={'kb_id':kb},files={'file':('history.txt',original.encode())})
        self.assertEqual(result.status_code,201);ident=result.json()['id']
        revision=client.post('/api/ingest/documents/'+ident+'/revise',files={'file':('v2.txt',b'new current synthetic text')})
        self.assertEqual(revision.status_code,200);return ident
    def route(self,ident,version=1):return f'/api/ingest/documents/{ident}/versions/{version}/page'
    def test_all_history_pages_equal_stored_snapshot_and_legacy_unchanged(self):
        ident=self.fixture();expected=self.client.get(self.route(ident).removesuffix('/page')).json()
        self.assertGreater(len(expected),50);items=[];offset=0
        while True:
            response=self.client.get(self.route(ident),params={'offset':offset,'limit':20,'kb_id':'default'})
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['cache-control'],'no-store')
            page=response.json();self.assertEqual(page['document'],{'id':ident,'kb_id':'default','name':'history.txt','version':1})
            self.assertEqual(page['total'],len(expected));self.assertEqual(page['offset'],offset)
            self.assertLessEqual(len(page['items']),20);items.extend(page['items'])
            if page['next_offset'] is None:break
            offset=page['next_offset']
        self.assertEqual(items,expected);self.assertIn('TAIL-HISTORY',items[-1]['text'])
        self.assertEqual(self.client.get(self.route(ident).removesuffix('/page')).json(),expected)
        self.assertEqual(self.client.get(self.route(ident),params={'kb_id':'wrong'}).status_code,404)
    def test_query_bounds_empty_and_missing_versions(self):
        ident=self.fixture()
        for query in ({'offset':-1},{'offset':2147483648},{'limit':0},{'limit':51},{'limit':'x'}):
            with self.subTest(query=query):self.assertEqual(self.client.get(self.route(ident),params=query).status_code,422)
        self.assertEqual(self.client.get(self.route(ident,0)).status_code,422)
        self.assertEqual(self.client.get(self.route(ident,9223372036854775808)).status_code,422)
        self.assertEqual(self.client.get(self.route(ident,2)).status_code,404)
        response=self.client.get(self.route(ident),params={'offset':2147483647,'limit':50})
        self.assertEqual(response.status_code,200);self.assertEqual(response.json()['items'],[])
        self.assertIsNone(response.json()['next_offset'])
        with database(self.root) as db:db.execute("UPDATE document_versions SET chunks_json='[]' WHERE document_id=?",(ident,))
        data=self.client.get(self.route(ident)).json();self.assertEqual(data['total'],0);self.assertEqual(data['items'],[])
    def test_history_stays_immutable_after_revision_and_restart(self):
        ident=self.fixture();first=self.client.get(self.route(ident));self.assertEqual(first.status_code,200)
        self.client.post('/api/ingest/documents/'+ident+'/revise',files={'file':('v3.txt',b'third synthetic revision')})
        self.client=TestClient(create_app(self.root))
        self.assertEqual(self.client.get(self.route(ident)).json(),first.json())
        self.assertEqual(self.client.get(self.route(ident,2)).json()['items'][0]['text'],'new current synthetic text')
    def test_trash_and_restore_guard_history(self):
        ident=self.fixture();self.client.delete('/api/documents/'+ident)
        self.assertEqual(self.client.get(self.route(ident)).status_code,404)
        self.client.post('/api/trash/'+ident+'/restore')
        self.assertEqual(self.client.get(self.route(ident)).status_code,200)
        self.assertEqual(self.client.get(self.route('missing')).status_code,404)
    def test_reader_access_revoked_between_pages(self):
        owner=TestClient(self.app);reader=TestClient(self.app)
        for client,user in ((owner,'alice'),(reader,'bobby')):
            self.assertEqual(client.post('/api/auth/register',json={'username':user,'password':'synthetic-only-'+user}).status_code,201)
        kb=owner.post('/api/workspace/bases',json={'name':'synthetic-private'}).json()['id']
        ident=self.fixture(owner,kb)
        self.assertEqual(reader.get(self.route(ident)).status_code,403)
        owner.post('/api/workspace/bases/'+kb+'/members',json={'username':'bobby','role':'reader'})
        self.assertEqual(reader.get(self.route(ident),params={'limit':1}).status_code,200)
        owner.delete('/api/workspace/bases/'+kb+'/members/bobby')
        response=reader.get(self.route(ident),params={'offset':1})
        self.assertEqual(response.status_code,403);self.assertNotIn('items',response.json())
    def test_permission_and_text_share_one_snapshot(self):
        ident=self.fixture();before=self.client.get(self.route(ident));self.assertEqual(before.status_code,200)
        fired=[];test=self
        @contextmanager
        def interleaved(root):
            with database(root) as db:
                class Proxy:
                    def execute(self,sql,args=()):
                        result=db.execute(sql,args)
                        if 'count(*)' in sql and 'json_each' in sql and not fired:
                            fired.append(True)
                            test.assertEqual(test.client.delete('/api/documents/'+ident).status_code,200)
                        return result
                yield Proxy()
        with patch('app.document_pages.database',interleaved):response=self.client.get(self.route(ident))
        self.assertTrue(fired);self.assertEqual(response.json(),before.json())
        self.assertEqual(self.client.get(self.route(ident)).status_code,404)
    def test_only_requested_slice_is_deserialized_in_python(self):
        ident=self.fixture();calls=[];decode=json.loads
        def capture(value,*args,**kwargs):
            if isinstance(value,str):calls.append(value)
            return decode(value,*args,**kwargs)
        with patch('app.document_pages.json.loads',capture):
            response=self.client.get(self.route(ident),params={'limit':1})
        self.assertEqual(response.status_code,200);self.assertEqual(len(response.json()['items']),1)
        self.assertEqual(len([v for v in calls if 'original text only' in v]),1)
        self.assertFalse(any(v.lstrip().startswith('[') and 'original text only' in v for v in calls))

    def test_invalid_snapshot_json_is_controlled_conflict(self):
        ident=self.fixture()
        for invalid in ('broken-json','{}','null','[null]','[1]','[{}]'):
            with self.subTest(invalid=invalid):
                with database(self.root) as db:
                    db.execute('UPDATE document_versions SET chunks_json=? WHERE document_id=?',(invalid,ident))
                response=self.client.get(self.route(ident))
                self.assertEqual(response.status_code,409);self.assertNotIn('items',response.json())

if __name__=='__main__':unittest.main()
