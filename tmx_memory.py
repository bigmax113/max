# -*- coding: utf-8 -*-
import os
import xml.etree.ElementTree as ET

# Глобальный кэш:
# TMX_CACHE: dict[str_source][str_target_lang] = str_translated
TMX_CACHE = {}

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

def _add_pair(src_text: str, trg_lang: str, trg_text: str):
    if not src_text or not trg_text:
        return
    src_key = src_text.strip()
    trg_val = trg_text.strip()
    if not src_key or not trg_val:
        return
    if src_key not in TMX_CACHE:
        TMX_CACHE[src_key] = {}
    TMX_CACHE[src_key][trg_lang.lower()] = trg_val

def load_tmx_folder(folder_path: str):
    """
    Загружает все TMX из папки (или распакованного ZIP) в кэш TMX_CACHE.
    Поддерживает стандарт TMX с <tuv xml:lang=".."><seg>...</seg></tuv>
    """
    global TMX_CACHE
    TMX_CACHE = {}

    for root, _, files in os.walk(folder_path):
        for name in files:
            if not name.lower().endswith(".tmx"):
                continue
            path = os.path.join(root, name)
            try:
                tree = ET.parse(path)
                root_tmx = tree.getroot()
                for tu in root_tmx.findall(".//{*}tu"):
                    # Собираем список (lang, text)
                    tuv_list = []
                    for tuv in tu.findall(".//{*}tuv"):
                        lang = (tuv.attrib.get(XML_LANG) or tuv.attrib.get("lang") or "").lower()
                        seg = tuv.find(".//{*}seg")
                        text = (seg.text or "") if seg is not None else ""
                        if text:
                            tuv_list.append((lang, text))
                    # Формируем пары: первый считаем источником для остальных
                    if len(tuv_list) >= 2:
                        src_lang, src_text = tuv_list[0]
                        for trg_lang, trg_text in tuv_list[1:]:
                            _add_pair(src_text, trg_lang, trg_text)
            except Exception as e:
                print(f"[TMX] Ошибка чтения '{path}': {e}")

    print(f"[TMX] Загружено {sum(len(v) for v in TMX_CACHE.values())} переводов из {len(TMX_CACHE)} исходных сегментов.")

def tmx_lookup(source_text: str, src_lang: str, trg_lang: str):
    """
    Возвращает перевод из кэша TMX для точного совпадения source_text -> target_lang, если есть.
    Языки используются как подсказка, но сейчас lookup — по точному исходному тексту и целевому языку.
    """
    if not source_text:
        return None
    src = source_text.strip()
    if src in TMX_CACHE:
        trg_norm = (trg_lang or "").lower().split("-")[0]
        # Прямая попытка на точный код
        if trg_norm in TMX_CACHE[src]:
            return TMX_CACHE[src][trg_norm]
        # Попытка совпадения по более длинным вариантам (например, 'pt-br')
        for k, v in TMX_CACHE[src].items():
            if trg_norm and k.startswith(trg_norm):
                return v
    return None
