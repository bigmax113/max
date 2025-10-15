# -*- coding: utf-8 -*-
import os, requests
import xml.etree.ElementTree as ET
from translation_prompt import generate_prompt
from tmx_memory import tmx_lookup

# === Контроль стоимости ===
MAX_LINES_PER_REQUEST   = 150      # батч по строкам/сегментам
MAX_TOKENS_PER_REQUEST  = 200000   # ограничение объёма запроса к LLM

# --- Вспомогательные функции XLIFF ---

def extract_langs(root):
    """
    Читает языковые пары из XLIFF: <file source-language="ru" target-language="uk">
    """
    file_tag = root.find(".//{*}file")
    if file_tag is not None:
        src = file_tag.attrib.get("source-language", "auto")
        trg = file_tag.attrib.get("target-language", "auto")
        return src, trg
    return "auto", "auto"

def get_units(root):
    """
    Возвращает список <trans-unit> и исходные тексты (<source>), сохраняя порядок.
    """
    units = root.findall(".//{*}trans-unit")
    sources = []
    for u in units:
        # Считываем текст источника с учётом возможных подузлов.
        src_el = u.find("{*}source")
        if src_el is None:
            sources.append("")
            continue
        # Простой вариант: берем текст целиком, включая подузлы, через ''.join(…)
        # (модель должна вернуть те же теги и структуру; это контролируется промптом)
        text_parts = []
        if src_el.text:
            text_parts.append(src_el.text)
        for child in src_el:
            # сериализуем узлы как текст (без строгой реконструкции XLIFF-тегов)
            # модель обучена не менять теги; мы вернем плоский текст в target
            # Если нужна идеальная реконструкция — потребуется полноценный сериализатор.
            text_parts.append(ET.tostring(child, encoding="unicode"))
            if child.tail:
                text_parts.append(child.tail)
        sources.append("".join(text_parts).strip())
    return units, sources

def post_chat_completion(API_URL, API_KEY, payload):
    headers = {"Authorization": f"Bearer {API_KEY}"}
    r = requests.post(API_URL, json=payload, headers=headers, timeout=300)
    r.raise_for_status()
    js = r.json()
    return js["choices"][0]["message"]["content"].strip()

# --- Основной конвейер ---

def process_xliff_file(file_path, API_URL, API_KEY, MODEL):
    """
    Переводит целый XLIFF-файл пакетами по MAX_LINES_PER_REQUEST.
    Использует TMX-кэш (если загружен) для примеров и терминов.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()
    src_lang, trg_lang = extract_langs(root)

    units, segments = get_units(root)

    translated_segments = []
    for i in range(0, len(segments), MAX_LINES_PER_REQUEST):
        batch_segments = segments[i:i + MAX_LINES_PER_REQUEST]
        batch_text = "\n".join(batch_segments)

        # Сформировать промпт с примерами из TMX (внутри generate_prompt есть вызов tmx_lookup)
        prompt = generate_prompt(src_lang, trg_lang, batch_text, tmx_lookup_func=lambda s: tmx_lookup(s, src_lang, trg_lang))

        payload = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS_PER_REQUEST,
            "messages": [
                {"role": "system", "content": "Ты профессиональный технический переводчик Smartcat."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        out_text = post_chat_completion(API_URL, API_KEY, payload)
        translated_segments.extend(out_text.splitlines())

    # Синхронизация длины (на случай, если модель вернёт меньше/больше строк)
    if len(translated_segments) < len(units):
        translated_segments += [""] * (len(units) - len(translated_segments))
    if len(translated_segments) > len(units):
        translated_segments = translated_segments[:len(units)]

    # Запись результатов в <target>
    for u, t_text in zip(units, translated_segments):
        tgt = u.find("{*}target")
        if tgt is None:
            tgt = ET.SubElement(u, "target")
        # Вставляем как простой текст (модель не должна менять теги)
        tgt.clear()
        tgt.text = t_text

    out_file = file_path.rsplit(".", 1)[0] + "_translated.xliff"
    tree.write(out_file, encoding="utf-8", xml_declaration=True)
    return out_file
