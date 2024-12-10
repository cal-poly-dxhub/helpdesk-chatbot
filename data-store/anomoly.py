import boto3
import time
import datetime
import numpy as np

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('YourDynamoDBTableName')  # Replace with your table name

def get_recent_counts(question_id, time_window_minutes=60):
    """
    Query DynamoDB to count occurrences of a specific question within a time window.
    """
    end_time = datetime.datetime.utcnow()
    start_time = end_time - datetime.timedelta(minutes=time_window_minutes)

    # DynamoDB query for the specific question ID and time window
    response = table.query(
        KeyConditionExpression="question_id = :qid AND timestamp BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ':qid': question_id,
            ':start': start_time.isoformat(),
            ':end': end_time.isoformat(),
        }
    )

    # Return the count of occurrences
    return len(response['Items'])

def detect_anomalies(historical_data, current_count, threshold_factor=3):
    """
    Detect if the current count is anomalous based on historical data.
    """
    mean_lambda = np.mean(historical_data)
    threshold = mean_lambda + threshold_factor * np.sqrt(mean_lambda)
    is_anomalous = current_count > threshold
    return is_anomalous, mean_lambda, threshold

def main():
    # Replace with the actual question ID you're monitoring
    question_id = "example_question_id"
    historical_window_minutes = 1440  # Past 24 hours
    #anomaly_check_interval = 300  # Check every 5 minutes (300 seconds)

    # Fetch historical data for anomaly threshold calculation
    historical_counts = [
        get_recent_counts(question_id, time_window_minutes=60)
        for _ in range(historical_window_minutes // 60)
    ]

    # Get the current count in the last hour
    current_count = get_recent_counts(question_id, time_window_minutes=60)

    # Detect anomalies
    is_anomalous, mean_lambda, threshold = detect_anomalies(historical_counts, current_count)

    # Log results
    if is_anomalous:
        print(f"[ALERT] Anomaly detected for question '{question_id}'!")
        print(f"Current count: {current_count}, Threshold: {threshold}, Mean: {mean_lambda}")
    else:
        print(f"No anomaly detected. Current count: {current_count}, Threshold: {threshold}")


if __name__ == "__main__":
    main()
