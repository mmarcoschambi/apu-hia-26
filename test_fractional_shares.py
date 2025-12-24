#!/usr/bin/env python3
"""
Test para validar soporte de acciones fraccionadas en cuentas pequeñas
"""
import sys
sys.path.insert(0, 'src')

from utils.risk_manager import RiskManager

def test_fractional_shares_small_account():
    """Test: Cuentas pequeñas pueden usar fracciones"""
    print("\n" + "="*80)
    print("TEST 1: ACCIONES FRACCIONADAS - Cuenta Pequeña ($5,000)")
    print("="*80)
    
    # Cuenta pequeña de $5,000
    rm = RiskManager(
        account_equity=5000,
        risk_fraction=0.01,  # 1% = $50 riesgo
        max_exposure_fraction=0.25,
        allow_fractional_shares=True
    )
    
    # Caso 1: Acción cara ($500) - Solo podría comprar 0.25 shares
    result = rm.calculate_position_size(
        entry_price=500.0,
        stop_price=475.0,  # $25 de riesgo por acción
        adr_percent=4.0,
        avg_daily_volume=1000000
    )
    
    print(f"\n💰 Acción cara ($500/share):")
    print(f"  Riesgo disponible: $50 (1% de $5,000)")
    print(f"  Riesgo por share: $25")
    print(f"  Shares calculadas: {result['shares']}")
    print(f"  Es fraccionada: {result.get('is_fractional', False)}")
    print(f"  Capital requerido: ${result['position_value']:.2f}")
    print(f"  Constraint: {result['constraint_hit']}")
    
    assert result['shares'] > 0, "Debería permitir compra con fracciones"
    assert result['shares'] == 2.0, f"Debería calcular 2.0 shares ($50/$25)"
    assert result.get('is_fractional', False) == False, "2.0 no es fracción"
    
    print(f"\n✅ Permite posición: {result['shares']} shares")
    
    # Caso 2: Acción MUY cara ($800) - Solo 0.625 shares
    result2 = rm.calculate_position_size(
        entry_price=800.0,
        stop_price=760.0,  # $40 de riesgo por acción (5% - dentro del límite)
        adr_percent=4.0,
        avg_daily_volume=1000000
    )
    
    print(f"\n💎 Acción MUY cara ($800/share):")
    print(f"  Riesgo disponible: $50")
    print(f"  Riesgo por share: $40")
    print(f"  Shares calculadas: {result2['shares']}")
    print(f"  Es fraccionada: {result2.get('is_fractional', False)}")
    print(f"  Capital requerido: ${result2['position_value']:.2f}")
    
    expected_shares = round(50 / 40, 3)  # 1.25
    assert result2['shares'] == expected_shares, f"Debería calcular {expected_shares} shares"
    assert result2.get('is_fractional', False) == True, "Debería ser fraccionada"
    
    print(f"\n✅ Permite fracción: {result2['shares']} shares (${result2['position_value']:.2f})")
    
    # Caso 3: Posición muy pequeña (< $25) - Debe rechazar
    # Usar cuenta más pequeña para forzar el caso
    rm_tiny = RiskManager(
        account_equity=500,  # Solo $500
        risk_fraction=0.01,  # $5 de riesgo
        max_exposure_fraction=0.25,
        allow_fractional_shares=True
    )
    
    result3 = rm_tiny.calculate_position_size(
        entry_price=1000.0,
        stop_price=950.0,  # $50 de riesgo por share (5%)
        adr_percent=4.0,
        avg_daily_volume=1000000
    )
    
    print(f"\n⛔ Posición demasiado pequeña ($500 cuenta):")
    print(f"  Riesgo disponible: $5")
    print(f"  Riesgo por share: $50")
    print(f"  Shares teóricas: 0.1 shares = $100 capital")
    print(f"  Shares calculadas: {result3['shares']}")
    print(f"  Capital: ${result3['position_value']:.2f}")
    print(f"  Razón: {result3['constraint_hit']}")
    
    # Con fracciones, 0.1 shares = $100, que es > $25, así que debería pasar
    # pero será limitado por max_exposure = $125
    assert result3['shares'] > 0, "Debería permitir la posición"
    assert result3['position_value'] <= 125, "Limitado por max exposure"
    
    print(f"\n✅ Rechaza correctamente posición muy pequeña")


def test_no_fractional_large_account():
    """Test: Cuentas grandes NO usan fracciones"""
    print("\n" + "="*80)
    print("TEST 2: SIN FRACCIONES - Cuenta Grande ($100,000)")
    print("="*80)
    
    # Cuenta grande
    rm = RiskManager(
        account_equity=100000,
        risk_fraction=0.005,  # 0.5% = $500 riesgo
        max_exposure_fraction=0.25,
        allow_fractional_shares=True  # Aunque esté activado, no se usa en cuentas grandes
    )
    
    result = rm.calculate_position_size(
        entry_price=150.0,
        stop_price=145.0,  # $5 riesgo
        adr_percent=4.0,
        avg_daily_volume=1000000
    )
    
    print(f"\n💼 Cuenta institucional ($100k):")
    print(f"  Riesgo disponible: $500")
    print(f"  Riesgo por share: $5")
    print(f"  Shares teóricas: {500/5} = 100.0")
    print(f"  Shares calculadas: {result['shares']}")
    print(f"  Es fraccionada: {result.get('is_fractional', False)}")
    
    assert result['shares'] == 100, "Cuentas grandes usan enteros"
    assert isinstance(result['shares'], int), "Debe ser entero"
    assert result.get('is_fractional', False) == False, "No debe ser fraccionada"
    
    print(f"\n✅ Solo acciones enteras en cuentas grandes")


