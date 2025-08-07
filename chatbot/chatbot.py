import ast
import json
import re
from datetime import datetime

import boto3
import streamlit as st
import tiktoken
import yaml
from llm_utils import *
from logging_config import log_chat, save_results
from os_query import getSimilarDocs
from search_utils import embed
from streamlit_star_rating import st_star_rating

# Load Config
with open("../config.yaml", "r") as file:
    config = yaml.safe_load(file)


tokenizer = tiktoken.get_encoding("o200k_base")

SONNET_INPUT_COST_PER_TOKEN = 0.000003
SONNET_OUTPUT_COST_PER_TOKEN = 0.000015
HAIKU_INPUT_COST_PER_TOKEN = 0.00000025
HAIKU_OUTPUT_COST_PER_TOKEN = 0.00000125

helpdesk_list = [
    "IT Helpdesk",
    "Farm Service Agency Helpdesk",
    "Forest Service Helpdesk",
]

helpdesk_info = [
    "IT Helpdesk - Helpdesk dealing with technological issues",
    "Farm Service Agency Helpdesk - The Farm Service Agency implements agricultural policy, administers credit and loan programs, and manages conservation, commodity, disaster and farm marketing programs through a national network of offices.",
    "Forest Service Helpdesk - FS sustains the health, diversity and productivity of the Nation's forests and grasslands to meet the needs of present and future generations.",
]


