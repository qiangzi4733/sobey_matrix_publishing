from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.models import Account


@dataclass
class PublishResult:
    # 平台侧的作品 ID（公众号 publish_id、快手 photo_id 等）；异步平台先拿到任务 ID
    external_id: str | None
    url: str | None = None
    raw: dict = field(default_factory=dict)


class Publisher(ABC):
    """每个平台实现一个 Publisher，上层只负责选账号、建任务。"""

    @abstractmethod
    def check_credentials(self, account: Account) -> bool:
        """凭证是否仍然有效；失效时上层把账号标记为 expired 并提醒客户。"""

    @abstractmethod
    def publish(self, account: Account, content: dict) -> PublishResult:
        """提交发布。返回成功只代表平台已受理，最终结果由 query_status 确认。"""

    @abstractmethod
    def query_status(self, account: Account, result: PublishResult) -> str:
        """查询发布结果：pending / success / failed。"""
