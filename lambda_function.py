import os
import io
import json
import uuid
import boto3
import base64
import logging
import pinecone
from datetime import datetime
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
upsert_check_system_prompt = f"""
    You are to determine if the text content provided is to be upserted into the database or not.
    If the text contains no factual information then return "N" else "Y".
    
    Examples:
    Example #1:
    Input: No factual information can be extracted from this statement, as it is a personal opinion or intention without any specific factual content.
    Output: N
    Example #2:
    Input: No factual information to extract.
    Output: N
    Example #3:
    Input: - The speaker went to the store to buy fruit and vegetables. - The speaker went to the park to have a picnic
    Output: Y
    
    Content: 
"""

def start_processing(event):
    # Get bucket name and object key from the event
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']
    logger.info(f"Event: {bucket_name} - {object_key}\n")
    
    # Get the filename and download path
    filename = object_key.split("/")[-1]
    download_path = os.path.join('/tmp', filename)
    logger.info(f"filename: {filename} - download_path: {download_path}\n")
    
    # Download the file from S3
    s3.download_file(bucket_name, object_key, download_path)
    
    # Retrieve metadata for the object
    response = s3.head_object(Bucket=bucket_name, Key=object_key)
    metadata = response.get('Metadata', {})
    logger.info(f"Metadata: {metadata}\n")
    
    with open(download_path, 'rb') as file_obj:
        raw_transcript = whisper(whisper_prompt, file_obj)
        clean_transcript = gpt("gpt-3.5-turbo", clean_system_prompt, raw_transcript)
        factual_transcript = gpt("gpt-4-1106-preview", facts_system_prompt, clean_transcript)
        vector(factual_transcript, metadata)
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
def vector(text, metadata):
    # Initialize the Pinecone client
    embedding = embeddings_model.embed_documents([text])

    # Create a document for upsertion with metadata
    document = {
        "text": text,
        "source": "recording"
    }

    # Convert specific metadata keys to the appropriate types
    if 'address' in metadata:
        metadata['address'] = str(metadata['address'])
    if 'currenttimeformattedstring' in metadata:
        metadata['currenttimeformattedstring'] = datetime.strptime(metadata['currenttimeformattedstring'], '%a %d/%m/%y %H:%M')
    if 'longitude' in metadata:
        metadata['longitude'] = float(metadata['longitude'])
    if 'latitude' in metadata:
        metadata['latitude'] = float(metadata['latitude'])


    # Merge the metadata into the document dictionary
    document.update(metadata)
    
    index.upsert([
        (
            str(uuid.uuid4()),  # Convert UUID to string
            embedding[0],
            document
        ),
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
                check_to_upsert = gpt("gpt-4-1106-preview", upsert_check_system_prompt, factual_transcript)
                
                if(check_to_upsert == 'Y'):
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