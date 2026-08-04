import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

def read_log_from_blob(blob_name: str) -> str:
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = os.getenv("AZURE_STORAGE_CONTAINER")
    
    client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = client.get_blob_client(
        container=container_name,
        blob=blob_name
    )
    
    data = blob_client.download_blob()
    return data.readall().decode("utf-8")