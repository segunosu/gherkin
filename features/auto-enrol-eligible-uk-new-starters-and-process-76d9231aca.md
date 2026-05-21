# Auto-enrol eligible UK new starters and process valid statutory opt-outs

**As** UK payroll and pensions operations owner
**I need to** assess each in-scope new starter against UK automatic-enrolment eligible-jobholder rules, enrol eligible workers into the qualifying workplace pension scheme from their start date, and process valid statutory opt-outs
**So that** the employer meets automatic-enrolment duties under UK workplace pension legislation and retains auditable evidence of eligibility, enrolment, and opt-out decisions

## Acceptance criteria
- The system SHALL run this story only for new starter records where worker_status = 'IN_SCOPE_WORKER' and employment_start_date is populated; non-workers and excluded categories SHALL be rejected before this story by upstream worker-classification controls.
- The assessment date SHALL be the worker's employment_start_date; postponement SHALL NOT be applied in this story.
- A worker SHALL satisfy the age criterion only where employment_start_date >= date_of_birth + 22 years AND employment_start_date < state_pension_age_date, where state_pension_age_date is derived from [STATE_PENSION_AGE_REFERENCE_DATA_SOURCE] version [SPA_REF_DATA_VERSION].
- A worker whose employment_start_date is exactly their 22nd birthday SHALL be treated as meeting the lower age boundary.
- A worker whose employment_start_date is exactly their state_pension_age_date SHALL NOT be treated as meeting the upper age boundary.
- The system SHALL use expected_qualifying_earnings_for_pay_reference_period supplied by payroll, not annual salary, gross pay, or pensionable pay, when assessing the earnings trigger.
- The system SHALL select the automatic-enrolment earnings trigger from [AE_EARNINGS_TRIGGER_TABLE] using employment_start_date, tax_year, pay_frequency, and pay_reference_period length; for [TAX_YEAR_TO_CONFIRM, e.g. 2025/26], configured reference values SHALL include annual = GBP 10,000.00, monthly = GBP 833.00, weekly = GBP 192.00, unless superseded by the approved reference-data version.
- A worker SHALL satisfy the earnings criterion only where expected_qualifying_earnings_for_pay_reference_period > selected_earnings_trigger_amount; the boundary is exclusive, so earnings exactly equal to the trigger SHALL NOT qualify.
- A worker SHALL be treated as already in a scheme only where the scheme-membership source contains active_membership = true, qualifying_scheme = true, and employment_id matches the new employment being assessed.
- The system SHALL auto-enrol a new starter only where all of the following are true on the assessment date: worker_status = 'IN_SCOPE_WORKER', age criterion is satisfied, earnings criterion is satisfied, and the worker is not already an active member of a qualifying workplace pension scheme for this employment.
- For an auto-enrolled worker, the system SHALL create an enrolment record with enrolment_reason = 'AUTOMATIC_ENROLMENT', enrolment_effective_date = employment_start_date, assessment_date = employment_start_date, qualifying_scheme_id = [DEFAULT_QUALIFYING_SCHEME_ID], contribution_group = [DEFAULT_AE_CONTRIBUTION_GROUP], and audit correlation_id.
- For a worker who fails any eligibility criterion, the system SHALL record the assessment outcome and reason code, SHALL NOT create an auto-enrolment record, and SHALL NOT send a provider enrolment instruction.
- The system SHALL accept a statutory opt-out only for a worker with a prior enrolment_reason = 'AUTOMATIC_ENROLMENT' where the pension provider supplies opt_out_notice_valid = true and opt_out_notice_date within the statutory opt-out period; statutory window validation SHALL be evidenced by provider notice metadata.
- For a valid statutory opt-out, the system SHALL set membership_status = 'OPTED_OUT', cessation_reason = 'STATUTORY_OPT_OUT', cease future pension deductions from the next available payroll run, generate a payroll refund instruction for employee contributions taken in relation to the opted-out enrolment, generate a provider cancellation/update instruction, and record all source notice metadata for audit.
- For an invalid or late opt-out notice, the system SHALL NOT refund contributions under statutory opt-out rules, SHALL NOT change membership_status to 'OPTED_OUT', and SHALL record rejection_reason using the provider-supplied validity outcome.
- If any mandatory data required for assessment is missing or invalid, including date_of_birth, employment_start_date, worker_status, expected_qualifying_earnings_for_pay_reference_period, pay_frequency, qualifying-scheme membership status, or applicable reference data, the system SHALL set assessment_status = 'FAILED_DATA_QUALITY', SHALL NOT auto-enrol the worker, and SHALL raise an operational exception containing the failed field names.
- All assessment, enrolment, opt-out, refund, and provider-instruction decisions SHALL be retained with input values, reference-data version, rule version, timestamp, actor/system identity, and outcome for [AUDIT_RETENTION_PERIOD] in accordance with [RECORD_RETENTION_POLICY].

