from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=2000, description="User's question")
    top_k: int = Field(2, ge=1, le=5, description="Maximum number of context chunks to retrieve")