def sessionStateInit():
    if "currentHelpdesk" not in st.session_state:
        st.session_state.currentHelpdesk = "IT Helpdesk"

    if "warningThreshold" not in st.session_state:
        st.session_state.warningThreshold = 0.5

    if "terminateThreshold" not in st.session_state:
        st.session_state.terminateThreshold = 1

    if "humanRedirectThreshold" not in st.session_state:
        st.session_state.humanRedirectThreshold = 2

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "user_question" not in st.session_state:
        st.session_state.user_question = []

    if "issueFound" not in st.session_state:
        st.session_state.issueFound = False

    if "chooseStepStyleMode" not in st.session_state:
        st.session_state.chooseStepStyleMode = False

    if "issueResolved" not in st.session_state:
        st.session_state.issueResolved = False

    if "humanRedirect" not in st.session_state:
        st.session_state.humanRedirect = False

    if "first_interaction" not in st.session_state:
        st.session_state.first_interaction = True

        # with open('startingPrompt.txt', 'r') as startingPromptFile:
        #     st.session_state.startingPrompt = startingPromptFile.read()
        st.session_state.startingPrompt = f"""
        You are a friendly and helpful help desk assistant for the USDA.
        You are to assist with any technical problem a user may have.
        Goal:
        Find out what issue the user is currently facing.
        Instructions:
        Respond in a friendly and concise manner to encourage the user to share what they need help with.
        After the User Mentions a Valid Issue:
        Respond with the following message verbatim, do not say anythin else, inserting the user's issue where indicated:
        "Identified the issue - let's solve {{the user's issue}} right away."
        If a user ask a question unrelated to an issue or if the user
        asks a question that one of the relevant departments can't answer,
        respond by prompting the user to ask another question. Here are the relevant departments: {helpdesk_list}
        Do not ask for additional details after the user mentions a valid issue.
        Accept any expression of a valid problem as sufficient to proceed.
        Maintain a friendly and professional tone throughout the interaction."""

        # with open('issueSolvePrompt.txt', 'r') as issueSolvePromptFile:
        #     st.session_state.issueSolvePrompt = issueSolvePromptFile.read()
        st.session_state.issueSolvePrompt = f"""
        You are a friendly and helpful {st.session_state.currentHelpdesk} assistant for the USDA.
        If the document is not relevant to the user question {st.session_state.user_question} use your general knowledge to provide an answer.
        Goal: Assist the user in resolving their issue by guiding them through the instructions outlined in the provided help desk issue document.
        Instructions:
        Walk the user through the issue they are having one step at a time.
        If the user wants to speak to a human, push back a little bit and insist that you can suffice.
        Only list step at a time, and wait to move onto the next one until the user indicates they have finished it.
        Do not tell them to contact the help desk unless you cannot help the user figure out the issue."""

        st.session_state.issueSolvePromptGuide = f"""
        You are a friendly and helpful {st.session_state.currentHelpdesk} assistant for the USDA.
        If the document is not relevant to the user question {st.session_state.user_question} use your general knowledge to provide an answer.
        Goal: Assist the user in resolving their issue by guiding them through the instructions outlined in the provided help desk issue document.
        Instructions:
        Walk the user through the issue they are having by providing a guide of what to do that contains step by step instructions.
        If the user wants to speak to a human, push back a little bit and insist that you can suffice.
        Do not tell them to contact the help desk unless you cannot help the user figure out the issue."""

        st.session_state.chooseStepStylePrompt = f"""
        You are a friendly and helpful {st.session_state.currentHelpdesk} assistant for the USDA.
        Ask the user if they would like to receive the steps for solving their issue
        in a guide containing all steps or separate individuall steps.
        If the user indicates they want multiple separate steps, respond with "Got it - multiple steps." verbatim.
        If the user indicates they want a guide of steps, respond with "Got it - comprehensive guide." verbatim.
        If the user is off topic or isn't choosing between the two previously mentioned step styles, urge them to choose between those two.
        """

    if "feedback" not in st.session_state:
        st.session_state.feedback = ""

    if "stars" not in st.session_state:
        st.session_state.stars = 0

    if "start_time" not in st.session_state:
        st.session_state.start_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    if "no_similar_issues" not in st.session_state:
        st.session_state.no_similar_issues = False

    if "selectedIssue" not in st.session_state:
        st.session_state.selectedIssue = {}

    if "diagnoseMode" not in st.session_state:
        st.session_state.diagnoseMode = False

    if "input_tokens" not in st.session_state:
        st.session_state.input_tokens = 0

    if "output_tokens" not in st.session_state:
        st.session_state.output_tokens = 0

    if "total_cost" not in st.session_state:
        st.session_state.total_cost = 0

    if "inputSummaryTokens" not in st.session_state:
        st.session_state.inputSummaryTokens = 0

    if "outputSummaryTokens" not in st.session_state:
        st.session_state.outputSummaryTokens = 0

    if "summaryCost" not in st.session_state:
        st.session_state.summaryCost = 0
        # for now summary cost accounts for the (marginal) cost of generating tags
        # i was just too lazy to make tag generation cost its own thing

    if "inputFlagTokens" not in st.session_state:
        st.session_state.inputFlagTokens = 0

    if "outputFlagTokens" not in st.session_state:
        st.session_state.outputFlagTokens = 0

    if "flagRaiserCost" not in st.session_state:
        st.session_state.flagRaiserCost = 0

    if "redirectRequests" not in st.session_state:
        st.session_state.redirectRequests = 0

    if "tooHighCost" not in st.session_state:
        st.session_state.tooHighCost = False

    if "costWarningHappened" not in st.session_state:
        st.session_state.costWarningHappened = False

    if "pills" not in st.session_state:
        st.session_state.pills = []

    if "stepStyle" not in st.session_state:
        st.session_state.stepStyle = ""


def reset_session():
    keys_to_delete = list(st.session_state.keys())
    for key in keys_to_delete:
        del st.session_state[key]
    st.rerun()


def get_feedback():
    if st.button("New Chat"):
        reset_session()
    st.session_state.stars = st_star_rating(
        label="Please rate your experience",
        maxValue=5,
        defaultValue=3,
        key="rating",
        emoticons=False,
    )
    st.session_state.feedback = st.text_input("Give me some quick feedback!")

    convo = ""
    for message in st.session_state.messages:
        if message["role"] != "Administrator":
            convo += f"{message} \n"
    if len(st.session_state.pills) == 0:
        st.session_state.pills = generate_tags(st, f"{str(convo)}")
    actualTagList = ast.literal_eval(st.session_state.pills)

    selected_category = st.pills(
        "Select one or more categories that best match your issue:",
        options=actualTagList,
        selection_mode="multi",
    )

    if st.button("Complete"):
        if st.session_state.stars == 5:
            st.balloons()
        st.write(f"""Selected Category: {selected_category}   \nInput Tokens: {st.session_state.input_tokens}  \nOutput Tokens:
                    {st.session_state.output_tokens}  \nConversation Total Cost: \${round(st.session_state.total_cost, 4)}  \nFlag Check Input Tokens:
                    {st.session_state.inputFlagTokens}  \nFlag Check Output Tokens: {st.session_state.outputFlagTokens}  \nFlag Check Total Cost: \${round(st.session_state.flagRaiserCost, 4)}
                    \nTotal Cost: \${round(st.session_state.total_cost + st.session_state.flagRaiserCost, 4)}""")
        with st.spinner("Generating Summary..."):
            summary = generate_summary(
                st,
                f"{str(convo)} *** The user also gave this feedback {st.session_state.feedback} and this star rating {st.session_state.stars} ***",
            )
            st.write(f"""To the helpdesk:  \n{summary}""")
        save_results(st)


