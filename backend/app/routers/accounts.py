from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import Account, Platform
from app.schemas import AccountOut, AccountUpdate

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _get_owned(db: DbSession, user: CurrentUser, account_id: int) -> Account:
    account = db.get(Account, account_id)
    # 其他租户的账号一律当作不存在，避免泄露
    if account is None or account.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "账号不存在")
    return account


@router.get("", response_model=list[AccountOut])
def list_accounts(db: DbSession, user: CurrentUser, platform: Platform | None = None) -> list[Account]:
    query = select(Account).where(Account.tenant_id == user.tenant_id).order_by(Account.id)
    if platform:
        query = query.where(Account.platform == platform)
    return list(db.scalars(query))


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: int, body: AccountUpdate, db: DbSession, user: CurrentUser) -> Account:
    account = _get_owned(db, user, account_id)
    account.display_name = body.display_name
    db.commit()
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: DbSession, user: CurrentUser) -> None:
    db.delete(_get_owned(db, user, account_id))
    db.commit()
