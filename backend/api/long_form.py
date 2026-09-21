from fastapi import APIRouter, Depends, Request
from backend.dependencies import require_valid_license
from backend.errors import ApplicationError, ErrorCode
from backend.schemas.long_form import LongFormRequest, LongFormStatus

router = APIRouter(prefix="/tts/long-form", tags=["tts"])


def service(request: Request):
    value = getattr(request.app.state, "long_form_service", None)
    if value is None:
        raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
    return value


@router.post("", response_model=LongFormStatus, status_code=202, response_model_exclude_none=True, dependencies=[Depends(require_valid_license)])
def submit(payload: LongFormRequest, jobs=Depends(service)):
    return jobs.submit(payload)


@router.get("/{job_id}", response_model=LongFormStatus, response_model_exclude_none=True)
def status(job_id: str, jobs=Depends(service)):
    return jobs.status(job_id)


@router.delete("/{job_id}", response_model=LongFormStatus, response_model_exclude_none=True)
def cancel(job_id: str, jobs=Depends(service)):
    return jobs.cancel(job_id)
