import unittest
from fastapi import HTTPException
from app.main import extract

class TextImportTests(unittest.TestCase):
    def test_unicode_big5_and_sparse_padding(self):
        text=('閱讀知識庫，保存完整的資料與文字。\n'*100)
        for encoding in ['utf-16-le','utf-16-be','utf-32-le','big5']:
            with self.subTest(encoding=encoding):self.assertEqual(extract(text.encode(encoding),'.txt'),[(1,text)])
        padded=text[:100]+'\0'+text[100:]
        self.assertEqual(extract(padded.encode(),'.md'),[(1,text)])
    def test_binary_disguised_as_text_is_rejected(self):
        with self.assertRaises(HTTPException):extract(b'PK\x03\x04not text','.txt')

if __name__=='__main__':unittest.main()
