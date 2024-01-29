import os
import json
import requests

TOGETHER_API_KEY = os.environ.get('TOGETHER_API_KEY')

def together(modelName, system_prompt, user_text):
    url = "https://api.together.xyz/v1/chat/completions"
    payload = {
        "model": modelName,
        "max_tokens": 1024,
        "stop": ["</s>", "[/INST]"],
        "temperature": 0.0,
        "top_p": 0.7,
        "top_k": 50,
        "repetition_penalty": 1,
        "n": 1,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "Authorization": f"Bearer 878cecce3658eeea8a1fc9085f5f935f95b2e80f7b17e3f1a16a60c297f343be"
    }
    response = requests.post(url, json=payload, headers=headers)
    response_data = json.loads(response.text)
    response_text = response_data['choices'][0]['message']['content']
    print(f"Deepgram API response_text: {response_text}\n")

modelName = f"mistralai/Mixtral-8x7B-Instruct-v0.1"
system_prompt = f"""
You will receive a user's transcribed speech and are to process it to correct potential errors. 
DO NOT DO THE FOLLOWING: 
- Generate any additional content 
- Censor any of the content 
- Print repetitive content 
DO THE FOLLOWING: 
- Account for transcript include speech of multiple users 
- Translate everything to English 
- Only output corrected text 
- If too much of the content seems erroneous return '.'
"""
user_text = """
S0: हमारे साथ लेकर सही (chain हो गया) हो गया. हमने बोला है Bombay वाले को बहुत अच्छे लड़के हैं, ना वो मिलेंगे. बाहर वाले हैं तो (अच्छा है) अच्छा है, नहीं, उनको यह बोलो कि Bombay का (kilometer कितना है) कितना है वह, समझ जाएंगे. अभी तक traffic देख ही नहीं (नहीं नहीं उनको यह) आपने देखा है, ना (walking distance कितना था) था? चार घंटे.

S1: Time मिलता है तो वो जाके गांव में जाके बैठ के अपना laptop लेके गांव में बैठता (proper करता है) करता है. नहीं, I am not interested in this crowd. वो बैंगलोर हो, इधर हो, हां यह problem करेगा तेरे को. आधा गिर जाते हैं उसमें but इसमें खाली भी. कोई कह (नहीं हो ना) नहीं हो रहा है सुमित के लिए, हम लोग कर क्या है?

S2: हां वह हमारे नहीं थे पूछा वह.

S0: नहीं, मैं पूछी उसको अपनी. मैंने (confirm किया वह) जाँचा था उससे.
"""
final_transcript = together(modelName, system_prompt, user_text)