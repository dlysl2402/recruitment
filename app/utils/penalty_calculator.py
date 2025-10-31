"""Utility for calculating time-based penalties in candidate scoring."""


class PenaltyCalculator:
    """Calculates penalties based on years of experience with a multiplier.

    Used for avoid companies, avoid title keywords, and other negative signals
    where penalty should scale with time spent in undesirable positions.
    """

    DEFAULT_NO_DATA_PENALTY = 1000  # Elimination penalty when duration unknown

    @staticmethod
    def calculate(
        years: float,
        multiplier: float,
        no_data_penalty: int = DEFAULT_NO_DATA_PENALTY
    ) -> int:
        """Calculate time-based penalty.

        Args:
            years: Years of experience at company/position.
            multiplier: Penalty multiplier (e.g., 10.0 for managers, 3.0 for network roles).
            no_data_penalty: Penalty to apply when years is 0 or unknown (default: 1000).

        Returns:
            Penalty value as integer.

        Examples:
            >>> PenaltyCalculator.calculate(2.5, 10.0)
            25  # 2.5 years × 10.0 multiplier

            >>> PenaltyCalculator.calculate(0.0, 10.0)
            1000  # No duration data → elimination penalty

            >>> PenaltyCalculator.calculate(1.5, 3.0)
            4  # 1.5 years × 3.0 multiplier = 4.5 → 4
        """
        if years == 0:
            return no_data_penalty

        return int(multiplier * years)
