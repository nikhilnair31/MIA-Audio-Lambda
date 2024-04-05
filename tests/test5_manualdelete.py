import os
import pinecone
import numpy as np
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

# Embedding text
text_to_embed = " null"
embedding = embeddings_model.embed_query(text_to_embed)
print(f'embedding\n{len(embedding)}')

# Query top 1000 with metadata
query_results = index.query(
    vector=[embedding],
    filter={
        "text": text_to_embed
    },
    top_k=1000,
    include_metadata=True
)
print(f'query_results\n{query_results}')

# Store IDs
result_ids = [result.id for result in query_results['matches']]
print(f'result_ids\n{result_ids}')

# Delete by ID
index.delete(ids=result_ids)
print(f'Deleted')
