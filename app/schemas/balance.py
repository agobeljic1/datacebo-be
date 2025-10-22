from pydantic import BaseModel, Field


class BalanceIncreaseRequest(BaseModel):
    amount: int = Field(gt=0)


class BalanceResponse(BaseModel):
    balance: int


