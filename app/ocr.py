"""Optional local OCR for scanned PDF pages. Requires user-installed Tesseract."""
from pathlib import Path
import os,shutil,subprocess,tempfile
from fastapi import HTTPException

def ocr_page(raw,page_index):
    executable=os.getenv('TESSERACT_PATH') or shutil.which('tesseract')
    if not executable:raise HTTPException(503,'扫描PDF需要Tesseract，请安装并设置TESSERACT_PATH；文字PDF无需OCR')
    try:
        import pypdfium2 as pdfium
        document=pdfium.PdfDocument(raw)
        page=document[page_index];image=page.render(scale=2).to_pil()
        if image.width*image.height>25_000_000:raise ValueError('page limit')
        with tempfile.TemporaryDirectory() as tmp:
            png=Path(tmp)/'page.png';image.save(png)
            result=subprocess.run([executable,str(png),'stdout','-l',os.getenv('OCR_LANG','eng')],capture_output=True,timeout=45)
            if result.returncode:raise ValueError('ocr failed')
            text=result.stdout.decode('utf-8')
        page.close();document.close()
        return text
    except (ImportError,OSError,ValueError,subprocess.TimeoutExpired):raise HTTPException(503,'OCR失败；检查PDF渲染依赖、Tesseract语言包与页大小') from None
