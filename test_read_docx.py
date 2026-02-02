from docx import Document
from io import BytesIO

path = r"C:\govy\repos\govy-function-current\Art. 65 - HABILITAÇÃO - DEFINIÇÕES.docx"

with open(path, "rb") as f:
    docx_bytes = f.read()

doc = Document(BytesIO(docx_bytes))
paras = []

for p in doc.paragraphs:
    t = (p.text or "").strip()
    if t:
        t = " ".join(t.split())
        paras.append(t)

text = "\n".join(paras).strip()
print("CHARS:", len(text))
print("PREVIEW:", text[:300])
