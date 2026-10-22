"""Bounded current and historical text pages from one SQLite read snapshot."""
import json
from fastapi import HTTPException,Path,Query,Request
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

    @app.get('/api/ingest/documents/{ident}/versions/{version}/page')
    def history(ident:str,request:Request,version:int=Path(...,ge=1,le=2147483647),kb_id:str='',
                offset:int=Query(0,ge=0,le=2147483647),limit:int=Query(20,ge=1,le=50)):
        user=identity(request)['id']
        with database(root) as db:
            db.execute('BEGIN')
            doc=db.execute('SELECT id,kb_id FROM documents WHERE id=? AND deleted_at=0',(ident,)).fetchone()
            if not doc:raise HTTPException(404,'文档不存在或已移入回收站')
            owner=db.execute('SELECT owner FROM knowledge_bases WHERE id=?',(doc['kb_id'],)).fetchone()
            grant=db.execute('SELECT 1 FROM members WHERE kb_id=? AND user_id=?',(doc['kb_id'],user)).fetchone()
            if not owner or (owner[0]!=user and not grant):raise HTTPException(403,'没有知识库访问权限')
            if kb_id and kb_id!=doc['kb_id']:raise HTTPException(404,'文档不属于当前知识库')
            snapshot=db.execute('''SELECT name,CASE WHEN json_valid(chunks_json) THEN json_type(chunks_json)
                ELSE '' END AS kind FROM document_versions WHERE document_id=? AND version=?''',(ident,version)).fetchone()
            if not snapshot:raise HTTPException(404,'版本不存在')
            if snapshot['kind']!='array':raise HTTPException(409,'历史版本格式损坏，请检查备份')
            # Keep legacy JSON untouched. SQLite traverses the snapshot; Python only decodes the requested slice.
            # JSON1 still parses the original value: this is not a hard SQLite CPU/RSS budget.
            total=db.execute('''SELECT count(*) FROM document_versions,json_each(document_versions.chunks_json)
                WHERE document_id=? AND version=?''',(ident,version)).fetchone()[0]
            items=[]
            for row in db.execute('''SELECT part.type,part.value FROM document_versions,
                json_each(document_versions.chunks_json) AS part WHERE document_id=? AND version=?
                ORDER BY CAST(part.key AS INTEGER) LIMIT ? OFFSET ?''',(ident,version,limit,offset)):
                if row['type']!='object':raise HTTPException(409,'历史片段格式损坏，请检查备份')
                item=json.loads(row['value'])
                if (type(item.get('idx')) is not int or item['idx']<0 or type(item.get('page')) is not int or
                    item['page']<1 or not isinstance(item.get('text'),str)):
                    raise HTTPException(409,'历史片段格式损坏，请检查备份')
                items.append(item)
            document={'id':ident,'kb_id':doc['kb_id'],'name':snapshot['name'],'version':version}
        next_offset=offset+len(items) if items and offset+len(items)<total else None
        return JSONResponse({'document':document,'items':items,'total':total,'offset':offset,
                             'limit':limit,'next_offset':next_offset},headers={'Cache-Control':'no-store'})
