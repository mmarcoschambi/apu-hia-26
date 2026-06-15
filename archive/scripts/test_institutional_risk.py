#!/usr/bin/env python3
"""
Test script para validar las 3 modificaciones críticas del Risk Manager Institucional
"""
import sys
sys.path.insert(0, 'src')

from utils.risk_manager import RiskManager

def test_stop_loss_sanity_check():
    """Test 1: Rechazar stops amplios (>8%)"""
    print("\n" + "="*80)
    print("TEST 1: STOP LOSS SANITY CHECK (Anti-Bagholding)")
    print("="*80)
    
    rm = RiskManager(account_equity=100000, risk_fraction=0.01, max_exposure_fraction=0.25)
    
    # Caso 1: Stop normal del 4% - DEBE PASAR
    result = rm.calculate_position_size(
        entry_price=100.0,
        stop_price=96.0,  # 4% stop
        adr_percent=4.5,
        avg_daily_volume=1000000
    )
    print(f"\n✓ Stop 4% (Normal):")
    print(f"  Shares: {result['shares']}, Constraint: {result['constraint_hit']}")
    assert result['shares'] > 0, "Debería permitir trade con stop del 4%"
    
    # Caso 2: Stop del 13% - DEBE RECHAZAR
    result = rm.calculate_position_size(
        entry_price=100.0,
        stop_price=87.0,  # 13% stop - MALO
        adr_percent=4.5,
        avg_daily_volume=1000000
    )
    print(f"\n✗ Stop 13% (Demasiado amplio):")
    print(f"  Shares: {result['shares']}, Constraint: {result['constraint_hit']}")
    assert result['shares'] == 0, "Debería RECHAZAR trade con stop del 13%"
    assert "Stop Loss too wide" in result['constraint_hit'], "Razón incorrecta"
    
    print("\n✅ TEST 1 PASADO: Stops amplios son rechazados correctamente")


def test_dynamic_exposure_by_volatility():
    """Test 2: Exposición dinámica basada en ADR"""
    print("\n" + "="*80)
    print("TEST 2: EXPOSICIÓN DINÁMICA por VOLATILIDAD (ADR Tiering)")
    print("="*80)
    
    rm = RiskManager(account_equity=100000, risk_fraction=0.01, max_exposure_fraction=0.25)
    
    # Caso 1: Acción con ADR normal (4%)
    result_normal = rm.calculate_position_size(
        entry_price=100.0,
        stop_price=95.0,  # 5% stop
        adr_percent=4.0,  # ADR normal
        avg_daily_volume=5000000  # Muy líquida
    )
    print(f"\n✓ ADR 4% (Normal volatilidad):")
    print(f"  Max Exposure: 25% (${rm.account_equity * 0.25:,.0f})")
    print(f"  Shares: {result_normal['shares']}, Position: ${result_normal['position_value']:,.0f}")
    
    # Caso 2: Acción con ADR alto (7%) - Como OKLO con 13.46%
    result_volatile = rm.calculate_position_size(
        entry_price=100.0,
        stop_price=95.0,  # 5% stop
        adr_percent=7.0,  # ADR alto - VOLÁTIL
        avg_daily_volume=5000000
    )
    print(f"\n⚠ ADR 7% (Alta volatilidad):")
    print(f"  Max Exposure: 12.5% (${rm.account_equity * 0.125:,.0f}) - REDUCIDO A LA MITAD")
    print(f"  Shares: {result_volatile['shares']}, Position: ${result_volatile['position_value']:,.0f}")
    
    # La exposición en acción volátil debe ser significativamente menor
    assert result_volatile['position_value'] < result_normal['position_value'], \
        "Acción volátil debería tener menor exposición"
    
    print(f"\n✅ TEST 2 PASADO: Exposición reducida en {result_normal['position_value']/result_volatile['position_value']:.1f}x para alta volatilidad")


