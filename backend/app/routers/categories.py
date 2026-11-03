from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession
from app.models import Category, Post
from app.schemas import CategoryIn, CategoryOut

router = APIRouter(prefix="/api/categories", tags=["categories"])

# 再深界面放不下，实际也用不上
MAX_DEPTH = 3


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


def _depth(parents: dict[int, int | None], category_id: int | None) -> int:
    depth = 0
    while category_id is not None:
        depth += 1
        category_id = parents[category_id]
    return depth


def _height(parents: dict[int, int | None], category_id: int) -> int:
    children = [cid for cid, pid in parents.items() if pid == category_id]
    return 1 + max((_height(parents, cid) for cid in children), default=0)


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
    height = _height(parents, category.id) if category is not None else 1
    if _depth(parents, body.parent_id) + height > MAX_DEPTH:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"分类最多 {MAX_DEPTH} 层")
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


def _out(db: DbSession, category: Category) -> CategoryOut:
    count = db.scalar(select(func.count()).where(Post.category_id == category.id))
    return CategoryOut(id=category.id, parent_id=category.parent_id, name=category.name, post_count=count)


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DbSession, user: CurrentUser) -> list[CategoryOut]:
    counts = dict(
        db.execute(
            select(Post.category_id, func.count())
            .where(Post.tenant_id == user.tenant_id, Post.category_id.is_not(None))
            .group_by(Post.category_id)
        ).all()
    )
    rows = db.scalars(select(Category).where(Category.tenant_id == user.tenant_id).order_by(Category.id)).all()
    return [CategoryOut(id=c.id, parent_id=c.parent_id, name=c.name, post_count=counts.get(c.id, 0)) for c in rows]


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryIn, db: DbSession, user: CurrentUser) -> CategoryOut:
    _check(db, user, body)
    category = Category(tenant_id=user.tenant_id, parent_id=body.parent_id, name=body.name)
    db.add(category)
    db.commit()
    return _out(db, category)


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, body: CategoryIn, db: DbSession, user: CurrentUser) -> CategoryOut:
    """改名或移到别的上级分类下（连同下级分类一起移）。"""
    category = get_category(db, user, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "分类不存在")
    _check(db, user, body, category)
    category.name = body.name
    category.parent_id = body.parent_id
    db.commit()
    return _out(db, category)


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
