"""
AWS CDK Stack for 3GPP Event-Driven RAG Pipeline.
Deploys: S3, Lambda, EventBridge, Glue, Aurora Serverless.
"""

from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_rds as rds,
    aws_ec2 as ec2,
)
from constructs import Construct


class ThreeGppRagStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # S3 Buckets
        raw_bucket = s3.Bucket(self, "RawBucket", bucket_name="3gpp-data-raw",
                               removal_policy=RemovalPolicy.RETAIN, versioned=True)
        processed_bucket = s3.Bucket(self, "ProcessedBucket", bucket_name="3gpp-data-processed",
                                     removal_policy=RemovalPolicy.RETAIN)

        # Lambda: Change Detector
        change_detector = _lambda.Function(self, "ChangeDetector",
            function_name="3gpp-change-detector",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda/change_detector"),
            timeout=Duration.minutes(5), memory_size=512,
            environment={"RAW_BUCKET": raw_bucket.bucket_name})
        raw_bucket.grant_write(change_detector)

        # EventBridge: Hourly Poll
        events.Rule(self, "HourlyPoll", rule_name="3gpp-hourly-poll",
                    schedule=events.Schedule.rate(Duration.hours(1)),
                    targets=[targets.LambdaFunction(change_detector)])

        # Lambda: Preprocessor
        preprocessor = _lambda.Function(self, "Preprocessor",
            function_name="3gpp-preprocessor",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda/preprocessor"),
            timeout=Duration.minutes(15), memory_size=1024,
            environment={"PROCESSED_BUCKET": processed_bucket.bucket_name})
        raw_bucket.grant_read(preprocessor)
        processed_bucket.grant_write(preprocessor)
        preprocessor.add_to_role_policy(iam.PolicyStatement(actions=["textract:*"], resources=["*"]))
        raw_bucket.add_event_notification(s3.EventType.OBJECT_CREATED, s3n.LambdaDestination(preprocessor))

        # VPC + Aurora Serverless
        vpc = ec2.Vpc(self, "RagVpc", max_azs=2)
        aurora = rds.ServerlessCluster(self, "KnowledgeBase",
            engine=rds.DatabaseClusterEngine.aurora_postgres(version=rds.AuroraPostgresEngineVersion.VER_15_4),
            vpc=vpc, default_database_name="knowledge_base_3gpp",
            scaling=rds.ServerlessScalingOptions(auto_pause=Duration.minutes(10),
                min_capacity=rds.AuroraCapacityUnit.ACU_2, max_capacity=rds.AuroraCapacityUnit.ACU_16))

        # Lambda: Vector Generator
        vector_gen = _lambda.Function(self, "VectorGenerator",
            function_name="3gpp-vector-generator",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambda/vector_generator"),
            timeout=Duration.minutes(10), memory_size=1024, vpc=vpc,
            environment={"AURORA_SECRET_ARN": aurora.secret.secret_arn,
                         "DB_NAME": "knowledge_base_3gpp"})
        processed_bucket.grant_read(vector_gen)
        aurora.secret.grant_read(vector_gen)
        vector_gen.add_to_role_policy(iam.PolicyStatement(actions=["sagemaker:InvokeEndpoint"], resources=["*"]))
        processed_bucket.add_event_notification(s3.EventType.OBJECT_CREATED, s3n.LambdaDestination(vector_gen))
