Feature: Auto-enrol eligible UK new starters and process statutory opt-outs
  To meet UK workplace pension automatic-enrolment duties
  the employer must assess in-scope new starters on their employment start date,
  enrol eligible jobholders into a qualifying workplace pension scheme,
  and process valid statutory opt-outs with audit evidence.

  Background:
    Given the employer is in scope of UK automatic enrolment duties
    And postponement is not used for the new-starter population
    And the assessment date is the worker's employment start date
    And the lower age boundary is the worker's 22nd birthday inclusive
    And the upper age boundary is the worker's State Pension age date exclusive
    And State Pension age is resolved from "[STATE_PENSION_AGE_REFERENCE_DATA_SOURCE]" version "[SPA_REF_DATA_VERSION]"
    And AE earnings triggers are loaded from "[AE_EARNINGS_TRIGGER_TABLE]" version "[AE_REF_DATA_VERSION]"
    And for tax year "[TAX_YEAR_TO_CONFIRM]" the monthly AE earnings trigger is GBP 833.00
    And for tax year "[TAX_YEAR_TO_CONFIRM]" the weekly AE earnings trigger is GBP 192.00
    And a worker meets the earnings criterion only when qualifying earnings for the pay reference period are greater than the selected trigger
    And the default qualifying scheme is "[DEFAULT_QUALIFYING_SCHEME_ID]"
    And the default AE contribution group is "[DEFAULT_AE_CONTRIBUTION_GROUP]"

  Scenario: Auto-enrol an eligible new starter who is not already in a qualifying scheme
    Given a new starter has worker status "IN_SCOPE_WORKER"
    And their employment start date is 2026-05-01
    And their date of birth is 1990-04-30
    And their State Pension age date is 2058-04-30
    And their pay frequency is "MONTHLY"
    And their expected qualifying earnings for the pay reference period are GBP 2500.00
    And they have no active qualifying scheme membership for this employment
    When the automatic-enrolment assessment runs
    Then the assessment outcome is "ELIGIBLE_JOBHOLDER"
    And an enrolment record is created with enrolment reason "AUTOMATIC_ENROLMENT"
    And the enrolment effective date is 2026-05-01
    And the qualifying scheme is "[DEFAULT_QUALIFYING_SCHEME_ID]"
    And an audit record contains the input values, rule version, and reference-data version

  # Boundary case: the 22nd birthday is included in the statutory age band.
  Scenario: Treat a new starter on their 22nd birthday as meeting the lower age boundary
    Given a new starter has worker status "IN_SCOPE_WORKER"
    And their employment start date is 2026-05-01
    And their date of birth is 2004-05-01
    And their State Pension age date is 2072-05-01
    And their pay frequency is "MONTHLY"
    And their expected qualifying earnings for the pay reference period are GBP 834.00
    And they have no active qualifying scheme membership for this employment
    When the automatic-enrolment assessment runs
    Then the age criterion is satisfied
    And the earnings criterion is satisfied
    And an auto-enrolment record is created

  # Boundary case: the State Pension age date itself is excluded.
  Scenario: Do not auto-enrol a new starter who has reached State Pension age on the assessment date
    Given a new starter has worker status "IN_SCOPE_WORKER"
    And their employment start date is 2026-05-01
    And their date of birth is 1960-05-01
    And their State Pension age date is 2026-05-01
    And their pay frequency is "MONTHLY"
    And their expected qualifying earnings for the pay reference period are GBP 2500.00
    And they have no active qualifying scheme membership for this employment
    When the automatic-enrolment assessment runs
    Then the age criterion is not satisfied
    And the assessment outcome is "NOT_ELIGIBLE_AGE"
    And no auto-enrolment record is created

  # Variable input case: the selected trigger depends on the pay frequency/pay reference period.
  Scenario: Use the weekly earnings trigger for a weekly-paid new starter
    Given a new starter has worker status "IN_SCOPE_WORKER"
    And their employment start date is 2026-05-01
    And their date of birth is 1995-02-01
    And their State Pension age date is 2063-02-01
    And their pay frequency is "WEEKLY"
    And their expected qualifying earnings for the pay reference period are GBP 193.00
    And they have no active qualifying scheme membership for this employment
    When the automatic-enrolment assessment runs
    Then the selected AE earnings trigger is GBP 192.00
    And the earnings criterion is satisfied
    And an auto-enrolment record is created

  Scenario: Do not auto-enrol a worker who is already an active member of a qualifying scheme for this employment
    Given a new starter has worker status "IN_SCOPE_WORKER"
    And their employment start date is 2026-05-01
    And their date of birth is 1990-04-30
    And their State Pension age date is 2058-04-30
    And their pay frequency is "MONTHLY"
    And their expected qualifying earnings for the pay reference period are GBP 2500.00
    And they have active qualifying scheme membership for this employment
    When the automatic-enrolment assessment runs
    Then the assessment outcome is "ALREADY_ACTIVE_IN_QUALIFYING_SCHEME"
    And no auto-enrolment record is created
    And no provider enrolment instruction is generated

  Scenario: Process a valid statutory opt-out after automatic enrolment
    Given a worker was auto-enrolled with enrolment effective date 2026-05-01
    And the pension provider supplies opt out notice date 2026-05-20
    And the pension provider supplies opt out notice valid as true
    And employee contributions of GBP 125.00 were deducted for the auto-enrolled membership
    When the opt-out process runs
    Then the membership status is set to "OPTED_OUT"
    And the cessation reason is "STATUTORY_OPT_OUT"
    And future pension deductions are stopped from the next available payroll run
    And a payroll refund instruction is created for GBP 125.00
    And a provider cancellation update is generated
    And opt-out notice metadata is recorded for audit

  # Should-fail case: assessment must fail closed where governed reference data is unavailable.
  Scenario: Fail assessment when AE earnings trigger reference data is missing
    Given a new starter has worker status "IN_SCOPE_WORKER"
    And their employment start date is 2026-05-01
    And their date of birth is 1990-04-30
    And their State Pension age date is 2058-04-30
    And their pay frequency is "MONTHLY"
    And their expected qualifying earnings for the pay reference period are GBP 2500.00
    And they have no active qualifying scheme membership for this employment
    And no AE earnings trigger exists for tax year "[TAX_YEAR_TO_CONFIRM]" and pay frequency "MONTHLY"
    When the automatic-enrolment assessment runs
    Then the assessment status is "FAILED_DATA_QUALITY"
    And no auto-enrolment record is created
    And an operational exception is raised for field "AE earnings trigger reference data"

  Scenario Outline: Assess earnings boundary against the selected AE trigger
    Given a new starter has worker status "IN_SCOPE_WORKER"
    And their employment start date is 2026-05-01
    And their date of birth is 1990-04-30
    And their State Pension age date is 2058-04-30
    And their pay frequency is "<pay_frequency>"
    And their expected qualifying earnings for the pay reference period are GBP <earnings>
    And the selected AE earnings trigger is GBP <trigger>
    And they have no active qualifying scheme membership for this employment
    When the automatic-enrolment assessment runs
    Then the earnings criterion is "<earnings_result>"
    And auto-enrolment created is "<enrolment_created>"

    Examples:
      | pay_frequency | trigger | earnings | earnings_result | enrolment_created |
      | MONTHLY       | 833.00  | 833.00   | not satisfied    | false             |
      | MONTHLY       | 833.00  | 833.01   | satisfied        | true              |
      | WEEKLY        | 192.00  | 192.00   | not satisfied    | false             |
      | WEEKLY        | 192.00  | 192.01   | satisfied        | true              |