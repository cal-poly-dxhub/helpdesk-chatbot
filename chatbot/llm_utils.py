import boto3
import json
import yaml
import tiktoken
import logging

# Load Config
with open('config.yaml', 'r') as file:
    config = yaml.safe_load(file)

SONNET_INPUT_COST_PER_TOKEN = 0.000003
SONNET_OUTPUT_COST_PER_TOKEN = 0.000015
HAIKU_INPUT_COST_PER_TOKEN = 0.00000025
HAIKU_OUTPUT_COST_PER_TOKEN = 0.00000125

tokenizer = tiktoken.get_encoding("o200k_base")

def log_chat(chat):
    role = chat.get("role", "unknown")
    content = chat.get("content", "")
    logging.info(f"{role}: {content}")

def decide_redirect(conversation, current_helpdesk, helpdesk_info): 
    prompt = f"""
    You are to read the above conversation, 
    and decide whether or not the user is on the correct helpdesk.

    The current helpdesk is {current_helpdesk}

    Here are the avaible helpdesks to choose from: {helpdesk_info}

    Put ONLY the exact name of the helpdesk in the helpdesk tags.
    Respond in this format:
    <reasoning>Why you chose that helpdesk</reasoning>
    <helpdesk>NAME_OF_HELPDESK</helpdesk>

    """

    prompt += conversation

    bedrock_session = boto3.session.Session()
    bedrock = bedrock_session.client("bedrock-runtime", region_name=config['region'])

    body = json.dumps({
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": prompt}],
    "anthropic_version": "bedrock-2023-05-31"
    })

    response = bedrock.invoke_model(body=body, modelId=config['model']['redirect'])

    response_body = json.loads(response.get("body").read())
    return response_body.get("content")[0].get("text")

def flagRaiser(user_query, lastMessage, st): 

    prompt = f"""
    Evaluate the content of the provided messages carefully. 
    Based on the following criteria, respond only with the exact matching string (without any additional text or explanation):
    - If the *User's message* explicitly requests to speak to a human, respond with: "Human request".
    - If the *User's message* or *System's message* suggests that the bot cannot assist the user any further, respond with: "Redirect request".
    - If the *User's message* or *System's message* EXPLICITLY indicates that the entire user's issue has been resolved, and NOT that a single step has been resolved, respond with: "Issue Resolved". In order for this to be "Issue Resolved" the system must not have any more steps to talk about.
    - If neither message matches any of the above conditions, respond with: "NA".
    - If the *User's message* or *System's message* contains profanity or personally identifiable information, still use the above criteria to respond with the appropriate string, but separated by a ;, respond with "innapropriate" (example: "NA;innapropriate").

    User's message to evaluate: {user_query}
    System's message to evaluate: {lastMessage}
    """

    bedrock_session = boto3.session.Session()
    bedrock = bedrock_session.client("bedrock-runtime", region_name=config['region'])

    body = json.dumps({
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": prompt}],
    "anthropic_version": "bedrock-2023-05-31"
    })

    tokens = len(tokenizer.encode(body))
    st.session_state.inputFlagTokens += tokens

    response = bedrock.invoke_model(body=body, modelId=config['model']['flag_raiser'])

    response_body = json.loads(response.get("body").read())
    text = response_body.get("content")[0].get("text")
    tokens = len(tokenizer.encode(text))
    st.session_state.outputFlagTokens += tokens
    st.session_state.flagRaiserCost += (
        st.session_state.inputFlagTokens * SONNET_INPUT_COST_PER_TOKEN + 
        st.session_state.outputFlagTokens * SONNET_OUTPUT_COST_PER_TOKEN
    )
    return text

def profanity_check(text):
    bedrock_session = boto3.session.Session()
    client = bedrock_session.client("bedrock-runtime", region_name=config['region'])

    response = client.apply_guardrail(
        guardrailIdentifier=config['guardrail_id'],
        guardrailVersion=config['guardrail_version'],
        source='INPUT',
        content=[
            {
                'text': {
                    'text': text,
                    'qualifiers': [
                        'guard_content',
                    ]
                }
            },
        ]
    )
    action = response.get('action', '')

    return True if action == "GUARDRAIL_INTERVENED" else False


