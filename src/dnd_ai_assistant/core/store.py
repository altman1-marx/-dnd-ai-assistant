from __future__ import annotations

from .campaign import Campaign


class InMemoryCampaignStore:
    """Simple repository for prototypes and tests.

    This deliberately avoids a database for now. The later web app can keep the
    same method shape while swapping this for SQLite or PostgreSQL.
    """

    def __init__(self) -> None:
        self._campaigns: dict[str, Campaign] = {}

    def save(self, campaign: Campaign) -> Campaign:
        self._campaigns[campaign.id] = campaign
        return campaign

    def get(self, campaign_id: str) -> Campaign:
        try:
            return self._campaigns[campaign_id]
        except KeyError as exc:
            raise KeyError(f"Campaign not found: {campaign_id}") from exc

    def list(self) -> list[Campaign]:
        return list(self._campaigns.values())

