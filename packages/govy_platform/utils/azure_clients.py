# govy/utils/azure_clients.py
"""
Clientes Azure Storage autenticados via DefaultAzureCredential (Managed Identity).

Uso:
    from govy.utils.azure_clients import get_blob_service_client, get_container_client

    blob_service = get_blob_service_client()
    container = get_container_client("kb-raw")

Autenticacao:
    - No Azure: usa Managed Identity (SystemAssigned) do func-govy-parse-test
    - Local (dev): usa credencial do `az login`

Config:
    - GOVY_STORAGE_ACCOUNT (app setting): nome do storage account (default: stgovyparsetestsponsor)
"""
import os
import logging
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContainerClient

logger = logging.getLogger(__name__)

_DEFAULT_ACCOUNT = "stgovyparsetestsponsor"

# Singleton: credential e client reutilizados entre chamadas
_credential = None
_blob_service_clients: dict = {}


def _get_credential() -> DefaultAzureCredential:
    """Retorna credential singleton."""
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
        logger.info("DefaultAzureCredential inicializada")
    return _credential


def get_blob_service_client(account_name: str = None) -> BlobServiceClient:
    """
    Retorna BlobServiceClient autenticado via Azure AD.

    Args:
        account_name: nome do storage account. Default: GOVY_STORAGE_ACCOUNT env var
                      ou 'stgovyparsetestsponsor'.

    Returns:
        BlobServiceClient com cache (singleton por account_name)
    """
    if account_name is None:
        account_name = os.environ.get("GOVY_STORAGE_ACCOUNT", _DEFAULT_ACCOUNT)

    if account_name not in _blob_service_clients:
        account_url = f"https://{account_name}.blob.core.windows.net"
        credential = _get_credential()
        _blob_service_clients[account_name] = BlobServiceClient(
            account_url=account_url,
            credential=credential,
        )
        logger.info(f"BlobServiceClient criado para {account_name} (Azure AD)")

    return _blob_service_clients[account_name]


def get_container_client(container_name: str, account_name: str = None) -> ContainerClient:
    """
    Retorna ContainerClient autenticado via Azure AD.

    Args:
        container_name: nome do container
        account_name: nome do storage account (default: GOVY_STORAGE_ACCOUNT)

    Returns:
        ContainerClient
    """
    blob_service = get_blob_service_client(account_name)
    return blob_service.get_container_client(container_name)
