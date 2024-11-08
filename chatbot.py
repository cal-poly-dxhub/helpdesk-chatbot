import streamlit as st
import boto3
import json
import base64
import re
from os_query import getSimilarDocs
from injectImage import replace_uuid_with_base64, decode_base64_to_image
from search_utils import embed
from botocore.exceptions import ClientError

def main():

    st.title("USDA Help Desk Chatbot")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "issueFound" not in st.session_state:
        st.session_state.issueFound = False

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
            #st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            passage = json.loads(st.session_state.selectedIssue['_source']['passage'])
            # print(f"\n\n{f"{st.session_state.issueSolvePrompt} [{passage}]"}\n\n\n")

            invokeModel(prompt, f"[{passage}]")

    elif st.session_state.no_similar_issues:
        st.write(f"""There were no similar help desk issue
             documents found. Consider seeking further assistance from a help desk associate.""")
    else:
        if prompt := st.chat_input('How can I help you today?'):
            #st.session_state.messages.append({"role": "user", "content": prompt})
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
    model_id = "anthropic.claude-3-sonnet-20240229-v1:0"

    # Initialize an empty conversation history
    conversation_history = []

    def generate_response(user_input):
        # Append user's input to conversation history
        conversation_history.append({"role": "user", "content": [{"text": user_input}]})
        st.session_state.messages.append({"role": "user", "content": user_input})

        try:
            # Send the conversation history to the model using ConverseStream
            streaming_response = client.converse_stream(
                modelId=model_id,
                messages=conversation_history,
                inferenceConfig={"maxTokens": 512, "temperature": 0.5, "topP": 0.9},
            )

            response_text = ""
            # Yield each chunk of text as it arrives
            for chunk in streaming_response['stream']:
                if 'contentBlockDelta' in chunk:
                    text = chunk['contentBlockDelta']['delta']['text']
                    yield text  # Yield each chunk of text immediately
                    response_text += text

            # Add the model's response to the conversation history
            conversation_history.append({"role": "assistant", "content": [{"text": response_text}]})
            st.session_state.messages.append({"role": "assistant", "content": [{"text": response_text}]})

            return response_text
            # st.session_state.messages.append({"role": "assistant", "content": full_response})
            # if "Identified the issue -" in full_response:
            #     st.session_state.issueFound = True
            #     findRelevantIssue(prompt)

        except (ClientError, Exception) as e:
            print(f"\nERROR: Unable to invoke '{model_id}'. Reason: {e}")


    with st.chat_message("assistant"):
        fullResponse = "".join(st.write_stream(generate_response(prompt)))

    # with st.chat_message("user"):
    #     st.write(full_response)

    print(fullResponse)
    
    if st.session_state.diagnoseMode:
        image_dict = st.session_state.selectedIssue["_source"]["images"]
        fullResponse = replace_uuid_with_base64(fullResponse, image_dict)
        images = re.findall(r"<image_base64>(.*?)</image_base64>", fullResponse)
        
        for image_base64 in images:
            image = decode_base64_to_image(image_base64)
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
