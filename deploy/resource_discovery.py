import boto3

ec2_client = boto3.client('ec2')

def discover_vpc():
    """Discover available VPCs and let the user choose one."""
    vpcs = ec2_client.describe_vpcs()['Vpcs']
    print("Available VPCs:")
    for i, vpc in enumerate(vpcs, start = 1):
        print(f"{i}. VPC ID: {vpc['VpcId']} - CIDR: {vpc['CidrBlock']}")
    choice = int(input("Select VPC (number): ")) - 1
    return vpcs[choice]['VpcId']

def discover_subnets(vpc_id):
    """Discover available subnets in the selected VPC, including their names and internet gateway status."""
    subnets = ec2_client.describe_subnets(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
    route_tables = ec2_client.describe_route_tables(Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])['RouteTables']

    # Identify the main route table
    main_route_table = next((rt for rt in route_tables if any(assoc.get('Main') for assoc in rt.get('Associations', []))), None)

    def has_internet_gateway(subnet_id):
        # Check for explicit association
        for route_table in route_tables:
            for association in route_table.get('Associations', []):
                if association.get('SubnetId') == subnet_id:
                    return any(
                        route.get('DestinationCidrBlock') == '0.0.0.0/0' and route.get('GatewayId', '').startswith('igw-')
                        for route in route_table.get('Routes', [])
                    )
        # Fallback to the main route table
        if main_route_table:
            return any(
                route.get('DestinationCidrBlock') == '0.0.0.0/0' and route.get('GatewayId', '').startswith('igw-')
                for route in main_route_table.get('Routes', [])
            )
        return False

    print("Available Subnets:")
    for i, subnet in enumerate(subnets):
        subnet_name = next(
            (tag['Value'] for tag in subnet.get('Tags', []) if tag['Key'] == 'Name'),
            'N/A'
        )
        igw_status = "Yes" if has_internet_gateway(subnet['SubnetId']) else "No"
        print(f"{i + 1}. Subnet ID: {subnet['SubnetId']} - CIDR: {subnet['CidrBlock']} - Name: {subnet_name} - Has Internet Gateway: {igw_status}")
    
    selected = input("Enter numbers of subnets to use (comma-separated): ").split(",")
    return [subnets[int(i) - 1]['SubnetId'] for i in selected]
