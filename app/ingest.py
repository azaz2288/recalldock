"""Durable document ingestion and revision history, with cancellable queue."""
from pathlib import Path
from contextlib import asynccontextmanager
import hashlib,json,os,threading,time,uuid
from fastapi import HTTPException,Request,UploadFile,File,Form
from .common import database,read_upload
from .retrieval import chunks,index_chunk,tokens

def install_ingest(app,root,access,identity):
    spool=root/'ingest';spool.mkdir(exist_ok=True)
    with database(root) as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS ingest_jobs(id TEXT PRIMARY KEY,kb_id TEXT,user_id TEXT,name TEXT,path TEXT,state TEXT,error TEXT,document_id TEXT,created REAL,updated REAL);
        CREATE TABLE IF NOT EXISTS document_versions(document_id TEXT,version INTEGER,name TEXT,chunks_json TEXT,created REAL,PRIMARY KEY(document_id,version));''')
        db.execute("UPDATE ingest_jobs SET state='queued' WHERE state='running'")
    stop=threading.Event()
    def worker():
        from .main import extract
        while not stop.wait(.5):
            with database(root) as db:
                db.execute('BEGIN IMMEDIATE');job=db.execute("SELECT * FROM ingest_jobs WHERE state='queued' ORDER BY created LIMIT 1").fetchone()
                if not job:continue
                db.execute("UPDATE ingest_jobs SET state='running',updated=? WHERE id=?",(time.time(),job['id']))
            try:
                raw=Path(job['path']).read_bytes();suffix=Path(job['name']).suffix.lower();pages=extract(raw,suffix)
                parts=[(page,text) for page,content in pages for text in chunks(content)]
                digest=hashlib.sha256(job['kb_id'].encode()+raw).hexdigest()
                with database(root) as db:
                    db.execute('BEGIN IMMEDIATE');state=db.execute('SELECT state FROM ingest_jobs WHERE id=?',(job['id'],)).fetchone()[0]
                    if state=='cancelled':continue
                    kb=db.execute('SELECT owner FROM knowledge_bases WHERE id=?',(job['kb_id'],)).fetchone()
                    grant=db.execute("SELECT 1 FROM members WHERE kb_id=? AND user_id=? AND role='editor'",(job['kb_id'],job['user_id'])).fetchone()
                    if not kb or (kb[0]!=job['user_id'] and not grant):raise HTTPException(403,'摄取期间编辑权限已撤销')
                    old=db.execute('SELECT id,deleted_at FROM documents WHERE digest=?',(digest,)).fetchone()
                    if old and old['deleted_at']>0:raise HTTPException(409,'相同文档已在回收站，请明确恢复后再使用')
                    ident=old[0] if old else uuid.uuid4().hex
                    if not old:
                        db.execute('INSERT INTO documents(id,name,digest,kind,pages,characters,created,kb_id,version) VALUES(?,?,?,?,?,?,?,?,?)',(ident,job['name'],digest,suffix,len(pages),sum(len(t) for _,t in pages),time.time(),job['kb_id'],1))
                        for index,(page,text) in enumerate(parts):
                            key=f'{ident}-{index:06}';db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',(key,ident,index,page,text,len(tokens(text))));index_chunk(db,key,text)
                    db.execute("UPDATE ingest_jobs SET state='completed',document_id=?,updated=? WHERE id=?",(ident,time.time(),job['id']))
            except Exception as exc:
                error=exc.detail if isinstance(exc,HTTPException) else '摄取失败，请检查文档或重试'
                with database(root) as db:db.execute("UPDATE ingest_jobs SET state='failed',error=?,updated=? WHERE id=? AND state!='cancelled'",(str(error)[:300],time.time(),job['id']))
            finally:
                with database(root) as db:state=db.execute('SELECT state FROM ingest_jobs WHERE id=?',(job['id'],)).fetchone()[0]
                if state in {'completed','cancelled'}:Path(job['path']).unlink(missing_ok=True)
    @asynccontextmanager
    async def lifespan(application):
        threading.Thread(target=worker,daemon=True).start()
        try:yield
        finally:stop.set()
    app.router.lifespan_context=lifespan
    @app.post('/api/ingest/jobs',status_code=202)
    def enqueue(request:Request,kb_id:str=Form(''),file:UploadFile=File(...)):
        kb=access(request,kb_id,True);name=Path(file.filename.replace('\\','/')).name[:180]
        if Path(name).suffix.lower() not in {'.txt','.md','.pdf'}:raise HTTPException(400,'支持TXT/MD/PDF')
        raw=read_upload(file,20*1024*1024);key=uuid.uuid4().hex;path=spool/(key+'.input');path.write_bytes(raw)
        with database(root) as db:db.execute('INSERT INTO ingest_jobs VALUES(?,?,?,?,?,?,?,?,?,?)',(key,kb,identity(request)['id'],name,str(path),'queued','','',time.time(),time.time()))
        return {'id':key}
    @app.get('/api/ingest/jobs')
    def jobs(request:Request,kb_id:str=''):
        kb=access(request,kb_id)
        with database(root) as db:return [{k:v for k,v in dict(r).items() if k!='path'} for r in db.execute('SELECT * FROM ingest_jobs WHERE kb_id=? ORDER BY created DESC LIMIT 100',(kb,))]
    @app.post('/api/ingest/jobs/{ident}/cancel')
    def cancel(ident:str,request:Request):
        with database(root) as db:
            row=db.execute('SELECT * FROM ingest_jobs WHERE id=?',(ident,)).fetchone()
            if not row:raise HTTPException(404,'任务不存在')
            access(request,row['kb_id'],True)
            if row['state'] not in {'queued','running'}:raise HTTPException(409,'任务已结束')
            db.execute("UPDATE ingest_jobs SET state='cancelled' WHERE id=?",(ident,))
        if row['state']=='queued':Path(row['path']).unlink(missing_ok=True)
        return {'ok':True}
    @app.post('/api/ingest/jobs/{ident}/retry')
    def retry(ident:str,request:Request):
        with database(root) as db:
            row=db.execute('SELECT * FROM ingest_jobs WHERE id=?',(ident,)).fetchone()
            if not row:raise HTTPException(404,'任务不存在')
            access(request,row['kb_id'],True)
            if row['state']!='failed' or not Path(row['path']).exists():raise HTTPException(409,'任务无法重试，请重新上传')
            db.execute("UPDATE ingest_jobs SET state='queued',error='' WHERE id=?",(ident,))
        return {'ok':True}
    @app.post('/api/ingest/documents/{ident}/revise')
    def revise(ident:str,request:Request,file:UploadFile=File(...)):
        from .main import extract
        with database(root) as db:doc=db.execute('SELECT * FROM documents WHERE id=?',(ident,)).fetchone()
        if not doc or doc['deleted_at']>0:raise HTTPException(404,'活动文档不存在')
        access(request,doc['kb_id'],True);suffix=Path(file.filename or '').suffix.lower()
        if suffix not in {'.txt','.md','.pdf'}:raise HTTPException(400,'文档格式不支持')
        raw=read_upload(file,20*1024*1024);pages=extract(raw,suffix);digest=hashlib.sha256(doc['kb_id'].encode()+raw).hexdigest()
        with database(root) as db:
            db.execute('BEGIN IMMEDIATE');old=[dict(r) for r in db.execute('SELECT idx,page,text FROM chunks WHERE document_id=? ORDER BY idx',(ident,))]
            current=db.execute('SELECT version,deleted_at FROM documents WHERE id=?',(ident,)).fetchone()
            if not current or current[0]!=doc['version'] or current['deleted_at']>0:raise HTTPException(409,'文档已更新或移入回收站，请重试')
            if db.execute('SELECT 1 FROM documents WHERE digest=? AND id!=?',(digest,ident)).fetchone():raise HTTPException(409,'新内容与其他文档重复')
            db.execute('INSERT INTO document_versions VALUES(?,?,?,?,?)',(ident,doc['version'],doc['name'],json.dumps(old,ensure_ascii=False),time.time()))
            db.execute('DELETE FROM chunks WHERE document_id=?',(ident,))
            for index,(page,text) in enumerate([(p,t) for p,c in pages for t in chunks(c)]):
                key=f'{ident}-{index:06}';db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',(key,ident,index,page,text,len(tokens(text))));index_chunk(db,key,text)
            db.execute('UPDATE documents SET digest=?,kind=?,pages=?,characters=?,version=version+1 WHERE id=?',(digest,suffix,len(pages),sum(len(t) for _,t in pages),ident))
        return {'version':doc['version']+1}
    @app.get('/api/ingest/documents/{ident}/versions')
    def versions(ident:str,request:Request):
        with database(root) as db:
            doc=db.execute('SELECT kb_id FROM documents WHERE id=? AND deleted_at=0',(ident,)).fetchone()
            if not doc:raise HTTPException(404,'文档不存在')
            access(request,doc[0]);return [dict(r) for r in db.execute('SELECT version,name,created FROM document_versions WHERE document_id=? ORDER BY version DESC',(ident,))]
    @app.get('/api/ingest/documents/{ident}/versions/{version}')
    def version_text(ident:str,version:int,request:Request):
        with database(root) as db:
            doc=db.execute('SELECT kb_id FROM documents WHERE id=? AND deleted_at=0',(ident,)).fetchone()
            if not doc:raise HTTPException(404,'文档不存在')
            access(request,doc[0]);row=db.execute('SELECT chunks_json FROM document_versions WHERE document_id=? AND version=?',(ident,version)).fetchone()
            if not row:raise HTTPException(404,'版本不存在')
            return json.loads(row[0])
