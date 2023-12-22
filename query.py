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
pinecone.init(api_key=pinecone_api_key, environment=pinecone_env_key)
index = pinecone.Index(pinecone_index_name)

query_text = 'mute sound'
query_embedding = embeddings_model.embed_documents([query_text])[0]
top_k = 3

query_result = index.query(vector=query_embedding, top_k=top_k, include_metadata=True)
# print(f"Query Results: {query_result}")

for match in query_result['matches']:
    print(f"ID: {match['id']}, Score: {match['score']}, Metadata: {match.get('metadata', {})}")