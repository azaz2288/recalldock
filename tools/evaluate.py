"""Reproducible synthetic retrieval evaluation; no provider calls."""
from pathlib import Path
import sys,tempfile,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import create_app
cases=[('备份','备份文件保留三十天，每晚运行数据库备份。','备份文件保留多久'),('认证','会话有效期七天，退出登录后令牌立即撤销。','登录会话有效期'),('媒体','上传视频使用后台转码，生成封面和HLS。','视频上传后如何处理'),('阅读','阅读器支持EPUB导入和选段批注。','EPUB可以添加批注吗'),('权限','只读成员可以检索资料，但不能删除文档。','只读成员能删除吗')]
with tempfile.TemporaryDirectory() as tmp:
    client=TestClient(create_app(Path(tmp)))
    for title,text,q in cases:client.post('/api/documents',files={'file':(title+'.txt',text.encode())})
    report={}
    for hybrid in (False,True):
        hits=0;details=[]
        for title,text,q in cases:
            result=client.post('/api/ask',json={'question':q,'hybrid':hybrid}).json();names=[s['name'] for s in result['sources']]
            hit=title+'.txt' in names[:3];hits+=hit;details.append({'question':q,'hit_at_3':hit,'ranked_sources':names})
        report['hybrid' if hybrid else 'bm25']={'recall_at_3':hits/len(cases),'questions':len(cases),'cases':details}
    no_evidence=client.post('/api/ask',json={'question':'unrelated quasar'}).json()
    report['no_evidence_handled']=no_evidence['mode']=='no-evidence'
    print(json.dumps(report,ensure_ascii=True,indent=2))
