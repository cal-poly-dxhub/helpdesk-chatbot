import boto3
import time

acm_client = boto3.client('acm')

def request_acm_certificate(domain_name):
    """
    Request an ACM certificate and handle DNS validation.
    The user is expected to manually update DNS with provided records.
    """
    response = acm_client.request_certificate(
        DomainName=domain_name,
        ValidationMethod='DNS'
    )
    cert_arn = response['CertificateArn']
    print(f"\nCertificate requested successfully! ARN: {cert_arn}")
    
    print("\nWaiting for DNS validation details to become available...")  # Print once
    while True:
        cert_details = acm_client.describe_certificate(CertificateArn=cert_arn)

        # Check if validation details are available
        if 'DomainValidationOptions' in cert_details['Certificate'] and 'ResourceRecord' in cert_details['Certificate']['DomainValidationOptions'][0]:
            validation_options = cert_details['Certificate']['DomainValidationOptions'][0]['ResourceRecord']
            print("\nPlease provide the following CNAME record to the DNS administrator:")
            print(f"  CNAME: {validation_options['Name']}")
            print(f"  CValue: {validation_options['Value']}")
            break  # Exit loop once validation details are available

        time.sleep(10)

    print("\nWaiting for validation to complete...")  # Print once for waiting

    # Wait for the certificate status to be 'ISSUED'
    previous_status = None
    while True:
        cert_details = acm_client.describe_certificate(CertificateArn=cert_arn)
        status = cert_details['Certificate']['Status']

        # Print status only when it changes
        if status != previous_status:
            print(f"\nCertificate status: {status}.")
            previous_status = status

        if status == 'ISSUED':
            print("\nCertificate successfully validated and issued!")
            return cert_arn
        elif status != 'PENDING_VALIDATION':
            print(f"\nCertificate status: {status}. Exiting.")
            break

        time.sleep(10)
