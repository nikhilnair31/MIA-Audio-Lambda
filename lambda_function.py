import os
import io
import json
import uuid
import boto3
import base64
import logging
import pinecone
from openai import OpenAI
from langchain.embeddings import OpenAIEmbeddings

# API keys
openai_api_key = os.environ.get('OPENAI_API_KEY')
openai_client = OpenAI(api_key=openai_api_key)
embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)

pinecone_api_key = os.environ.get('PINECONE_API_KEY')
pinecone_env_key = os.environ.get('PINECONE_ENV_KEY')
pinecone_index_name = os.environ.get('PINECONE_INDEX_NAME')
pinecone.init(api_key=pinecone_api_key, environment=pinecone_env_key)
index = pinecone.Index(pinecone_index_name)

# Initialize
s3 = boto3.client('s3')

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# System Prompts
whisper_prompt = f"""
    don't translate or make up words to fill in the rest of the sentence. if background noise return .
"""
clean_system_prompt = f"""
    You will receive a user's transcribed speech and are to process it to correct potential errors. 
    DO NOT DO THE FOLLOWING:
    - Generate any additional content 
    - Censor any of the content
    - Print repetitive content
    DO THE FOLLOWING:
    - Account for transcript include speech of multiple users
    - Only output corrected text 
    - If too much of the content seems erronous return '.' 
    Transcription: 
"""
facts_system_prompt = f"""
    You will receive transcribed speech from the environment and are to extract relevant facts from it. 
    DO THE FOLLOWING:
    - Extract statements about factual information from the content
    - Account for transcript to be from various sources like the user, surrrounding people, music or video playing in vicinity etc.
    - Only output factual information
    DO NOT DO THE FOLLOWING:
    - Generate bullet points
    - Generate any additional content
    - Censor any of the content
    - Print repetitive content
    Content: 
"""

def start_processing(event):
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']
    logger.info(f"Event: {bucket_name} - {object_key}\n")
    
    filename = object_key.split("/")[-1]
    download_path = os.path.join('/tmp', filename)
    logger.info(f"filename: {filename} - download_path: {download_path}\n")
    s3.download_file(bucket_name, object_key, download_path)
    
    with open(download_path, 'rb') as file_obj:
        raw_transcript = whisper(whisper_prompt, file_obj)
        clean_transcript = gpt("gpt-3.5-turbo", clean_system_prompt, raw_transcript)
        factual_transcript = gpt("gpt-4-1106-preview", facts_system_prompt, clean_transcript)
        vector(factual_transcript)
def whisper(system_prompt, file_content):
    response = openai_client.audio.transcriptions.create(
        model = "whisper-1", 
        file = file_content, 
        language = "en",
        prompt = system_prompt
    )
    transcript_text = response.text

    print(f'transcript_text: {transcript_text}\n')
    logger.info(f"Whisper API Response: {transcript_text}\n")

    return transcript_text
def gpt(modelName, system_prompt, user_text):
    response = openai_client.chat.completions.create(
        model=modelName,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
    )
    assitant_text = response.choices[0].message.content

    print(f'assitant_text: {assitant_text}\n')
    logger.info(f"GPT API Response: {assitant_text}\n")

    return assitant_text
def vector(text):
    # Initialize the Pinecone client
    embedding = embeddings_model.embed_documents([text])
    
    index.upsert([
        (
            str(uuid.uuid4()),  # Convert UUID to string
            embedding[0],
            {
                "text": f'{text}', 
                "source": "recording"
            }),
    ])

    print("Upserted into DB successfully!\n")
    logger.info(f"Upserted into DB successfully!\n")

def handler(event, context):
    try:
        logger.info(f'started lambda_handler\n\n')

        # Running on AWS Lambda
        if context:
            start_processing(event)
        # Running locally
        else:
            local_file_path = r'.\Data\recordings\recording_206419037.m4a'
            object_key = r'recordings\recording_206419037.m4a'

            with open(local_file_path, 'rb') as file_obj:
                raw_transcript = whisper(whisper_prompt, file_obj)
                clean_transcript = gpt("gpt-3.5-turbo", clean_system_prompt, raw_transcript)
                factual_transcript = gpt("gpt-4-1106-preview", facts_system_prompt, clean_transcript)
                vector(factual_transcript, object_key)
        return {
            'statusCode': 200,
            'body': json.dumps('Processing complete')
        }

    except Exception as e: 
        logger.error(f'Error: \n{e}\n\n')
        logger.error("Stack Trace:", exc_info=True)
        
        return {
            'statusCode': 400,
            'body': f'Error! {e}'
        }

if __name__ == '__main__':
    # Dummy context
    test_context = None
    # Dummy event
    test_event = {
        'Records': [{
            's3': {
                'bucket': {'name': 'mia-audiofiles'},
                'object': {'key': 'recording_155994629.m4a'}
            }
        }]
    }

    # Call the lambda handler
    response = handler(test_event, test_context)
    print(response)