# region Imports
import os
import io
import json
import time
import uuid
import boto3
import base64
import logging
import pinecone
import requests
import urllib.parse
from botocore.config import Config
from datetime import datetime
from openai import OpenAI
from langchain.embeddings import OpenAIEmbeddings
# endregion 

# region Initialization
# Initialization Related
config = Config(
    read_timeout=900,
    connect_timeout=900,
    retries={"max_attempts": 0},
    tcp_keepalive=True,
)
start = time.time()
session = boto3.Session()
s3 = session.client('s3')
lam = session.client('lambda', config=config)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# General Related
delete_s3_obj = os.environ.get('DELETE_S3_OBJ', 'False').lower() == 'true'
clean_audio = os.environ.get('CLEAN_AUDIO', 'False').lower() == 'true'
audio_cleaning_lambda_name = os.environ.get('AUDIO_CLEANING_LAMBDA_NAME')

# OpenAI Related
openai_api_key = os.environ.get('OPENAI_API_KEY')
openai_client = OpenAI(api_key=openai_api_key)
embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)
clean_model = str(os.environ.get('CLEAN_MODEL'))
speaker_label_model = str(os.environ.get('SPEAKER_LABEL_MODEL'))

# Deepgram Related
deepgram_api_key = os.environ.get('DEEPGRAM_API_KEY')

# Pinecone Related
pinecone_api_key = os.environ.get('PINECONE_API_KEY')
pinecone_env_key = os.environ.get('PINECONE_ENV_KEY')
pinecone_index_name = os.environ.get('PINECONE_INDEX_NAME')
pinecone.init(api_key=pinecone_api_key, environment=pinecone_env_key)
index = pinecone.Index(pinecone_index_name)

# System Prompts
whisper_prompt = str(os.environ.get('WHISPER_PROMPT'))
clean_system_prompt = str(os.environ.get('CLEAN_SYSTEM_PROMPT'))
facts_system_prompt = str(os.environ.get('FACTS_SYSTEM_PROMPT'))
upsert_check_system_prompt = str(os.environ.get('UPSERT_CHECK_SYSTEM_PROMPT'))
speaker_label_system_prompt = str(os.environ.get('SPEAKER_LABEL_SYSTEM_PROMPT'))
# endregion 

# region Functions
def update_metadata_type(metadata, text):
    document = metadata

    document['text'] = str(text)

    if 'source' in metadata:
        document['source'] = str(metadata['source'])
    if 'username' in metadata:
        document['username'] = str(metadata['username'])
    if 'filename' in metadata:
        document['filename'] = str(metadata['filename'])
    
    # if 'systemTime' in metadata:
    #     document['systemTime'] = int(metadata['systemTime'])
    if 'currenttimeformattedstring' in metadata:
        document['currenttimeformattedstring'] = str(datetime.strptime(metadata['currenttimeformattedstring'], '%y-%m-%d %H:%M:%S'))
    if 'day' in metadata:
        document['day'] = int(metadata['day'])
    if 'month' in metadata:
        document['month'] = int(metadata['month'])
    if 'year' in metadata:
        document['year'] = int(metadata['year'])
    if 'hours' in metadata:
        document['hours'] = int(metadata['hours'])
    if 'minutes' in metadata:
        document['minutes'] = int(metadata['minutes'])

    if 'address' in metadata:
        document['address'] = str(metadata['address'])
    # if 'longitude' in metadata:
    #     document['longitude'] = float(metadata['longitude'])
    # if 'latitude' in metadata:
    #     document['latitude'] = float(metadata['latitude'])

    if 'batterylevel' in metadata:
        document['batterylevel'] = int(metadata['batterylevel'])

    if 'cloudall' in metadata:
        document['cloudall'] = int(metadata['cloudall'])
    if 'feelslike' in metadata:
        document['feelslike'] = float(metadata['feelslike'])
    if 'humidity' in metadata:
        document['humidity'] = int(metadata['humidity'])
    if 'windspeed' in metadata:
        document['windspeed'] = float(metadata['windspeed'])

    return document