## Assumptions
- The employer is UK-based and in scope of workplace pension automatic-enrolment duties under the Pensions Act 2008.
- Upstream processes have already determined that the new starter is an in-scope worker/employee for UK automatic enrolment; contractors, non-workers, and excluded directors are outside this story.
- The employer is not using postponement for the new-starter population covered by this story.
- State Pension age is available either through a governed reference-data service or a governed calculation implementing current legislation; the exact source and version must be confirmed in [STATE_PENSION_AGE_REFERENCE_DATA_SOURCE].
- Payroll can provide expected qualifying earnings for the relevant pay reference period on or before employment_start_date, even where actual payroll earnings are not yet known.
- Automatic-enrolment earnings trigger values are maintained as dated reference data; the PO/compliance owner must confirm [TAX_YEAR_TO_CONFIRM] and [AE_REF_DATA_VERSION] before release.
- The earnings-trigger comparison is implemented as strictly greater than the configured trigger amount because UK AE guidance describes the eligible-jobholder threshold as earnings over the trigger; if compliance requires inclusive treatment, this must be explicitly changed before build.
- The pension-provider integration supplies opt-out notice date, notice validity, and refund/cancellation metadata sufficient to evidence the statutory opt-out window.
- Communication content and delivery are delivered separately; this story records communication-required events and consumes communication evidence where needed for opt-out audit.
- Default qualifying scheme and contribution group are known configuration values: [DEFAULT_QUALIFYING_SCHEME_ID] and [DEFAULT_AE_CONTRIBUTION_GROUP].

## Out of scope (split into separate stories)
- Upstream worker-status classification, including contractor/director exclusions and non-worker determination.
- Employer postponement/deferral logic, postponement notices, and opt-in requests during postponement.
- Opt-in handling for non-eligible jobholders and joining rights for entitled workers.
- Creation, approval, and maintenance workflow for automatic-enrolment threshold reference data.
- Detailed statutory communication content, channel selection, delivery, and employee-facing templates; this story only emits/records communication-required events and consumes communication evidence where available.
- Payroll contribution-rate calculation, deduction scheduling, and provider contribution-file implementation beyond issuing enrolment, stop, and refund instructions required by this story.
- Re-enrolment/cyclical re-enrolment duties and three-year re-assessment.
- Handling external personal pensions that are not the qualifying workplace pension scheme for this employment.
- Late opt-out, cessation, leave, and refund rules outside the statutory opt-out process.
- Regulatory declaration of compliance submission to The Pensions Regulator.

## Gherkin
```gherkin
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
```

## Traceability
- Originating regulation: UK Pensions Act 2008, Part 1, workplace pension automatic-enrolment duties; Occupational and Personal Pension Schemes (Automatic Enrolment) Regulations 2010, as amended. Exact legal citations to be confirmed by [COMPLIANCE_OWNER].
- Regulator guidance: The Pensions Regulator automatic enrolment guidance, including guidance on assessing the workforce, eligible jobholders, automatic enrolment, and opt-out process. Specific guidance document/version/date: [TPR_GUIDANCE_VERSION_DATE].
- Reference data version: [AE_REF_DATA_VERSION] for earnings triggers; [SPA_REF_DATA_VERSION] for State Pension age; [SCHEME_REF_DATA_VERSION] for qualifying scheme status.
- Linked downstream stories:
  - [STORY-ID-CLASSIFY-WORKER-STATUS] Upstream UK AE worker-status classification
  - [STORY-ID-AE-COMMS] Issue and evidence statutory automatic-enrolment communications
  - [STORY-ID-PAYROLL-PENSION-DEDUCTIONS] Calculate and apply pension contributions in payroll
  - [STORY-ID-PROVIDER-INTEGRATION] Send enrolment, cancellation, and contribution instructions to pension provider
  - [STORY-ID-AE-REFERENCE-DATA] Maintain UK AE thresholds and State Pension age reference data
  - [STORY-ID-OPT-IN-JOINING] Process opt-in and joining requests for non-eligible jobholders and entitled workers
