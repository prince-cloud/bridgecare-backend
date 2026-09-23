from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

import logging

logger = logging.getLogger(__name__)


class BaseException(APIException):
    status_code = 400

    def __init__(
        self,
        detail=None,
        response_code=None,
        error_code=None,
    ):
        self.response_code = response_code
        self.error_code = error_code
        self.detail = detail or self.default_detail


class GenericFieldException(BaseException):
    status_code = 400
    default_code = 400
    default_detail = "Please check the highlighted fields and try again."


class ServerFaultException(BaseException):
    status_code = 500
    default_code = 500
    default_detail = "An error occured on the server. Please report to the admin."


# Keys this handler adds to the body. They are not field names, so the
# summary must skip them when it looks for the first field error.
ENVELOPE_KEYS = ("errorCode", "errorMsg", "status_code")

# DRF keys that carry a message for the whole form, not for one field.
FORM_LEVEL_KEYS = ("non_field_errors", "detail", "__all__")


def _label(field_name):
    """`emergency_contact_phone` -> `Emergency contact phone`."""
    if field_name in FORM_LEVEL_KEYS:
        return ""
    return str(field_name).replace("_", " ").strip().capitalize()


def _first_leaf(value, path=()):
    """
    Walk a DRF error payload (dicts, lists, strings) and return the first
    (path, message) pair. Serializer errors nest for related objects, for
    example `{"user": {"phone_number": ["Enter a valid number."]}}`.
    """
    if isinstance(value, dict):
        for key, child in value.items():
            if key in ENVELOPE_KEYS:
                continue
            found = _first_leaf(child, path + (key,))
            if found:
                return found
        return None
    if isinstance(value, (list, tuple)):
        for child in value:
            found = _first_leaf(child, path)
            if found:
                return found
        return None
    if value is None or str(value).strip() == "":
        return None
    return (path, str(value))


def field_error_message(data):
    """
    One sentence a user can act on, built from the first field error, for
    example `Phone number: Enter a valid phone number.`

    The full per-field dict stays in the body so the client can also show
    each message next to its field.
    """
    found = _first_leaf(data)
    if not found:
        return GenericFieldException.default_detail
    path, message = found
    labels = [_label(part) for part in path if not isinstance(part, int)]
    labels = [label for label in labels if label]
    if not labels:
        return message
    return f"{labels[-1]}: {message}"


def custom_exception_handler(exception: Exception, context):
    status_code = 500
    code = 500
    details = "Some unexpected exception occured"

    # Example of how these could be branched out further with error message and status code edited
    if isinstance(exception, BaseException):
        status_code = exception.response_code or exception.status_code
        code = exception.error_code or exception.default_code
        details = exception.detail or exception.default_detail

    else:
        response = exception_handler(exception, context)
        if isinstance(exception, ValidationError):
            code = GenericFieldException.default_code
            # Before this, every validation error carried the same text:
            # "A field exception occured. Find the exact fields as part of
            # this json data." Clients showed that raw string to users
            # (QA findings SET-01, PRO-01, XCUT-01).
            details = field_error_message(response.data if response else None)
        elif response is None or response.status_code == 500:
            code = ServerFaultException.default_code
            details = ServerFaultException.default_detail
            logger.exception(exception)
        elif isinstance(exception, APIException):
            # Throttled, NotAuthenticated, PermissionDenied, NotFound and the
            # like already carry a sentence for the user ("Request was
            # throttled. Expected available in 42 seconds."). Before this they
            # were labelled "Some unexpected exception occured", and clients
            # that read `errorMsg` first showed that (QA finding AUTH-03).
            code = response.status_code
            details = _first_leaf(exception.detail)
            details = details[1] if details else str(exception.detail)
        if response:
            # A ValidationError raised with a list has a list body. Wrap it so
            # the envelope keys below always have a dict to land in.
            if not isinstance(response.data, dict):
                response.data = {"non_field_errors": response.data}
            response.data["errorCode"] = code
            response.data["errorMsg"] = details
            return response

    data = {
        "status_code": status_code,
        "errorCode": code,
        "errorMsg": details,
    }
    return Response(data, status=status_code)
