import boto3
from botocore.exceptions import ClientError
import time
from utils import ask_yes_no

acm_client = boto3.client('acm')
elbv2_client = boto3.client('elbv2')
ec2_client = boto3.client('ec2')

def cleanup_all_resources(resource_names):
    """
    Clean up all resources using their names.
    resource_names should be a dict containing names of resources to clean up.
    """
    # Show resources that will be deleted and ask for confirmation
    print("\nThe following resources will be deleted:")
    print(f"- Load Balancer: {resource_names['load_balancer']}")
    print(f"- Target Group: {resource_names['target_group']}")
    print(f"- Security Group: {resource_names['security_group']}")
    print(f"- SSL Certificate for domain: {resource_names['Domain Name']}")
    
    if not ask_yes_no("\nAre you sure you want to delete these resources?"):
        print("Deletion cancelled.")
        return False

    # Ask about certificate separately
    delete_cert = ask_yes_no(f"\nWould you like to delete the SSL certificate for {resource_names['Domain Name']} as well?")

    success = True
    print("\nStarting cleanup of resources...")

    # Delete in reverse order of creation
    if resource_names.get('load_balancer'):
        if not cleanup_load_balancer(resource_names['load_balancer']):
            success = False
        
    if resource_names.get('target_group'):
        if not cleanup_target_group(resource_names['target_group']):
            success = False

    if resource_names.get('security_group'):
        if not cleanup_security_group(resource_names['security_group']):
            success = False

    # Only cleanup certificate if user confirmed
    if delete_cert and resource_names.get('Domain Name'):
        if not cleanup_certificate(resource_names['Domain Name']):
            success = False

    return success

def cleanup_certificate(domain_name):
    try:
        # List certificates to find the ones matching the domain name
        paginator = acm_client.get_paginator('list_certificates')
        certificates = []
        
        for page in paginator.paginate():
            for cert in page['CertificateSummaryList']:
                if domain_name in cert['DomainName']:
                    certificates.append(cert['CertificateArn'])
        
        # If no certificates found, return
        if not certificates:
            print(f"No certificates found for domain: {domain_name}")
            return True
        
        # Delete each certificate found
        for cert_arn in certificates:
            try:
                acm_client.delete_certificate(CertificateArn=cert_arn)
                print(f"Successfully deleted certificate: {cert_arn}")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == 'ResourceInUseException':
                    print(f"Certificate {cert_arn} is currently in use and cannot be deleted")
                else:
                    print(f"Error deleting certificate {cert_arn}: {e}")
                return False
        
        return True
    
    except ClientError as e:
        print(f"Error in cleanup_certificate: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error in cleanup_certificate: {e}")
        return False

def get_load_balancer_arn(lb_name):
    """Get load balancer ARN from name."""
    try:
        response = elbv2_client.describe_load_balancers(
            Names=[lb_name]
        )
        load_balancers = response.get('LoadBalancers', [])
        if load_balancers:
            return load_balancers[0]['LoadBalancerArn']
    except ClientError as e:
        if e.response['Error']['Code'] != 'LoadBalancerNotFound':
            print(f"Error finding load balancer {lb_name}: {str(e)}")
    return None

def get_target_group_arn(tg_name):
    """Get target group ARN from name."""
    try:
        response = elbv2_client.describe_target_groups(
            Names=[tg_name]
        )
        target_groups = response.get('TargetGroups', [])
        if target_groups:
            return target_groups[0]['TargetGroupArn']
    except ClientError as e:
        if e.response['Error']['Code'] != 'TargetGroupNotFound':
            print(f"Error finding target group {tg_name}: {str(e)}")
    return None

def get_security_group_id(group_name):
    """Get security group ID from name."""
    try:
        response = ec2_client.describe_security_groups(
            Filters=[{'Name': 'group-name', 'Values': [group_name]}]
        )
        security_groups = response.get('SecurityGroups', [])
        if security_groups:
            return security_groups[0]['GroupId']
    except ClientError as e:
        if e.response['Error']['Code'] != 'InvalidGroup.NotFound':
            print(f"Error finding security group {group_name}: {str(e)}")
    return None

