import boto3
from utils import ask_yes_no

elbv2_client = boto3.client('elbv2')
ec2_client = boto3.client('ec2')

def create_load_balancer(lb_name, subnets, security_groups):
    """Create a new Application Load Balancer."""
    # Check if the load balancer already exists
    existing_lbs = elbv2_client.describe_load_balancers()['LoadBalancers']
    for lb in existing_lbs:
        if lb['LoadBalancerName'] == lb_name:
            lb_arn = lb['LoadBalancerArn']
            print(f"Load Balancer already exists: {lb_arn}")
            return lb_arn

    # Create a new load balancer if it doesn't exist
    response = elbv2_client.create_load_balancer(
        Name=lb_name,
        Subnets=subnets,
        SecurityGroups=security_groups,
        Scheme='internet-facing',
        Type='application',
        IpAddressType='ipv4'
    )
    lb_arn = response['LoadBalancers'][0]['LoadBalancerArn']
    print(f"Created Load Balancer: {lb_arn}")
    return lb_arn

def create_target_group(vpc_id, tg_name):
    """
    Create a Target Group if it doesn't exist or offer to register instances if it does.
    """

    # Check if the target group already exists
    existing_target_groups = elbv2_client.describe_target_groups()['TargetGroups']
    for tg in existing_target_groups:
        if tg['VpcId'] == vpc_id and tg['TargetGroupName'] == tg_name:
            print(f"Target Group {tg_name} already exists: {tg['TargetGroupArn']}")

            # Offer to register instances to the existing target group
            if ask_yes_no("Do you want to register instances to this Target Group?"):
                register_instances_to_target_group(tg['TargetGroupArn'])

            return tg['TargetGroupArn']

    # Create the target group if it doesn't exist
    response = elbv2_client.create_target_group(
        Name=tg_name,
        Protocol='HTTP',
        Port=8501, 
        VpcId=vpc_id,
        TargetType='instance'  # Assuming instance-based target group
    )
    tg_arn = response['TargetGroups'][0]['TargetGroupArn']
    print(f"Created Target Group: {tg_arn}")

    # Offer to register instances to the new target group
    if ask_yes_no("Do you want to register instances to this Target Group?"):
        register_instances_to_target_group(tg_arn)

    return tg_arn

def register_instances_to_target_group(tg_arn):
    """
    Helper function to register instances to a target group.
    """
    # Fetch all running instances
    instances = fetch_running_instances()

    if instances:
        # Display instances with name and ID
        print("Available instances:")
        for idx, instance in enumerate(instances, start=1):
            print(f"{idx}. Name: {instance.get('Name', 'N/A')} - ID: {instance['InstanceId']}")

        # Ask user to select instances
        selected_indices = input("Enter the numbers of the instances to register (comma-separated): ").strip()
        try:
            selected_indices = [int(i) for i in selected_indices.split(",") if i.strip().isdigit()]
            selected_instances = [instances[i - 1]['InstanceId'] for i in selected_indices if 1 <= i <= len(instances)]

            # Register selected instances
            if selected_instances:
                elbv2_client.register_targets(
                    TargetGroupArn=tg_arn,
                    Targets=[{'Id': iid} for iid in selected_instances]
                )
                print(f"Instances {', '.join(selected_instances)} registered with Target Group.")
            else:
                print("No valid instances selected. Skipping registration.")
        except (ValueError, IndexError):
            print("Invalid input. Skipping registration.")
    else:
        print("No running instances found in the account.")


def fetch_running_instances():
    """Fetch all running instances with their IDs and names."""
    response = ec2_client.describe_instances(
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['running']}  # Only fetch running instances
        ]
    )
    instances = []

    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instance_info = {
                'InstanceId': instance['InstanceId'],
                'Name': next(
                    (tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'),
                    'N/A'
                )
            }
            instances.append(instance_info)

    return instances

def attach_https_listener(lb_arn, cert_arn, tg_arn):
    """Attach both HTTPS and HTTP Listeners to the Load Balancer."""
    # Fetch existing listeners for the load balancer
    existing_listeners = elbv2_client.describe_listeners(LoadBalancerArn=lb_arn)['Listeners']

    https_listener_arn = None
    http_listener_arn = None

    # Check if an HTTPS listener already exists
    for listener in existing_listeners:
        if listener['Protocol'] == 'HTTPS' and listener['Port'] == 443:
            https_listener_arn = listener['ListenerArn']
            print(f"HTTPS Listener already exists: {https_listener_arn}")
            break

    # Create HTTPS Listener if it doesn't exist
    if not https_listener_arn:
        https_response = elbv2_client.create_listener(
            LoadBalancerArn=lb_arn,
            Protocol='HTTPS',
            Port=443,
            Certificates=[{'CertificateArn': cert_arn}],
            DefaultActions=[{'Type': 'forward', 'TargetGroupArn': tg_arn}]
        )
        https_listener_arn = https_response['Listeners'][0]['ListenerArn']
        print(f"Created HTTPS Listener: {https_listener_arn}")

    # Check if an HTTP listener with redirect already exists
    for listener in existing_listeners:
        if listener['Protocol'] == 'HTTP' and listener['Port'] == 80:
            actions = elbv2_client.describe_rules(ListenerArn=listener['ListenerArn'])['Rules'][0]['Actions']
            if actions[0]['Type'] == 'redirect':
                http_listener_arn = listener['ListenerArn']
                print(f"HTTP Listener with redirect already exists: {http_listener_arn}")
                break

    # Create HTTP Listener with redirect to HTTPS if it doesn't exist
    if not http_listener_arn:
        http_response = elbv2_client.create_listener(
            LoadBalancerArn=lb_arn,
            Protocol='HTTP',
            Port=80,
            DefaultActions=[
                {
                    'Type': 'redirect',
                    'RedirectConfig': {
                        'Protocol': 'HTTPS',
                        'Port': '443',
                        'StatusCode': 'HTTP_301'  # Permanent redirect
                    }
                }
            ]
        )
        http_listener_arn = http_response['Listeners'][0]['ListenerArn']
        print(f"Created HTTP Listener with redirect to HTTPS: {http_listener_arn}")

    return https_listener_arn

def get_load_balancer_dns(lb_arn):
    """Get the DNS name of the load balancer."""
    elbv2_client = boto3.client('elbv2')
    try:
        response = elbv2_client.describe_load_balancers(
            LoadBalancerArns=[lb_arn]
        )
        return response['LoadBalancers'][0]['DNSName']
    except Exception as e:
        print(f"Error getting load balancer DNS: {str(e)}")
        return None
