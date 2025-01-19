import argparse
import boto3
import json

from botocore.exceptions import ClientError


def create_secret_if_not_exists(secret_name, secret_value):
    # Create a Secrets Manager client
    client = boto3.client(
        "secretsmanager", endpoint_url="http://localhost.localstack.cloud:4566"
    )

    try:
        # Check if the secret already exists
        response = client.describe_secret(SecretId=secret_name)
        return response["ARN"]
    except client.exceptions.ResourceNotFoundException:
        # Secret does not exist, proceed with creating it
        try:
            # Create the secret
            response = client.create_secret(Name=secret_name, SecretString=secret_value)
            print(f"Secret '{secret_name}' created successfully!")
            return response["ARN"]
        except ClientError as e:
            print(f"Failed to create secret '{secret_name}': {e}")
            return None
    except ClientError as e:
        print(f"Failed to check for secret '{secret_name}': {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a secret containing database connection "
            "configuration as a JSON string for API_Foundry."
        )
    )
    parser.add_argument(
        "--secret-name",
        required=True,
        help="The name of the secret to be created or checked.",
    )
    parser.add_argument(
        "--engine",
        required=True,
        help="The type of database engine. Required, one of: mysql, oracle, postgres",
    )
    parser.add_argument("--host", required=True, help="The database host name")
    parser.add_argument("--port", help="The database port. Optional, defaults to 5432.")
    parser.add_argument("--database", required=True, help="The database name")
    parser.add_argument("--user", required=True, help="The database user")
    parser.add_argument("--password", required=True, help="The database password")
    parser.add_argument(
        "--schema", default="public", help="The database schema (default: public)"
    )

    args = parser.parse_args()

    secret_value = json.dumps(
        {
            "engine": args.engine,
            "dbname": args.database,
            "username": args.user,
            "password": args.password,
            "host": args.host,
            "port": args.port,
            "schema": args.schema,
        }
    )

    create_secret_if_not_exists(args.secret_name, secret_value)


if __name__ == "__main__":
    main()
