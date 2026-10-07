"""Liabilities — the other half of net worth.

Until this existed the app tracked assets only and still called the total "net
worth", a word that means assets MINUS liabilities. With a loan larger than
the portfolio outstanding, the headline figure was not merely imprecise — it
had the wrong sign on the largest number in the picture.

Kept separate from ``ExternalAsset`` rather than bolted on as a negative-value
row: a liability carries fields an asset has no use for (rate, EMI, term), and
a sign convention smuggled into a `value` column is the kind of thing that
silently flips a total later.

``outstanding`` is the live figure and the only one net worth uses. ``principal``
is kept for context (how much was borrowed) and to make progress legible.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Liability(Base, TimestampMixin):
    __tablename__ = "liabilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    #: gold_loan | car_loan | personal_loan | home_loan | credit_card | other
    kind: Mapped[str] = mapped_column(String(32))
    #: Amount originally borrowed.
    principal: Mapped[float] = mapped_column(Float)
    #: Current balance owed. This is what net worth subtracts.
    outstanding: Mapped[float] = mapped_column(Float)
    #: Annual interest rate, percent. Null when unknown — the payoff projection
    #: degrades to interest-free rather than inventing a number.
    rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: Monthly instalment. Null for bullet/interest-only loans (common for gold
    #: loans, where principal falls due at maturity).
    emi: Mapped[float | None] = mapped_column(Float, nullable=True)
    #: When repayment started, and the agreed term. Together they give the
    #: contractual end date without the user re-deriving it.
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    term_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
