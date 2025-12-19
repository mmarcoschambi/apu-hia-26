"""
Risk Management Calculator
Position sizing based on Camino and stop distance
"""


class RiskCalculator:
    
    @staticmethod
    def calculate_position_size(
        account_size: float,
        risk_pct: float,
        entry_price: float,
        stop_loss: float,
        multiplier: float = 1.0
    ) -> dict:
        """
        Calculate position size based on risk parameters
        
        multiplier: 1.0 = standard, 0.5 = reduced (Camino 2)
        """
        if entry_price <= 0 or stop_loss <= 0 or entry_price <= stop_loss:
            return {'error': 'Invalid prices'}
        
        # Risk amount in dollars
        risk_amount = account_size * risk_pct * multiplier
        
        # Risk per share
        risk_per_share = entry_price - stop_loss
        
        # Shares to buy
        shares = int(risk_amount / risk_per_share)
        
        # Capital required
        capital_required = shares * entry_price
        
        # Actual risk percentage
        actual_risk = (shares * risk_per_share) / account_size
        
        return {
            'shares': shares,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'capital_required': capital_required,
            'risk_amount': shares * risk_per_share,
            'risk_pct': actual_risk * 100,
            'risk_per_share': risk_per_share,
            'risk_reward_1to1': entry_price + risk_per_share,
            'risk_reward_2to1': entry_price + (2 * risk_per_share),
            'risk_reward_3to1': entry_price + (3 * risk_per_share)
        }


if __name__ == "__main__":
    # Example calculation
    calc = RiskCalculator()
    
    # Example: $100k account, 0.5% risk, Blue Sky setup
    result = calc.calculate_position_size(
        account_size=100000,
        risk_pct=0.005,  # 0.5%
        entry_price=100.05,
        stop_loss=95.20,
        multiplier=1.0
    )
    
    print("Position Size Calculation:")
    print(f"  Shares: {result['shares']}")
    print(f"  Capital: ${result['capital_required']:,.2f}")
    print(f"  Risk: ${result['risk_amount']:.2f} ({result['risk_pct']:.2f}%)")
    print(f"  Entry: ${result['entry_price']:.2f}")
    print(f"  Stop: ${result['stop_loss']:.2f}")
    print(f"  R:R 1:1 = ${result['risk_reward_1to1']:.2f}")
    print(f"  R:R 2:1 = ${result['risk_reward_2to1']:.2f}")
    print(f"  R:R 3:1 = ${result['risk_reward_3to1']:.2f}")
