"""Deterministic lexical index with Chinese bigrams and English terms."""
from collections import Counter
import math
import re
import hashlib,json,os

def local_vector(text):
    """Offline feature-hashing vector; lexical similarity, not a semantic language model."""
    vector=[0.0]*256
    for term,count in Counter(tokens(text)).items():
        digest=hashlib.blake2b(term.encode(),digest_size=8).digest()
        slot=int.from_bytes(digest[:4],'little')%256
        vector[slot]+=count*(1 if digest[4]&1 else -1)
    norm=math.sqrt(sum(x*x for x in vector)) or 1
    return [round(x/norm,7) for x in vector]


def tokens(text):
    result=[]
    for match in re.finditer(r'[a-zA-Z0-9_]+|[\u3400-\u9fff]+',text.lower()):
        word=match.group()
        if '\u3400'<=word[0]<='\u9fff':
            result.extend(word[i:i+2] for i in range(len(word)-1))
            if len(word)==1:result.append(word)
        else:result.append(word[:100])
    return result


def chunks(text,maximum=900,overlap=150):
    text=text.strip()
    for offset in range(0,len(text),maximum-overlap):
        value=text[offset:offset+maximum]
        if value.strip():yield value
        if offset+maximum>=len(text):break


def index_chunk(db,ident,text):
    counts=Counter(tokens(text))
    db.executemany('INSERT INTO terms(chunk_id,term,tf) VALUES(?,?,?)',[(ident,t,n) for t,n in counts.items()])
    db.execute('INSERT OR REPLACE INTO vectors VALUES(?,?,?)',(ident,'feature-hash-v1',json.dumps(local_vector(text))))


def retrieve(db,question,limit=6,kb='default',hybrid=True):
    terms=list(dict.fromkeys(tokens(question)))[:64]
    if not terms:return []
    count=db.execute('SELECT count(*) FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.kb_id=? AND d.deleted_at=0',(kb,)).fetchone()[0]
    if not count:return []
    scores={}
    average=db.execute('SELECT avg(c.length) FROM chunks c JOIN documents d ON d.id=c.document_id WHERE d.kb_id=? AND d.deleted_at=0',(kb,)).fetchone()[0] or 1
    for term in terms:
        frequency=db.execute('SELECT count(*) FROM terms t JOIN chunks c ON c.id=t.chunk_id JOIN documents d ON d.id=c.document_id WHERE term=? AND d.kb_id=? AND d.deleted_at=0',(term,kb)).fetchone()[0]
        idf=math.log(1+(count-frequency+.5)/(frequency+.5))
        for row in db.execute('SELECT t.chunk_id,t.tf,c.length FROM terms t JOIN chunks c ON c.id=t.chunk_id JOIN documents d ON d.id=c.document_id WHERE t.term=? AND d.kb_id=? AND d.deleted_at=0 LIMIT 10000',(term,kb)):
            denominator=row['tf']+1.2*(1-.75+.75*row['length']/average)
            scores[row['chunk_id']]=scores.get(row['chunk_id'],0)+idf*row['tf']*2.2/denominator
    lexical=sorted(scores,key=lambda k:(-scores[k],k))
    if hybrid and lexical:
        query=local_vector(question);similarities={}
        # Only overlap-supported candidates: hash collisions must not turn unrelated text into evidence.
        for ident in lexical[:100]:
            row=db.execute("SELECT values_json FROM vectors WHERE chunk_id=? AND model='feature-hash-v1'",(ident,)).fetchone()
            if row:similarities[ident]=sum(a*b for a,b in zip(query,json.loads(row[0])))
        vector_rank=sorted(similarities,key=lambda k:(-similarities[k],k))
        combined={ident:1/(60+rank) for rank,ident in enumerate(lexical,1)}
        for rank,ident in enumerate(vector_rank,1):combined[ident]=combined.get(ident,0)+1/(60+rank)
        scores=combined
    results=[]
    for ident,score in sorted(scores.items(),key=lambda p:(-p[1],p[0]))[:limit]:
        row=db.execute('SELECT c.id,c.document_id,c.idx,c.page,c.text,d.name,d.version FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=?',(ident,)).fetchone()
        results.append({**dict(row),'score':round(score,6),'citation':len(results)+1})
    return results