def test_liquidity_filter():
    """Test 3: Filtro de liquidez (No ser la ballena)"""
    print("\n" + "="*80)
    print("TEST 3: FILTRO DE LIQUIDEZ (No seas la Ballena)")
    print("="*80)
    
    rm = RiskManager(account_equity=100000, risk_fraction=0.01, max_exposure_fraction=0.25)
    
    # Caso 1: Acción muy líquida (5M volumen diario)
    result_liquid = rm.calculate_position_size(
        entry_price=50.0,
        stop_price=48.0,  # 4% stop
        adr_percent=4.0,
        avg_daily_volume=5000000  # 5M shares/día
    )
    print(f"\n✓ Alta liquidez (5M vol/día):")
    print(f"  Max permitido: {int(5000000 * 0.01):,} shares (1% de ADV)")
    print(f"  Shares calculadas: {result_liquid['shares']:,}")
    print(f"  Constraint: {result_liquid['constraint_hit']}")
    
    # Caso 2: Acción ilíquida (100k volumen diario)
    result_illiquid = rm.calculate_position_size(
        entry_price=50.0,
        stop_price=48.0,  # 4% stop
        adr_percent=4.0,
        avg_daily_volume=100000  # Solo 100k shares/día - ILÍQUIDA
    )
    print(f"\n⚠ Baja liquidez (100k vol/día):")
    print(f"  Max permitido: {int(100000 * 0.01):,} shares (1% de ADV)")
    print(f"  Shares calculadas: {result_illiquid['shares']:,}")
    print(f"  Constraint: {result_illiquid['constraint_hit']}")
    
    # Verificar que respeta el límite del 1% del ADV
    max_allowed = int(100000 * 0.01)
    assert result_illiquid['shares'] <= max_allowed, \
        f"Debería limitar a {max_allowed} shares (1% de ADV)"
    
    print(f"\n✅ TEST 3 PASADO: Posición limitada correctamente por liquidez")


def test_combined_scenario():
    """Test 4: Escenario real combinando todas las protecciones"""
    print("\n" + "="*80)
    print("TEST 4: ESCENARIO REAL - OKLO con ADR 13.46%")
    print("="*80)
    
    rm = RiskManager(account_equity=100000, risk_fraction=0.01, max_exposure_fraction=0.25)
    
    # Simular OKLO: Alta volatilidad, stop amplio, baja liquidez
    result = rm.calculate_position_size(
        entry_price=50.0,
        stop_price=43.0,  # 14% stop - HORRIBLE
        adr_percent=13.46,  # ADR extremo
        avg_daily_volume=500000
    )
    
    print(f"\n⛔ OKLO - Setup peligroso:")
    print(f"  Entry: $50.00, Stop: $43.00 (14% - MUY AMPLIO)")
    print(f"  ADR: 13.46% (EXTREMO)")
    print(f"  Vol diario: 500k shares")
    print(f"\n  DECISIÓN DEL RISK MANAGER:")
    print(f"  → Shares: {result['shares']}")
    print(f"  → Razón: {result['constraint_hit']}")
    
    # Este trade debe ser rechazado por el stop amplio
    assert result['shares'] == 0, "Debería RECHAZAR este trade horrible"
    
    print(f"\n✅ TEST 4 PASADO: Trade peligroso rechazado automáticamente")


if __name__ == "__main__":
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + " "*20 + "INSTITUTIONAL RISK MANAGER TEST SUITE" + " "*21 + "█")
    print("█" + " "*78 + "█")
    print("█"*80)
    
    try:
        test_stop_loss_sanity_check()
        test_dynamic_exposure_by_volatility()
        test_liquidity_filter()
        test_combined_scenario()
        
        print("\n" + "█"*80)
        print("█" + " "*78 + "█")
        print("█" + " "*25 + "🎉 TODOS LOS TESTS PASADOS 🎉" + " "*23 + "█")
        print("█" + " "*78 + "█")
        print("█"*80)
        print("\n✅ El Risk Manager Institucional está funcionando correctamente")
        print("✅ Ya no entrarás en trades con stops del 13%")
        print("✅ La exposición se ajusta automáticamente por volatilidad")
        print("✅ Respetas la liquidez del mercado\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FALLIDO: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
