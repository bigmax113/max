# -*- coding: utf-8 -*-
import re

def normalize_language_code(lang_code: str) -> str:
    return (lang_code or "").lower().strip().split("-")[0]

def get_language_specific_rules(target_lang_norm: str) -> str:
    rules = {
        "ru": "Используй русскую пунктуацию и кавычки «».",
        "uk": "Використовуй українські лапки «» та граматично правильні форми.",
        "kk": "Переклад виконуй кирилицею. Одиниці виміру — кирилицею (Вт, В, Гц).",
        "sr": "Користуйся сербською латиницею. Збережи технічну термінологію.",
        "en": "Use concise technical style without extra explanations.",
        "de": "Beachte V2/SOV Wortstellung, korrekte Artikel und Kasus.",
        "pl": "Stosuj polskie cudzysłowy „…”.",
        "hu": "Használj magyar idézőjeleket „…”.",
    }
    return rules.get(target_lang_norm, "Соблюдай грамматику и орфографию целевого языка.")

def generate_prompt(source_lang: str, target_lang: str, source_text: str, tmx_lookup_func=None) -> str:
    """
    Улучшенный промпт: XLIFF-охрана, TMX-примеры, единицы/кавычки, OSD/описание, self-check.
    tmx_lookup_func(src_segment:str)->str|None — колбэк поиска точных совпадений из TMX.
    """
    src = normalize_language_code(source_lang)
    trg = normalize_language_code(target_lang)

    # Алфавитные/общие правила
    if trg == "sr":
        alphabet_rule = "Перевод выполняй на латинице (sr-Latn), даже если указан sr-Cyrl.\n"
    elif trg == "kk":
        alphabet_rule = "Перевод выполняй кириллицей; единицы измерения тоже кириллицей.\n"
    elif trg == "uk":
        alphabet_rule = "Перевод выполняй кириллицей, без русизмов и англицизмов.\n"
    elif trg == "el":
        alphabet_rule = "Перевод выполняй греческим алфавитом; не оставляй латиницу (кроме USB/BT).\n"
    else:
        alphabet_rule = f"Перевод должен соответствовать стандартному алфавиту языка '{trg}'.\n"

    # TMX-примеры для текущего батча
    tmx_examples = []
    for line in source_text.splitlines():
        if not line.strip():
            continue
        if tmx_lookup_func:
            match = tmx_lookup_func(line.strip())
            if match:
                tmx_examples.append(f"• TMX: '{line.strip()}' → '{match}'")

    tmx_block = ""
    if tmx_examples:
        tmx_block = "Примеры из TMX (используй как предпочтительный стиль):\n" + "\n".join(tmx_examples) + "\n"

    lang_rules = get_language_specific_rules(trg)

    prompt = f"""
Ты профессиональный технический переводчик, специализирующийся на переводе XLIFF Smartcat для технических устройств, интерфейсов (OSD) и руководств.
Выполни точный, терминологически согласованный перевод, строго сохраняя структуру XML и теги Smartcat.

❗ Строго обязательно:
— Сохрани все теги <g>, <x>, <bpt>, <ept>, <ph>, <it> и их атрибуты.
— Переводи только текст между тегами.
— Не добавляй/не удаляй теги и не меняй их порядок.
— Сохрани все спецсимволы, пробелы и НЕРАЗРЫВНЫЕ пробелы.

{tmx_block}Общие правила форматирования:
— Между числом и единицей измерения используй неразрывный пробел (U+00A0).
— Международные единицы не переводить (W, V, Hz, °C, mm, cm).
— Для кириллических языков единицы — кириллицей (Вт, В, Гц, мм).
— Национальные кавычки:
  «...» — ru, uk, bg, be, kk, mk
  „...” — pl, lt, lv, hu, sk, sl, cs, sr-Latn
  «...» — fr, el, es, ro, it, pt, nl
  “...” — en, da, no, sv

{alphabet_rule}{lang_rules}

Контекстная адаптация:
— Если сегмент короткий (≤5 слов) и похож на пункт меню/OSD — переводи кратко, без артиклей/лишних слов.
— Если текст описательный — используй нейтральный технический стиль.

ПРОВЕРЬ ПОСЛЕ ПЕРЕВОДА:
1) Все XLIFF-теги на месте (<x>, <g>, <bpt>, <ept>, <ph>, <it>).
2) Нет непереведённых слов исходного языка.
3) Единицы/термины локализованы корректно.
4) Формулировки естественные для носителя языка.

Ниже — пакет сегментов для перевода (каждая строка — отдельный сегмент).
Выведи ТОЛЬКО переводы, построчно и в том же количестве строк, без комментариев, без Markdown:
{source_text}
"""
    return prompt.strip()
