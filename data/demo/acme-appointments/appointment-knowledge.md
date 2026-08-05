# Acme Appointment Reference

Version 1.2 — current reference facts

## Clinics and services

ACME-KNOW-CLINIC-001: Harbour Clinic uses clinic identifier CLINIC-TOR-01 and provides consultation and follow-up services.
ACME-KNOW-CLINIC-002: Riverside Clinic uses clinic identifier CLINIC-LON-02 and provides consultation services.
ACME-KNOW-SERVICE-001: A standard consultation lasts thirty minutes.
ACME-KNOW-SERVICE-002: A follow-up appointment lasts twenty minutes.

## Time and timezone reference

ACME-KNOW-TZ-001: Customer timezone is a trusted customer-profile fact, not a value inferred by the agent.
ACME-KNOW-TZ-002: Availability instants are stored as UTC timestamps and displayed using the customer's recorded IANA timezone.
ACME-KNOW-TZ-003: Clinic timezone is reference information and must not replace a different recorded customer timezone.

## Fees

ACME-KNOW-FEE-001: Fee values come from current appointment state and use a three-letter currency plus integer minor units.
ACME-KNOW-FEE-002: The agent must not calculate, waive, or alter a fee from prose.

## Unsupported phrase

ACME-KNOW-AMBIGUITY-001: No approved Acme reference defines "daylight hours" for scheduling decisions.
ACME-KNOW-AMBIGUITY-002: A definition would need a location, calendar source, sunrise/sunset interpretation, daylight-saving behavior, and exception policy before it could be reviewed for enforcement.
