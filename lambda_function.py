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
DELETE_S3_OBJ = os.environ.get('DELETE_S3_OBJ', 'False').lower() == 'true'
CLEAN_AUDIO = os.environ.get('CLEAN_AUDIO', 'False').lower() == 'true'
AUDIO_CLEANING_LAMBDA_NAME = os.environ.get('AUDIO_CLEANING_LAMBDA_NAME')

# OpenAI Related
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
openai_client = OpenAI(api_key=OPENAI_API_KEY)
embeddings_model = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
CLEAN_MODEL = str(os.environ.get('CLEAN_MODEL'))
SPEAKER_LABEL_MODEL = str(os.environ.get('SPEAKER_LABEL_MODEL'))

# Deepgram Related
DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')

# Pinecone Related
PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
PINECONE_ENV_KEY = os.environ.get('PINECONE_ENV_KEY')
PINECONE_INDEX_NAME = os.environ.get('PINECONE_INDEX_NAME')
pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENV_KEY)
index = pinecone.Index(PINECONE_INDEX_NAME)

# System Prompts
WHISPER_PROMPT = str(os.environ.get('WHISPER_PROMPT'))
CLEAN_SYSTEM_PROMPT = str(os.environ.get('CLEAN_SYSTEM_PROMPT'))
FACTS_SYSTEM_PROMPT = str(os.environ.get('FACTS_SYSTEM_PROMPT'))
UPSERT_CHECK_SYSTEM_PROMPT = str(os.environ.get('UPSERT_CHECK_SYSTEM_PROMPT'))
SPEAKER_LABEL_SYSTEM_PROMPT = str(os.environ.get('SPEAKER_LABEL_SYSTEM_PROMPT'))
# endregion 

# region Functions
def pulling_s3_object_details(event):
    logger.info(f'Pulling S3 Object Details...')

    # Get global bucket name and object key from the event
    bucket_name = event['Records'][0]['s3']['bucket']['name']
    initial_object_key = event['Records'][0]['s3']['object']['key']
    logger.info(f"Event\nBucket Name: {bucket_name}\nObject Key: {initial_object_key}")

    return bucket_name, initial_object_key

def downloading_s3_objects(event, bucket_name, initial_object_key):
    logger.info(f'Downloading S3 Objects (audio file and metadata)...')

    # Retrieve metadata for the object
    audiofile_s3obj = s3.head_object(Bucket=bucket_name, Key=initial_object_key)
    audiofile_metadata = audiofile_s3obj.get('Metadata', {})
    logger.info(f"Audio File Metadata: {audiofile_metadata}\n")

    # Check if audio cleaning is required by flag
    final_object_key = clean_or_not_final_audio_path(event, bucket_name, initial_object_key)
    logger.info(f"Final Audio File's Object Key: {final_object_key}")

    # Create a path to download the final audio file
    audiofile_name = final_object_key.split("/")[-1].strip()
    updated_audiofile_name = audiofile_name.replace("\"", "").strip()
    audiofile_download_path = os.path.join('/tmp', updated_audiofile_name)
    logger.info(f"Audio file name: {audiofile_name} - Audio file download path: {audiofile_download_path}")
    s3.download_file(bucket_name, final_object_key, audiofile_download_path)
    
    return audiofile_s3obj, final_object_key, audiofile_download_path, audiofile_metadata

def start_processing(bucket_name, final_object_key, audiofile_s3obj, audiofile_download_path, audiofile_metadata):
    logger.info(f'Starting processing audio..')

    raw_transcript = ''

    with open(audiofile_download_path, 'rb') as file_obj:
        file_content = file_obj.read()
        raw_transcript = deepgram(file_content)
        # raw_transcript = whisper(file_obj)
    
        clean_transcript = gpt(CLEAN_MODEL, CLEAN_SYSTEM_PROMPT, raw_transcript)
        
        speaker_label_transcript = gpt(SPEAKER_LABEL_MODEL, SPEAKER_LABEL_SYSTEM_PROMPT, clean_transcript)

    if speaker_label_transcript.lower() not in {'.', 'null'}:
        vector_id = vectorupsert(speaker_label_transcript, audiofile_metadata)
    
