import json,time,uuid
from fastapi import HTTPException,Request
from fastapi.responses import Response
from pydantic import BaseModel,Field
from .common import database
from .retrieval import index_chunk,tokens

class Space(BaseModel):
    name:str=Field(min_length=1,max_length=80)
class Grant(BaseModel):
    username:str
    role:str=Field(pattern='^(reader|editor)$')
class Feedback(BaseModel):
    message_id:str
    rating:int=Field(ge=-1,le=1)
    note:str=Field('',max_length=1000)

def install_workspace(app,root,identity):
    with database(root) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS knowledge_bases(id TEXT PRIMARY KEY,name TEXT,owner TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS members(kb_id TEXT REFERENCES knowledge_bases(id) ON DELETE CASCADE,user_id TEXT,role TEXT,PRIMARY KEY(kb_id,user_id));
        CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY,user_id TEXT,kb_id TEXT,question TEXT,answer TEXT,sources TEXT,mode TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,message_id TEXT,user_id TEXT,rating INTEGER,note TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,user_id TEXT,kb_id TEXT,action TEXT,detail TEXT,created REAL);''')
        db.execute("INSERT OR IGNORE INTO knowledge_bases VALUES('default','我的知识库','local',?)",(time.time(),))
        if 'parent_id' not in {r[1] for r in db.execute('PRAGMA table_info(messages)')}:db.execute("ALTER TABLE messages ADD COLUMN parent_id TEXT DEFAULT ''")
    def access(request,kb='',write=False):
        user=identity(request)['id'];kb=kb or ('default' if user=='local' else 'default-'+user)
        with database(root) as db:
            if kb=='default-'+user and user!='local':db.execute('INSERT OR IGNORE INTO knowledge_bases VALUES(?,?,?,?)',(kb,'我的知识库',user,time.time()))
            row=db.execute('SELECT * FROM knowledge_bases WHERE id=?',(kb,)).fetchone()
            member=db.execute('SELECT role FROM members WHERE kb_id=? AND user_id=?',(kb,user)).fetchone()
            if not row or (row['owner']!=user and (not member or (write and member['role']!='editor'))):raise HTTPException(403,'没有知识库访问权限')
        return kb
    def audit(user,kb,action,detail=''):
        with database(root) as db:db.execute('INSERT INTO audit VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,user,kb,action,detail[:300],time.time()))
    @app.get('/api/workspace/bases')
    def bases(request:Request):
        access(request)
        with database(root) as db:return [dict(r) for r in db.execute('SELECT k.* FROM knowledge_bases k WHERE owner=? OR id IN (SELECT kb_id FROM members WHERE user_id=?) ORDER BY created',(identity(request)['id'],identity(request)['id']))]
    @app.post('/api/workspace/bases',status_code=201)
    def create(body:Space,request:Request):
        key=uuid.uuid4().hex;user=identity(request)['id']
        with database(root) as db:db.execute('INSERT INTO knowledge_bases VALUES(?,?,?,?)',(key,body.name.strip(),user,time.time()))
        audit(user,key,'create');return {'id':key}
    @app.post('/api/workspace/bases/{kb}/members')
    def share(kb:str,body:Grant,request:Request):
        access(request,kb,True);user=identity(request)['id']
        with database(root) as db:
            if db.execute('SELECT owner FROM knowledge_bases WHERE id=?',(kb,)).fetchone()[0]!=user:raise HTTPException(403,'只有所有者能授权')
            target=db.execute('SELECT id FROM users WHERE username=?',(body.username.lower(),)).fetchone()
            if not target:raise HTTPException(404,'账户不存在')
            db.execute('INSERT OR REPLACE INTO members VALUES(?,?,?)',(kb,target['id'],body.role))
        audit(user,kb,'grant',body.username+':'+body.role);return {'ok':True}
    @app.delete('/api/workspace/bases/{kb}/members/{username}')
    def revoke(kb:str,username:str,request:Request):
        access(request,kb,True)
        with database(root) as db:
            if db.execute('SELECT owner FROM knowledge_bases WHERE id=?',(kb,)).fetchone()[0]!=identity(request)['id']:raise HTTPException(403,'只有所有者能撤销')
            db.execute('DELETE FROM members WHERE kb_id=? AND user_id IN (SELECT id FROM users WHERE username=?)',(kb,username.lower()))
        return {'ok':True}
    @app.get('/api/workspace/messages')
    def messages(request:Request,kb:str=''):
        kb=access(request,kb)
        with database(root) as db:
            return [{**dict(r),'sources':json.loads(r['sources'])} for r in db.execute('SELECT * FROM messages WHERE user_id=? AND kb_id=? ORDER BY created DESC LIMIT 100',(identity(request)['id'],kb))]
    def save_message(request,kb,question,result,parent=''):
        key=uuid.uuid4().hex
        with database(root) as db:db.execute('INSERT INTO messages(id,user_id,kb_id,question,answer,sources,mode,created,parent_id) VALUES(?,?,?,?,?,?,?,?,?)',(key,identity(request)['id'],kb,question,result['answer'],json.dumps(result['sources'],ensure_ascii=False),result['mode'],time.time(),parent))
        result['message_id']=key;return result
    @app.post('/api/workspace/feedback')
    def feedback(body:Feedback,request:Request):
        user=identity(request)['id']
        with database(root) as db:
            if not db.execute('SELECT 1 FROM messages WHERE id=? AND user_id=?',(body.message_id,user)).fetchone():raise HTTPException(404,'问答记录不存在')
            db.execute('INSERT INTO feedback VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,body.message_id,user,body.rating,body.note,time.time()))
        return {'ok':True}
    @app.post('/api/workspace/bases/{kb}/reindex')
    def reindex(kb:str,request:Request):
        access(request,kb,True)
        with database(root) as db:
            rows=db.execute('SELECT c.id,c.text FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.kb_id=? AND d.deleted_at=0',(kb,)).fetchall()
            for row in rows:
                db.execute('DELETE FROM terms WHERE chunk_id=?',(row['id'],));db.execute('DELETE FROM vectors WHERE chunk_id=?',(row['id'],));index_chunk(db,row['id'],row['text'])
            db.execute('UPDATE chunks SET length=length WHERE document_id IN (SELECT id FROM documents WHERE kb_id=? AND deleted_at=0)',(kb,))
        audit(identity(request)['id'],kb,'reindex',str(len(rows)));return {'chunks':len(rows)}
    @app.get('/api/workspace/bases/{kb}/backup')
    def backup(kb:str,request:Request):
        access(request,kb)
        with database(root) as db:
            documents=[dict(r) for r in db.execute('SELECT * FROM documents WHERE kb_id=?',(kb,))]
            for doc in documents:doc['chunks']=[dict(r) for r in db.execute('SELECT * FROM chunks WHERE document_id=? ORDER BY idx',(doc['id'],))]
        return Response(json.dumps({'version':1,'documents':documents},ensure_ascii=False),media_type='application/json',headers={'Content-Disposition':'attachment; filename="recalldock-backup.json"'})
    @app.get('/api/workspace/bases/{kb}/audit')
    def audit_list(kb:str,request:Request):
        access(request,kb,True)
        with database(root) as db:return [dict(r) for r in db.execute('SELECT * FROM audit WHERE kb_id=? ORDER BY created DESC LIMIT 100',(kb,))]
    return access,save_message,audit
