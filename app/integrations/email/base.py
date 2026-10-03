from abc import ABC, abstractmethod

class EmailSender(ABC):
    """Abstract interface for email delivery providers."""

    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> bool:
        """Send an email message.

        Args:
            to: Recipient email address.
            subject: Subject line.
            body: Plain text content.

        Returns:
            bool: True if dispatched successfully, False or raises otherwise.
        """
        pass
