import streamlit as st
import boto3
import json
import base64
import re
from os_query import getSimilarDocs
from streamlit_star_rating import st_star_rating
from injectImage import replace_uuid_with_base64, decode_base64_to_image
from search_utils import embed
import tiktoken
from summary_utils import generate_summary

tokenizer = tiktoken.get_encoding("o200k_base")

SONNET_INPUT_COST_PER_TOKEN = 0.000003
SONNET_OUTPUT_COST_PER_TOKEN = 0.000015

def main():

    st.title("USDA Help Desk Chatbot")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "issueFound" not in st.session_state:
        st.session_state.issueFound = False

    if "issueResolved" not in st.session_state:
        st.session_state.issueResolved = False

    if "first_interaction" not in st.session_state:
        st.session_state.first_interaction = True

        with open('startingPrompt.txt', 'r') as startingPromptFile:
            st.session_state.startingPrompt = startingPromptFile.read()

        with open('issueSolvePrompt.txt', 'r') as issueSolvePromptFile:
            st.session_state.issueSolvePrompt = issueSolvePromptFile.read()

    if "no_similar_issues" not in st.session_state:
        st.session_state.no_similar_issues = False

    if "selectedIssue" not in st.session_state:
        st.session_state.selectedIssue = ""

    if "diagnoseMode" not in st.session_state:
        st.session_state.diagnoseMode = False

    if "input_tokens" not in st.session_state:
        st.session_state.input_tokens = 0

    if "output_tokens" not in st.session_state:
        st.session_state.output_tokens = 0

    if "total_cost" not in st.session_state:
        st.session_state.total_cost = 0

    


    for message in st.session_state.messages:
        if message['role'] == "Administrator":
            if ('PIL' in f"{type(message['content'])}"):
                st.image(message['content'])
        else:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])



    if st.session_state.first_interaction:
        st.session_state.first_interaction = False 
        simulated_user_input = "Hi"
        if st.session_state.diagnoseMode:
            simulated_user_input = "Let's get started."
            passage = json.loads(st.session_state.selectedIssue['_source']['passage'])
            # print(f"\n\n{f"{st.session_state.issueSolvePrompt} [{passage}]"}\n\n\n")
            invokeModel(simulated_user_input, f"{st.session_state.issueSolvePrompt} [{passage}]")
            st.session_state.messages.append({"role": "Administrator", "content": f"{st.session_state.issueSolvePrompt} [{passage}]"})

        else:
            invokeModel(simulated_user_input, st.session_state.startingPrompt)
            st.session_state.messages.append({"role": "Administrator", "content": st.session_state.startingPrompt})



    if st.session_state.diagnoseMode:
        if prompt := st.chat_input('How can I help you today?'):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            passage = json.loads(st.session_state.selectedIssue['_source']['passage'])
            # print(f"\n\n{f"{st.session_state.issueSolvePrompt} [{passage}]"}\n\n\n")

            invokeModel(prompt, f"[{passage}]")

    elif st.session_state.issueResolved:
        stars = st_star_rating(label = "Please rate your experience", maxValue = 5, defaultValue = 3, key = "rating", emoticons = True)
        feedback = st.text_input("Give me some quick feedback!")
        if st.button("Complete"):
            summary = generate_summary(f"{str(st.session_state.messages)} *** The user also gave this feedback {feedback} and this star rating {stars} ***")
            st.markdown(f"To the helpdesk:\n{summary} \n\nInput Tokens: {st.session_state.input_tokens}\n\nOutput Tokens: {st.session_state.output_tokens}\n\nTotal Cost: ${st.session_state.total_cost}")


    elif st.session_state.no_similar_issues:
        st.write(f"""There were no similar help desk issue
             documents found. Consider seeking further assistance from a help desk associate.""")
    else:
        if prompt := st.chat_input('How can I help you today?'):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            invokeModel(prompt)


