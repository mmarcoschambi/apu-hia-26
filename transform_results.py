#!/usr/bin/env python3
"""
Transform backtest results to dashboard format
"""
import pandas as pd
from datetime import datetime

def transform_results(input_file, output_file):
    """
    Transform the backtest results from TriadOpenBB format to dashboard format
    """
    # Read the results
    df = pd.read_csv(input_file)
    
    print(f"Original columns: {list(df.columns)}")
    print(f"Original shape: {df.shape}")
    
    # Create a new dataframe with the expected columns for the dashboard
    transformed_df = pd.DataFrame()
    
    # Map the columns to the expected format
    transformed_df['date'] = df['entry_date']  # Use entry date as the main date
    transformed_df['symbol'] = df['symbol']
    transformed_df['camino'] = df['signal_type'].apply(lambda x: x.upper().replace('C', 'Camino '))
    transformed_df['entry_price'] = df['entry_price']
    transformed_df['exit_price'] = df['exit_price']
    transformed_df['return_pct'] = df['returns_pct']
    transformed_df['risk_pct'] = df['returns_pct'].abs() * 0.5  # Estimado: la mitad del retorno como riesgo
    transformed_df['outcome'] = df['is_profitable'].map({True: 'WIN', False: 'LOSS'})
    transformed_df['hold_days'] = 5  # Valor por defecto
    transformed_df['stop_loss'] = df['entry_price'] * 0.99  # Estimado: stop del 1%
    transformed_df['base_high'] = df['entry_price'] * 0.98  # Estimado: base un poco por debajo
    
    # Save the transformed dataframe
    transformed_df.to_csv(output_file, index=False)
    
    print(f"Transformed shape: {transformed_df.shape}")
    print(f"Transformed columns: {list(transformed_df.columns)}")
    print(f"Win rate: {(transformed_df['outcome'] == 'WIN').sum() / len(transformed_df) * 100:.2f}%")
    print(f"Saved to: {output_file}")
    
    return transformed_df

if __name__ == "__main__":
    input_file = "backtest_results.csv"
    output_file = "dashboard_results.csv"
    
    transform_results(input_file, output_file)