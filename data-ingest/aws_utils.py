import boto3
import os
import json
import base64
import boto3
from botocore.exceptions import ClientError

def download_s3_object(bucket_name, object_key, download_dir='./downloads'):
    # Initialize S3 client
    s3_client = boto3.client('s3')
    
    # Ensure the download directory exists
    os.makedirs(download_dir, exist_ok=True)
    
    # Define the local file path
    local_file_path = os.path.join(download_dir, os.path.basename(object_key))
    
    # Download the file from S3
    s3_client.download_file(bucket_name, object_key, local_file_path)
    
    # Construct the public URL
    public_url = f'https://{bucket_name}.s3.amazonaws.com/{object_key}'
    
    return local_file_path, public_url


def list_s3_objects(bucket_name):
    # Initialize S3 client
    s3_client = boto3.client('s3')
    object_keys = []
    
    # Paginate through all objects in the bucket
    paginator = s3_client.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name):
        if 'Contents' in page:
            for obj in page['Contents']:
                object_keys.append(obj['Key'])
    
    return object_keys

def describe_image_with_claude(image_base64, max_tokens=500):
    """
    Invokes Claude with a multimodal prompt to describe a base64-encoded image.
    
    Args:
        image_base64 (str): The base64-encoded image string.
        max_tokens (int, optional): The maximum number of tokens to generate. Default is 500.
    
    Returns:
        dict: The response from Claude, or error message if the call fails.
    """
    # Prepare the multimodal message with the image and text prompt
    role_to_assume = 'aws_account_arn'    

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

    bedrock_runtime = bedrock_session.client("bedrock-runtime", region_name="your_aws_region")
    
    message = {
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_base64}},
            {"type": "text", "text": "Describe the contents of this image."}
        ]
    }

    messages = [message]

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages
    })

    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    try:
        # Call Claude model with the image and prompt
        response = bedrock_runtime.invoke_model(body=body, modelId=model_id)
        response_body = json.loads(response.get('body').read())
        return response_body["content"][0]["text"]
    except ClientError as err:
        # Handle any client errors that may occur
        return {"error": err.response["Error"]["Message"]}