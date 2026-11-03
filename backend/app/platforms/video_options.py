"""发布视频时各平台不同的规则和专属配置。不依赖浏览器，backend 提交时校验、worker 发布时取值都用它。

标题、视频、封面（竖版）、描述、话题是各平台通用的，存在 Post 上；
只有某个平台才有的选项放在 Post.options，每个平台一个模型。接入新平台或新选项时在这里加。
"""

from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from app.models import Platform

# 标题字数上限。抖音标题框最多 30 字；视频号的标题写在描述第一行，短标题另由标题自动截取
TITLE_MAX = {Platform.douyin: 30, Platform.channels: 200}


class _Options(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 值是图片的字段：接口里传图片地址，库里存相对 media_dir 的路径，发布时换成文件路径
    IMAGE_FIELDS: ClassVar[set[str]] = set()


class DouyinOptions(_Options):
    IMAGE_FIELDS = {"cover_landscape"}

    # 横封面（4:3）；竖封面用通用的封面
    cover_landscape: str | None = None


class ChannelsOptions(_Options):
    pass


OPTIONS: dict[Platform, type[_Options]] = {Platform.douyin: DouyinOptions, Platform.channels: ChannelsOptions}
IMAGE_FIELDS = set().union(*(model.IMAGE_FIELDS for model in OPTIONS.values()))


def parse(platform: Platform, data: Any) -> _Options:
    """校验客户提交的配置，不合法抛 ValueError（pydantic 的 ValidationError 也是）。"""
    return OPTIONS[platform].model_validate(data)


def for_publish(options: dict, media_dir: Path) -> dict:
    """发布时交给平台模块的配置：图片字段换成文件路径。"""
    return {key: media_dir / value if key in IMAGE_FIELDS else value for key, value in options.items()}
