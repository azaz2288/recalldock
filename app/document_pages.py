"""Bounded current-version text pages from one SQLite read snapshot."""
from fastapi import HTTPException,Query,Request
from fastapi.responses import JSONResponse
from .common import database


def install_document_pages(app,root,identity):
    with database(root) as db:
        db.execute('CREATE INDEX IF NOT EXISTS chunks_document_page ON chunks(document_id,idx,id)')

    @app.get('/api/documents/{ident}/chunks/page')
    def listing(ident:str,request:Request,kb_id:str='',
                offset:int=Query(0,ge=0,le=2147483647),
                limit:int=Query(20,ge=1,le=50),
                expected_version:int|None=Query(None,ge=1)):
        user=identity(request)['id']
        with database(root) as db:
            db.execute('BEGIN')
            doc=db.execute('SELECT id,name,kb_id,version FROM documents WHERE id=? AND deleted_at=0',(ident,)).fetchone()
            if not doc:raise HTTPException(404,'文档不存在或已移入回收站')
            owner=db.execute('SELECT owner FROM knowledge_bases WHERE id=?',(doc['kb_id'],)).fetchone()
            grant=db.execute('SELECT 1 FROM members WHERE kb_id=? AND user_id=?',(doc['kb_id'],user)).fetchone()
            if not owner or (owner[0]!=user and not grant):raise HTTPException(403,'没有知识库访问权限')
            if kb_id and kb_id!=doc['kb_id']:raise HTTPException(404,'文档不属于当前知识库')
            if expected_version is not None and expected_version!=doc['version']:
                raise HTTPException(409,'文档版本已变化，请重新打开当前原文')
            total=db.execute('SELECT count(*) FROM chunks WHERE document_id=?',(ident,)).fetchone()[0]
            items=[dict(r) for r in db.execute('SELECT idx,page,text FROM chunks WHERE document_id=? ORDER BY idx,id LIMIT ? OFFSET ?',(ident,limit,offset))]
        next_offset=offset+len(items) if items and offset+len(items)<total else None
        return JSONResponse({'document':dict(doc),'items':items,'total':total,'offset':offset,
                             'limit':limit,'next_offset':next_offset},headers={'Cache-Control':'no-store'})
