"""
LLM backend protocol.

The agent loop talks to *a backend*, not to Bedrock directly. Swapping the model
provider — or the offline mock — is a matter of picking a different backend
class, with no change to the loop. Each backend takes a conversation (list of
{role, content}) and returns the model's raw text response.
"""

from __future__ import annotations

import abc

from ...models import ReportIR


class LLMBackend(abc.ABC):
    @abc.abstractmethod
    def complete(self, messages: list[dict[str, str]], ir: ReportIR) -> str:
        """Return the model's raw text response for `messages`.

        `ir` is passed so deterministic/mock backends can synthesize output;
        real backends ignore it and use only `messages`.
        Raise BackendError on transport/auth/throttle failures.
        """
        raise NotImplementedError
