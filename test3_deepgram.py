import os
import requests
import urllib.parse

DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')

def deepgram(file_content):
    url = "https://api.deepgram.com/v1/listen"
    headers = {
        "Accept": "application/json",
        "Content-Type": 'audio/m4a',
        "Authorization": f"Token {DEEPGRAM_API_KEY}"
    }
    params = {
        'model': 'nova-2-general',
        'version': 'latest',
        'detect_language': 'true',
        'diarize': 'true',
        'smart_format': 'true',
        'filler_words': 'true'
    }
    response = requests.post(url, params=params, headers=headers, data=file_content, timeout=300)
    
    response_json = response.json()
    print(f"Deepgram API response_json: {response_json}\n")
    
    # Access elements using dictionary keys
    channels = response_json.get('results', {}).get('channels', [])
    if channels:
        alternatives = channels[0].get('alternatives', [])
        if alternatives:
            paragraphs = alternatives[0].get('paragraphs', {})
            if paragraphs:
                return paragraphs.get('transcript', '')
            else:
                print("No paragraphs found in the response.")
        else:
            print("No alternatives found in the response.")
    else:
        print("No channels found in the response.")
    
    return null

with open(r'Data\recording_13012024180858.m4a', 'rb') as file_obj:
    file_content = file_obj.read()
    final_transcript = deepgram(file_content)