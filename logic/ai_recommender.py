import logging

import openai

from config.settings import OPENAI_KEY

openai.api_key = OPENAI_KEY

def get_access_recommendation(user_profile):
    prompt = f"""
    Recommend roles and access for:
    Job Title: {user_profile.get('title', '')}
    Department: {user_profile.get('department', '')}
    Level: {user_profile.get('level', '')}
    Region: {user_profile.get('location', '')}
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        logging.error(f"LLM error: {str(e)}")
        return f"Error during LLM access recommendation: {str(e)}"

