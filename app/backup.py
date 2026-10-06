import hashlib,json,time,uuid,math
from fastapi import HTTPException,Request,UploadFile,File,Form
from .common import database,read_upload
from .retrieval import index_chunk,tokens

def install_backup(app,root,access):
    @app.post('/api/workspace/restore-backup')
    def restore(request:Request,kb_id:str=Form(''),file:UploadFile=File(...)):
        kb=access(request,kb_id,True);raw=read_upload(file,30*1024*1024)
        try:
            body=json.loads(raw);documents=body['documents']
            if body['version']!=1 or not isinstance(documents,list) or len(documents)>1000:raise ValueError()
            count=0
            for doc in documents:
                if not isinstance(doc,dict):raise ValueError('invalid document')
                deleted=doc.get('deleted_at',0)
                if type(deleted) not in (int,float) or not 0<=deleted<=253402300799 or not math.isfinite(deleted):raise ValueError('invalid trash timestamp')
                if not isinstance(doc['name'],str) or not 0<len(doc['name'])<=180 or not isinstance(doc['chunks'],list) or len(doc['chunks'])>10000:raise ValueError()
                for i,c in enumerate(doc['chunks']):
                    if c['idx']!=i or not isinstance(c['page'],int) or c['page']<1 or not isinstance(c['text'],str) or len(c['text'])>900:raise ValueError()
                    count+=len(c['text'])
                if count>20_000_000:raise ValueError()
        except (ValueError,KeyError,TypeError):raise HTTPException(400,'备份格式无效，未写入文档') from None
        restored=0
        with database(root) as db:
            for doc in documents:
                text='\n'.join(c['text'] for c in doc['chunks']);digest=hashlib.sha256((kb+text).encode()).hexdigest()
                if db.execute('SELECT 1 FROM documents WHERE digest=?',(digest,)).fetchone():continue
                ident=uuid.uuid4().hex
                db.execute('INSERT INTO documents(id,name,digest,kind,pages,characters,created,kb_id,version,deleted_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,doc['name'],digest,'.restored',len({c['page'] for c in doc['chunks']}),len(text),time.time(),kb,1,doc.get('deleted_at',0)))
                for i,c in enumerate(doc['chunks']):
                    key=f'{ident}-{i:06}';db.execute('INSERT INTO chunks VALUES(?,?,?,?,?,?)',(key,ident,i,c['page'],c['text'],len(tokens(c['text']))));index_chunk(db,key,c['text'])
                restored+=1
        return {'restored':restored}
