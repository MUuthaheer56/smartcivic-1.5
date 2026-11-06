import re

PROFANITY_WORDS = ["badword1", "badword2", "spammyword"] # Placeholder list

def sanitize_description(description: str) -> str:
    if not description:
        return ""
    
    # 1. Strip HTML tags
    clean_text = re.sub(r'<[^>]*>', '', description)
    
    # 2. Redact PII (email patterns)
    clean_text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL_REDACTED]', clean_text)
    
    # 3. Redact PII (phone number patterns - 10 digits or country code variants)
    clean_text = re.sub(r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '[PHONE_REDACTED]', clean_text)
    
    # 4. Profanity filter
    for word in PROFANITY_WORDS:
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        clean_text = pattern.sub("****", clean_text)
        
    # 5. Limit to 500 characters
    clean_text = clean_text[:500]
    
    return clean_text.strip()
