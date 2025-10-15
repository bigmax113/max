# -*- coding: utf-8 -*-
import zipfile, os, tempfile, requests, xml.etree.ElementTree as ET
from translation_prompt import generate_prompt
from tmx_memory import tmx_lookup

MAX_LINES_PER_REQUEST  = 150
MAX_TOKENS_PER_REQUEST = 2300   # лимит для экономии

def extract_text_elements(xml_root):
    """Возвращает список (элемент, текст) всех <w:t>"""
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    elts = []
    for t in xml_root.findall(".//w:t", ns):
        elts.append(t)
    return elts

def docx_to_xml(docx_path):
    """Извлекает document.xml из DOCX"""
    tmp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(docx_path, "r") as z:
        z.extract("word/document.xml", tmp_dir)
    xml_path = os.path.join(tmp_dir, "word/document.xml")
    tree = ET.parse(xml_path)
    return tree, xml_path, tmp_dir

def rebuild_docx(xml_path, tmp_dir, out_path):
    """Создаёт новый DOCX с заменённым document.xml"""
    # копируем весь DOCX, но заменяем document.xml
    orig_docx = [f for f in os.listdir(tmp_dir) if f.endswith(".docx")]
    if orig_docx:
        src_docx = os.path.join(tmp_dir, orig_docx[0])
        with zipfile.ZipFile(src_docx, "r") as zin:
            with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    data = zin.read(item.filename)
                    if item.filename == "word/document.xml":
                        data = open(xml_path, "rb").read()
                    zout.writestr(item, data)

def post_chat_completion(API_URL, API_KEY, payload):
    h = {"Authorization": f"Bearer {API_KEY}"}
    r = requests.post(API_URL, json=payload, headers=h, timeout=300)
    r.raise_for_status()
    js = r.json()
    return js["choices"][0]["message"]["content"].strip()

def process_docx_file(docx_path, API_URL, API_KEY, MODEL, src_lang, trg_lang):
    tree, xml_path, tmp_dir = docx_to_xml(docx_path)
    root = tree.getroot()
    texts = extract_text_elements(root)
    all_segments = [t.text or "" for t in texts]

    translated = []
    for i in range(0, len(all_segments), MAX_LINES_PER_REQUEST):
        batch = "\n".join(all_segments[i:i+MAX_LINES_PER_REQUEST])
        prompt = generate_prompt(src_lang, trg_lang, batch,
                                 tmx_lookup_func=lambda s: tmx_lookup(s, src_lang, trg_lang))
        payload = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS_PER_REQUEST,
            "messages": [
                {"role": "system", "content": "Ты профессиональный технический переводчик Smartcat."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        text_out = post_chat_completion(API_URL, API_KEY, payload)
        translated.extend(text_out.splitlines())

    for el, t in zip(texts, translated):
        el.text = t

    out_name = os.path.basename(docx_path).rsplit(".",1)[0]
    out_path = os.path.join(tmp_dir, f"Translate_{out_name}.docx")
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)

    # собираем новый DOCX
    with zipfile.ZipFile(docx_path, "r") as zin:
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == "word/document.xml":
                    data = open(xml_path, "rb").read()
                zout.writestr(item, data)

    return out_path
