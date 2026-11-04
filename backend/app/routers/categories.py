from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app import tasks
from app.deps import CurrentUser, DbSession
from app.models import Account, Category, Post
from app.schemas import CategoryIn, CategoryOut, PostAccountOut

router = APIRouter(prefix="/api/categories", tags=["categories"])


def get_category(db: DbSession, user: CurrentUser, category_id: int) -> Category | None:
    category = db.get(Category, category_id)
    return category if category is not None and category.tenant_id == user.tenant_id else None


def _parents(db: DbSession, user: CurrentUser) -> dict[int, int | None]:
    """租户的整棵树（id → 上级 id）。分类数量很少，整棵取出来在内存里算层级。"""
    rows = db.execute(select(Category.id, Category.parent_id).where(Category.tenant_id == user.tenant_id))
    return dict(rows.all())


def subtree_ids(db: DbSession, user: CurrentUser, category_id: int) -> set[int]:
    """这个分类和它所有下级分类的 id，按分类筛选内容时包含子分类。"""
    parents = _parents(db, user)
    ids = {category_id} if category_id in parents else set()
    while True:
        more = {cid for cid, pid in parents.items() if pid in ids} - ids
        if not more:
            return ids
        ids |= more


def _check(db: DbSession, user: CurrentUser, body: CategoryIn, category: Category | None = None) -> None:
    parents = _parents(db, user)
    if body.parent_id is not None and body.parent_id not in parents:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "上级分类不存在")
    if category is not None:
        # 不能移到自己或自己的下级分类下面
        node = body.parent_id
        while node is not None:
            if node == category.id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能移到自己或下级分类下面")
            node = parents[node]
    if body.account_id is not None:
        account = db.get(Account, body.account_id)
        if account is None or account.tenant_id != user.tenant_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "账号不存在或已被移除，请重新选择")
        if account.platform not in tasks.PUBLISHABLE:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "这个渠道暂未开放发布")
    duplicate = db.scalar(
        select(Category.id).where(
            Category.tenant_id == user.tenant_id,
            Category.parent_id.is_(None) if body.parent_id is None else Category.parent_id == body.parent_id,
            Category.name == body.name,
            Category.id != (category.id if category is not None else 0),
        )
    )
    if duplicate:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"同一层已有「{body.name}」")


def _out(category: Category, post_count: int) -> CategoryOut:
    return CategoryOut(
        id=category.id,
        parent_id=category.parent_id,
        name=category.name,
        account=PostAccountOut.model_validate(category.account) if category.account else None,
        post_count=post_count,
        created_at=category.created_at,
    )


def _saved(db: DbSession, category: Category) -> CategoryOut:
    db.refresh(category)
    return _out(category, db.scalar(select(func.count()).where(Post.category_id == category.id)))


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DbSession, user: CurrentUser) -> list[CategoryOut]:
    counts = dict(
        db.execute(
            select(Post.category_id, func.count())
            .where(Post.tenant_id == user.tenant_id, Post.category_id.is_not(None))
            .group_by(Post.category_id)
        ).all()
    )
    rows = db.scalars(
        select(Category)
        .where(Category.tenant_id == user.tenant_id)
        .options(selectinload(Category.account))
        .order_by(Category.id)
    ).all()
    return [_out(c, counts.get(c.id, 0)) for c in rows]


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, db: DbSession, user: CurrentUser) -> CategoryOut:
    _check(db, user, body)
    category = Category(tenant_id=user.tenant_id, parent_id=body.parent_id, name=body.name, account_id=body.account_id)
    db.add(category)
    db.commit()
    return _saved(db, category)


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, body: CategoryIn, db: DbSession, user: CurrentUser) -> CategoryOut:
    """改名、改绑定账号，或移到别的上级分类下（连同下级分类一起移）。
    改绑定不影响已有内容：已提交的仍发到提交时的账号，草稿在提交审核时改用新账号。"""
    category = get_category(db, user, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "分类不存在")
    _check(db, user, body, category)
    category.name = body.name
    category.parent_id = body.parent_id
    category.account_id = body.account_id
    db.commit()
    return _saved(db, category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: DbSession, user: CurrentUser) -> None:
    category = get_category(db, user, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "分类不存在")
    if db.scalar(select(Category.id).where(Category.parent_id == category.id).limit(1)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先删除或移走下级分类")
    # 不自动把内容改成未分类，免得内容悄悄从原来的分类里消失
    if db.scalar(select(Post.id).where(Post.category_id == category.id).limit(1)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "分类下还有内容，请先把内容移到其他分类")
    db.delete(category)
    db.commit()
