import boto3


def make_client(settings):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def object_key(settings, filename: str) -> str:
    return f"{settings.r2_key_prefix}{filename}"


def public_url(settings, filename: str) -> str:
    return f"{settings.r2_public_base_url}/{settings.r2_key_prefix}{filename}"


def upload_bytes(client, bucket: str, key: str, data: bytes) -> None:
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType="application/json",
        CacheControl="public, max-age=300",
    )
