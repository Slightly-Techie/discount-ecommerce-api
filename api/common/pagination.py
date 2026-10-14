from rest_framework.pagination import PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    """Default page size of 10 (unchanged), with an optional ?page_size= override."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
