"""Deterministic lexical index with Chinese bigrams and English terms."""
from collections import Counter
import math
import re


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


def retrieve(db,question,limit=6):
    terms=list(dict.fromkeys(tokens(question)))[:64]
    if not terms:return []
    count=db.execute('SELECT count(*) FROM chunks').fetchone()[0]
    if not count:return []
    scores={}
    for term in terms:
        frequency=db.execute('SELECT count(*) FROM terms WHERE term=?',(term,)).fetchone()[0]
        idf=math.log(1+(count-frequency+.5)/(frequency+.5))
        for row in db.execute('SELECT t.chunk_id,t.tf,c.length FROM terms t JOIN chunks c ON c.id=t.chunk_id WHERE t.term=? LIMIT 10000',(term,)):
            scores[row['chunk_id']]=scores.get(row['chunk_id'],0)+idf*(1+math.log(row['tf']))/math.sqrt(max(row['length'],1))
    results=[]
    for ident,score in sorted(scores.items(),key=lambda p:(-p[1],p[0]))[:limit]:
        row=db.execute('SELECT c.id,c.document_id,c.idx,c.page,c.text,d.name FROM chunks c JOIN documents d ON d.id=c.document_id WHERE c.id=?',(ident,)).fetchone()
        results.append({**dict(row),'score':round(score,6),'citation':len(results)+1})
    return results
