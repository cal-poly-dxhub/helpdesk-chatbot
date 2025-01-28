from opensearch_insert import insert_document_os
from aws_utils import *
import os
import time
from os_index_creator import check_create_index

def list_objects_in_folder(folder_path):
    return [os.path.join(folder_path, item) for item in os.listdir(folder_path)]

check_create_index()

folder_path = "/home/ec2-user/Knowledge Articles/docx/rawText"
document_paths = list_objects_in_folder(folder_path)

for file in document_paths:
    file_name = os.path.basename(file)
    with open(file, "r") as file:
        text_content = file.read()
    document = insert_document_os(text_content, file_name)

    # Sleep to not throttle LLM
    time.sleep(5)


