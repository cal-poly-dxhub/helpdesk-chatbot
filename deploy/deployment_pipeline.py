from resource_discovery import discover_vpc, discover_subnets
from security_group_manager import create_security_group, configure_security_group
from acm_manager import request_acm_certificate
from elb_manager import create_load_balancer, create_target_group, attach_https_listener, get_load_balancer_dns
from cleanup_manager import cleanup_all_resources

def deploy_resources(resource_names):
    """Create all required resources."""

    try:
        print("Starting deployment process...")

        # Step 1: Discover VPC
        vpc_id = discover_vpc()
        subnets = discover_subnets(vpc_id)

        # Step 2: Create Security Group
        sg_id = create_security_group(vpc_id, resource_names['security_group'])
        configure_security_group(sg_id)

        # Step 3: Create Target Group
        tg_arn = create_target_group(vpc_id, resource_names['target_group'])

        # Step 4: Create Load Balancer
        lb_arn = create_load_balancer(resource_names['load_balancer'], subnets, [sg_id])

        # Step 5: Request ACM Certificate and Attach Listener
        cert_arn = request_acm_certificate(resource_names['Domain Name'])

        print("\nAttaching HTTPS Listener...")
        attach_https_listener(lb_arn, cert_arn, tg_arn)

        # Get Load Balancer DNS name
        lb_dns = get_load_balancer_dns(lb_arn)
        
        if lb_dns:
            print("\nDeployment completed successfully!")
            print("\nIMPORTANT DNS Configuration Instructions:")
            print("----------------------------------------")
            print("To complete the HTTPS setup, please create a CNAME record in your DNS settings:")
            print(f"Load Balancer DNS: {lb_dns}")
            print("\nIn your DNS provider's console:")
            print("1. Create a new CNAME record")
            print("2. Point your domain to the Load Balancer DNS name above")
            print("3. Wait for DNS propagation (can take up to 48 hours)")
            print("\nUse the record information below to create an alias for your new domain name:")
            print("Record Type: CNAME")
            print(f"Host: {resource_names['Domain Name']}")
            print(f"Points to: {lb_dns}")
            print("----------------------------------------")
        else:
            print("\nWarning: Could not retrieve load balancer DNS name")

        return True

    except Exception as e:
        print(f"\nError during deployment: {str(e)}")
        print("\nStarting cleanup of partially created resources...")
        cleanup_all_resources(resource_names)
        return False
