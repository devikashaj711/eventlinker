# -------------------------------------
# backend/storage.py
# all aws s3 functionality
# -------------------------------------


import boto3
import os
from datetime import datetime
import uuid
import io

BUCKET = os.getenv("AWS_S3_BUCKET")
REGION = os.getenv("AWS_REGION")

# print("DEBUG AWS BUCKET =", BUCKET)
# print("DEBUG AWS REGION =", REGION)


s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=REGION
)

def upload_file_to_s3(file, folder):

    # Create unique filename
    file_ext = os.path.splitext(file.filename)[1] if hasattr(file, "filename") else ".png"
    filename = f"{uuid.uuid4().hex}{file_ext}"

    key = f"{folder}/{filename}"

    if hasattr(file, "read"):  # FileStorage
        s3.upload_fileobj(
            file,
            BUCKET,
            key
        )
    else:
        raise Exception("Invalid file object")

    # S3 public URL
    return f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{key}"


def upload_qr_to_s3(qr_img, folder="qr_codes"):

    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    buffer.seek(0)

    key = f"{folder}/{uuid.uuid4().hex}.png"

    s3.upload_fileobj(
        buffer,
        BUCKET,
        key,
        ExtraArgs={'ContentType': 'image/png'}
    )

    return f"https://{BUCKET}.s3.{REGION}.amazonaws.com/{key}"


def delete_from_s3(file_url):

    if not file_url:
        return

    # Extract key after amazonaws.com/
    try:
        key = file_url.split(".amazonaws.com/")[-1]
    except:
        return

    if not key:
        return

    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
        print(f"Deleted from S3: {key}")
    except Exception as e:
        print("Error deleting from S3:", e)

