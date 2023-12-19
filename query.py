import os
import json
import boto3
import logging
import pinecone
from openai import OpenAI
from langchain.vectorstores import Pinecone
from langchain.embeddings import OpenAIEmbeddings
from langchain.embeddings.openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

# API keys
openai_api_key = os.getenv('OPENAI_API_KEY')
pinecone_api_key = os.getenv('PINECONE_API_KEY')
pinecone_env_key = os.getenv('PINECONE_ENV_KEY')
pinecone_index_name = os.getenv('PINECONE_INDEX_NAME')

# Initialize the Pinecone client
embed = OpenAIEmbeddings(openai_api_key=openai_api_key)
pinecone.init(api_key=pinecone_api_key, environment=pinecone_env_key)
index = pinecone.Index(index_name=pinecone_index_name)
vectorstore = Pinecone(index, embed, "text")

# query_text = str(input("Search Pinecone...\n"))
query_text = "elon musk"
query_results = vectorstore.similarity_search(query_text, k=3)
print(f'query_results\n{query_results}')

# Iterate through search matches and retrieve documents
for document in query_results:
    print(f"Document content: {document.page_content}")
    print(f"Document source: {document.metadata['source']}")
    print("-----------------------------")