def filter_and_write_message(prompt):
    if profanity_check(prompt):
        prompt = "The user has entered profanity."
    chat = {"role": "user", "content": prompt}
    st.session_state.messages.append(chat)
    log_chat(chat)

    with st.chat_message("user"):
        st.markdown(prompt)


def filter_docs(results, min_score=0.7, relative_threshold=0.1):
    # Filter out documents below the absolute score threshold
    filtered_results = [
        result for result in results if result["_score"] >= min_score
    ]

    # If no documents pass the absolute score threshold, return an empty list
    if not filtered_results:
        return []

    # Sort results by score in descending order (already sorted in your case, but for safety)
    filtered_results.sort(key=lambda x: x["_score"], reverse=True)

    # Apply relative threshold filtering
    final_results = [
        filtered_results[0]
    ]  # Start with the highest score document
    for i in range(1, len(filtered_results)):
        current_score = filtered_results[i]["_score"]
        previous_score = final_results[-1]["_score"]

        # Keep the document if the score drop is within the relative threshold
        if previous_score - current_score <= relative_threshold:
            final_results.append(filtered_results[i])
        else:
            break  # Stop when the score drop exceeds the threshold

    return final_results


def setDiagnoseMode():
    st.session_state.diagnoseMode = True
    st.session_state.first_interaction = True
    st.rerun()


def noSimilarIssues():
    st.session_state.no_similar_issues = True
    st.rerun()


def diagnoseIssue(issue):
    st.session_state.selectedIssue = issue


def diagnoseIssueRerun(issue):
    st.session_state.selectedIssue = issue
    st.rerun()


def findRelevantIssue(prompt):
    embedding = embed(prompt)
    selectedDocs = getSimilarDocs(prompt, embedding)
    if len(selectedDocs) == 0:
        noSimilarIssues()
        return
    else:
        filteredIssues = filter_docs(selectedDocs)
    if len(filteredIssues) == 0:
        noSimilarIssues()
        return
    elif len(filteredIssues) == 1:
        diagnoseIssueRerun(filteredIssues[0])
        return
    else:
        st.write("Select the issue that most closely matches your query.")
        for idx, result in enumerate(filteredIssues):
            st.button(
                f"Title: {result['_source']['guide_title']}, Score: {result['_score']}",
                key=f"issue_button_{idx}",
                on_click=diagnoseIssue,
                args=(result,),
            )


