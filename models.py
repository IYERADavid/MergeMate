from pydantic import BaseModel
from typing import List, Optional, Dict

class Commit(BaseModel):
    message: str

class Project(BaseModel):
    id: str
    name: Optional[str] = None

class MergeRequestAttributes(BaseModel):
    title: str
    url: str

class GitlabWebhookPayload(BaseModel):
    object_kind: str
    project: Project
    object_attributes: MergeRequestAttributes
    commits: Optional[List[Commit]] = []
