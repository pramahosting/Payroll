"""
Unit tests for the Australian Payroll Engine.
Run with: pytest tests/test_payroll.py -v
"""
import sys
sys.path.insert(0, '../services/payroll-service')
sys.path.insert(0, '../shared')

from tax_engine import (
    PayrollInput, calculate_payroll,
    calculate_payg_weekly, get_hourly_rate,
    SUPER_GUARANTEE_RATE
)


# ── Tax Calculation Tests ─────────────────────────────────────────────────────

def test_payg_low_earner_with_tft():
    """Low earner with tax-free threshold should pay no or minimal tax."""
    weekly = 400  # ~$20,800/yr - below tax-free threshold
    tax = calculate_payg_weekly(weekly, tax_free_threshold=True)
    assert tax >= 0, "Tax should not be negative"
    assert tax < 50, f"Low earner should pay minimal tax, got {tax}"


def test_payg_high_earner_without_tft():
    """High earner without TFT should pay more tax."""
    weekly_with_tft = calculate_payg_weekly(2000, tax_free_threshold=True)
    weekly_no_tft = calculate_payg_weekly(2000, tax_free_threshold=False)
    assert weekly_no_tft > weekly_with_tft, "No TFT should mean higher tax"


def test_payg_increases_with_income():
    """Higher income = higher weekly tax (progressive)."""
    tax_low = calculate_payg_weekly(500, True)
    tax_mid = calculate_payg_weekly(1500, True)
    tax_high = calculate_payg_weekly(3000, True)
    assert tax_low < tax_mid < tax_high, "Tax should be progressive"


def test_payg_non_negative():
    """Tax should never be negative."""
    for weekly in [0, 100, 350, 500, 1000, 5000]:
        tax = calculate_payg_weekly(weekly, True)
        assert tax >= 0, f"Tax negative at {weekly}/week: {tax}"


# ── Hourly Rate Tests ─────────────────────────────────────────────────────────

def test_hourly_rate_full_time():
    """Full-time $80,000 salary = ~$40.43/hr (38hrs/week)."""
    rate = get_hourly_rate(80000, 'full_time')
    assert 40.0 <= rate <= 41.0, f"Expected ~$40.43/hr, got {rate}"


def test_hourly_rate_scales_with_salary():
    rate_80k = get_hourly_rate(80000, 'full_time')
    rate_160k = get_hourly_rate(160000, 'full_time')
    assert abs(rate_160k - rate_80k * 2) < 0.01, "Rate should double with salary"


# ── Payroll Calculation Tests ─────────────────────────────────────────────────

def make_input(**kwargs):
    defaults = dict(
        employee_id='emp-001',
        employee_number='E001',
        first_name='Jane',
        last_name='Smith',
        annual_salary=80000,
        employment_type='full_time',
        pay_frequency='fortnightly',
        ordinary_hours=76,
        overtime_hours_1_5x=0,
        overtime_hours_2x=0,
        public_holiday_hours=0,
        annual_leave_hours=0,
        sick_leave_hours=0,
        long_service_leave_hours=0,
        tax_free_threshold=True,
        residency_status='resident',
        super_fund_name='AustralianSuper',
        period_start='2024-01-15',
        period_end='2024-01-28',
    )
    defaults.update(kwargs)
    return PayrollInput(**defaults)


def test_standard_fortnightly_payroll():
    """Standard FT employee $80k salary, 76hrs fortnightly."""
    inp = make_input()
    result = calculate_payroll(inp)

    # Fortnightly gross = $80,000 / 26 = ~$3,076.92
    expected_gross = 80000 / 26
    assert abs(result.gross_earnings - expected_gross) < 1.0, \
        f"Gross {result.gross_earnings} should be ~{expected_gross:.2f}"

    # Super = 11% of OTE
    expected_super = expected_gross * 0.11
    assert abs(result.super_guarantee - expected_super) < 1.0, \
        f"Super {result.super_guarantee} should be ~{expected_super:.2f}"

    # Net < Gross
    assert result.net_pay < result.gross_earnings, "Net must be less than gross"
    assert result.net_pay > 0, "Net pay must be positive"
    assert result.payg_tax >= 0, "Tax cannot be negative"


def test_overtime_increases_gross():
    """Overtime hours should increase gross pay."""
    no_ot = calculate_payroll(make_input(ordinary_hours=76))
    with_ot = calculate_payroll(make_input(ordinary_hours=76, overtime_hours_1_5x=5))
    assert with_ot.gross_earnings > no_ot.gross_earnings, "OT should increase gross"


def test_overtime_1_5x_rate():
    """1.5x overtime should be calculated correctly."""
    inp = make_input(ordinary_hours=0, overtime_hours_1_5x=10)
    result = calculate_payroll(inp)
    hourly = result.hourly_rate
    expected_ot = hourly * 1.5 * 10
    assert abs(result.overtime_pay_1_5x - expected_ot) < 0.01, \
        f"1.5x OT: expected {expected_ot:.2f}, got {result.overtime_pay_1_5x}"