def invokeModel(prompt, st, extraInstructions=""):
    bedrock_session = boto3.session.Session()
    client = bedrock_session.client(
        "bedrock-runtime", region_name=config["region"]
    )
    model_id = config["model"]["chat"]

    chatHistory = ""
    for m in st.session_state.messages:
        chatHistory += f"{m['role']} : {m['content']}\n"

    adminContent = [
        {
            "type": "text",
            "text": f"{extraInstructions} \n Chat History: {chatHistory}",
        }
    ]
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
                "content": f"Administrator: {adminContent} User: {userContent} Assistant:",
            },
        ],
    }

    request = json.dumps(native_request)
    tokens = len(tokenizer.encode(request))
    st.session_state.input_tokens += tokens

    streaming_response = client.invoke_model_with_response_stream(
        modelId=model_id,
        body=request,
        guardrailIdentifier=config["guardrail_id"],
        guardrailVersion=config["guardrail_version"],
    )

    # Generator function to yield text chunks for `st.write_stream`
    def generate_response():
        full_response = ""
        show_text = True
        for event in streaming_response["body"]:
            chunk = json.loads(event["chunk"]["bytes"].decode("utf-8"))
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
            st.session_state.stepStyle = "m"
            st.session_state.chooseStepStyleMode = False
            setDiagnoseMode()

        if "Got it - comprehensive guide." in full_response:
            st.session_state.stepStyle = "g"
            st.session_state.chooseStepStyleMode = False
            setDiagnoseMode()

    with st.chat_message("assistant", avatar="usda-social-profile-round.png"):
        st.write_stream(generate_response())

    fullResponse = st.session_state.messages[-1]["content"]
    s = True
    if s:  # originally was if st.session_state.diagnoseMode:
        flag = flagRaiser(prompt, fullResponse, st)
        print(f"\n{flag=}")

        if "innapropriate" in flag:
            st.toast("Please refrain from profanity usage", icon="👮")

        if "Issue Resolved" in flag:
            st.session_state.diagnoseMode = False
            st.session_state.issueResolved = True
            st.session_state.first_interaction = False
            st.rerun()

        if "Human request" in flag:
            st.session_state.redirectRequests += 1
            if (
                st.session_state.redirectRequests
                >= st.session_state.humanRedirectThreshold
            ):
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
        st.session_state.input_tokens * SONNET_INPUT_COST_PER_TOKEN
        + st.session_state.output_tokens * SONNET_OUTPUT_COST_PER_TOKEN
    )


