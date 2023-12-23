import os
import pinecone
from openai import OpenAI
from langchain.embeddings import OpenAIEmbeddings
from dotenv import load_dotenv

# region Vars & Initialization
load_dotenv()

openai_api_key = os.environ.get('OPENAI_API_KEY')
openai_client = OpenAI(api_key=openai_api_key)
embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)

pinecone_api_key = os.environ.get('PINECONE_API_KEY')
pinecone_env_key = os.environ.get('PINECONE_ENV_KEY')
pinecone_index_name = os.environ.get('PINECONE_INDEX_NAME')
pinecone.init(api_key=pinecone_api_key, environment=pinecone_env_key)
index = pinecone.Index(pinecone_index_name)
# endregion

def query(text, showLog = False):
    top_k = 3
    query_embedding = embeddings_model.embed_documents([text])[0]
    query_result = index.query(vector=query_embedding, top_k=top_k, include_metadata=True)

    if showLog:
        print(f"Query Results: {query_result}\n")
        print(f"{'*'*50}\n")

        print(f"Query Results\n")
        for match in query_result['matches']:
            print(f"ID: {match['id']}\nScore: {match['score']}\nMetadata: {match.get('metadata', {})}\n")
        print(f"{'*'*50}\n")
    
    return query_result

def gpt(query_text, query_result, modelName = "gpt-4-1106-preview", seed = 48, length = 1024, temp = 0.0):
    system_prompt = f"""
        You are the user's companion. Help them using the context provided from metadata text. 
        Do not make up any information, admit if you don't know something. 
        Context:
    """
    response = openai_client.chat.completions.create(
        model=modelName,
        seed=seed,
        max_tokens=length,
        temperature=temp,
        messages=[
            {"role": "system", "content": f'{system_prompt} {query_result}'},
            {"role": "user", "content": query_text},
        ],
    )
    res = response.choices[0].message.content
    
    print(f"\n{'*'*50}")
    print(f"Response\n{res}")
    print(f"{'*'*50}\n")

if __name__ == '__main__':
    query_text = f"""
        I remember hearing something about a forklift?
    """
    query_result = query(text = query_text, showLog = False)
    gpt(query_text = query_text, query_result = query_result, modelName = "gpt-4-1106-preview", seed = 48, length = 1024, temp = 0.0)