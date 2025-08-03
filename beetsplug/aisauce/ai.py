from __future__ import annotations

from typing import TypeVar

from .types import Provider
from openai import AsyncOpenAI
from pydantic import BaseModel
import instructor


def get_ai_client(provider: Provider) -> instructor.AsyncInstructor:
    """
    Create an Instructor API client.

    Currently, we only support the OpenAI API format.
    """
    return instructor.from_openai(
        AsyncOpenAI(
            api_key=provider["api_key"],
            base_url=provider["api_base_url"],
        )
    )


R = TypeVar("R", bound=BaseModel)


async def get_structured_output(
    client: instructor.AsyncInstructor,
    user_prompt: str,
    system_prompt: str,
    type: type[R],
    model: str | None = None,
) -> R:
    """
    Use OpenAI API to get structured output.
    """
    return await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=type,
        # we want this to be reproducible, otherwise you might get hard-to-find
        # not-quite duplicates
        temperature=0.0,
    )
