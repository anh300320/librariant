import re


def remove_all_chars_except_alnum(
    text: str,
) -> str:
    normalized_text = ''
    for ch in text:
        if not ch.isalnum():
            normalized_text += ' '
        else:
            normalized_text += ch
    normalized_text = re.sub(r'\s+', ' ', normalized_text)
    return normalized_text


def normalize_node_name(name: str) -> str:
    name = name.replace("/", "")
    return name
