import boto3
import json
from langchain_aws import BedrockEmbeddings
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from requests_aws4auth import AWS4Auth
import re
import yaml

# Load Config
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

def generate_report(document_text):
    with open("ingest_prompt.txt", "r") as file:
        template = file.read()

    prompt = template.format(document=document_text)

    bedrock_session = boto3.session.Session()
    bedrock = bedrock_session.client("bedrock-runtime", region_name=config['region'])

    body = json.dumps({
    "max_tokens": 4096,
    "messages": [{"role": "user", "content": prompt}],
    "anthropic_version": "bedrock-2023-05-31"
    })

    response = bedrock.invoke_model(body=body, modelId=config['model']['ingest'])

    response_body = json.loads(response.get("body").read())
    return response_body.get("content")[0].get("text")


def generate_embedding(passage):
    embeddings_client = BedrockEmbeddings(model_id=config['model']['embedding'], region_name=config['region'])

    embedding = embeddings_client.embed_query(passage)
    return (embedding)


def insert_into_opensearch(document):
    region = config['region']
    service = 'aoss'
    host = config['opensearch_endpoint']

    session = boto3.Session()
    credentials = session.get_credentials()
    auth = AWSV4SignerAuth(credentials, region, service)

    client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )

    response = client.index(
        index=config['opensearch_index'],
        body=document
    )

    print(f"Inserted document: {document['guide_file_name']}")

def insert_document_os(text_data, guide_file_name):
    try:
        report = generate_report(text_data)
    
        report_text = re.search(r'<report>(\s*{.*?}\s*)</report>', report, re.DOTALL).group(1)
        data = json.loads(report_text)

        embedding = generate_embedding(text_data)

        # Preparing document for OpenSearch
        document = {
            "guide_title": data["guide_title"],
            "question_asked": data["question_asked"],
            "description": data["description"],
            "passage": text_data,
            "embedding": embedding,
            "guide_file_name": guide_file_name
        }

        insert_into_opensearch(document)
    except Exception as e:
        print(f"Inserting {guide_file_name} into opensearch failed due to {e}")