def test_double_time_rate():
    """2x overtime should be calculated correctly."""
    inp = make_input(ordinary_hours=0, overtime_hours_2x=8)
    result = calculate_payroll(inp)
    hourly = result.hourly_rate
    expected_ot = hourly * 2.0 * 8
    assert abs(result.overtime_pay_2x - expected_ot) < 0.01, \
        f"2x OT: expected {expected_ot:.2f}, got {result.overtime_pay_2x}"


def test_super_rate_on_ote():
    """Super is 11% of Ordinary Time Earnings (not including overtime)."""
    inp = make_input(ordinary_hours=76, overtime_hours_1_5x=10)
    result = calculate_payroll(inp)

    ote = result.ordinary_pay + result.annual_leave_pay + result.sick_leave_pay + \
          result.long_service_leave_pay + result.public_holiday_pay
    expected_super = ote * SUPER_GUARANTEE_RATE

    assert abs(result.super_guarantee - expected_super) < 0.01, \
        f"Super should be {expected_super:.2f}, got {result.super_guarantee}"


def test_super_not_on_overtime():
    """Overtime earnings do NOT attract super guarantee."""
    no_ot = calculate_payroll(make_input(ordinary_hours=76))
    with_ot = calculate_payroll(make_input(ordinary_hours=76, overtime_hours_1_5x=20))

    # Super should be the same (both on OTE = ordinary hours only)
    assert abs(no_ot.super_guarantee - with_ot.super_guarantee) < 0.01, \
        "Super should not increase with overtime"


def test_weekly_pay_frequency():
    """Weekly pay: 52 periods/year."""
    inp = make_input(pay_frequency='weekly', ordinary_hours=38)
    result = calculate_payroll(inp)
    expected_weekly = 80000 / 52
    assert abs(result.gross_earnings - expected_weekly) < 1.0, \
        f"Weekly gross: expected ~{expected_weekly:.2f}, got {result.gross_earnings}"


def test_monthly_pay_frequency():
    """Monthly pay: 12 periods/year. Standard monthly hours = 38*52/12 = 164.67."""
    inp = make_input(pay_frequency='monthly', ordinary_hours=164.67)
    result = calculate_payroll(inp)
    expected_monthly = 80000 / 12
    assert abs(result.gross_earnings - expected_monthly) < 2.0, \
        f"Monthly gross: expected ~{expected_monthly:.2f}, got {result.gross_earnings}"


def test_leave_pay_at_ordinary_rate():
    """Leave should be paid at ordinary rate."""
    inp = make_input(ordinary_hours=0, annual_leave_hours=38)
    result = calculate_payroll(inp)
    hourly = result.hourly_rate
    expected_leave = hourly * 38
    assert abs(result.annual_leave_pay - expected_leave) < 0.01, \
        f"Leave pay: expected {expected_leave:.2f}, got {result.annual_leave_pay}"


def test_ytd_accumulation():
    """YTD values should accumulate correctly."""
    inp = make_input(ytd_gross=10000, ytd_tax=2000, ytd_super=1100)
    result = calculate_payroll(inp)
    assert result.ytd_gross > 10000, "YTD gross should grow"
    assert result.ytd_tax > 2000, "YTD tax should grow"
    assert result.ytd_super > 1100, "YTD super should grow"
    assert abs(result.ytd_gross - (10000 + result.gross_earnings)) < 0.01


def test_public_holiday_loading():
    """Public holidays should attract 2.25x loading."""
    inp = make_input(ordinary_hours=0, public_holiday_hours=7.6)
    result = calculate_payroll(inp)
    hourly = result.hourly_rate
    expected = hourly * 7.6 * 2.25
    assert abs(result.public_holiday_pay - expected) < 0.01, \
        f"PH pay: expected {expected:.2f}, got {result.public_holiday_pay}"


def test_result_fields_populated():
    """All result fields should be populated and sensible."""
    result = calculate_payroll(make_input())
    assert result.employee_id == 'emp-001'
    assert result.full_name == 'Jane Smith'
    assert result.hourly_rate > 0
    assert result.annual_salary == 80000
    assert result.gross_earnings > 0
    assert result.net_pay > 0
    assert result.super_guarantee > 0
    assert isinstance(result.period_start, str)


def test_high_earner_top_tax_rate():
    """High earner should hit top marginal rate (45% above $180k)."""
    # $300k salary → weekly ~$5,769
    inp = make_input(annual_salary=300000, ordinary_hours=76)
    result = calculate_payroll(inp)
    # Effective tax rate should be significant
    effective_rate = result.total_tax / result.gross_earnings
    assert effective_rate > 0.35, f"High earner effective rate too low: {effective_rate:.2%}"


def test_casual_employee_higher_rate():
    """Casual employees may have different pay structures."""
    inp = make_input(employment_type='casual', hourly_rate=35.0, ordinary_hours=20)
    result = calculate_payroll(inp)
    expected_gross = 35.0 * 20
    assert abs(result.gross_earnings - expected_gross) < 0.01, \
        f"Casual pay: expected {expected_gross:.2f}, got {result.gross_earnings}"


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
