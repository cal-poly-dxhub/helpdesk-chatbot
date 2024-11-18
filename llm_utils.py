import boto3
import json

def decide_redirect(conversation, current_helpdesk):
    role_to_assume = 'aws_account_arn'    

    prompt = f"""
    You are to read the above conversation, 
    and decide whether or not the user is on the correct helpdesk.

    The current helpdesk is {current_helpdesk}

    Respond in this format: 
    <reasoning>Why you chose that helpdesk</reasoning>
    <helpdesk>NAME_OF_HELPDESK</helpdesk>

    """

    prompt += conversation

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
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": prompt}],
    "anthropic_version": "bedrock-2023-05-31"
    })

    response = bedrock.invoke_model(body=body, modelId="anthropic.claude-3-5-sonnet-20240620-v1:0")

    response_body = json.loads(response.get("body").read())
    return response_body.get("content")[0].get("text")