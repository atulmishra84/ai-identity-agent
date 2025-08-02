import boto3

from config.settings import AWS_REGION


def assign_aws_permission_set(identity_center_user_id, permission_set_arn, instance_arn):
    client = boto3.client('sso-admin', region_name=AWS_REGION)
    response = client.create_account_assignment(
        InstanceArn=instance_arn,
        TargetId=identity_center_user_id,
        TargetType='USER',
        PermissionSetArn=permission_set_arn,
        PrincipalType='USER',
        PrincipalId=identity_center_user_id
    )
    return response