def start_processing(event):
    # Get bucket name and object key from the event
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    object_key = event['Records'][0]['s3']['object']['key']
    logger.info(f"Event: {bucket_name} - {object_key}\n")
    
    # Retrieve metadata for the object
    response = s3.head_object(Bucket=bucket_name, Key=object_key)
    metadata = response.get('Metadata', {})
    logger.info(f"Metadata: {metadata}\n")

    # Invoke Lambda B for audio cleaning
    final_obj_key = ''
    if clean_audio:
        response = lam.invoke(
            FunctionName=audio_cleaning_lambda_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        payload_stream = response['Payload']
        payload_content = payload_stream.read()
        payload_json = json.loads(payload_content)
        cleaned_audio_path = payload_json.get('body', '').replace("\"", "")
        final_obj_key = cleaned_audio_path
        logger.info(f"final_obj_key: {final_obj_key}")
    else:
        final_obj_key = object_key
    
    # Create a path to download the cleaned audio file
    filename = final_obj_key.split("/")[-1].strip()
    updated_filename = filename.replace("\"", "").strip()
    download_path = os.path.join('/tmp', updated_filename)
    logger.info(f"filename: {filename}\ndownload_path: {download_path}")
    s3.download_file(bucket_name, final_obj_key, download_path)

    with open(download_path, 'rb') as file_obj:
        file_content = file_obj.read()
        # raw_transcript = deepgram(file_content)
        raw_transcript = whisper(whisper_prompt, file_obj)
        clean_transcript = gpt(clean_model, clean_system_prompt, raw_transcript)
        speaker_label_transcript = gpt(speaker_label_model, speaker_label_system_prompt, clean_transcript)

        if(speaker_label_transcript != '.' and speaker_label_transcript.lower() != 'null'):
            vectorupsert(speaker_label_transcript, metadata)
    
    # If required delete the S3 object after processing is complete
    if delete_s3_obj:
        s3.delete_object(Bucket=bucket_name, Key=final_obj_key)
        logger.info(f"Deleted S3 object: {bucket_name}/{final_obj_key}")

def whisper(system_prompt, file_content):
    response = openai_client.audio.translations.create(
        model = "whisper-1", 
        file = file_content, 
        # language = "en",
        prompt = system_prompt
    )
    transcript_text = response.text
    logger.info(f"Whisper API Response: {transcript_text}\n")
    return transcript_text
def deepgram(file_content):
    url = "https://api.deepgram.com/v1/listen"
    audio_format = 'audio/wav'
    headers = {
        "Accept": "application/json",
        "Content-Type": audio_format,
        "Authorization": f"Token {deepgram_api_key}"
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
    logger.info(f"Deepgram API response_json: {response_json}\n")
    final_transcript = response_json.results.channels[0].alternatives[0].paragraphs.transcript
    logger.info(f"Deepgram API final_transcript: {final_transcript}\n")
    
    return final_transcript
def gpt(modelName, system_prompt, user_text):
    response = openai_client.chat.completions.create(
        model=modelName,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ]
    )
    assitant_text = response.choices[0].message.content

    logger.info(f"GPT API Response: {assitant_text}\n")

    return assitant_text
def vectorupsert(text, metadata):
    # Initialize the Pinecone client
    embedding = embeddings_model.embed_documents([text])
    updated_metadata = update_metadata_type(metadata, text)
    vector_id = str(uuid.uuid4())
    index.upsert([
        (
            vector_id,  # Convert UUID to string
            embedding[0],
            updated_metadata
        ),
    ])

    logger.info(f"Upserted into DB successfully!\n")
# endregion 

# region Main
def handler(event, context):
    try:
        logger.info(f'started lambda_handler\n\n')

        start_processing(event)

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
# endregion 