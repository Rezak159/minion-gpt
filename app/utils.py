def smart_split(text: str, max_length: int = 3500) -> list[str]:
    """Разделяет текст по переносам строк и пробелам"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        
        # Ищем последний перенос строки
        part = text[:max_length]
        last_newline = part.rfind('\n')
        
        if last_newline != -1:
            parts.append(part[:last_newline])
            text = text[last_newline + 1:]
        else:
            # Ищем последний пробел
            last_space = part.rfind(' ')
            if last_space != -1:
                parts.append(part[:last_space])
                text = text[last_space + 1:]
            else:
                # Режем жестко
                parts.append(part)
                text = text[max_length:]
    
    return parts
