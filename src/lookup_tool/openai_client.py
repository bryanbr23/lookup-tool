# ========== app/openai_client.py ==========

import openai

def summarize_with_openai(text, api_key):
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Summarize the following company website content and extract key facts and officers if possible."},
            {"role": "user", "content": text[:3000]}
        ]
    )
    return response.choices[0].message.content