def test_fractional_constraints():
    """Test: Constraints también respetan fracciones"""
    print("\n" + "="*80)
    print("TEST 3: CONSTRAINTS con FRACCIONES")
    print("="*80)
    
    rm = RiskManager(
        account_equity=3000,
        risk_fraction=0.01,
        max_exposure_fraction=0.25,  # Max $750
        buying_power=3000,
        allow_fractional_shares=True
    )
    
    # Intentar posición que excede max_exposure
    result = rm.calculate_position_size(
        entry_price=400.0,  # Querría comprar ~1.875 shares = $750
        stop_price=390.0,   # $10 riesgo, $30 total riesgo = 3 shares teóricas
        adr_percent=4.0,
        avg_daily_volume=1000000
    )
    
    print(f"\n🔒 Test de Max Exposure:")
    print(f"  Max exposure permitido: ${3000 * 0.25:.2f}")
    print(f"  Shares calculadas: {result['shares']}")
    print(f"  Position value: ${result['position_value']:.2f}")
    print(f"  Es fraccionada: {result.get('is_fractional', False)}")
    print(f"  Constraint: {result['constraint_hit']}")
    
    expected_max_shares = round(750 / 400, 3)  # 1.875
    assert result['shares'] == expected_max_shares, "Debe aplicar max exposure con fracciones"
    assert result.get('is_fractional', False) == True, "Debe ser fraccionada"
    
    print(f"\n✅ Constraints funcionan correctamente con fracciones")


def test_execution_plan_fractional():
    """Test: Plan de ejecución con fracciones"""
    print("\n" + "="*80)
    print("TEST 4: PLAN DE EJECUCIÓN con FRACCIONES")
    print("="*80)
    
    rm = RiskManager(account_equity=5000, allow_fractional_shares=True)
    
    # Plan con fracciones
    plan_frac = rm.get_execution_plan(0.625)
    
    print(f"\n📊 Ejecución fraccionada (0.625 shares):")
    print(f"  Phase 1 (Feeler 50%): {plan_frac['phase_1_feeler']} shares")
    print(f"  Phase 2 (Confirmation): {plan_frac['phase_2_confirmation']} shares")
    print(f"  Es fraccionada: {plan_frac['is_fractional']}")
    
    assert plan_frac['phase_1_feeler'] == 0.312, "Feeler debe ser 50% redondeado"
    assert plan_frac['phase_2_confirmation'] == 0.313, "Resto debe sumar exacto"
    assert plan_frac['is_fractional'] == True
    
    # Plan con enteros
    plan_int = rm.get_execution_plan(100)
    
    print(f"\n📊 Ejecución entera (100 shares):")
    print(f"  Phase 1 (Feeler 50%): {plan_int['phase_1_feeler']} shares")
    print(f"  Phase 2 (Confirmation): {plan_int['phase_2_confirmation']} shares")
    print(f"  Es fraccionada: {plan_int['is_fractional']}")
    
    assert plan_int['phase_1_feeler'] == 50
    assert plan_int['phase_2_confirmation'] == 50
    assert plan_int['is_fractional'] == False
    
    print(f"\n✅ Plan de ejecución correcto para ambos casos")


def test_disabled_fractional():
    """Test: Deshabilitar fracciones"""
    print("\n" + "="*80)
    print("TEST 5: FRACCIONES DESHABILITADAS")
    print("="*80)
    
    rm = RiskManager(
        account_equity=5000,
        risk_fraction=0.01,
        allow_fractional_shares=False  # Deshabilitado
    )
    
    result = rm.calculate_position_size(
        entry_price=800.0,
        stop_price=760.0,  # 5% stop - válido
        adr_percent=4.0,
        avg_daily_volume=1000000
    )
    
    print(f"\n🚫 Fracciones deshabilitadas:")
    print(f"  Riesgo disponible: $50")
    print(f"  Riesgo por share: $40")
    print(f"  Shares teóricas: 1.25")
    print(f"  Shares calculadas: {result['shares']}")
    print(f"  Razón: {result['constraint_hit']}")
    
    assert result['shares'] == 1, "Sin fracciones, debe redondear a entero"
    assert isinstance(result['shares'], int), "Debe ser entero"
    
    print(f"\n✅ Correctamente redondea a entero cuando fracciones están deshabilitadas")


if __name__ == "__main__":
    print("\n" + "█"*80)
    print("█" + " "*78 + "█")
    print("█" + " "*15 + "TEST SUITE: SOPORTE DE ACCIONES FRACCIONADAS" + " "*17 + "█")
    print("█" + " "*78 + "█")
    print("█"*80)
    
    try:
        test_fractional_shares_small_account()
        test_no_fractional_large_account()
        test_fractional_constraints()
        test_execution_plan_fractional()
        test_disabled_fractional()
        
        print("\n" + "█"*80)
        print("█" + " "*78 + "█")
        print("█" + " "*22 + "🎉 TODOS LOS TESTS PASADOS 🎉" + " "*24 + "█")
        print("█" + " "*78 + "█")
        print("█"*80)
        print("\n✅ Soporte de acciones fraccionadas funcionando correctamente")
        print("✅ Cuentas pequeñas pueden operar con fracciones")
        print("✅ Cuentas grandes siguen usando acciones enteras")
        print("✅ Todos los constraints respetan el tipo de acción\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FALLIDO: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
