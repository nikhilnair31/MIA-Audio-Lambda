
import os
import io
import json
import boto3
import pinecone
from openai import OpenAI
from langchain.embeddings import OpenAIEmbeddings

# Inititlizing
openai_api_key = os.environ.get('OPENAI_API_KEY')
openai_client = OpenAI(api_key=openai_api_key)
embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)

pinecone_api_key = os.environ.get('PINECONE_API_KEY')
pinecone_env_key = os.environ.get('PINECONE_ENV_KEY')
pinecone_index_name = os.environ.get('PINECONE_INDEX_NAME')
print(f"Pinecone API Key: {os.environ.get('PINECONE_API_KEY')}")

s3 = boto3.client('s3')

# System Prompts
whisper_prompt = f"""
    don't translate or make up words to fill in the rest of the sentence. if background noise return .
"""

def whisper(system_prompt, file_content):
    response = openai_client.audio.transcriptions.create(
        model = "whisper-1", 
        file = file_content, 
        language = "en",
        prompt = system_prompt
    )
    transcript_text = response.text

    print(f'transcript_text: {transcript_text}\n')

    return transcript_text
def vector(text, object_key):
    embedding = embeddings_model.embed_documents([text])
    embedding_json = json.dumps(embedding[0])

    # Initialize the ChromaDB client
    chroma_db_dir = "/tmp/mia-audiofiles/texts"
    client = chromadb.PersistentClient(path=chroma_db_dir)

    # Write the embedding to a file
    chroma_db_path = f"{chroma_db_dir}/{object_key}"
    os.makedirs(os.path.dirname(chroma_db_path), exist_ok=True)
    with open(chroma_db_path, 'w') as db_file:
        db_file.write(embedding_json)

    # Upload the virtual database file to S3
    s3.upload_file(Filename=chroma_db_path, Bucket='mia-audiofiles', Key=chroma_db_key)
    print(f"Object uploaded: {chroma_db_path} -> {chroma_db_key}")

    print("Upserted into DB successfully!\n")

def handler(event, context):
    try:
        with open('Data\mia-audiofiles\recordings\recording_206419037.m4a', 'rb') as file_obj:
            raw_transcript = whisper(whisper_prompt, file_obj)
            vector(raw_transcript, object_key)

        return {
            'statusCode': 200,
            'body': json.dumps('Processing complete')
        }

    except Exception as e: 
        print(f'Error: \n{e}\n\n')
        
        return {
            'statusCode': 400,
            'body': f'Error! {e}'
        }

if __name__ == '__main__':
    test_context = None
    test_event = None
    response = handler(test_event, test_context)
    print(response)