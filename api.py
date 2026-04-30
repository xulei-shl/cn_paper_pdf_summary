import sys
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))

from utils.api_queue import QueueManager

queue_manager = QueueManager(max_concurrent=1)


def get_api_bind_host() -> str:
    """
    获取 API 监听地址

    Returns:
        API 监听地址
    """
    return os.getenv("PDF_SUMMARY_API_BIND_HOST", "0.0.0.0").strip() or "0.0.0.0"


def get_api_port() -> int:
    """
    获取 API 监听端口

    Returns:
        API 监听端口
    """
    raw_port = (os.getenv("PDF_SUMMARY_API_PORT") or "").strip()
    if not raw_port:
        return 8081

    try:
        port = int(raw_port)
    except ValueError:
        return 8081

    if 0 < port <= 65535:
        return port

    return 8081


class ProcessRequest(BaseModel):
    """处理请求模型"""

    title: str = Field(
        ...,
        description="论文题名，用于 PDF 下载检索。",
        examples=["Deep Learning for Computer Vision"]
    )
    id: Optional[int] = Field(
        default=None,
        description="legacy 可选字段。传入时执行 LIS-RSS 上传；不传则跳过。",
        examples=[123]
    )
    push_wechat: bool = Field(
        default=False,
        description="是否强制启用本次企业微信成功结果推送。默认 false。",
    )


class UploadStages(BaseModel):
    """上传阶段结果"""

    hiagent_rag: bool = False
    lis_rss: bool = False
    memos: bool = False
    blinko: bool = False
    wechat: bool = False


class NotifyStages(BaseModel):
    """通知阶段结果"""

    telegram_log: bool = False
    telegram_result: bool = False
    wechat: bool = False


class ProcessStages(BaseModel):
    """处理阶段结果"""

    pdf_download: Optional[str] = None
    pdf_validate: Optional[str] = None
    pdf_summary: Optional[str] = None
    upload: Optional[UploadStages] = None
    notify: Optional[NotifyStages] = None


class ProcessResponse(BaseModel):
    """处理响应模型"""

    success: bool = Field(..., description="整体是否成功。")
    article_id: Optional[int] = Field(default=None, description="文章 ID；未传 legacy id 时通常为 0。")
    md_path: Optional[str] = Field(default=None, description="生成的 Markdown 摘要文件路径。")
    stages: ProcessStages = Field(default_factory=ProcessStages, description="各处理阶段结果。")
    reason: Optional[str] = Field(default=None, description="失败原因或部分失败说明。")


class HealthResponse(BaseModel):
    status: str
    queue_size: int


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    queue_manager._ensure_config()
    yield


app = FastAPI(
    title="Paper PDF Summary API",
    description="论文 PDF 摘要工作流 API，支持下载、总结、可选 legacy LIS-RSS 上传与本地通知分发。",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
    "/process",
    response_model=ProcessResponse,
    summary="处理指定论文",
    description="阻塞执行单篇论文处理流程。支持可选 legacy id 控制 LIS-RSS 上传，并可通过 push_wechat 强制启用本次企业微信成功结果推送。"
)
async def process(req: ProcessRequest) -> ProcessResponse:
    task_id = await queue_manager.enqueue(req.title, req.id, req.push_wechat)
    result = await queue_manager.get_result(task_id)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return ProcessResponse(
        success=result.get("success", False),
        article_id=result.get("article_id"),
        md_path=result.get("md_path"),
        stages=ProcessStages.model_validate(result.get("stages", {})),
        reason=result.get("reason")
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    queue_size = await queue_manager.get_queue_size()
    return HealthResponse(
        status="ok",
        queue_size=queue_size
    )


if __name__ == "__main__":
    uvicorn.run(
        "api:app",
        host=get_api_bind_host(),
        port=get_api_port(),
        reload=False
    )
