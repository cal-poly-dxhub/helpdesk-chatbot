import boto3
import json
from langchain_aws import BedrockEmbeddings
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from requests_aws4auth import AWS4Auth
import re

def generate_report(document_text):
    role_to_assume = 'aws_account_arn'    

    with open("ingest_prompt.txt", "r") as file:
        template = file.read()

    prompt = template.format(document=document_text)

    # Use STS to assume role  
    credentials = boto3.client('sts').assume_role(  
        RoleArn=role_to_assume,  
        RoleSessionName='RoleBSession'  
    )['Credentials']  

    # Create Bedrock client with temporary credentials  
    bedrock_session = boto3.session.Session(  
        aws_access_key_id=credentials['AccessKeyId'],  
        aws_secret_access_key=credentials['SecretAccessKey'],  
        aws_session_token=credentials['SessionToken']  
    )  

    bedrock = bedrock_session.client("bedrock-runtime", region_name="your_aws_region")

    body = json.dumps({
    "max_tokens": 4096,
    "messages": [{"role": "user", "content": prompt}],
    "anthropic_version": "bedrock-2023-05-31"
    })

    response = bedrock.invoke_model(body=body, modelId="anthropic.claude-3-5-sonnet-20240620-v1:0")

    response_body = json.loads(response.get("body").read())
    return response_body.get("content")[0].get("text")


def generate_embedding(passage):
    embeddings_client = BedrockEmbeddings(model_id="amazon.titan-embed-text-v2:0", region_name="your_aws_region")

    embedding = embeddings_client.embed_query(passage)
    return (embedding)


def insert_into_opensearch(document):
    region = 'your_aws_region'
    service = 'aoss'
    host = 'ouv6ulfktpkqvgekbhd3.your_aws_region.aoss.amazonaws.com'

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
        index="helpdesk-index",
        body=document
    )

    print(f"Inserted document: {document['guide_file_name']}")

def insert_document_os(text_data, guide_file_name):
    try:
        report = generate_report(text_data)
    
        report_text = re.search(r'<report>(\s*{.*?}\s*)</report>', report, re.DOTALL).group(1)
        data = json.loads(report_text)

        passage = json.dumps({
            "guide_title": data["guide_title"],
            "question_asked": data["question_asked"],
            "description": data["description"],
            "passage": text_data
        })

        embedding = generate_embedding(passage)

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






