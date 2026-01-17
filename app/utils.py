def split_message_by_lines(text, max_length=4096):
    if len(text) <= max_length:
        return [text]
    
    parts = []
    while len(text) > 0:
        if len(text) > max_length:
            part = text[:max_length]
            last_newline = part.rfind('\n')
            
            if last_newline != -1:
                parts.append(part[:last_newline])
                text = text[last_newline+1:]
            else:
                parts.append(part)
                text = text[max_length:]
        else:
            parts.append(text)
            break
    
    return parts