def delete_or_not_audio_file(bucket_name, final_object_key):
    logger.info(f'Deleting audio file...')

    # If required delete the S3 object after processing is complete
    if DELETE_S3_OBJ:
        s3.delete_object(Bucket=bucket_name, Key=final_object_key)
        logger.info(f"Deleted S3 object: {bucket_name}/{final_object_key}")

def clean_or_not_final_audio_path(event, bucket_name, initial_object_key):
    logger.info(f'Creating final audio file object key...')

    if CLEAN_AUDIO:
        logger.info(f"Cleaning audio file...")

        # Invoke Lambda B for audio cleaning
        audio_cleaning_lambda_response = lam.invoke(
            FunctionName=AUDIO_CLEANING_LAMBDA_NAME,
            InvocationType='RequestResponse',
            Payload=json.dumps(event)
        )
        payload_stream = audio_cleaning_lambda_response['Payload']
        payload_content = payload_stream.read()
        payload_json = json.loads(payload_content)
        cleaned_audiofile_object_key = payload_json.get('body', '').replace("\"", "")
        
        s3.delete_object(Bucket=bucket_name, Key=initial_object_key)
        logger.info(f"Deleted Initial Audio File S3 Object at {bucket_name}/{initial_object_key}")

        return cleaned_audiofile_object_key

    logger.info(f"NOT cleaning audio file...")
    return null

def update_metadata_type(metadata, text):
    document = metadata

    document['text'] = str(text)

    if 'source' in metadata:
        document['source'] = str(metadata['source'])
    if 'username' in metadata:
        document['username'] = str(metadata['username'])
    if 'filename' in metadata:
        document['filename'] = str(metadata['filename'])
    
    if 'currenttimeformattedstring' in metadata:
        document['currenttimeformattedstring'] = str(datetime.strptime(metadata['currenttimeformattedstring'], '%Y-%m-%d %H:%M:%S'))
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

def whisper(file_content):
    response = openai_client.audio.translations.create(
        model = "whisper-1", 
        file = file_content, 
        # language = "en",
        prompt = WHISPER_PROMPT
    )
    transcript_text = response.text
    logger.info(f"Whisper API Response: {transcript_text}\n")
    return transcript_text

def deepgram(file_content):
    url = "https://api.deepgram.com/v1/listen"
    headers = {
        "Accept": "application/json",
        "Content-Type": 'audio/wav',
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
    logger.info(f"Deepgram API response_json: {response_json}\n")

    # Extract transcript if available, otherwise use default
    response_data = response_json['results']['channels'][0]['alternatives'][0]
    final_transcript = response_data.get('paragraphs', {}).get('transcript', response_data['transcript'])
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
    logger.info(f"Upserting vector to Pinecone...")

    # Initialize the Pinecone client
    embedding = embeddings_model.embed_documents([text])
    updated_metadata = update_metadata_type(metadata, text)
    vector_id = str(uuid.uuid4())
    index.upsert([
        (
            vector_id,
            embedding[0],
            updated_metadata
        ),
    ])

    logger.info(f"Upserted successfully!\n")

    return vector_id
# endregion 

# region Main
def handler(event, context):
    try:
        logger.info(f'Started!')

        bucket_name, initial_object_key = pulling_s3_object_details(event)
        audiofile_s3obj, final_object_key, audiofile_download_path, audiofile_metadata = downloading_s3_objects(event, bucket_name, initial_object_key)
        start_processing(bucket_name, final_object_key, audiofile_s3obj, audiofile_download_path, audiofile_metadata)
        delete_or_not_audio_file(bucket_name, final_object_key)

        return {
            'statusCode': 200,
            'body': json.dumps('Processing complete!')
        }

    except Exception as e: 
        logger.error(f'Error: {e}', exc_info=True)
        
        return {
            'statusCode': 400,
            'body': f'Error :(\n{e}'
        }
# endregion 