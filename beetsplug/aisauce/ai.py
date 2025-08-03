from typing import TypeVar
from .plugin import Provider
from openai import OpenAI
from pydantic import BaseModel
import instructor


class Response(BaseModel):
    title: str
    artist: str
    album: str
    album_artist: str
    genres: str
    date: str


def get_ai_client(provider: Provider) -> instructor.Instructor:
    """
    Create an OpenAI client using the provided provider configuration.
    """
    return instructor.from_openai(
        OpenAI(
            api_key=provider["api_key"],
            base_url=provider["api_base_url"],
        )
    )


R = TypeVar("R", bound=type[BaseModel])


def get_structured_output(
    client: instructor.Instructor,
    user_prompt: str,
    system_prompt: str,
    type: R,
    model: str | None = None,
) -> R:
    """
    Use OpenAI API to get structured output.
    """
    return client.chat.completions.create(
        model=model,
        messages=[
            # {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_model=type,
        # we want this to be reproducible, otherwise you might get hard-to -find
        # not-quite duplicates
        temperature=0.0,
    )
