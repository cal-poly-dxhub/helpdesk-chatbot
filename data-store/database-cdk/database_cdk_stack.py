from aws_cdk import (
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    App, Stack, Duration, RemovalPolicy, CfnOutput
)
from constructs import Construct

class PostgresRdsStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Define a VPC (required for RDS)
        vpc = ec2.Vpc(
            self, "MyVpc",
            max_azs=2
        )

        # Security group for RDS
        security_group = ec2.SecurityGroup(
            self, "USDADatabaseAccess",
            vpc=vpc,
            allow_all_outbound=True
        )
        security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(),
            connection=ec2.Port.tcp(5432),  # Allow PostgreSQL traffic
            description="Allow PostgreSQL access from security group"
        )

        # RDS PostgreSQL instance
        rds_instance = rds.DatabaseInstance(
            self, "PostgresRDS",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_3
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3, ec2.InstanceSize.MICRO
            ),
            vpc=vpc,
            vpc_subnets={
                "subnet_type": ec2.SubnetType.PRIVATE_WITH_EGRESS
            },
            multi_az=False,  # Set to True for production workloads
            allocated_storage=20,  # Storage in GB
            storage_encrypted=True,
            credentials=rds.Credentials.from_generated_secret("postgres"),  # Auto-generate password
            database_name="USDAConversationStorage",
            security_groups=[security_group],
            backup_retention=Duration.days(1),  # Retain backups for 1 day
            delete_automated_backups=True,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Output the endpoint
        CfnOutput(
            self, "RdsEndpoint",
            value=rds_instance.db_instance_endpoint_address
        )
