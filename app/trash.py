"""Recoverable document removal; no permanent purge endpoint or auto-expiry."""
import time,uuid
from fastapi import HTTPException,Request,Query
from .common import database


def install_trash(app,root,access,identity):
    with database(root) as db:
        if 'deleted_at' not in {r[1] for r in db.execute('PRAGMA table_info(documents)')}:
            db.execute('ALTER TABLE documents ADD COLUMN deleted_at REAL NOT NULL DEFAULT 0')
        db.execute('CREATE INDEX IF NOT EXISTS documents_lifecycle ON documents(kb_id,deleted_at,id)')

    @app.get('/api/trash')
    def listing(request:Request,kb_id:str='',offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100)):
        kb=access(request,kb_id)
        with database(root) as db:
            # One read snapshot for count and page, no document bodies in list.
            db.execute('BEGIN')
            count=db.execute('SELECT count(*) FROM documents WHERE kb_id=? AND deleted_at>0',(kb,)).fetchone()[0]
            rows=db.execute('SELECT id,name,kind,characters,version,deleted_at FROM documents WHERE kb_id=? AND deleted_at>0 ORDER BY deleted_at DESC,id LIMIT ? OFFSET ?',(kb,limit,offset)).fetchall()
        return {'items':[dict(r) for r in rows],'total':count,'offset':offset,'limit':limit}

    def change(ident,request,restore=False):
        with database(root) as db:
            row=db.execute('SELECT kb_id FROM documents WHERE id=?',(ident,)).fetchone()
        if not row:raise HTTPException(404,'文档不存在')
        kb=access(request,row['kb_id'],True);user=identity(request)['id']
        with database(root) as db:
            db.execute('BEGIN IMMEDIATE')
            # Revalidate editor membership within the lifecycle write snapshot.
            owner=db.execute('SELECT owner FROM knowledge_bases WHERE id=?',(kb,)).fetchone()
            grant=db.execute("SELECT 1 FROM members WHERE kb_id=? AND user_id=? AND role='editor'",(kb,user)).fetchone()
            if not owner or (owner[0]!=user and not grant):raise HTTPException(403,'编辑权限已撤销')
            doc=db.execute('SELECT deleted_at FROM documents WHERE id=? AND kb_id=?',(ident,kb)).fetchone()
            if not doc:raise HTTPException(404,'文档不存在')
            if restore and doc[0]==0:raise HTTPException(409,'文档已经处于活动状态')
            changed=restore or doc[0]==0
            if changed:
                db.execute('UPDATE documents SET deleted_at=? WHERE id=?',(0 if restore else time.time(),ident))
                db.execute('INSERT INTO audit VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,user,kb,'restore-document' if restore else 'trash-document',ident,time.time()))
        return {'ok':True,'id':ident,'state':'active' if restore else 'trashed','changed':changed}

    @app.delete('/api/documents/{ident}')
    def remove(ident:str,request:Request):return change(ident,request)

    @app.post('/api/trash/{ident}/restore')
    def restore(ident:str,request:Request):return change(ident,request,True)
