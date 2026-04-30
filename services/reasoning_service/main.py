from typing import Any


def reason(query: str, docs: list[dict[str, Any]]) -> str:
    if not docs:
        return (
            "I could not find relevant pages in the uploaded PDFs for this query yet."
        )

    citations = ", ".join(
        f"{doc['file_name']} page {doc['page_number']}" for doc in docs[:3]
    )
    return (
        f'I found the most relevant PDF context for: "{query}". '
        f"Start with {citations}. Use the viewer below to inspect the cited pages."
    )
