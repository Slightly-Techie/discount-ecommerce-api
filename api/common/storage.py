from django.core.files.storage import storages


def private_storage():
    """Storage for files only served through permission-checked views."""
    return storages["private"]