def invokeModel(prompt, st, extraInstructions=""):

    bedrock_session = boto3.session.Session()
    client = bedrock_session.client("bedrock-runtime", region_name=config['region'])
    model_id = config['model']['chat']

    chatHistory = ""
    for m in st.session_state.messages:
        chatHistory += f"{m['role']} : {m['content']}\n"

    adminContent = [{"type": "text", "text": f"{extraInstructions} \n Chat History: {chatHistory}"}]
    userContent = [{"type": "text", "text": f"{prompt}"}]

    native_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "temperature": 0.7,
        "amazon-bedrock-guardrailConfig": {
            "streamProcessingMode": "ASYNCHRONOUS"
        },
        "messages": [
            {
                "role": "user",
                "content": f"Administrator: {adminContent} User: {userContent} Assistant:"
            },
        ],
    }
    
    request = json.dumps(native_request)
    tokens = len(tokenizer.encode(request))
    st.session_state.input_tokens += tokens

    streaming_response = client.invoke_model_with_response_stream(
        modelId=model_id, 
        body=request,
        guardrailIdentifier=config['guardrail_id'],
        guardrailVersion=config['guardrail_version']
    )

    # Generator function to yield text chunks for `st.write_stream`
    def generate_response():
        full_response = ""
        show_text = True
        for event in streaming_response["body"]:
            chunk = json.loads(event["chunk"]["bytes"].decode('utf-8'))
            if chunk["type"] == "content_block_delta":
                text_delta = chunk["delta"].get("text", "")
                full_response += text_delta
                    
                if show_text:
                    yield text_delta  # Yielding for streaming


        chat = {"role": "assistant", "content": full_response}
        st.session_state.messages.append(chat)
        log_chat(chat)


        if "Identified the issue -" in full_response:
            st.session_state.issueFound = True
            st.session_state.first_interaction = True
            st.session_state.chooseStepStyleMode = True
            findRelevantIssue(prompt)

        if "Got it - multiple steps." in full_response:
            st.session_state.stepStyle = 'm'
            st.session_state.chooseStepStyleMode = False
            setDiagnoseMode()

        if "Got it - comprehensive guide." in full_response:
            st.session_state.stepStyle = 'g'
            st.session_state.chooseStepStyleMode = False
            setDiagnoseMode()

    with st.chat_message("assistant", avatar="usda-social-profile-round.png"):
        st.write_stream(generate_response())
    
    fullResponse = st.session_state.messages[-1]['content']

    if st.session_state.diagnoseMode:
        flag = flagRaiser(prompt, fullResponse, st)

        print(f"\n{flag=}")

        if "innapropriate" in flag:
            st.toast('Please refrain from profanity usage', icon="👮")

        if "Issue Resolved" in flag:
            st.session_state.diagnoseMode = False
            st.session_state.issueResolved = True
            st.session_state.first_interaction = False
            st.rerun()
        
        if "Human request" in flag:
            st.session_state.redirectRequests += 1
            if st.session_state.redirectRequests >= st.session_state.humanRedirectThreshold:
                st.session_state.diagnoseMode = False
                st.session_state.humanRedirect = True
                st.session_state.first_interaction = False
            st.rerun()

        if "Redirect request" in flag:
            st.session_state.diagnoseMode = False
            st.session_state.humanRedirect = True
            st.session_state.first_interaction = False
            st.rerun()

    
    tokens = len(tokenizer.encode(fullResponse))
    st.session_state.output_tokens += tokens

    st.session_state.total_cost += (
        st.session_state.input_tokens * SONNET_INPUT_COST_PER_TOKEN + 
        st.session_state.output_tokens * SONNET_OUTPUT_COST_PER_TOKEN
    )

def generate_tags(document_text):
    role_to_assume = 'aws_account_arn'    

    prompt = f"""
    From the contents of this conversation,
    generate a list of possible helpdesk one-word 'categories.' 
    Examples include but are not limited to "Printer", "Wi-Fi", "USDA System", "Work Laptop", "Website".
    Return nothing but a valid list object containing of categorical tags
    in the following format: ['category 1','category 2']
    Here is the conversation: {document_text}
    """
    bedrock_session = boto3.session.Session()
    bedrock = bedrock_session.client("bedrock-runtime", region_name=config['region'])

    body = json.dumps({
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": prompt}],
    "anthropic_version": "bedrock-2023-05-31"
    })

    tokens = len(tokenizer.encode(body))
    st.session_state.inputSummaryTokens += tokens

    response = bedrock.invoke_model(body=body, modelId=config['model']['category_generation'])

    response_body = json.loads(response.get("body").read())
    text = response_body.get("content")[0].get("text")
    tokens = len(tokenizer.encode(text))
    st.session_state.outputSummaryTokens += tokens
    st.session_state.summaryCost += (
        st.session_state.inputSummaryTokens * HAIKU_INPUT_COST_PER_TOKEN + 
        st.session_state.outputSummaryTokens * HAIKU_OUTPUT_COST_PER_TOKEN
    )
    return text