import os
import logging
from datetime import datetime   
import csv

# Set up logging
LOG_FILE = "chat_log.log"

# Create or append to the log file
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w"):
        pass

logging.basicConfig(
    filename=LOG_FILE, 
    level=logging.INFO, 
    format="%(asctime)s - %(message)s", 
    datefmt="%Y-%m-%d %H:%M:%S"
)

logging.getLogger('boto3').setLevel(logging.CRITICAL)
logging.getLogger('boto3').propagate = False
logging.getLogger('botocore').setLevel(logging.CRITICAL)
logging.getLogger('botocore').propagate = False
logging.getLogger('opensearch').setLevel(logging.CRITICAL)
logging.getLogger('opensearch').propagate = False

def log_chat(chat):
    role = chat.get("role", "unknown")
    content = chat.get("content", "")
    logging.info(f"{role}: {content}")


def save_results(st):
    end_reason = "Not resolved"
    if st.session_state.humanRedirect:
        end_reason = "Human Redirect"
    elif st.session_state.issueResolved:
        end_reason = "Issue Resolved"
    elif st.session_state.tooHighCost:
        end_reason = "Max Cost Exceeded"

    end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    step_style = "Complete Guide" if st.session_state.stepStyle == "g" else "Individual Steps"

    headers = ["Categories", "Conversation", "Total Cost", "Input Tokens",
               "Output Tokens", "Feedback", "Stars", "End Reason", "Start Time", "End Time", "Step Style"]

    messages = [entry for entry in st.session_state.messages if entry.get("role") != "Administrator"]

    data = [
        st.session_state.pills,
        str(messages),
        ("$" + str(st.session_state.total_cost)),
        st.session_state.input_tokens,
        st.session_state.output_tokens,
        st.session_state.feedback,
        str(st.session_state.stars),
        end_reason,
        str(st.session_state.start_time),
        str(end_time),
        step_style
    ]

    # Output file
    output_file = "saved_chats.csv"

    # Check if the file exists
    file_exists = os.path.exists(output_file)

    # Open the file in append mode
    with open(output_file, mode="a", newline="") as file:
        writer = csv.writer(file)
        # If file does not exist, write the headers first
        if not file_exists:
            writer.writerow(headers)
        # Append the data
        writer.writerow(data)

    print(f"Data saved to CSV file at: {output_file}")