def main():
    # hide top bar
    hide_decoration_bar_style = (
        """ <style> header {visibility: hidden;} </style> """
    )
    st.markdown(hide_decoration_bar_style, unsafe_allow_html=True)
    st.markdown(
        """
    <style>
    textarea[data-testid="stChatInputTextArea"]::placeholder {
        color: #c0b7b6 !important; /* Replace with your desired color */
        opacity: 1 !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title("USDA Help Desk Chatbot")
    sessionStateInit()
    if st.session_state.stepStyle != "":
        if st.session_state.stepStyle == "g":
            st.session_state.issueSolvePrompt = (
                st.session_state.issueSolvePromptGuide
            )

    # True means the service is working
    services_status = {
        "Tier One Helpdesk": True,
        "Tier Two Helpdesk": False,
    }

    def status_indicator(is_up):
        if is_up:
            return ":large_green_circle:"
        else:
            return ":red_circle:"

    with st.sidebar:
        st.write("   \n")
        for service, status in services_status.items():
            indicator = status_indicator(status)
            status_text = "In Service" if status else "Out of Service"
            st.markdown(f"{indicator} **{service}** - {status_text}")

        st.write("   \n")
        st.write("   \n")

        st.write(
            f"Total Conversation Cost: {round(st.session_state.total_cost, 4)}"
        )
        st.write("   \n")
        st.write("   \n")

        st.session_state.warningThreshold = st.slider(
            label="Set the cost warning threshold",
            min_value=0.1,
            max_value=100.0,
            step=0.1,
            value=10.0,
        )
        st.session_state.warningThreshold /= 100
        st.write(
            f"Current Warning Threshold: {round(st.session_state.warningThreshold, 4)}"
        )
        st.write("   \n")

        st.session_state.terminateThreshold = st.slider(
            label="Set the cost terminate threshold",
            min_value=0.2,
            max_value=150.0,
            step=0.1,
            value=45.0,
        )
        st.session_state.terminateThreshold /= 100
        st.write(
            f"Current Terminate Threshold: {round(st.session_state.terminateThreshold, 4)}"
        )
        st.write("   \n")

        st.session_state.humanRedirectThreshold = st.slider(
            label="Set the human redirect threshold",
            min_value=1,
            max_value=5,
            step=1,
            value=2,
        )
        if st.button("Reset App"):
            reset_session()

    for message in st.session_state.messages:
        if message["role"] == "Administrator":
            pass
        elif message["role"] == "user":
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        else:
            with st.chat_message(
                message["role"], avatar="usda-social-profile-round.png"
            ):
                st.markdown(message["content"])

    if (
        (
            st.session_state.total_cost
            + st.session_state.summaryCost
            + st.session_state.flagRaiserCost
        )
        >= st.session_state.warningThreshold
    ) and not (st.session_state.costWarningHappened):
        st.toast(
            "This conversation is starting to take a long time. Consider speaking to a help desk associate.",
            icon="⚠️",
        )
        st.session_state.costWarningHappened = True

    if (
        (
            st.session_state.total_cost
            + st.session_state.summaryCost
            + st.session_state.flagRaiserCost
        )
        >= st.session_state.terminateThreshold
    ) and not (st.session_state.humanRedirect):
        st.session_state.tooHighCost = True
        st.session_state.diagnoseMode = False
        st.session_state.humanRedirect = True
        st.session_state.first_interaction = False
        st.rerun()

    if st.session_state.first_interaction:
        st.session_state.first_interaction = False
        simulated_user_input = "Hi"
        if st.session_state.diagnoseMode:
            simulated_user_input = "Let's get started."
            if st.session_state.selectedIssue != {}:
                passage = st.session_state.selectedIssue["_source"]["passage"]
                invokeModel(
                    simulated_user_input,
                    st,
                    f"{st.session_state.issueSolvePrompt} [{passage}]",
                )
            else:
                passage = "No Issue selected. Try re-entering the prompt and selecting an issue."
                st.write(passage)
                st.session_state.diagnoseMode = False
                st.session_state.first_interaction = True

            st.session_state.messages.append(
                {"role": "Administrator", "content": passage}
            )

        elif st.session_state.chooseStepStyleMode:
            st.session_state.user_question = st.session_state.messages
            simulated_user_input = "Ok"
            invokeModel(
                simulated_user_input, st, st.session_state.chooseStepStylePrompt
            )
            st.session_state.messages.append(
                {
                    "role": "Administrator",
                    "content": st.session_state.chooseStepStylePrompt,
                }
            )
        else:
            invokeModel(
                simulated_user_input, st, st.session_state.startingPrompt
            )
            st.session_state.messages.append(
                {
                    "role": "Administrator",
                    "content": st.session_state.startingPrompt,
                }
            )

    if st.session_state.chooseStepStyleMode:
        if prompt := st.chat_input("Choose a step style."):
            filter_and_write_message(prompt)
            invokeModel(prompt, st)

    elif st.session_state.diagnoseMode:
        if prompt := st.chat_input(
            f"How can I help you with your issue: {st.session_state.selectedIssue['_source']['guide_title']}?"
        ):
            filter_and_write_message(prompt)
            passage = st.session_state.selectedIssue["_source"]["passage"]
            invokeModel(prompt, st, f"[{passage}]")

    elif st.session_state.issueResolved:
        get_feedback()

    elif st.session_state.humanRedirect:
        if st.session_state.tooHighCost:
            st.error(
                "This conversation is not going anywhere, redirecting you to a help desk associate.",
                icon="🚨",
            )
        get_feedback()

    elif st.session_state.no_similar_issues:
        st.write("""There were no similar help desk issue
            documents found. Redirecting you to a help desk associate.""")
    else:
        if prompt := st.chat_input("How can I help you today?"):
            filter_and_write_message(prompt)

            if not st.session_state.selectedIssue:
                st.session_state.input_tokens += len(tokenizer.encode(prompt))

                redirect_info = decide_redirect(
                    prompt, st.session_state.currentHelpdesk, helpdesk_info
                )
                try:
                    helpdesk = re.search(
                        r"<helpdesk>(.*?)</helpdesk>", redirect_info
                    ).group(1)
                except:
                    print("No redirect found")
                    helpdesk = st.session_state.currentHelpdesk

                st.session_state.output_tokens += len(
                    tokenizer.encode(redirect_info)
                )

                if (
                    helpdesk in helpdesk_list
                    and helpdesk != st.session_state.currentHelpdesk
                ):
                    reasoning = re.search(
                        r"<reasoning>(.*?)</reasoning>", redirect_info
                    ).group(1)

                    with st.chat_message("assistant"):
                        st.write(f"Redirecting to the {helpdesk}. {reasoning}")
                else:
                    invokeModel(prompt, st)


if __name__ == "__main__":
    main()
