from pydantic import BaseModel, Field

class IngestRequest(BaseModel):
    document_text: str = Field(..., min_length=10, description="Original document text to be processed")
    source_name: str = Field(..., min_length=3, description="The source or name of the document (e.g., skatteverket_2026.pdf))")

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=5, description="User's question")
    top_k: int = Field(2, ge=1, le=5, description="Maximum number of contexts (parts) to be retrieved")