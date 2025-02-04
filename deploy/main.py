import argparse
from cleanup_manager import cleanup_all_resources
from deployment_pipeline import deploy_resources

def main():
    parser = argparse.ArgumentParser(description='Deploy or delete AWS resources')
    parser.add_argument('-c', '--create', action='store_true', help='Create resources')
    parser.add_argument('-d', '--delete', action='store_true', help='Delete resources')
    
    args = parser.parse_args()

    resource_names = {
        'security_group': "Alameda-WEB-SG",
        'target_group': "Alameda-TG",
        'load_balancer': "Alameda-LB",
        'Domain Name': "alameda-test.calpoly.io"
    }

    if args.create:
        deploy_resources(resource_names)
    elif args.delete:
        print("Starting cleanup process...")
        if cleanup_all_resources(resource_names):
            print("\nAll resources deleted successfully")
        else:
            print("\nSome resources could not be deleted")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()