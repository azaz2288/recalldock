"""Optional remote semantic embeddings; only explicit indexing calls transmit documents."""
import json,math
import httpx
from fastapi import HTTPException,Request
from .llm import setting
from .common import database

def embed(texts):
    model=setting('EMBEDDING_MODEL');key=setting('LLM_API_KEY');base=setting('LLM_BASE_URL','https://api.openai.com/v1').rstrip('/')
    if not model or not key:raise HTTPException(503,'请配置Embedding模型和API Key')
    from urllib.parse import urlsplit
    url=urlsplit(base)
    if not url.hostname or url.username or url.password or url.query or url.fragment or (url.scheme!='https' and not(url.scheme=='http' and url.hostname in {'127.0.0.1','localhost'})):raise HTTPException(503,'Embedding地址无效')
    try:
        with httpx.Client(timeout=60,follow_redirects=False,trust_env=False) as client:
            response=client.post(base+'/embeddings',headers={'Authorization':'Bearer '+key},json={'model':model,'input':texts,'encoding_format':'float'});response.raise_for_status()
        rows=sorted(response.json()['data'],key=lambda r:r['index']);vectors=[r['embedding'] for r in rows]
        if [r['index'] for r in rows]!=list(range(len(texts))) or len(vectors)!=len(texts) or not vectors or not all(isinstance(v,list) and 0<len(v)<=10000 and len(v)==len(vectors[0]) and all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in v) for v in vectors):raise ValueError('invalid embedding')
        return model,vectors
    except (httpx.HTTPError,KeyError,ValueError,TypeError):raise HTTPException(502,'Embedding请求失败或向量格式无效') from None

def semantic_retrieve(db,question,kb,limit=6):
    model,vectors=embed([question]);query=vectors[0];norm=math.sqrt(sum(x*x for x in query)) or 1
    ranked=[]
    for row in db.execute('SELECT e.values_json,c.*,d.name,d.version FROM semantic_vectors e JOIN chunks c ON c.id=e.chunk_id JOIN documents d ON d.id=c.document_id WHERE d.kb_id=? AND e.model=? LIMIT 10000',(kb,model)):
        value=json.loads(row['values_json'])
        if len(value)!=len(query):continue
        denom=norm*(math.sqrt(sum(x*x for x in value)) or 1);score=sum(x*y for x,y in zip(value,query))/denom
        if score>0:ranked.append((score,dict(row)))
    return [{k:v for k,v in row.items() if k!='values_json'}|{'score':round(score,6),'citation':i+1} for i,(score,row) in enumerate(sorted(ranked,key=lambda x:-x[0])[:limit])]

def install_semantic(app,root,access):
    with database(root) as db:db.execute('CREATE TABLE IF NOT EXISTS semantic_vectors(chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,model TEXT,values_json TEXT)')
    @app.get('/api/semantic/{kb}/preview')
    def preview(kb:str,request:Request):
        access(request,kb,True)
        with database(root) as db:count=db.execute('SELECT count(*) FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.kb_id=?',(kb,)).fetchone()[0]
        return {'chunks':count,'model':setting('EMBEDDING_MODEL',''),'notice':'将向已配置服务商发送本知识库所有原文片段，会产生API费用'}
    @app.post('/api/semantic/{kb}/index')
    def index(kb:str,request:Request,body:dict):
        access(request,kb,True)
        if body.get('confirm') is not True:raise HTTPException(400,'需要明确确认发送文档')
        with database(root) as db:rows=[dict(r) for r in db.execute('SELECT c.id,c.text FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.kb_id=?',(kb,))]
        values=[]
        for offset in range(0,len(rows),32):
            batch=rows[offset:offset+32];model,vectors=embed([r['text'] for r in batch]);values.extend((r['id'],model,json.dumps(v)) for r,v in zip(batch,vectors))
        with database(root) as db:
            db.execute('BEGIN IMMEDIATE')
            current={r['id']:r['text'] for r in db.execute('SELECT c.id,c.text FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.kb_id=?',(kb,))}
            if current!={r['id']:r['text'] for r in rows}:raise HTTPException(409,'文档在生成向量期间发生变化；未保存索引，请重试')
            if len({value[1] for value in values})>1:raise HTTPException(409,'模型设置在索引过程中变化，请重试')
            for ident,model,value in values:db.execute('INSERT OR REPLACE INTO semantic_vectors VALUES(?,?,?)',(ident,model,value))
        return {'indexed':len(values)}