def invokeModel(prompt, extraInstructions=""):
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
    client = bedrock_session.client("bedrock-runtime", region_name="your_aws_region")
    model_id = "anthropic.claude-3-5-sonnet-20240620-v1:0"

    chatHistory = ""
    for m in st.session_state.messages:
        chatHistory += f"{m['role']} : {m['content']}\n"

    adminContent = [{"type": "text", "text": f"{extraInstructions} \n Chat History: {chatHistory}"}]
    userContent = [{"type": "text", "text": f"{prompt}"}]

    native_request = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1000,
        "temperature": 0.7,
        "messages": [
            {
                "role": "user",
                "content": f"Administrator: {adminContent} User: {userContent} Assistant:"
            }
        ],
    }
    
    request = json.dumps(native_request)
    tokens = len(tokenizer.encode(request))
    st.session_state.input_tokens += tokens

    streaming_response = client.invoke_model_with_response_stream(
        modelId=model_id, body=request
    )

    # Generator function to yield text chunks for `st.write_stream`
    def generate_response():
        full_response = ""
        show_text = True
        for event in streaming_response["body"]:
            chunk = json.loads(event["chunk"]["bytes"].decode('utf-8'))
            if chunk["type"] == "content_block_delta":
                text_delta = chunk["delta"].get("text", "")
                print(text_delta)
                full_response += text_delta
                uuid = re.search(r"\{([a-zA-Z0-9]{8})\}", full_response)
                if "(" in text_delta:
                    text_delta = text_delta.split("(")[0]
                    yield text_delta
                    show_text = False
                if ")" in text_delta:
                    show_text = True
                    text_delta = text_delta.split(")")[1]
                if uuid:
                    full_response = full_response.replace(uuid.group(1), "")
                    
                if show_text:
                    yield text_delta  # Yielding for streaming

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        if "Identified the issue -" in full_response:
            st.session_state.issueFound = True
            findRelevantIssue(prompt)
        

    with st.chat_message("assistant"):
        st.write_stream(generate_response())
    
    fullResponse = st.session_state.messages[-1]['content']

    if "Issue Resolved" in fullResponse:
        st.session_state.diagnoseMode = False
        st.session_state.issueResolved = True
        st.session_state.first_interaction = False
        st.rerun()
    
    tokens = len(tokenizer.encode(fullResponse))
    st.session_state.output_tokens += tokens

    st.session_state.total_cost += (
        st.session_state.input_tokens * SONNET_INPUT_COST_PER_TOKEN + 
        st.session_state.output_tokens * SONNET_OUTPUT_COST_PER_TOKEN
    )

    if st.session_state.diagnoseMode:
        image_dict = st.session_state.selectedIssue["_source"]["images"]
        fullResponse = replace_uuid_with_base64(fullResponse, image_dict)
        images = re.findall(r"<image_base64>(.*?)</image_base64>", fullResponse)
        
        for image_base64 in images:
            image = decode_base64_to_image(image_base64)
            st.session_state.messages.append({"role": "Administrator", "content": image})
            st.image(image)




def findRelevantIssue(prompt):
    embedding = embed(prompt)
    selectedDocs = getSimilarDocs(prompt,embedding)
    if len(selectedDocs) == 0:
        noSimilarIssues()
        return
    else:    
        filteredIssues = filter_docs(selectedDocs)
    if len(filteredIssues) == 0:
        noSimilarIssues()
        return
    elif len(filteredIssues) == 1:
        diagnoseIssue(filteredIssues[0])
        return
    else:
        st.write("Select the issue that most closely matches your query.")
        for idx, result in enumerate(filteredIssues):
            st.button(
                f"Title: {result['_source']['section_title']}, Score: {result['_score']}",
                key=f"issue_button_{idx}",
                on_click=diagnoseIssue,
                args=(result,)
            )

def filter_docs(results, min_score=0.7, relative_threshold=0.1):
    # Filter out documents below the absolute score threshold
    filtered_results = [result for result in results if result['_score'] >= min_score]

    # If no documents pass the absolute score threshold, return an empty list
    if not filtered_results:
        return []

    # Sort results by score in descending order (already sorted in your case, but for safety)
    filtered_results.sort(key=lambda x: x['_score'], reverse=True)

    # Apply relative threshold filtering
    final_results = [filtered_results[0]]  # Start with the highest score document
    for i in range(1, len(filtered_results)):
        current_score = filtered_results[i]['_score']
        previous_score = final_results[-1]['_score']

        # Keep the document if the score drop is within the relative threshold
        if previous_score - current_score <= relative_threshold:
            final_results.append(filtered_results[i])
        else:
            break  # Stop when the score drop exceeds the threshold

    return final_results


def noSimilarIssues():
    st.session_state.no_similar_issues = True
    st.rerun()


def diagnoseIssue(issue):
    st.session_state.diagnoseMode = True
    st.session_state.first_interaction = True 
    st.session_state.selectedIssue = issue
    st.rerun()


if __name__ == "__main__":
    main()