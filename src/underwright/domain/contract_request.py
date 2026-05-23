from datetime import datetime

from pydantic import BaseModel, Field

from underwright.domain.case_context_base import _utc_now


class ContractRequest(BaseModel):
    request_id: int
    client_id: int
    request_status: str = "created"  # created - when the request is made, pending - when the request is processing and has missing file, in_review - when the request is under review, completed - if the request is completed successfully, rejected - if the request is failed
    # grija sa relag ok cu corespondentul din frontend
    client_data: dict = Field(default_factory=dict)
    insured_data: dict = Field(default_factory=dict)
    request_details: dict = Field(default_factory=dict)
    attachments: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)
