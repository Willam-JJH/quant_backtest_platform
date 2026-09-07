"""数据模型：Team、Submission 以及枚举类型。"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class DataTrack(str, Enum):
    """数据轨道。"""
    learning_1 = "learning_1"
    learning_2 = "learning_2"
    learning_3 = "learning_3"
    hidden = "hidden"


class SubmissionStatus(str, Enum):
    """提交状态。"""
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class Team(BaseModel):
    """队伍模型。"""
    id: Optional[int] = None
    name: str
    display_name: str
    password: str
    created_at: Optional[str] = None


class Submission(BaseModel):
    """提交模型。"""
    id: Optional[int] = None
    team_id: int
    data_track: str
    status: str = SubmissionStatus.pending.value
    score: Optional[float] = None
    metrics: Optional[str] = None
    file_path: Optional[str] = None
    error_message: Optional[str] = None
    submitted_at: Optional[str] = None
    scored_at: Optional[str] = None