def cleanup_load_balancer(lb_name):
    """Delete a load balancer by name."""
    if not lb_name:
        return True
    print(f"\nCleaning up load balancer: {lb_name}")
    
    try:
        # First, get the ARN
        lb_arn = get_load_balancer_arn(lb_name)
        if not lb_arn:
            print(f"Load balancer {lb_name} not found (may have been already deleted)")
            return True

        # Delete all listeners first
        try:
            listeners = elbv2_client.describe_listeners(LoadBalancerArn=lb_arn)
            for listener in listeners.get('Listeners', []):
                elbv2_client.delete_listener(ListenerArn=listener['ListenerArn'])
                print(f"Deleted listener: {listener['ListenerArn']}")
        except ClientError as e:
            print(f"Error deleting listeners: {str(e)}")

        # Then delete the load balancer
        elbv2_client.delete_load_balancer(LoadBalancerArn=lb_arn)
        print("Waiting for load balancer to be deleted...")
        
        waiter = elbv2_client.get_waiter('load_balancers_deleted')
        waiter.wait(
            LoadBalancerArns=[lb_arn],
            WaiterConfig={'Delay': 10, 'MaxAttempts': 30}
        )
        
        print("Load balancer deleted successfully")
        return True

    except elbv2_client.exceptions.LoadBalancerNotFoundException:
        print("Load balancer already deleted")
        return True
    except Exception as e:
        print(f"Error deleting load balancer: {str(e)}")
        return False

def cleanup_target_group(tg_name):
    """Delete a target group by name."""
    if not tg_name:
        return True
    print(f"\nCleaning up target group: {tg_name}")
    
    try:
        # First, get the ARN
        tg_arn = get_target_group_arn(tg_name)
        if not tg_arn:
            print(f"Target group {tg_name} not found (may have been already deleted)")
            return True

        elbv2_client.delete_target_group(TargetGroupArn=tg_arn)
        print("Target group deleted successfully")
        return True

    except elbv2_client.exceptions.TargetGroupNotFoundException:
        print("Target group already deleted")
        return True
    except Exception as e:
        print(f"Error deleting target group: {str(e)}")
        return False

def remove_security_group_rules(sg_id):
    """Remove all rules from a security group."""
    try:
        # Get current security group rules
        response = ec2_client.describe_security_groups(GroupIds=[sg_id])
        if not response['SecurityGroups']:
            return True
            
        sg = response['SecurityGroups'][0]
        
        # Remove ingress rules if they exist
        if sg.get('IpPermissions'):
            ec2_client.revoke_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=sg['IpPermissions']
            )
            print(f"Removed ingress rules from security group {sg_id}")
            
        # Remove egress rules if they exist
        if sg.get('IpPermissionsEgress'):
            ec2_client.revoke_security_group_egress(
                GroupId=sg_id,
                IpPermissions=sg['IpPermissionsEgress']
            )
            print(f"Removed egress rules from security group {sg_id}")
            
        return True
        
    except ClientError as e:
        print(f"Error removing rules from security group {sg_id}: {str(e)}")
        return False

def cleanup_security_group(group_name):
    """Clean up a security group and its rules by name."""
    if not group_name:
        return True
    print(f"\nCleaning up security group: {group_name}")
    
    # First, get the ID
    sg_id = get_security_group_id(group_name)
    if not sg_id:
        print(f"Security group {group_name} not found (may have been already deleted)")
        return True

    # Remove rules
    if not remove_security_group_rules(sg_id):
        print("Failed to remove security group rules")
        return False

    # Then try to delete the security group with retries
    max_retries = 10
    retry_delay = 10  # seconds

    for attempt in range(max_retries):
        try:
            ec2_client.delete_security_group(GroupId=sg_id)
            print(f"Security group {group_name} deleted successfully")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'DependencyViolation':
                if attempt < max_retries - 1:
                    print(f"Security group {group_name} still has dependencies. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"Failed to delete security group {group_name} after {max_retries} attempts")
                    return False
            
            elif error_code == 'InvalidGroup.NotFound':
                print(f"Security group {group_name} not found (may have been already deleted)")
                return True
                
            else:
                print(f"Error deleting security group: {str(e)}")
                return False

    return False