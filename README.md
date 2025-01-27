
# Helpdesk Chatbot Solution

# Collaboration
Thanks for your interest in our solution.  Having specific examples of replication and cloning allows us to continue to grow and scale our work. If you clone or download this repository, kindly shoot us a quick email to let us know you are interested in this work!

[wwps-cic@amazon.com] 

# Disclaimers

**Customers are responsible for making their own independent assessment of the information in this document.**

**This document:**

(a) is for informational purposes only, 

(b) represents current AWS product offerings and practices, which are subject to change without notice, and 

(c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided “as is” without warranties, representations, or conditions of any kind, whether express or implied. The responsibilities and liabilities of AWS to its customers are controlled by AWS agreements, and this document is not part of, nor does it modify, any agreement between AWS and its customers. 

(d) is not to be considered a recommendation or viewpoint of AWS

**Additionally, all prototype code and associated assets should be considered:**

(a) as-is and without warranties

(b) not suitable for production environments

(d) to include shortcuts in order to support rapid prototyping such as, but not limitted to, relaxed authentication and authorization and a lack of strict adherence to security best practices

**All work produced is open source. More information can be found in the GitHub repo.**

## Authors
- Nick Riley - njriley@calpoly.edu
- Noor Dhaliwal - rdhali07@calpoly.edu

## Table of Contents
- [Overview](#chatbot-overview)
- [Backend Services](#backend-services)
- [Additional Resource Links](#additional-resource-links)

## Chatbot Overview
- The [DxHub](https://dxhub.calpoly.edu/challenges/) developed a helpdesk chatbot solution that can answer user questions pulling from their knowledge base articles. The chatbot contains many features: 

- Answer questions grounded in knowledge article truth
- Ability to answer questions outside of the scope of the knowledge base information
- Cost analysis
- Helpdesk summarization
- Handoff with conversation summary to helpdesk representatives
- Ability to adjust threshold for human redirection
- Profanity/PII detection
- Handoff to other chatbots
- Two information styles: a guide or individual steps
- User feedback
- Cost warnings and limits


## Steps to Deploy and Configure the System

### 1. Deploy an EC2 Instance
- Deploy an EC2 instance in your desired region and configure it as required.


### 2. Pull the Git Repository
- Install git using this command 
    ```
    sudo yum install git
    ```

- Clone the necessary repository to the EC2 instance:
    ```bash
    git clone https://github.com/cal-poly-dxhub/helpdesk-chatbot.git
    ```

### 3. Run OpenSearch CDK

- Install Node.js for cdk
    ```
    sudo yum install -y nodejs
    ```
- Configure AWS Credentials
    ```
    aws configure
    ```
- Install cdk
    ```
    sudo npm install -g aws-cdk
    ```

- Install python 3.11
    ```
    sudo yum install python3.11
    ```
    
- Install pip3.11
    ```
    curl -O https://bootstrap.pypa.io/get-pip.py

    python3.11 get-pip.py --user
    ```

- Create and activate venv and install requirements
    ```
    python -m venv env

    source env/bin/activate

    pip3.11 install -r requirements.txt
    ```

- CDK deploy 
    ```
    cdk synth

    cdk bootstrap

    cdk deploy --all
    ```

- Set up and execute the OpenSearch CDK to initialize the environment.

- Create a vector search index with a vector embedding following this format:
    ```
    Vector Field Name:    embedding
    Engine:               nmslib
    Precision:            FP32
    Dimensions:           1024
    Distance Type:        cosine
    M:                    16
    ef_construction:      512
    ef_search:            512
    ```

### 4. Upload Knowledge Articles
- Locate the knowledge articles and upload them to the EC2 instance.
- Update line 9 of `data-ingest/main.py` to point to the exact path of the rawText part of document folder.

- Example path: `/home/ec2-user/Knowledge Articles`

### 5. Create Bedrock Guardrail
- Configure the Bedrock guardrail with the following settings:
  - **Content Filters**: Enable all prompt and response filters at medium strength.
  - **Sensitive Information PII Behavior**: Set to `mask`.
  - **Profanity Filter**: Ensure it is enabled.

### 6. Configure Settings
- Rename `example_config.yaml` to `config.yaml`:
  ```bash
  mv example_config.yaml config.yaml
  ```
- Update the values in `config.yaml` with your specific information.


### 7. Run the streamlit app in the `chatbot` directory with
```
streamlit run chatbot.py
```
By following these steps, you will have a properly deployed and configured system with the desired settings.


## Known Bugs/Concerns
- Quick PoC with no intent verification or error checking
- Hardcoded placeholder text in various components.

## Support
For any queries or issues, please contact:
- Darren Kraker, Sr Solutions Architect - dkraker@amazon.com
- Nick Riley, Software Developer Intern - njriley@calpoly.edu
- Noor Dhaliwal, Software Developer Intern - rdhali07@calpoly.edu