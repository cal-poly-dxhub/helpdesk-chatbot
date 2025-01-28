from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
from requests_aws4auth import AWS4Auth
import boto3
import yaml

# Load Config
with open('../config.yaml', 'r') as file:
    config = yaml.safe_load(file)

service = 'aoss'
# replace with your OpenSearch Service domain/Serverless endpoint
domain_endpoint = config["opensearch_endpoint"]

credentials = boto3.Session().get_credentials()
awsauth = AWSV4SignerAuth(credentials, config["region"], service)
os_ = OpenSearch(
    hosts=[{'host': domain_endpoint, 'port': 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    timeout=300,
    # http_compress = True, # enables gzip compression for request bodies
    connection_class=RequestsHttpConnection
)

# Sample Opensearch domain index mapping
mapping = {
    "mappings": {
      "properties": {
        "description": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        },
        "embedding": {
          "type": "knn_vector",
          "dimension": 1024,
          "method": {
            "engine": "nmslib",
            "space_type": "cosinesimil",
            "name": "hnsw",
            "parameters": {}
          }
        },
        "guide_file_name": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        },
        "guide_title": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        },
        "page_number": {
          "type": "long"
        },
        "passage": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        },
        "question_asked": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        },
        "section_title": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        },
        "url": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        }
      }
    }
}

def check_create_index():
    domain_index = config["opensearch_index"] # domain index name

    if not os_.indices.exists(index=domain_index):
        os_.indices.create(index=domain_index, body=mapping)
        # Verify that the index has been created
        if os_.indices.exists(index=domain_index):
            print(f"Index {domain_index} created successfully.")
        else:
            print(f"Failed to create index '{domain_index}'.")
    else:
        print(f'Index {domain_index} already exists!')