import boto3
from botocore.exceptions import ClientError
from utils import ask_yes_no

# Initialize the EC2 client
ec2_client = boto3.client('ec2')

def get_existing_security_group(group_name):
    """Check if a Security Group with the given name exists."""
    try:
        response = ec2_client.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': [group_name]}]
        )
        security_groups = response.get('SecurityGroups', [])
        if security_groups:
            sg_id = security_groups[0]['GroupId']
            print(f"Found existing Security Group: {sg_id}")
            return sg_id
    except ClientError as e:
        print(f"Error checking for existing security group: {e}")
    return None

def create_security_group(vpc_id, group_name):
    """Create a new Security Group if it doesn't already exist."""
    sg_id = get_existing_security_group(group_name)
    if sg_id:
        return sg_id

    try:
        response = ec2_client.create_security_group(
            GroupName=group_name,
            Description="Security group for HTTPS",
            VpcId=vpc_id
        )
        sg_id = response['GroupId']
        print(f"Created Security Group: {sg_id}")
        return sg_id
    except ClientError as e:
        print(f"Error creating security group: {e}")
        return None

def configure_security_group(sg_id):
    """
    Configure inbound rules for HTTP and HTTPS.
    Prompts the user for whether to allow access to everyone or specify allowed IP ranges.
    """
    open_to_all = ask_yes_no("Should the security group allow access to everyone? (yes/no): ")
    ip_ranges = [{'CidrIp': '0.0.0.0/0'}] if open_to_all else get_allowed_ips()

    # Fetch current security group rules
    current_permissions = ec2_client.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]['IpPermissions']

    for port in [80, 443]:
        # Check if the rule for the port already exists
        existing_rule = any(
            perm['IpProtocol'] == 'tcp' and
            perm.get('FromPort') == port and
            perm.get('ToPort') == port and
            any(ip['CidrIp'] == ip_ranges[0]['CidrIp'] for ip in perm.get('IpRanges', []))
            for perm in current_permissions
        )

        if existing_rule:
            print(f"Security rule for port {port} already exists. Skipping...")
        else:
            try:
                ec2_client.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[
                        {
                            'IpProtocol': 'tcp',
                            'FromPort': port,
                            'ToPort': port,
                            'IpRanges': ip_ranges
                        }
                    ]
                )
                print(f"Added security rule for port {port}.")
            except ClientError as e:
                print(f"Error configuring rule for port {port}: {e}")

    print(f"Configured Security Group {sg_id} with HTTP and HTTPS rules.")

def get_allowed_ips():
    """Prompt the user for allowed IP ranges."""
    print("Enter IP ranges (CIDR format) to allow (type 'done' to finish):")
    ip_ranges = []
    while True:
        ip = input("Allowed IP: ").strip()
        if ip.lower() == 'done':
            break
        ip_ranges.append({'CidrIp': ip})
    return ip_ranges

