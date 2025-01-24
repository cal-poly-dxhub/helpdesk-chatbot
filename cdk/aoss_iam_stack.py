#!/usr/bin/env python3
import json

import aws_cdk as cdk

from aws_cdk import (
  Stack,
  aws_iam as iam
)
from constructs import Construct


class AOSSIamStack(Stack):

  def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
    super().__init__(scope, construct_id, **kwargs)

    #################################################################################
    # Lambda execution role for AOSS
    #################################################################################
    aoss_role = iam.Role(self, "aoss-role",
      assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
      managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonS3FullAccess'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonBedrockFullAccess'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonOpenSearchServiceFullAccess'),
                # Add CloudWatch Logs permission for basic Lambda execution
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole')
            ]
    )

    self.aoss_role = aoss_role