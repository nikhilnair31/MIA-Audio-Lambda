import os
import pinecone
from langchain.embeddings import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.environ.get('OPENAI_API_KEY')
embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)

pinecone_api_key = os.environ.get('PINECONE_API_KEY')
pinecone_env_key = os.environ.get('PINECONE_ENV_KEY')
pinecone_index_name = os.environ.get('PINECONE_INDEX_NAME')
print(f"Pinecone API Key: {os.environ.get('PINECONE_API_KEY')}")

pinecone.init(api_key=pinecone_api_key, environment=pinecone_env_key)
index = pinecone.Index(pinecone_index_name)

index.upsert([
    (
        "aee320cd-97bc-4f44-95ff-c623a5e2f320",
        [0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
        {
            "text": "text", 
            "source": "test.txt"
        }),
])

print(f'Upserted!')